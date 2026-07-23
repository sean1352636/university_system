"""Tests for the UCAS workflow pipeline."""

from __future__ import annotations

import sqlite3

import pytest


def _seed_ucas(db: str, student_id: str, year: int) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO ucas_applications (student_id, cycle_year, status) VALUES (?,?,?)",
        (student_id, year, "Draft"))
    conn.execute(
        "INSERT INTO personal_statements (student_id, body, status) VALUES (?,?,?)",
        (student_id, "My statement", "Approved"))
    conn.execute(
        "INSERT INTO academic_references (student_id, referee, status, submitted_at) "
        "VALUES (?,?,?,?)", (student_id, "Mr Ng", "Submitted", "2026-01-01"))
    conn.commit()
    conn.close()


def test_default_cycle_year_is_int():
    from education_system.post_16.sixthform_system.modules.domain.progression.ucas_workflow import (
        ucas_workflow as w,
    )
    assert isinstance(w.default_cycle_year(), int)


def test_pipeline_has_all_stages(feature_db):
    w = feature_db.mods["ucas_workflow"]
    p = w.get_pipeline("S1")
    assert p["total"] == len(w.STAGE_DEFS)
    keys = {s["key"] for s in p["stages"]}
    assert "tutor_check" in keys
    assert "application_submitted" in keys


def test_auto_stages_derive_from_live_data(feature_db):
    w = feature_db.mods["ucas_workflow"]
    year = w.default_cycle_year()
    _seed_ucas(feature_db.db, "S1", year)
    p = w.get_pipeline("S1", year)
    by_key = {s["key"]: s for s in p["stages"]}
    assert by_key["ucas_registered"]["status"] == "Complete"
    assert by_key["statement_drafted"]["status"] == "Complete"
    assert by_key["statement_approved"]["status"] == "Complete"
    assert by_key["reference_requested"]["status"] == "Complete"
    assert by_key["reference_submitted"]["status"] == "Complete"
    # S1 has predictions for all three subjects → complete.
    assert by_key["predicted_grades"]["status"] == "Complete"


def test_manual_signoff_persists_and_counts(feature_db):
    w = feature_db.mods["ucas_workflow"]
    year = w.default_cycle_year()
    before = w.get_pipeline("S1", year)["percent"]
    w.set_stage("S1", "tutor_check", cycle_year=year, status="Complete",
                signed_off_by="Ms Lee")
    after = w.get_pipeline("S1", year)
    by_key = {s["key"]: s for s in after["stages"]}
    assert by_key["tutor_check"]["status"] == "Complete"
    assert by_key["tutor_check"]["signed_off_by"] == "Ms Lee"
    assert by_key["tutor_check"]["signed_off_at"]      # stamped
    assert after["percent"] > before


def test_auto_stage_cannot_be_force_completed(feature_db):
    w = feature_db.mods["ucas_workflow"]
    with pytest.raises(w.ValidationError):
        w.set_stage("S1", "ucas_registered", status="Complete")
    # But marking N/A to skip is allowed.
    w.set_stage("S1", "ucas_registered", status="N/A")


def test_bad_due_date_rejected(feature_db):
    w = feature_db.mods["ucas_workflow"]
    with pytest.raises(w.ValidationError):
        w.set_stage("S1", "tutor_check", status="In Progress", due_date="not-a-date")


def test_overview_applicants_only(feature_db):
    w = feature_db.mods["ucas_workflow"]
    year = w.default_cycle_year()
    _seed_ucas(feature_db.db, "S1", year)
    rows = w.overview(year)                      # applicants_only default
    assert [r["student_id"] for r in rows] == ["S1"]
    allrows = w.overview(year, applicants_only=False)
    assert {r["student_id"] for r in allrows} == {"S1", "S2"}


def test_unknown_student_raises(feature_db):
    w = feature_db.mods["ucas_workflow"]
    with pytest.raises(ValueError):
        w.get_pipeline("NOPE")
