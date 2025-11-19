import pandas as pd
import pytest
from pathlib import Path

from app.services.excel_service import lookup_email_by_name


def write_excel(path: Path, df: pd.DataFrame, sheet: str = "Sheet1"):
    # pandas uses openpyxl engine by default for xlsx
    df.to_excel(path, index=False, sheet_name=sheet)


def test_lookup_standard_headers(tmp_path):
    path = tmp_path / "standard.xlsx"
    df = pd.DataFrame({"Name": ["Alice", "Bob"], "Email": ["a@example.com", "b@example.com"]})
    write_excel(path, df)

    email = lookup_email_by_name(str(path), "Sheet1", "Alice")
    assert email == "a@example.com"


def test_lookup_header_variations(tmp_path):
    path = tmp_path / "variations.xlsx"
    df = pd.DataFrame({" employee_name ": ["Carol"], " E-MAIL ": ["c@example.com"]})
    write_excel(path, df)

    email = lookup_email_by_name(str(path), "Sheet1", "carol")
    assert email == "c@example.com"


def test_lookup_multiple_matches_logs_warning(tmp_path, caplog):
    path = tmp_path / "multiple.xlsx"
    df = pd.DataFrame({"Full_Name": ["Dave", "Dave"], "Email_Address": ["d1@example.com", "d2@example.com"]})
    write_excel(path, df)

    caplog.clear()
    email = lookup_email_by_name(str(path), "Sheet1", "Dave")
    assert email == "d1@example.com"
    assert any("Multiple email matches" in rec.message for rec in caplog.records)


def test_lookup_not_found_returns_none(tmp_path):
    path = tmp_path / "none.xlsx"
    df = pd.DataFrame({"Name": ["Eve"], "Email": ["e@example.com"]})
    write_excel(path, df)

    email = lookup_email_by_name(str(path), "Sheet1", "Nonexistent")
    assert email is None
