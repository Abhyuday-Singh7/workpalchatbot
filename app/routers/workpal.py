from typing import Optional, Dict, Any, List
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.llm_service import call_llm
from .intent import execute_intent as execute_intent_handler


router = APIRouter(prefix="/workpal", tags=["workpal"])


def build_system_prompt(
    departments: List[str],
    dept_rule_texts: Dict[str, str],
    central_rules_text: str,
) -> str:
    """
    Build a system prompt that describes the WorkPal architecture and injects
    department and central rules text.
    """
    lines = [
        "You are WorkPal, the Central Automation Brain.",
        "You manage department bots for: HR, Accounts, Sales, Admin, Law, Dev Team, Product Team.",
        "Use ONLY the provided department rule_text, central company rules, and Excel content.",
        "Never invent workflows that are not in the rules.",
        "Always obey authority rules in the central company rules.",
        "",
        "For every user request, you MUST output one or more INTENT blocks.",
        "Each INTENT is a single atomic operation for one department.",
        "",
        "Each INTENT must follow this exact format (one field per line, no extra text on those lines):",
        "",
        "INTENT:",
        "ACTION: {READ | INSERT | UPDATE | DELETE | TEMPLATE | WORKFLOW | SEND_EMAIL}",
        "DEPARTMENT: {HR | Accounts | Sales | Admin | Law | Dev Team | Product Team}",
        "EXCEL_PATH: {local path or empty}",
        "SHEET: {sheet name or empty}",
        "CONDITION: {SQL-like condition or empty}",
        "VALUES: {values for insert/update or empty}",
        "NOTES: {any additional info or empty}",
        "EMPLOYEE_NAME: {for HR SEND_EMAIL or empty}",
        "EMAIL: {employee email or empty}",
        "SUBJECT: {email subject or empty}",
        "BODY: {email body or empty}",
        "",
        "IMPORTANT FORMAT RULES:",
        "- ACTION must be exactly one of: READ, INSERT, UPDATE, DELETE, TEMPLATE, WORKFLOW, SEND_EMAIL.",
        "- Never invent new ACTION names such as ROUTE, ROUTING, HANDLE, etc.",
        "- Routing is expressed ONLY by choosing the correct DEPARTMENT value.",
        "- Do NOT write anything between 'INTENT:' and 'ACTION:' on the same line.",
        "- VALUES should be valid JSON when possible (list for INSERT, object for UPDATE),",
        "  but the backend can normalise lists/dicts/CSV strings.",
        "- You may output MULTIPLE INTENT blocks per reply when a workflow has multiple steps",
        "  (for example: HR UPDATE + Accounts UPDATE + HR SEND_EMAIL).",
        "- After all INTENT blocks, you may optionally add 1–2 sentences of natural language summary.",
        "",
        "ACTION MAPPING GUIDELINES:",
        "- READ:    user asks to show, list, search, count, or summarize records.",
        "- INSERT:  user asks to add/register/create a new record.",
        "- UPDATE:  user asks to change/edit/mark/close/resign/terminate an existing record.",
        "- DELETE:  user asks to remove/delete/cancel a record.",
        "- TEMPLATE:user asks for a template or draft (letter, email, document) without sending.",
        "- WORKFLOW:user asks for steps/process explanation without changing data.",
        "- SEND_EMAIL: user asks to actually send an HR email (resignation, termination, onboarding, warning, appraisal, etc.).",
        "",
        "Central company rules (authority, restrictions, workflows):",
        central_rules_text or "(none provided).",
        "",
        "Department rules:",
    ]
    for dept in departments:
        text = dept_rule_texts.get(dept, "").strip() or "(no rules provided)"
        lines.append(f"[{dept}]")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _norm_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    if v.lower() in {"", "none", "null", "empty", "n/a"}:
        return None
    return v


