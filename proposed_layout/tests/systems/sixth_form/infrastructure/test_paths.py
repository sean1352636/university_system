"""Tests for ``education_system.systems.sixth_form.infrastructure.paths``."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def paths_mod():
    from education_system.systems.sixth_form.infrastructure import paths
    return paths


def test_package_root_is_sixthform_package(paths_mod):
    assert paths_mod.PACKAGE_ROOT.name == "sixthform_system"
    assert paths_mod.PACKAGE_ROOT.is_dir()


def test_data_dir_default_under_package(paths_mod):
    # In the default environment (no env override) the data dir should
    # live inside the package.
    assert paths_mod.DATA_DIR == (paths_mod.PACKAGE_ROOT / "data").resolve()


def test_email_templates_dir_lives_under_package(paths_mod):
    assert paths_mod.EMAIL_TEMPLATES_DIR == (
        paths_mod.PACKAGE_ROOT / "data" / "templates" / "email"
    )


def test_all_domain_dbs_share_the_students_file(paths_mod):
    """Almost every per-domain ``*_DB`` constant aliases to ``STUDENTS_DB``."""
    students = paths_mod.STUDENTS_DB
    # Sample a wide cross-section across the file.
    sentinels = [
        "ENROLMENTS_DB", "COURSES_DB", "SUBJECTS_DB", "CLASS_GROUPS_DB",
        "TIMETABLE_DB", "ATTENDANCE_DB", "HOMEWORK_DB", "GRADEBOOK_DB",
        "PREDICTED_GRADES_DB", "MOCK_EXAMS_DB", "EXAM_ENTRIES_DB",
        "EXAM_RESULTS_DB", "UCAS_DB", "PERSONAL_STATEMENTS_DB",
        "REFERENCES_DB", "OFFERS_DB", "APPRENTICESHIPS_DB", "CAREERS_DB",
        "UNIVERSITY_VISITS_DB", "EPQ_DB", "WORK_EXPERIENCE_DB",
        "ROOM_BOOKING_DB", "DESTINATIONS_DB", "MEDICAL_RECORDS_DB",
        "TUTOR_GROUPS_DB", "BEHAVIOUR_DB", "SAFEGUARDING_DB",
        "WELLBEING_DB", "STUDENT_WELLBEING_DB", "PREVENT_DUTY_DB",
        "SYSTEM_LOGS_DB", "STAFF_DB", "FEES_DB", "BURSARIES_DB",
        "TRIPS_DB", "RECEIPTS_DB", "SETTINGS_DB", "ACADEMIC_YEAR_DB",
        "ALUMNI_DB", "CALENDAR_DB", "TODO_DB", "MULTI_LANGUAGE_DB",
        "ASSETS_DB", "GDPR_DB", "GOVERNANCE_DB", "POLICIES_DB",
        "STAFF_HR_DB", "RECRUITMENT_DB", "APPRAISALS_DB", "CPD_DB",
        "DBS_CHECKS_DB", "VISITORS_DB", "NOTIFICATIONS_DB",
        "DOCUMENT_HUB_DB", "ATTACHMENTS_DB", "CENSUS_ILR_DB",
        "EXPENSE_CLAIMS_DB", "FUNDING_DB", "AUDIT_REPORTS_DB",
        "DATA_EXPORT_DB", "COMPLIANCE_DB",
    ]
    for name in sentinels:
        assert getattr(paths_mod, name) == students, name


def test_all_exports_are_present(paths_mod):
    for name in paths_mod.__all__:
        assert hasattr(paths_mod, name), name


def test_all_db_paths_are_path_objects(paths_mod):
    for name in paths_mod.__all__:
        if not name.endswith("_DB") and name not in {
            "DATA_DIR", "EMAIL_TEMPLATES_DIR", "PACKAGE_ROOT",
        }:
            continue
        val = getattr(paths_mod, name)
        assert isinstance(val, Path), f"{name} is not a Path"


def test_ensure_directories_creates_data_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "data"
    monkeypatch.setenv("EDU_SIXTHFORM_DATA_DIR", str(target))
    # Reload so DATA_DIR re-reads the env var.
    from education_system.systems.sixth_form.infrastructure import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    assert reloaded.DATA_DIR == target.resolve()
    assert not target.exists()
    reloaded.ensure_directories()
    assert target.exists() and target.is_dir()
    # Calling again is a no-op.
    reloaded.ensure_directories()
    assert target.exists()


def test_env_override_overrides_default(tmp_path, monkeypatch):
    override = tmp_path / "alt_data"
    monkeypatch.setenv("EDU_SIXTHFORM_DATA_DIR", str(override))
    from education_system.systems.sixth_form.infrastructure import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        assert reloaded.DATA_DIR == override.resolve()
        assert reloaded.STUDENTS_DB == override.resolve() / "sixthform.db"
    finally:
        # Reset for downstream tests so the module sees the default again.
        monkeypatch.delenv("EDU_SIXTHFORM_DATA_DIR", raising=False)
        importlib.reload(paths_mod)
