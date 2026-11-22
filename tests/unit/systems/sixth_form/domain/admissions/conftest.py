"""Admissions test fixtures: a temp sixthform.db and a signed-in user.

Every admissions module reads ``admissions.DB_PATH`` through
``admissions._connect`` (the enrolment/onboarding modules have their own
``DB_PATH``), so those paths plus each module's readiness flag are
redirected. The sensitive-access log writes to the students DB path
fixed at import, so it is replaced with a list the tests can inspect.
"""

from __future__ import annotations

import importlib

import pytest

_PKG = "education_system.systems.sixth_form.domain.admissions"
_MODULES = (
    "admissions", "applicant_details", "record_safety", "entry_requirements",
    "references", "open_events", "online_application", "gcse_results_day",
    "enrolments.enrolments", "enrolments.identity_checks",
    "onboarding.onboarding", "interviews", "college_intake",
    "cycles", "capacity", "retention", "admissions_insights",
    "admissions_comms", "applicant_portal",
)
_READY_FLAGS = ("_DB_READY", "_READY")
#: Modules outside admissions that conversion writes to.
_OTHER_MODULES = (
    "education_system.systems.sixth_form.domain.academics.qualifications.learning_aims",
    "education_system.systems.sixth_form.domain.academics.qualifications.prior_attainment",
    # Conversion hands contacts / SEND / medical / safeguarding / bursary
    # interest to these; onboarding reads GDPR consents.
    "education_system.systems.sixth_form.domains.communications.domain.parent_contacts.parent_contacts",
    "education_system.systems.sixth_form.domain.pastoral.health.medical_records.medical_records",
    "education_system.systems.sixth_form.domain.safeguarding.safeguarding",
    "education_system.systems.sixth_form.domains.finance.domain.bursaries.bursaries",
    "education_system.systems.sixth_form.domain.governance.gdpr.gdpr",
    "education_system.systems.sixth_form.domain.pastoral.accessibility.accessibility",
    "education_system.systems.sixth_form.domain.pastoral.send.send",
    # Leaving / rollover touch tutor groups, class groups, exit interviews.
    "education_system.systems.sixth_form.domain.pastoral.tutor_groups.tutor_groups",
    "education_system.systems.sixth_form.domain.learners.exit_interviews.exit_interviews",
    "education_system.systems.sixth_form.domain.academics.class_groups.class_groups",
    "education_system.systems.sixth_form.domain.academics.class_groups.class_group_membership",
    "education_system.systems.sixth_form.domain.academics.class_groups.class_group_history",
    # Onboarding evidence rules read these (ID card, locker, library,
    # timetable tasks) — keep them off the live DBs too.
    "education_system.systems.sixth_form.domains.operations.domain.id_cards.id_cards",
    "education_system.systems.sixth_form.domains.operations.domain.lockers.lockers",
    "education_system.systems.sixth_form.domain.academics.library.library",
    "education_system.systems.sixth_form.domain.academics.timetable.timetable",
    "education_system.systems.sixth_form.domain.academics.class_groups.class_group_conflicts",
)


@pytest.fixture
def admdb(tmp_path, monkeypatch):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    db_path = str(tmp_path / "sixthform.db")
    monkeypatch.setattr(students, "DB_PATH", db_path)
    monkeypatch.setattr(students, "_DB_READY", False)
    # create_student provisions a login in the shared auth.db.
    monkeypatch.setattr(students, "_provision_login_account",
                        lambda *_a, **_k: None)
    # Leaving (withdraw_student / an enrolment withdrawal that leaves the
    # learner with nothing open) closes logins in the shared auth.db and
    # the cross-system enrolment — keep tests off both.
    for step in ("_revoke_sixth_form_access", "disable_leaver_login",
                 "disable_orphaned_parent_logins",
                 "_close_sixth_form_enrolment"):
        monkeypatch.setattr(students, step, lambda *a, **k: None)
    # reinstate_student re-enables the login straight through auth.db.
    from education_system.platform.identity.auth import db as _auth_db

    def _no_auth_db(*a, **k):
        raise RuntimeError("auth.db is not available in admissions tests")
    monkeypatch.setattr(_auth_db, "connect", _no_auth_db)
    for name in _OTHER_MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        monkeypatch.setattr(mod, "DB_PATH", db_path, raising=False)
        if isinstance(getattr(mod, "_READY_PATHS", None), set):
            monkeypatch.setattr(mod, "_READY_PATHS", set())
        if hasattr(mod, "_DB_READY"):
            monkeypatch.setattr(mod, "_DB_READY", False)
    # The SEND register reads its path from ``paths`` at connect time.
    from education_system import paths as _paths
    monkeypatch.setattr(_paths, "SIXTH_FORM_SEND_DB", db_path, raising=False)
    # A filed safeguarding concern is mirrored onto the cross-system
    # register (platform DB) — keep tests off it.
    try:
        from education_system.platform.governance.safeguarding import (
            alert_service,
        )
        monkeypatch.setattr(alert_service, "raise_flag_for_local_concern",
                            lambda *a, **k: None)
    except ImportError:
        pass
    for name in _MODULES:
        try:
            mod = importlib.import_module(f"{_PKG}.{name}")
        except ImportError:
            continue
        monkeypatch.setattr(mod, "DB_PATH", db_path, raising=False)
        for flag in _READY_FLAGS:
            if hasattr(mod, flag):
                monkeypatch.setattr(mod, flag, False)
    logged: list[tuple] = []
    monkeypatch.setattr(access, "log_sensitive_access",
                        lambda p, area, action, **k: logged.append(
                            (p.username, area, action, k)))
    return {"path": db_path, "sensitive_log": logged}


