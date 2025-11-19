import os
from unittest.mock import Mock

import pytest

from app.services import email_service


class DummySMTP:
    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.logged = None
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, pw):
        self.logged = (user, pw)

    def sendmail(self, sender, recipients, msg):
        self.sent = (sender, recipients, msg)


def test_send_email_invokes_smtp(monkeypatch, tmp_path):
    # Provide env vars
    monkeypatch.setenv("SMTP_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("SMTP_SENDER_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_SERVER", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "465")

    dummy = DummySMTP("smtp.test", 465)

    def fake_smtp(server, port):
        assert server == "smtp.test"
        assert int(port) == 465
        return dummy

    monkeypatch.setattr("smtplib.SMTP_SSL", fake_smtp)

    # Should not raise
    email_service.send_email("to@example.com", "sub", "body")

    assert dummy.logged == ("sender@example.com", "pw")
    assert dummy.sent is not None


def test_missing_env_raises(monkeypatch):
    # Ensure SMTP env vars missing
    monkeypatch.delenv("SMTP_SENDER_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_SENDER_PASSWORD", raising=False)

    with pytest.raises(email_service.EmailConfigurationError):
        email_service._get_smtp_credentials()
