from pathlib import Path

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract plain text from a PDF using PyMuPDF.
    """
    doc = fitz.open(pdf_path)
    text_chunks = []
    for page in doc:
        text_chunks.append(page.get_text())
    doc.close()
    return "\n".join(text_chunks)


def parse_central_rules_flags(rule_text: str) -> dict:
    """Parse central rule text for known automatic-rule flags.

    Returns a dict of flags, for now contains key
    'auto_send_on_resignation': bool
    """
    text = (rule_text or "").lower()
    flags = {
        "auto_send_on_resignation": False,
    }

    # Phrases to detect for auto-send on resignation
    phrases = [
        "whenever an employee is marked as resigned",
        "hr is authorized to send resignation acceptance emails without requiring prior approval",
        "automatically send resignation acceptance",
    ]

    for p in phrases:
        if p in text:
            flags["auto_send_on_resignation"] = True
            break

    return flags


def central_rules_get_flag(user_id: str, flag_name: str, db_session) -> bool:
    """Return the latest value of a named central rule flag for the given user.

    This queries the `central_rules` table for the most recent entry for the user
    and returns the boolean value of the requested flag. Unknown flags return False.
    """
    if flag_name != "auto_send_on_resignation":
        return False

    from .. import models

    rule = (
        db_session.query(models.CentralRule)
        .filter(models.CentralRule.user_id == user_id)
        .order_by(models.CentralRule.created_at.desc())
        .first()
    )
    if not rule:
        return False
    return bool(getattr(rule, "auto_send_on_resignation", False))

