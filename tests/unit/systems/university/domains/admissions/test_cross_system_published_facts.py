"""The university adapter's published-facts methods, which the sixth form
calls instead of importing the university: institution name, published
courses, offer terms and filing a school visit in the Admissions CRM.

Fakes only — the prospectus and offer-terms reads are replaced, and the
school-visit write runs against an in-memory database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from education_system.systems.university.domains.admissions.domain import school_visits
from education_system.systems.university.domains.admissions.domain.cross_system_adapter import (
    UniversityAdapter,
)


@pytest.fixture
def adapter():
    return UniversityAdapter()


def test_institution_name(adapter, monkeypatch):
    from education_system.systems.university.application.programmes import prospectus
    monkeypatch.setattr(prospectus, "institution_name", lambda: "Teesside University")
    assert adapter.institution_name() == "Teesside University"


def test_published_courses_are_plain_dicts(adapter, monkeypatch):
    from education_system.systems.university.application.programmes import prospectus
    monkeypatch.setattr(prospectus, "published_courses", lambda: [
        SimpleNamespace(code="CS", name="Computer Science", min_tariff=112,
                        duration="3 years")])
    assert adapter.published_courses() == [
        {"code": "CS", "name": "Computer Science", "min_tariff": 112,
         "duration": "3 years"}]


def test_offer_terms_for_choices(adapter, monkeypatch):
    from education_system.systems.university.domains.admissions.domain.ucas import (
        offer_terms,
    )
    seen = []
    terms = SimpleNamespace(
        terms_id=9, grade_requirement="ABB", grade_alternative="112 points",
        reply_deadline="2027-06-01", expiry_date="2027-09-01", scholarship="£1,000",
        accommodation_guaranteed=True, notes="n", issued_at="2027-01-02",
        updated_at="2027-01-03", issued_by="admissions",
        conditions=[{"type": "academic"}])

    def fake(ids):
        seen.append(ids)
        return {5: terms}

    monkeypatch.setattr(offer_terms, "terms_for_choices", fake)
    out = adapter.offer_terms_for_choices((5, 6))
    assert seen == [[5, 6]]
    assert out[5]["terms_id"] == 9
    assert out[5]["issued_at"] == "2027-01-02"
    assert out[5]["accommodation_guaranteed"] is True
    assert out[5]["conditions"] == [{"type": "academic"}]


# ── record_school_visit ──────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE campus_tours (tour_id INTEGER PRIMARY KEY AUTOINCREMENT, tour_date TEXT,
    tour_time TEXT, tour_guide TEXT, max_attendees INTEGER, meeting_point TEXT,
    duration_minutes INTEGER, status TEXT, current_attendees INTEGER DEFAULT 0);
CREATE TABLE admission_prospects (prospect_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT, last_name TEXT, email TEXT, date_of_birth TEXT, high_school TEXT,
    source TEXT, status TEXT);
CREATE TABLE tour_registrations (registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tour_id INTEGER, prospect_id INTEGER, num_guests INTEGER, attended INTEGER);
"""


@pytest.fixture
def crm(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SCHEMA)

    @contextmanager
    def transaction():
        yield conn
        conn.commit()

    from education_system.systems.university.infrastructure.database import db
    monkeypatch.setattr(db, "transaction", transaction)
    monkeypatch.setattr(school_visits, "_ensure_schema", lambda: None)
    yield conn
    conn.close()


_TOUR = {"tour_id": None, "tour_date": "2027-03-01", "tour_time": "09:00",
         "tour_guide": "T1", "max_attendees": 20, "meeting_point": "Main gate",
         "duration_minutes": 120, "status": "scheduled"}


def _attendee(key, **kw):
    row = {"key": key, "prospect_id": None, "first_name": "Amy", "last_name": "Lee",
           "email": f"{key}@example.org", "date_of_birth": "2009-01-01",
           "high_school": "Sixth Form", "source": "School Visit — X", "attended": False}
    row.update(kw)
    return row


def test_school_visit_creates_tour_prospects_and_registrations(adapter, crm):
    out = adapter.record_school_visit(dict(_TOUR), [_attendee("1"), _attendee("2")])
    assert out["registrations_created"] == 2
    assert {k: v["created"] for k, v in out["prospects"].items()} == {"1": True, "2": True}
    assert crm.execute("SELECT current_attendees FROM campus_tours").fetchone() == (2,)


def test_school_visit_is_idempotent(adapter, crm):
    first = adapter.record_school_visit(dict(_TOUR), [_attendee("1")])
    again = adapter.record_school_visit(
        dict(_TOUR, tour_id=first["tour_id"], tour_guide="T2"),
        [_attendee("1", prospect_id=first["prospects"]["1"]["prospect_id"], attended=True)])
    assert again["tour_id"] == first["tour_id"]
    assert again["registrations_created"] == 0
    assert again["prospects"]["1"]["created"] is False
    assert crm.execute("SELECT COUNT(*) FROM admission_prospects").fetchone() == (1,)
    assert crm.execute("SELECT attended FROM tour_registrations").fetchone() == (1,)
    assert crm.execute("SELECT tour_guide FROM campus_tours").fetchone() == ("T2",)


def test_school_visit_matches_prospect_by_email(adapter, crm):
    crm.execute("INSERT INTO admission_prospects (email) VALUES ('1@example.org')")
    out = adapter.record_school_visit(dict(_TOUR), [_attendee("1")])
    assert out["prospects"]["1"] == {"prospect_id": 1, "created": False}
