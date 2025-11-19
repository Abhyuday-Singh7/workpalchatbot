from unittest.mock import Mock, patch

import pytest

from app.routers.intent import execute_intent
from app import schemas, models


@patch("app.services.pdf_service.central_rules_get_flag")
@patch("app.services.email_service.send_email")
@patch("app.services.excel_service.excel_update")
@patch("app.services.excel_service.excel_read")
def test_update_resigned_triggers_send_email(mock_read, mock_update, mock_send, mock_flag):
    # Setup mocks
    mock_update.return_value = 1
    mock_read.return_value = [{"Name": "Alice", "Email": "a@example.com"}]
    mock_flag.return_value = True
    mock_send.return_value = None

    # Mock DB with minimal methods used for audit/department rule lookup
    mock_db = Mock()
    mock_db.add = Mock()
    mock_db.commit = Mock()

    # Ensure check_authority allows action by monkeypatching it
    import app.routers.intent as intent_mod

    intent_mod.check_authority = lambda db, user_id, dept, action: (True, False, "")

    req = schemas.IntentExecutionRequest(
        user_id="u1",
        intent=schemas.OperationIntent(
            ACTION="UPDATE",
            DEPARTMENT="HR",
            EXCEL_PATH="/tmp/fake.xlsx",
            SHEET="Sheet1",
            CONDITION="id=1",
            VALUES={"status": "resigned", "employee_name": "Alice"},
        ),
    )

    res = execute_intent(req, db=mock_db)

    assert res.success
    # send_email should have been called as auto-send flag is True
    assert mock_send.called
    # EmailAudit should be attempted to be written
    assert mock_db.add.called
