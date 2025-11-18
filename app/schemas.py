from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class DepartmentSetupRequest(BaseModel):
    user_id: str
    departments: List[str]


class DepartmentRuleCreate(BaseModel):
    user_id: str
    department: str


class DepartmentRuleOut(BaseModel):
    id: int
    user_id: str
    department: str
    rule_text: str
    created_at: datetime

    class Config:
        orm_mode = True


class DepartmentFileCreate(BaseModel):
    user_id: str
    department: str


class DepartmentFileOut(BaseModel):
    id: int
    user_id: str
    department: str
    excel_path: str
    created_at: datetime

    class Config:
        orm_mode = True


class CentralRuleCreate(BaseModel):
    user_id: str


class CentralRuleOut(BaseModel):
    id: int
    user_id: str
    rule_text: str
    created_at: datetime

    class Config:
        orm_mode = True


class OperationIntent(BaseModel):
    ACTION: str
    DEPARTMENT: str
    EXCEL_PATH: Optional[str] = None
    SHEET: Optional[str] = None
    CONDITION: Optional[str] = None
    VALUES: Optional[Any] = None
    NOTES: Optional[str] = None
    # Email-specific fields (for ACTION=SEND_EMAIL, DEPARTMENT=HR)
    EMPLOYEE_NAME: Optional[str] = None
    EMAIL: Optional[str] = None
    SUBJECT: Optional[str] = None
    BODY: Optional[str] = None


class IntentExecutionRequest(BaseModel):
    user_id: str
    intent: OperationIntent


class ExcelReadResult(BaseModel):
    rows: List[dict]


class IntentExecutionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class WorkPalChatRequest(BaseModel):
    user_id: str
    message: str
    departments: List[str]


class WorkPalChatResponse(BaseModel):
    reply: str
    intent: Optional[OperationIntent] = None
    execution_result: Optional[IntentExecutionResponse] = None
    # Multi-intent support: optional lists for workflows
    intents: Optional[List[OperationIntent]] = None
    execution_results: Optional[List[IntentExecutionResponse]] = None