@pytest.fixture
def ilr_export_dbs(admdb, tmp_path, monkeypatch):
    """The ILR file is built by the census_ilr return builder, which also
    reads exam results, CTF postcodes, planned hours (timetable, courses,
    class groups, the academic-year register), attendance (when a return
    is generated) and its own census DB: point them all at the temp DBs
    so neither the export nor a generated return reaches the live var/."""
    from education_system import paths as _paths
    monkeypatch.setattr(_paths, "SIXTH_FORM_CENSUS_ILR_DB",
                        str(tmp_path / "census_ilr.db"), raising=False)
    monkeypatch.setattr(_paths, "ensure_sixth_form_directories",
                        lambda: None, raising=False)
    sf = "education_system.systems.sixth_form"
    for name in (
        f"{sf}.domain.assessment.exam_results.exam_results",
        f"{sf}.domain.assessment.exam_entries.exam_entries",
        f"{sf}.infrastructure.integrations.store",
        f"{sf}.domain.academics.timetable.timetable",
        f"{sf}.domain.academics.courses.courses",
        f"{sf}.domain.academics.class_groups.class_groups",
        f"{sf}.domain.academics.academic_year.academic_year",
        f"{sf}.domain.academics.attendance.attendance",
        f"{sf}.domain.academics.attendance.attendance_calendar",
        f"{sf}.domain.academics.attendance.attendance_codes",
        f"{sf}.domain.academics.attendance.attendance_sessions",
        f"{sf}.domain.academics.attendance.attendance_census",
    ):
        mod = importlib.import_module(name)
        monkeypatch.setattr(mod, "DB_PATH", admdb["path"], raising=False)
        for flag in _READY_FLAGS:
            ready = getattr(mod, flag, None)
            if isinstance(ready, set):
                monkeypatch.setattr(mod, flag, set())
            elif ready is not None:
                monkeypatch.setattr(mod, flag, False)
    return admdb


def principal(username="adm1", *, role="staff", capabilities=None):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    caps = capabilities if capabilities is not None else {access.ADMISSIONS}
    return access.Principal(username=username, user_id=None, role=role,
                            capabilities=frozenset(caps))


@pytest.fixture
def sign_in(monkeypatch):
    """``sign_in(username, capabilities=..., role=...)`` makes that the
    signed-in principal for the rest of the test."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )

    def _sign_in(username="adm1", **kw):
        p = principal(username, **kw)
        monkeypatch.setattr(access, "_current", p)
        return p
    return _sign_in


@pytest.fixture
def applicant_payload():
    import datetime as _dt

    def _make(**over):
        base = dict(first_name="Zed", last_name="Testerson",
                    dob="2010-03-04", email="zed.t@example.com",
                    phone="07700 900123", predicted_gcses="Maths 7",
                    subject_1="Mathematics", application_source="Direct",
                    submitted_at=_dt.date.today().isoformat())
        base.update(over)
        return base
    return _make


@pytest.fixture
def outbox(admdb, monkeypatch):
    """Messages go to the temp DB and are never delivered: ``send_message``
    only records the message (nothing reaches the platform outbox or the
    delivery mode) and every delivery reads as held. Returns the list of
    messages "sent". Also pins the online-form salt."""
    from types import SimpleNamespace

    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages,
    )
    monkeypatch.setattr(messages, "DB_PATH", admdb["path"])
    monkeypatch.setattr(messages, "_DB_READY", False)
    sent: list = []

    def _send(message_id):
        m = messages.get_message(message_id)
        sent.append(m)
        return m
    monkeypatch.setattr(messages, "send_message", _send)
    monkeypatch.setattr(messages, "delivery_status", lambda mid: SimpleNamespace(
        state="Held", detail="Held: delivery mode is inbox_only",
        last_error=None))
    monkeypatch.setenv("SIXTHFORM_APPLY_SALT", "unit-test-salt")
    return sent
