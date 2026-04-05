"""Tests for StudentFinanceService CRUD operations."""

import pytest
import sqlite3
import tempfile
import os

from education_system.university_system.modules.domain.student_finance.services.student_finance_service import (
    StudentFinanceService,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE student_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            fee_type TEXT,
            amount REAL,
            status TEXT DEFAULT 'unpaid',
            due_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


@pytest.fixture
def svc(temp_db):
    return StudentFinanceService(db_path=temp_db)


def test_create_returns_id(svc):
    rid = svc.create(student_id="STU001", fee_type="Tuition", amount=9250.00, status="unpaid")
    assert isinstance(rid, int)
    assert rid >= 1


def test_get_returns_created_record(svc):
    rid = svc.create(student_id="STU002", fee_type="Lab", amount=150.00)
    record = svc.get(rid)
    assert record is not None
    assert record["student_id"] == "STU002"
    assert record["fee_type"] == "Lab"
    assert record["amount"] == 150.00


def test_get_nonexistent_returns_none(svc):
    assert svc.get(9999) is None


def test_list_all_returns_all(svc):
    svc.create(student_id="STU001", fee_type="Tuition", amount=9250.00)
    svc.create(student_id="STU002", fee_type="Library", amount=50.00)
    records = svc.list_all()
    assert len(records) == 2


def test_list_all_with_filter(svc):
    svc.create(student_id="STU001", fee_type="Tuition", amount=9250.00)
    svc.create(student_id="STU002", fee_type="Library", amount=50.00)
    records = svc.list_all(student_id="STU001")
    assert len(records) == 1
    assert records[0]["student_id"] == "STU001"


def test_list_all_limit_offset(svc):
    for i in range(5):
        svc.create(student_id=f"STU{i:03d}", fee_type="Tuition", amount=100.00)
    records = svc.list_all(limit=2, offset=0)
    assert len(records) == 2


def test_update_record(svc):
    rid = svc.create(student_id="STU001", fee_type="Tuition", amount=9250.00, status="unpaid")
    result = svc.update(rid, status="paid")
    assert result is True
    record = svc.get(rid)
    assert record["status"] == "paid"


def test_update_no_kwargs_returns_false(svc):
    rid = svc.create(student_id="STU001", fee_type="Tuition", amount=100.00)
    assert svc.update(rid) is False


def test_delete_record(svc):
    rid = svc.create(student_id="STU001", fee_type="Tuition", amount=9250.00)
    result = svc.delete(rid)
    assert result is True
    assert svc.get(rid) is None


def test_list_all_empty(svc):
    records = svc.list_all()
    assert records == []
