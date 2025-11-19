from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean

from .database import Base


class DepartmentRule(Base):
    __tablename__ = "department_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    department = Column(String, index=True, nullable=False)
    rule_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DepartmentFile(Base):
    __tablename__ = "department_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    department = Column(String, index=True, nullable=False)
    excel_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CentralRule(Base):
    __tablename__ = "central_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    rule_text = Column(Text, nullable=False)
    auto_send_on_resignation = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

