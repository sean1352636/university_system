"""The sixth form adapter's methods the university calls instead of
importing the sixth form: the learner list, the handover consent and the
medical record. Fakes only — no sixthform.db reads."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from education_system.systems.sixth_form.infrastructure.adapters.cross_system_adapter import (
    SixthFormAdapter,
)


@pytest.fixture
def adapter():
    return SixthFormAdapter()


def test_list_learners(adapter, monkeypatch):
    from education_system.systems.sixth_form.domain.learners.students import students
    monkeypatch.setattr(students, "list_students", lambda: [
        SimpleNamespace(student_id="C1", full_name="Amy Lee", first_name="Amy",
                        last_name="Lee", status="Active", date_of_birth="2008-01-01")])
    assert adapter.list_learners() == [
        {"student_id": "C1", "full_name": "Amy Lee", "first_name": "Amy",
         "last_name": "Lee", "status": "Active", "date_of_birth": "2008-01-01"}]


@pytest.mark.parametrize("value, expected", [
    (None, None),
    ({"consent_id": 7, "expires_date": None}, {"consent_id": 7, "expires_date": None}),
])
def test_handover_consent(adapter, monkeypatch, value, expected):
    from education_system.systems.sixth_form.domain.progression import university_handover
    monkeypatch.setattr(university_handover, "consent_for", lambda sid: value)
    assert adapter.handover_consent("C1") == expected


def test_handover_consent_error_propagates(adapter, monkeypatch):
    """The university treats an unreadable register as no grant, so the
    adapter must not swallow the failure into a falsy answer silently."""
    from education_system.systems.sixth_form.domain.progression import university_handover

    def boom(sid):
        raise RuntimeError("register locked")

    monkeypatch.setattr(university_handover, "consent_for", boom)
    with pytest.raises(RuntimeError):
        adapter.handover_consent("C1")


@dataclass
class _Cond:
    name: str
    active: bool


def test_medical_record(adapter, monkeypatch):
    from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
        medical_records as mr,
    )
    calls = []
    monkeypatch.setattr(mr, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(mr, "get_profile", lambda sid: None)
    monkeypatch.setattr(mr, "list_conditions", lambda student_id: [_Cond("Asthma", True)])
    monkeypatch.setattr(mr, "list_medications", lambda student_id: [])
    monkeypatch.setattr(mr, "list_allergies", lambda student_id: [])
    assert adapter.medical_record("C1") == {
        "profile": None, "conditions": [{"name": "Asthma", "active": True}],
        "medications": [], "allergies": []}
    assert calls == ["init"]
