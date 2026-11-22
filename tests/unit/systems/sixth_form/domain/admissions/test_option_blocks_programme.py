"""Option blocks for an applicant's A-levels (option_blocks.programme_check),
as the Secondary School asks through the adapter: subjects in the same
block clash, and places come from the admissions programme places.

Uses the admissions ``admdb`` fixture (temp sixth form DB, no auth.db) and
also points the sixth form's SQLite log handler at the temp DB.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.qualifications import (
    option_blocks as OB,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    capacity,
)

YEAR = "2031/32"


@pytest.fixture(autouse=True)
def _quiet_log(admdb, monkeypatch):
    from education_system.systems.sixth_form.infrastructure import log_store
    monkeypatch.setattr(log_store, "DB_PATH", admdb["path"])
    monkeypatch.setattr(log_store, "_DB_READY", False)


def _blocks():
    for letter, subjects in {"A": ("Mathematics", "History"),
                             "B": ("Physics", "Biology"),
                             "C": ("Chemistry", "History")}.items():
        for s in subjects:
            OB.add_block_subject(YEAR, letter, s, qualification_type="A Level")


def _applicant(applicant_payload, first, subjects):
    s1, s2, s3 = subjects
    return adm.create_applicant(applicant_payload(
        first_name=first, email=f"{first.lower()}@example.com", intake_year=YEAR,
        subject_1=s1, subject_2=s2, subject_3=s3), allow_duplicate=True)


def test_subjects_in_different_blocks_fit(admdb, sign_in):
    sign_in()
    _blocks()
    out = OB.programme_check(["mathematics", "Physics", "History"], academic_year=YEAR)
    assert out["published"] and out["problems"] == []
    assert out["placement"] == {"A": "Mathematics", "B": "Physics", "C": "History"}
    assert out["courses"]["History"]["blocks"] == ["A", "C"]
    assert out["courses"]["Physics"]["capacity"] is None  # no places set: no limit


def test_a_block_clash_is_explained(admdb, sign_in):
    sign_in()
    _blocks()
    out = OB.programme_check(["Mathematics", "Physics", "Biology"], academic_year=YEAR)
    assert out["placement"] is None and out["full"] == []
    assert out["clashes"] and "Physics, Biology" in out["clashes"][0]
    out = OB.programme_check(["Mathematics", "Physics", "Latin"], academic_year=YEAR)
    assert out["clashes"] == ["Latin is not offered in any block"]


def test_full_subjects_use_admissions_places(admdb, sign_in, applicant_payload):
    sign_in()
    _blocks()
    capacity.set_places(YEAR, ("A Level", "Chemistry"), 1)
    ann = _applicant(applicant_payload, "Ann", ("Chemistry", "Physics", "History"))
    ben = _applicant(applicant_payload, "Ben", ("Chemistry", "Biology", "Mathematics"))
    assert OB.programme_check(["Chemistry"], academic_year=YEAR)["full"] == []
    adm.make_offer(ann.applicant_id)  # Ann now holds the only place
    out = OB.programme_check(["Chemistry", "Biology", "Mathematics"], academic_year=YEAR,
                             exclude_applicant=ben.applicant_id)
    assert out["full"] == ["Chemistry"] and out["courses"]["Chemistry"]["taken"] == 1
    assert "Chemistry is full (1 of 1 places taken)" in out["problems"]
    mine = OB.programme_check(["Chemistry", "Physics", "History"],
                              exclude_applicant=ann.applicant_id)  # Ann's own place
    assert mine["academic_year"] == YEAR and mine["full"] == []


def test_nothing_is_checked_without_blocks(admdb, sign_in):
    sign_in()
    out = OB.programme_check(["Mathematics", "Physics", "Biology"], academic_year=YEAR)
    assert out["published"] is False and out["problems"] == [] and out["placement"] is None


def test_the_adapter_asks_as_the_handover(admdb, monkeypatch):
    from education_system.systems.sixth_form.infrastructure.adapters.cross_system_adapter import (
        SixthFormAdapter,
    )
    monkeypatch.setattr(OB, "intake_year", lambda today=None: YEAR)
    out = SixthFormAdapter().option_blocks(["Mathematics"])  # nobody signed in
    assert out["academic_year"] == YEAR and out["published"] is False
