"""Audit entries with before → after values.

The diff and its storage format are tested pure. ``record()`` is tested
for backward compatibility — every existing caller passes no changes —
and the services that now record before and after are exercised on the
conftest's throwaway database.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.compliance.eligibility import AuditEntry
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.domain.records.audit import (
    AuditRecord,
    FieldChange,
)
from education_system.systems.apprenticeships.infrastructure.persistence import schema
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.compliance import compliance_service
from education_system.systems.apprenticeships.application.funding import funding_service
from education_system.systems.apprenticeships.application.learning import (
    learning_plan_service,
    training_service,
)
from education_system.systems.apprenticeships.application.security.access import PermissionDenied


@dataclass
class _Record:
    name: str | None
    hours: float
    status: str
    updated_at: str = ""


# ═════════════════════════════════════════════════════════════════════
# The diff
# ═════════════════════════════════════════════════════════════════════

class TestDiff:
    def test_only_changed_fields_are_reported(self):
        before = _Record("Jo", 30.0, "Draft", updated_at="t1")
        after = _Record("Jo", 37.5, "Draft", updated_at="t2")
        assert audit.diff(before, after) == [{"field": "hours", "before": 30.0, "after": 37.5}]

    def test_blank_and_none_are_the_same_value(self):
        assert audit.diff(_Record(None, 1, "A"), _Record("  ", 1, "A")) == []

    def test_named_fields_limit_the_comparison(self):
        assert audit.diff(_Record("Jo", 1, "A"), _Record("Al", 2, "B"), fields=["status"]) == [
            {"field": "status", "before": "A", "after": "B"}
        ]

    def test_a_mapping_can_stand_for_the_new_state(self):
        assert audit.diff(_Record("Jo", 1, "Submitted"), {"status": "Approved"}) == [
            {"field": "status", "before": "Submitted", "after": "Approved"}
        ]

    def test_creation_and_removal(self):
        assert audit.diff(None, {"grade": "Pass"}) == [
            {"field": "grade", "before": None, "after": "Pass"}
        ]
        assert audit.diff({"role": "staff"}, None, fields=["role"]) == [
            {"field": "role", "before": "staff", "after": None}
        ]

    def test_a_single_change_is_nothing_when_nothing_moved(self):
        assert audit.change("role", "staff", "staff") == []
        assert audit.change("role", None, "employer") == [
            {"field": "role", "before": None, "after": "employer"}
        ]

    def test_long_values_are_cut_short(self):
        long = "x" * (config.AUDIT_CHANGE_VALUE_MAX_LENGTH + 50)
        after = audit.diff({}, {"notes": long})[0]["after"]
        assert len(after) == config.AUDIT_CHANGE_VALUE_MAX_LENGTH and after.endswith("…")

    def test_a_change_reads_field_before_arrow_after(self):
        assert FieldChange("status", "Applicant", "On Programme").label == (
            "status: Applicant → On Programme"
        )
        assert FieldChange("tutor_id", None, 4).label == "tutor_id: — → 4"


class TestStoredForm:
    def test_encode_and_decode_round_trip(self):
        changes = audit.diff(_Record("Jo", 30.0, "Draft"), _Record("Al", 37.5, "Draft"))
        assert audit.decode(audit.encode(changes)) == [FieldChange(**c) for c in changes]

    def test_nothing_to_record_is_null(self):
        assert audit.encode([]) is None
        assert audit.encode(None) is None

    def test_tuples_and_field_changes_are_accepted_too(self):
        encoded = audit.encode([("a", 1, 2), FieldChange("b", None, "x")])
        assert audit.describe(audit.decode(encoded)) == "a: 1 → 2; b: — → x"

    def test_an_unreadable_value_is_still_shown(self):
        assert audit.decode("{oops") == [FieldChange("(unreadable)", None, "{oops")]
        assert audit.decode(None) == []


# ═════════════════════════════════════════════════════════════════════
# record() and the trail
# ═════════════════════════════════════════════════════════════════════

class TestRecord:
    def test_the_existing_call_shape_still_works(self, db, admin):
        compliance_repository.record(
            action="update", entity="apprentice", entity_id=7,
            actor="admin5", actor_role="admin", detail="email",
        )
        (entry,) = compliance_service.audit_trail(admin, entity="apprentice", entity_id=7)
        assert isinstance(entry, AuditEntry) and isinstance(entry, AuditRecord)
        assert (entry.detail, entry.changes, entry.changes_text) == ("email", [], "")

    def test_changes_are_stored_and_read_back(self, db, admin):
        compliance_repository.record(
            action="update", entity="apprentice", entity_id=7, actor="admin5",
            changes=[{"field": "status", "before": "Applicant", "after": "On Programme"}],
        )
        (entry,) = compliance_service.audit_trail(admin, entity="apprentice")
        assert entry.changes == [FieldChange("status", "Applicant", "On Programme")]
        assert entry.changes_text == "status: Applicant → On Programme"

    def test_a_malformed_change_list_never_breaks_the_caller(self, db):
        assert compliance_repository.record(
            action="update", entity="apprentice", changes=[object()]
        ) is None

    def test_filters_by_date_range_and_by_edits_only(self, db, admin):
        compliance_repository.record(action="export", entity="evidence_pack", entity_id=1)
        compliance_repository.record(
            action="update", entity="apprentice", entity_id=1,
            changes=[{"field": "email", "before": None, "after": "jo@example.com"}],
        )
        # A day either side: ts is UTC, date.today() is local.
        since = (date.today() - timedelta(days=1)).isoformat()
        until = (date.today() + timedelta(days=1)).isoformat()
        assert len(compliance_service.audit_trail(admin, since=since, until=until)) == 2
        assert compliance_service.audit_trail(admin, until="2000-01-01") == []
        (edit,) = compliance_service.audit_trail(admin, changes_only=True)
        assert edit.entity == "apprentice"

    def test_a_date_filter_must_be_a_date(self, db, admin):
        with pytest.raises(ValidationError):
            compliance_service.audit_trail(admin, since="last week")

    def test_only_an_administrator_reads_it(self, cohort):
        with pytest.raises(PermissionDenied):
            compliance_service.audit_trail(cohort["tutor"])
        with pytest.raises(PermissionDenied):
            compliance_service.audit_filter_options(cohort["tutor"])

    def test_an_existing_database_gains_the_column(self, db, admin):
        # Rebuild audit_log exactly as it was before the column existed.
        conn = sqlite3.connect(db)
        conn.execute("DROP TABLE audit_log")
        conn.execute(
            """CREATE TABLE audit_log (
                   audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts          TEXT    NOT NULL DEFAULT (datetime('now')),
                   actor       TEXT,
                   actor_role  TEXT,
                   action      TEXT    NOT NULL,
                   entity      TEXT    NOT NULL,
                   entity_id   TEXT,
                   detail      TEXT
               )"""
        )
        conn.execute(
            "INSERT INTO audit_log (action, entity, detail) VALUES ('update', 'apprentice', 'old')"
        )
        conn.commit()
        conn.close()

        schema.reset_ready_flag()
        schema.init_db()
        conn = sqlite3.connect(db)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
        conn.close()
        assert "changes" in columns
        (entry,) = compliance_service.audit_trail(admin, entity="apprentice")
        assert (entry.detail, entry.changes) == ("old", [])


# ═════════════════════════════════════════════════════════════════════
# The services record before and after
# ═════════════════════════════════════════════════════════════════════

def _changes(admin, **filters) -> dict[str, tuple]:
    """The newest matching entry's changes as {field: (before, after)}."""
    entry = compliance_service.audit_trail(admin, limit=1, **filters)[0]
    return {c.field: (c.before, c.after) for c in entry.changes}


