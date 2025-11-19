from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from openpyxl.utils.exceptions import InvalidFileException
import re
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import excel_service
from ..services.email_service import EmailConfigurationError, send_email
from ..services.pdf_service import central_rules_get_flag


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/intent", tags=["intent"])


def check_authority(
    db: Session, user_id: str, department: str, action: str
) -> tuple[bool, bool, str]:
    """
    Very simple authority checker based on central_rules.rule_text.

    Returns (allowed, requires_approval, reason).
    This is intentionally minimal; the LLM (WorkPal) should still
    interpret central_rules.rule_text in detail when composing intents.
    """
    central_rules = (
        db.query(models.CentralRule)
        .filter(models.CentralRule.user_id == user_id)
        .all()
    )
    full_text = "\n".join(rule.rule_text for rule in central_rules).lower()

    marker_disallow = f"disallow {action.lower()} {department.lower()}"
    marker_require_approval = (
        f"approval {action.lower()} {department.lower()}"
    )

    if marker_disallow in full_text:
        return False, False, "Disallowed by central rules markers."

    if marker_require_approval in full_text:
        return False, True, "Approval required by central rules markers."

    return True, False, "Allowed (no blocking markers found)."


@router.post("/execute", response_model=schemas.IntentExecutionResponse)
def execute_intent(
    request: schemas.IntentExecutionRequest,
    db: Session = Depends(get_db),
):
    """
    Execute an operation intent against the Excel databases and/or rules.
    The intent must be constructed by the WorkPal bot.
    """
    intent = request.intent
    action = intent.ACTION.upper()
    department = intent.DEPARTMENT

    allowed, requires_approval, reason = check_authority(
        db, request.user_id, department, action
    )

    if not allowed and requires_approval:
        return schemas.IntentExecutionResponse(
            success=False,
            message="This action requires approval based on company authority rules.",
        )

    if not allowed and not requires_approval:
        return schemas.IntentExecutionResponse(
            success=False,
            message="This action cannot be performed due to company policy restrictions.",
        )

    # For READ-like actions that do not modify Excel, we skip write enforcement.
    if action in {"READ", "INSERT", "UPDATE", "DELETE"}:
        if not intent.EXCEL_PATH:
            # Look up Excel path from department_files if not explicitly provided
            dept_file = (
                db.query(models.DepartmentFile)
                .filter(
                    models.DepartmentFile.user_id == request.user_id,
                    models.DepartmentFile.department == department,
                )
                .order_by(models.DepartmentFile.created_at.desc())
                .first()
            )
            if not dept_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Excel path not provided and no department file registered.",
                )
            excel_path = Path(dept_file.excel_path)
        else:
            excel_path = Path(intent.EXCEL_PATH)

        try:
            if action == "READ":
                rows = excel_service.excel_read(
                    excel_path, intent.SHEET, intent.CONDITION
                )
                return schemas.IntentExecutionResponse(
                    success=True,
                    message="READ completed",
                    data=rows,
                )

            # For write operations, central authority has already been checked above.
            if action == "INSERT":
                if intent.VALUES is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="INSERT requires VALUES.",
                    )
                excel_service.excel_insert(
                    excel_path, intent.SHEET, intent.VALUES
                )
                return schemas.IntentExecutionResponse(
                    success=True,
                    message="INSERT completed",
                )

            if action == "UPDATE":
                if (
                    not intent.SHEET
                    or not intent.CONDITION
                    or not isinstance(intent.VALUES, dict)
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "UPDATE requires SHEET, CONDITION and "
                            "VALUES (mapping column->new value)."
                        ),
                    )
                count = excel_service.excel_update(
                    excel_path, intent.SHEET, intent.CONDITION, intent.VALUES
                )

                # If the update set status to 'resigned', trigger auto-send logic
                try:
                    status_val = None
                    if isinstance(intent.VALUES, dict):
                        for k, v in intent.VALUES.items():
                            if str(k).strip().lower() == "status":
                                status_val = v
                                break

                    if status_val and str(status_val).strip().lower() == "resigned":
                        # Check central rules flag for this user
                        try:
                            flag = central_rules_get_flag(request.user_id, "auto_send_on_resignation", db)
                        except Exception:
                            flag = False

                        if flag:
                            # Determine employee name: try VALUES, then read the affected rows
                            employee_name = None
                            if isinstance(intent.VALUES, dict):
                                for candidate in ("employee_name", "name", "full_name"):
                                    if candidate in intent.VALUES and intent.VALUES[candidate]:
                                        employee_name = str(intent.VALUES[candidate])
                                        break

                            if not employee_name:
                                try:
                                    rows = excel_service.excel_read(excel_path, intent.SHEET, intent.CONDITION)
                                    if rows:
                                        first = rows[0]
                                        for col in first.keys():
                                            if isinstance(col, str) and "name" in col.lower():
                                                employee_name = first[col]
                                                break
                                except Exception:
                                    employee_name = None

                            if employee_name:
                                # Build SEND_EMAIL intent using HR template or fallback
                                # Fetch latest HR department rule for this user
                                dept_rule = (
                                    db.query(models.DepartmentRule)
                                    .filter(
                                        models.DepartmentRule.user_id == request.user_id,
                                        models.DepartmentRule.department == "HR",
                                    )
                                    .order_by(models.DepartmentRule.created_at.desc())
                                    .first()
                                )
                                template = None
                                if dept_rule and getattr(dept_rule, "rule_text", None):
                                    template = dept_rule.rule_text

                                subject = "Resignation Acceptance"
                                if template:
                                    body = template.replace("{name}", str(employee_name))
                                else:
                                    body = f"Dear {employee_name},\n\nWe acknowledge and accept your resignation.\n\nBest regards, HR"

                                send_intent = schemas.OperationIntent(
                                    ACTION="SEND_EMAIL",
                                    DEPARTMENT="HR",
                                    EMPLOYEE_NAME=str(employee_name),
                                    EMAIL=None,
                                    SUBJECT=subject,
                                    BODY=body,
                                )
                                send_request = schemas.IntentExecutionRequest(
                                    user_id=request.user_id, intent=send_intent
                                )

                                # Reuse execute_intent to perform send (synchronous)
                                try:
                                    result = execute_intent(send_request, db)
                                except Exception as exc:
                                    result = {"success": False, "message": str(exc)}

                                # Log to EmailAudit model if available
                                audit_status = "FAILED"
                                msg_text = None
                                try:
                                    if isinstance(result, dict):
                                        success = bool(result.get("success"))
                                        msg_text = result.get("message")
                                    elif hasattr(result, "success"):
                                        success = bool(getattr(result, "success"))
                                        msg_text = getattr(result, "message", None)
                                    else:
                                        success = False

                                    audit_status = "SENT" if success else "FAILED"
                                    if hasattr(models, "EmailAudit"):
                                        try:
                                            audit = models.EmailAudit(
                                                user_id=request.user_id,
                                                to_email=str(send_intent.EMAIL or ""),
                                                subject=subject,
                                                body=body,
                                                status=audit_status,
                                                error_message=(None if success else str(msg_text)),
                                            )
                                            db.add(audit)
                                            db.commit()
                                        except Exception:
                                            logger.exception("Failed to write EmailAudit record")
                                except Exception:
                                    logger.exception("Error processing send email result for audit")
                except Exception:
                    logger.exception("Error in auto-send-on-resignation flow; continuing")

                return schemas.IntentExecutionResponse(
                    success=True,
                    message=f"UPDATE completed for {count} rows",
                )

            if action == "DELETE":
                if not intent.SHEET or not intent.CONDITION:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="DELETE requires SHEET and CONDITION.",
                    )
                count = excel_service.excel_delete(
                    excel_path, intent.SHEET, intent.CONDITION
                )
                return schemas.IntentExecutionResponse(
                    success=True,
                    message=f"DELETE completed for {count} rows",
                )
        except FileNotFoundError as exc:
            logger.error("Excel file not found: %s", excel_path, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except (ValueError, InvalidFileException) as exc:
            logger.error("Excel operation error on %s", excel_path, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    if action in {"TEMPLATE", "WORKFLOW"}:
        # For template/workflow, the WorkPal bot will interpret rule_text.
        # Here we simply return the latest relevant rule_text.
        dept_rules = (
            db.query(models.DepartmentRule)
            .filter(
                models.DepartmentRule.user_id == request.user_id,
                models.DepartmentRule.department == department,
            )
            .order_by(models.DepartmentRule.created_at.desc())
            .first()
        )
        if not dept_rules:
            raise HTTPException(
                status_code=404,
                detail="No department rules found for TEMPLATE/WORKFLOW.",
            )
        return schemas.IntentExecutionResponse(
            success=True,
            message=f"{action} rule_text returned.",
            data={"rule_text": dept_rules.rule_text},
        )

    if action == "SEND_EMAIL":
        # Email sending is allowed only for HR in this implementation.
        if department.upper() != "HR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="SEND_EMAIL is only supported for HR department.",
            )

        employee_name = intent.EMPLOYEE_NAME
        to_email = intent.EMAIL
        subject = intent.SUBJECT or ""
        body = intent.BODY or ""

        if not employee_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="EMPLOYEE_NAME is required for SEND_EMAIL.",
            )

        # If email is not provided in the intent, look it up from the HR Excel
        # by employee name using pandas helper.
        if not to_email:
            # Look up latest HR Excel file for this user
            dept_file = (
                db.query(models.DepartmentFile)
                .filter(
                    models.DepartmentFile.user_id == request.user_id,
                    models.DepartmentFile.department == "HR",
                )
                .order_by(models.DepartmentFile.created_at.desc())
                .first()
            )
            if not dept_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No HR Excel database registered; cannot resolve "
                        "employee email."
                    ),
                )

            excel_path = str(Path(dept_file.excel_path))
            # Use provided sheet or default to first sheet (0)
            sheet_name = intent.SHEET if intent.SHEET else 0
            found = excel_service.lookup_email_by_name(excel_path, sheet_name, employee_name)
            if found is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Employee not found in HR database",
                )
            to_email = found

        # Validate email format with simple regex
        email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_re.match(str(to_email).strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email address format.",
            )

        if not subject or not body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "SUBJECT and BODY are required for SEND_EMAIL intents."
                ),
            )

        # Placeholder central rules check: ensure central rules allow sending emails
        def central_rules_allows_email(db_session: Session, user_id: str, action: str) -> bool:
            # Reuse check_authority to determine if action is disallowed by central rules
            allowed, requires_approval, _ = check_authority(db_session, user_id, "HR", action)
            return allowed and not requires_approval

        if not central_rules_allows_email(db, request.user_id, "SEND_EMAIL"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Central rules forbid sending this email.",
            )

        # Attempt to send the email and return structured JSON
        try:
            send_email(to_email=to_email, subject=subject, body=body)
            return {"success": True, "message": "EMAIL sent"}
        except EmailConfigurationError as exc:
            logger.error("Email configuration error: %s", exc, exc_info=True)
            return {"success": False, "message": str(exc)}
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to send email", exc_info=True)
            return {"success": False, "message": "Failed to send email: %s" % str(exc)}

    raise HTTPException(status_code=400, detail="Unsupported ACTION in intent.")
