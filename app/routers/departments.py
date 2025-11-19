from datetime import datetime
import logging
import os
from pathlib import Path
from typing import List
    
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import DATA_DIR, get_department_data_dir
from ..database import get_db
from ..services.pdf_service import extract_text_from_pdf


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("/setup", response_model=List[str])
def setup_departments(payload: schemas.DepartmentSetupRequest):
    """
    Initialize folders for the selected departments under /data.
    """
    initialized = []
    for dept in payload.departments:
        dept_dir = get_department_data_dir(dept)
        initialized.append(str(dept_dir.relative_to(DATA_DIR.parent)))
    return initialized


@router.post(
    "/{department}/upload-rules",
    response_model=schemas.DepartmentRuleOut,
)
async def upload_department_rules(
    department: str,
    user_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a department instruction PDF/TXT, extract text, and store in SQL.
    """
    dept_dir = get_department_data_dir(department)
    instructions_dir = dept_dir / "instructions"
    instructions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{department}_rules_{timestamp}_{file.filename}"
    file_path = instructions_dir / safe_name

    with file_path.open("wb") as f:
        content = await file.read()
        f.write(content)

    if file.filename.lower().endswith(".pdf"):
        rule_text = extract_text_from_pdf(file_path)
    else:
        rule_text = file_path.read_text(encoding="utf-8")

    rule = models.DepartmentRule(
        user_id=user_id,
        department=department,
        rule_text=rule_text,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post(
    "/{department}/upload-excel",
    response_model=schemas.DepartmentFileOut,
)
async def upload_department_excel(
    department: str,
    user_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload the department Excel database and persist its path.
    Saved as /data/{department}/{department}_database.xlsx.
    """
    # Validate extension and optional MIME type
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    mime = (file.content_type or "").lower()

    allowed_exts = {".xlsx", ".xlsm", ".xltx", ".xltm"}
    allowed_mimes = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
        ".xltx": "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
        ".xltm": "application/vnd.ms-excel.template.macroEnabled.12",
    }

    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Allowed: .xlsx, .xlsm, .xltx, .xltm",
        )

    # If client provided a MIME type, validate it against expected for the extension
    expected_mime = allowed_mimes.get(ext)
    if mime and expected_mime and mime != expected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MIME type for the provided Excel extension.",
        )

    dept_dir = get_department_data_dir(department)
    target_path: Path = (dept_dir / f"{department.lower()}_database{ext}").resolve()

    # Ensure parent directories exist
    os.makedirs(target_path.parent.as_posix(), exist_ok=True)

    # Read and save file in binary mode
    contents = await file.read()
    with open(target_path, "wb") as f:
        f.write(contents)

    # Validate saved file size
    try:
        file_size = os.path.getsize(target_path)
    except OSError:
        file_size = 0

    if file_size == 0:
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded Excel file is empty.",
        )

    # Log saved path and size (do NOT log binary contents)
    logger.info(
        "Saved Excel upload",
        extra={"path": str(target_path), "size_bytes": file_size, "extension": ext},
    )

    # Verify that openpyxl can open the workbook; if invalid, delete file and return 400
    try:
        import openpyxl

        wb = openpyxl.load_workbook(target_path)
        wb.close()
    except InvalidFileException:
        logger.error("Invalid or corrupted Excel file at %s", target_path, exc_info=True)
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted Excel file",
        )

    record = models.DepartmentFile(
        user_id=user_id,
        department=department,
        excel_path=str(target_path),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
