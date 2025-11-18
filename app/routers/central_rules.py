from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import DATA_DIR
from ..database import get_db
from ..services.pdf_service import extract_text_from_pdf


router = APIRouter(prefix="/central-rules", tags=["central-rules"])


@router.post("/upload", response_model=schemas.CentralRuleOut)
async def upload_central_rules(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload the central company rule PDF/TXT, extract text, and store in SQL.
    """
    rules_dir = DATA_DIR / "central_rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"central_rules_{timestamp}_{file.filename}"
    file_path = rules_dir / safe_name

    with file_path.open("wb") as f:
        content = await file.read()
        f.write(content)

    if file.filename.lower().endswith(".pdf"):
        rule_text = extract_text_from_pdf(file_path)
    else:
        rule_text = file_path.read_text(encoding="utf-8")

    rule = models.CentralRule(
        user_id=user_id,
        rule_text=rule_text,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/", response_model=List[schemas.CentralRuleOut])
def list_central_rules(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieve all central rules for a user.
    The WorkPal bot can use this to enforce authority.
    """
    rules = (
        db.query(models.CentralRule)
        .filter(models.CentralRule.user_id == user_id)
        .order_by(models.CentralRule.created_at.desc())
        .all()
    )
    return rules