class TestServicesRecordBeforeAndAfter:
    def test_editing_an_apprentice(self, cohort, admin):
        aid = cohort["apprentice_id"]
        apprentice_service.update_apprentice(admin, aid, {
            "email": "jo.bell@example.com", "weekly_hours": 30,
        })
        changes = _changes(admin, entity="apprentice", entity_id=aid, action="update")
        assert changes == {"email": (None, "jo.bell@example.com"), "weekly_hours": (37.5, 30.0)}

    def test_a_status_change_and_a_tutor_change(self, cohort, admin):
        aid = cohort["apprentice_id"]
        apprentice_service.change_status(
            admin, aid, "Break in Learning", reason="Long-term sickness", notes="Operation"
        )
        assert _changes(admin, entity="apprentice", entity_id=aid)["status"] == (
            "On Programme", "Break in Learning",
        )
        apprentice_service.assign_tutor(admin, aid, None)
        assert _changes(admin, entity="apprentice", entity_id=aid) == {
            "tutor_id": (cohort["tutor_id"], None)
        }

    def test_off_the_job_edits_and_approval(self, cohort, admin):
        entry = training_service.log_hours(cohort["learner"], {
            "activity_date": date.today().isoformat(), "hours": 3,
            "activity_type": "Online learning", "description": "Module 1",
        })
        training_service.update_entry(cohort["learner"], entry.entry_id, {"hours": 4})
        assert _changes(admin, entity="otj_entry", action="update") == {"hours": (3.0, 4.0)}

        training_service.submit_hours(cohort["learner"], entry.entry_id)
        training_service.approve_hours(cohort["employer_actor"], entry.entry_id, note="Fine")
        assert _changes(admin, entity="otj_entry", action="approve") == {
            "status": ("Submitted", "Approved"),
            "approved_by": (None, "employer1"),
            "decision_note": (None, "Fine"),
        }

    def test_a_price_change(self, cohort, admin):
        aid = cohort["apprentice_id"]
        funding_service.set_funding(admin, aid, {"negotiated_price": 18000.0})
        created = _changes(admin, entity="funding", entity_id=aid)
        assert created["negotiated_price"] == (None, 18000.0)

        funding_service.set_funding(admin, aid, {"negotiated_price": 16000.0})
        changed = _changes(admin, entity="funding", entity_id=aid, action="update")
        assert changed["negotiated_price"] == (18000.0, 16000.0)
        assert "funding_model" not in changed

    def test_objective_edits_and_progress(self, cohort, admin):
        objective = learning_plan_service.add_objective(
            admin, cohort["apprentice_id"], {"title": "Build a network"}
        )
        learning_plan_service.update_objective(
            admin, objective.objective_id, {"title": "Build and document a network"}
        )
        assert _changes(admin, entity="ilp_objective", action="update") == {
            "title": ("Build a network", "Build and document a network")
        }
        learning_plan_service.record_progress(admin, objective.objective_id, progress=40)
        assert _changes(admin, entity="ilp_objective", action="update") == {
            "status": ("Not started", "In progress"), "progress": (0, 40),
        }
