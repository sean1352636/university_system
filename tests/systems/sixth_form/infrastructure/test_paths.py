"""Tests for the sixth_form section of ``education_system.paths``."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def paths_mod():
    from education_system import paths
    return paths


def test_package_root_is_sixthform_package(paths_mod):
    assert paths_mod.SIXTH_FORM_PACKAGE_ROOT.name == "sixth_form"
    assert paths_mod.SIXTH_FORM_PACKAGE_ROOT.is_dir()


def test_data_dir_default_under_var(paths_mod):
    # Runtime state lives under <repo>/var (ADR 0018), not inside the package.
    assert paths_mod.SIXTH_FORM_DATA_DIR == (
        paths_mod.VAR_DIR / "data" / "sixth_form"
    ).resolve()


def test_email_templates_dir_lives_under_package(paths_mod):
    assert paths_mod.SIXTH_FORM_EMAIL_TEMPLATES_DIR == (
        paths_mod.SIXTH_FORM_PACKAGE_ROOT / "assets" / "templates" / "email"
    )


def test_all_domain_dbs_share_the_students_file(paths_mod):
    """Almost every per-domain ``*_DB`` constant aliases to ``STUDENTS_DB``."""
    students = paths_mod.SIXTH_FORM_STUDENTS_DB
    # Sample a wide cross-section across the file.
    sentinels = [
        "SIXTH_FORM_ENROLMENTS_DB", "SIXTH_FORM_COURSES_DB", "SIXTH_FORM_SUBJECTS_DB", "SIXTH_FORM_CLASS_GROUPS_DB",
        "SIXTH_FORM_TIMETABLE_DB", "SIXTH_FORM_ATTENDANCE_DB", "SIXTH_FORM_HOMEWORK_DB", "SIXTH_FORM_GRADEBOOK_DB",
        "SIXTH_FORM_PREDICTED_GRADES_DB", "SIXTH_FORM_MOCK_EXAMS_DB", "SIXTH_FORM_EXAM_ENTRIES_DB",
        "SIXTH_FORM_EXAM_RESULTS_DB", "SIXTH_FORM_UCAS_DB", "SIXTH_FORM_PERSONAL_STATEMENTS_DB",
        "SIXTH_FORM_REFERENCES_DB", "SIXTH_FORM_OFFERS_DB", "SIXTH_FORM_APPRENTICESHIPS_DB", "SIXTH_FORM_CAREERS_DB",
        "SIXTH_FORM_UNIVERSITY_VISITS_DB", "SIXTH_FORM_EPQ_DB", "SIXTH_FORM_WORK_EXPERIENCE_DB",
        "SIXTH_FORM_ROOM_BOOKING_DB", "SIXTH_FORM_DESTINATIONS_DB", "SIXTH_FORM_MEDICAL_RECORDS_DB",
        "SIXTH_FORM_TUTOR_GROUPS_DB", "SIXTH_FORM_BEHAVIOUR_DB", "SIXTH_FORM_SAFEGUARDING_DB",
        "SIXTH_FORM_WELLBEING_DB", "SIXTH_FORM_STUDENT_WELLBEING_DB", "SIXTH_FORM_PREVENT_DUTY_DB",
        "SIXTH_FORM_SYSTEM_LOGS_DB", "SIXTH_FORM_STAFF_DB", "SIXTH_FORM_FEES_DB", "SIXTH_FORM_BURSARIES_DB",
        "SIXTH_FORM_TRIPS_DB", "SIXTH_FORM_RECEIPTS_DB", "SIXTH_FORM_SETTINGS_DB", "SIXTH_FORM_ACADEMIC_YEAR_DB",
        "SIXTH_FORM_ALUMNI_DB", "SIXTH_FORM_CALENDAR_DB", "SIXTH_FORM_TODO_DB", "SIXTH_FORM_MULTI_LANGUAGE_DB",
        "SIXTH_FORM_ASSETS_DB", "SIXTH_FORM_GDPR_DB", "SIXTH_FORM_GOVERNANCE_DB", "SIXTH_FORM_POLICIES_DB",
        "SIXTH_FORM_STAFF_HR_DB", "SIXTH_FORM_RECRUITMENT_DB", "SIXTH_FORM_APPRAISALS_DB", "SIXTH_FORM_CPD_DB",
        "SIXTH_FORM_DBS_CHECKS_DB", "SIXTH_FORM_VISITORS_DB", "SIXTH_FORM_NOTIFICATIONS_DB",
        "SIXTH_FORM_DOCUMENT_HUB_DB", "SIXTH_FORM_ATTACHMENTS_DB", "SIXTH_FORM_CENSUS_ILR_DB",
        "SIXTH_FORM_EXPENSE_CLAIMS_DB", "SIXTH_FORM_FUNDING_DB", "SIXTH_FORM_AUDIT_REPORTS_DB",
        "SIXTH_FORM_DATA_EXPORT_DB", "SIXTH_FORM_COMPLIANCE_DB",
    ]
    for name in sentinels:
        assert getattr(paths_mod, name) == students, name


def test_all_exports_are_present(paths_mod):
    for name in paths_mod.__all__:
        assert hasattr(paths_mod, name), name


def test_all_db_paths_are_path_objects(paths_mod):
    for name in paths_mod.__all__:
        if not name.endswith("_DB") and name not in {
            "SIXTH_FORM_DATA_DIR", "SIXTH_FORM_EMAIL_TEMPLATES_DIR", "SIXTH_FORM_PACKAGE_ROOT",
        }:
            continue
        val = getattr(paths_mod, name)
        assert isinstance(val, Path), f"{name} is not a Path"


def test_ensure_directories_creates_data_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "data"
    monkeypatch.setenv("EDU_SIXTHFORM_DATA_DIR", str(target))
    # Reload so DATA_DIR re-reads the env var.
    from education_system import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    assert reloaded.SIXTH_FORM_DATA_DIR == target.resolve()
    assert not target.exists()
    reloaded.ensure_sixth_form_directories()
    assert target.exists() and target.is_dir()
    # Calling again is a no-op.
    reloaded.ensure_sixth_form_directories()
    assert target.exists()


def test_env_override_overrides_default(tmp_path, monkeypatch):
    override = tmp_path / "alt_data"
    monkeypatch.setenv("EDU_SIXTHFORM_DATA_DIR", str(override))
    from education_system import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        assert reloaded.SIXTH_FORM_DATA_DIR == override.resolve()
        assert reloaded.SIXTH_FORM_STUDENTS_DB == override.resolve() / "sixthform.db"
    finally:
        # Reset for downstream tests so the module sees the default again.
        monkeypatch.delenv("EDU_SIXTHFORM_DATA_DIR", raising=False)
        importlib.reload(paths_mod)