def parse_intent_from_text(text: str) -> Optional[schemas.OperationIntent]:
    """
    Parse a single INTENT block from the LLM response text.
    """
    marker = "INTENT:"
    if marker not in text:
        return None

    _, after = text.split(marker, 1)

    # Prepare a regex that extracts values for each known key until the next key
    # or end of string.
    keys = [
        "ACTION",
        "DEPARTMENT",
        "EXCEL_PATH",
        "SHEET",
        "CONDITION",
        "VALUES",
        "NOTES",
        "EMPLOYEE_NAME",
        "EMAIL",
        "SUBJECT",
        "BODY",
    ]
    lookahead_fields = (
        "ACTION|DEPARTMENT|EXCEL_PATH|SHEET|CONDITION|VALUES|NOTES|"
        "EMPLOYEE_NAME|EMAIL|SUBJECT|BODY"
    )
    pattern_template = (
        r"{key}\s*:(?P<{key}>.*?)(?=(" + lookahead_fields + r")\s*:|$)"
    )

    parsed: Dict[str, Any] = {}
    for key in keys:
        pattern = pattern_template.format(key=key)
        match = re.search(pattern, after, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(key).strip()
            parsed[key] = value

    action_raw = parsed.get("ACTION")
    department_raw = parsed.get("DEPARTMENT")
    if not action_raw or not department_raw:
        return None

    action = action_raw.strip().upper()
    department = department_raw.strip()

    allowed_actions = {
        "READ",
        "INSERT",
        "UPDATE",
        "DELETE",
        "TEMPLATE",
        "WORKFLOW",
        "SEND_EMAIL",
    }
    if action not in allowed_actions:
        # If the model produced an unsupported ACTION (e.g. ROUTE),
        # we treat it as no executable intent rather than calling the executor.
        return None

    values_parsed: Any = None
    values_raw = _norm_optional(parsed.get("VALUES"))
    if values_raw is not None:
        try:
            values_parsed = json.loads(values_raw)
        except json.JSONDecodeError:
            values_parsed = values_raw

    return schemas.OperationIntent(
        ACTION=action,
        DEPARTMENT=department,
        EXCEL_PATH=_norm_optional(parsed.get("EXCEL_PATH")),
        SHEET=_norm_optional(parsed.get("SHEET")),
        CONDITION=_norm_optional(parsed.get("CONDITION")),
        VALUES=values_parsed,
        NOTES=_norm_optional(parsed.get("NOTES")),
        EMPLOYEE_NAME=_norm_optional(parsed.get("EMPLOYEE_NAME")),
        EMAIL=_norm_optional(parsed.get("EMAIL")),
        SUBJECT=_norm_optional(parsed.get("SUBJECT")),
        BODY=_norm_optional(parsed.get("BODY")),
    )


def parse_intents_from_text(text: str) -> List[schemas.OperationIntent]:
    """
    Parse all INTENT blocks from the LLM response text.
    """
    marker = "INTENT:"
    if marker not in text:
        return []

    chunks = re.split(r"(?=INTENT:)", text)
    intents: List[schemas.OperationIntent] = []
    for chunk in chunks:
        if marker not in chunk:
            continue
        intent = parse_intent_from_text(chunk)
        if intent:
            intents.append(intent)
    return intents


@router.post("/chat", response_model=schemas.WorkPalChatResponse)
def workpal_chat(
    request: schemas.WorkPalChatRequest,
    db: Session = Depends(get_db),
):
    """
    Central WorkPal chat endpoint.

    - Loads department rules and central rules from SQL.
    - Calls the LLM to generate one or more INTENT blocks and summary.
    - Executes each INTENT via the existing intent execution logic.
    """
    # Load department rules for selected departments
    dept_rule_texts: Dict[str, str] = {}
    for dept in request.departments:
        latest_rule = (
            db.query(models.DepartmentRule)
            .filter(
                models.DepartmentRule.user_id == request.user_id,
                models.DepartmentRule.department == dept,
            )
            .order_by(models.DepartmentRule.created_at.desc())
            .first()
        )
        if latest_rule:
            dept_rule_texts[dept] = latest_rule.rule_text

    # Load central rules
    central_rules = (
        db.query(models.CentralRule)
        .filter(models.CentralRule.user_id == request.user_id)
        .order_by(models.CentralRule.created_at.desc())
        .all()
    )
    central_rules_text = "\n\n".join(rule.rule_text for rule in central_rules)

    system_prompt = build_system_prompt(
        request.departments, dept_rule_texts, central_rules_text
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.message},
    ]

    try:
        llm_reply = call_llm(messages)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Fallback if the LLM returns an empty or unusable response
    if not llm_reply or llm_reply.strip() in {"", "<s>", "</s>"}:
        llm_reply = (
            "The AI engine did not return a usable response. "
            "No automation has been executed. Please verify your "
            "LLM configuration or try again."
        )
        return schemas.WorkPalChatResponse(reply=llm_reply)

    intents = parse_intents_from_text(llm_reply)
    execution_results: List[schemas.IntentExecutionResponse] = []

    for intent in intents:
        intent_request = schemas.IntentExecutionRequest(
            user_id=request.user_id,
            intent=intent,
        )
        # Re-use the existing execution logic directly
        result = execute_intent_handler(intent_request, db)  # type: ignore[arg-type]
        execution_results.append(result)

    primary_intent: Optional[schemas.OperationIntent] = intents[0] if intents else None
    primary_result: Optional[
        schemas.IntentExecutionResponse
    ] = execution_results[-1] if execution_results else None

    return schemas.WorkPalChatResponse(
        reply=llm_reply,
        intent=primary_intent,
        execution_result=primary_result,
        intents=intents or None,
        execution_results=execution_results or None,
    )

