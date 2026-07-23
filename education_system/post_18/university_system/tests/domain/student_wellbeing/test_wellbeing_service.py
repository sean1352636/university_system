"""Tests for WellbeingService CRUD operations."""

import pytest
import sqlite3
import tempfile
import os

from education_system.post_18.university_system.modules.domain.student_affairs.student_wellbeing.services.wellbeing_service import (
    WellbeingService,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE wellbeing_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            concern_type TEXT,
            description TEXT,
            status TEXT DEFAULT 'open',
            counselor TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


@pytest.fixture
def svc(temp_db):
    return WellbeingService(db_path=temp_db)


def test_create_returns_id(svc):
    rid = svc.create(student_id="STU001", concern_type="Academic", description="Struggling with exams")
    assert isinstance(rid, int)
    assert rid >= 1


def test_get_returns_created_record(svc):
    rid = svc.create(student_id="STU002", concern_type="Mental Health", description="Anxiety", counselor="Dr Smith")
    record = svc.get(rid)
    assert record is not None
    assert record["student_id"] == "STU002"
    assert record["concern_type"] == "Mental Health"
    assert record["counselor"] == "Dr Smith"


def test_get_nonexistent_returns_none(svc):
    assert svc.get(9999) is None


def test_list_all_returns_all(svc):
    svc.create(student_id="STU001", concern_type="Academic", description="Exam stress")
    svc.create(student_id="STU002", concern_type="Financial", description="Fee concerns")
    records = svc.list_all()
    assert len(records) == 2


def test_list_all_with_filter(svc):
    svc.create(student_id="STU001", concern_type="Academic", description="Exam stress")
    svc.create(student_id="STU002", concern_type="Financial", description="Fee concerns")
    records = svc.list_all(concern_type="Academic")
    assert len(records) == 1
    assert records[0]["concern_type"] == "Academic"


def test_list_all_limit_offset(svc):
    for i in range(5):
        svc.create(student_id=f"STU{i:03d}", concern_type="General", description=f"Issue {i}")
    records = svc.list_all(limit=2, offset=0)
    assert len(records) == 2


def test_update_record(svc):
    rid = svc.create(student_id="STU001", concern_type="Academic", description="Exam stress", status="open")
    result = svc.update(rid, status="resolved", counselor="Dr Jones")
    assert result is True
    record = svc.get(rid)
    assert record["status"] == "resolved"
    assert record["counselor"] == "Dr Jones"


def test_update_no_kwargs_returns_false(svc):
    rid = svc.create(student_id="STU001", concern_type="Academic", description="Exam stress")
    assert svc.update(rid) is False


def test_delete_record(svc):
    rid = svc.create(student_id="STU001", concern_type="Academic", description="Exam stress")
    result = svc.delete(rid)
    assert result is True
    assert svc.get(rid) is None


def test_list_all_empty(svc):
    records = svc.list_all()
    assert records == []
