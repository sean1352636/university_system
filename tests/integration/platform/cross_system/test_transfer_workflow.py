"""Transfer workflow: audit trail, decisions, acknowledgement, checklist,
effective dates, reminders and the concurrency guard.

Every case runs against an isolated temp auth DB. The central audit rows
land in ``audit.db`` beside it, never in the running application's audit
database.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from education_system.platform.cross_system import (
    destinations,
    enrolment_schema,
    enrolments,
    handover,
    identity_service,
    transitions,
)
from education_system.platform.identity.auth.db import connect


@pytest.fixture
def db(tmp_path):
    """An isolated auth DB with the enrolment schema in place (the same
    fixture as test_enrolment_model.py)."""
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    destinations.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    destinations.reset_schema_cache_for_test()
    identity_service._initialised.clear()


@pytest.fixture
def journey(db):
    return identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2010-12-10",
        system="secondary", student_id="S9340", db_path=db)


def _outbox(db, name):
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cross_system_event_outbox WHERE event_name = ? "
            "ORDER BY created_at", (name,)).fetchall()]
    finally:
        conn.close()


def _audit_actions(db):
    path = Path(db).with_name("audit.db")
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute(
            "SELECT action FROM audit_log ORDER BY id").fetchall()]
    finally:
        conn.close()


def _open(db, journey, **kw):
    source = enrolments.current_enrolment(journey, "secondary", db_path=db)
    return transitions.start_transition(
        journey_id=journey, source_system="secondary",
        source_enrolment_id=source["enrolment_id"], db_path=db, **kw)


def _handover():
    return handover.build_handover(
        "secondary", "sixth_form",
        {"student_identity": {"n": "Ada"}, "application_details": {"r": 1},
         "gcse_results": {"maths": 8}, "attendance_behaviour": {"pct": 96}},
        consent={"attendance_behaviour"},
        safeguarding_reference="SG-1")


# ── Audit trail ─────────────────────────────────────────────────────

def test_every_step_writes_an_event_with_actor(db, journey):
    t = _open(db, journey, actor_user_id=5, effective_date="2026-09-01")
    tid = t["transition_id"]
    transitions.record_application(tid, actor_user_id=5, db_path=db)
    transitions.offer_place(tid, actor_user_id="admissions", db_path=db)
    transitions.accept_place(tid, accepted_by="parent", db_path=db)
    transitions.approve_handover(tid, _handover(), actor_user_id=7,
                                 db_path=db)
    transitions.admit(tid, local_student_id="SF1", actor_user_id=8,
                      db_path=db)
    transitions.complete(tid, actor_user_id=8, db_path=db)

    events = transitions.list_transition_events(tid, db_path=db)
    assert [e["step"] for e in events] == [
        "expected", "applied", "offered", "accepted", "handover_approved",
        "admitted", "completed"]
    assert [e["actor"] for e in events] == [
        "5", "5", "admissions", "parent", "7", "8", "8"]
    # The effective date set at the start is carried on every row.
    assert {e["effective_date"] for e in events} == {"2026-09-01"}
    assert events[1]["from_status"] == "expected"


def test_handover_event_records_released_and_withheld_keys(db, journey):
    tid = _open(db, journey)["transition_id"]
    transitions.approve_handover(tid, _handover(), db_path=db)
    event = transitions.list_transition_events(tid, db_path=db)[-1]
    assert event["step"] == "handover_approved"
    assert "gcse_results" in event["released_fields"]
    assert "safeguarding_reference" in event["released_fields"]
    # Not consented, and restricted — keys only, never values.
    assert "access_arrangements" not in event["released_fields"]
    assert "safeguarding_reference" in event["withheld_fields"]


def test_approve_and_complete_write_central_audit(db, journey):
    tid = _open(db, journey)["transition_id"]
    transitions.approve_handover(tid, _handover(), actor_user_id=7,
                                 db_path=db)
    transitions.admit(tid, local_student_id="SF1", db_path=db)
    transitions.complete(tid, db_path=db)
    actions = _audit_actions(db)
    assert "cross_system.handover" in actions
    assert "cross_system.transfer" in actions


# ── Decisions ───────────────────────────────────────────────────────

def test_accept_records_the_decision(db, journey):
    tid = _open(db, journey)["transition_id"]
    transitions.offer_place(tid, db_path=db)
    out = transitions.accept_place(tid, accepted_by="admissions-7",
                                   db_path=db)
    assert out["decision"] == "accepted"
    assert out["decided_by"] == "admissions-7"
    assert out["decided_at"]


def test_jumping_to_admitted_implies_acceptance(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="external",
        destination_system="secondary", db_path=db)
    out = transitions.admit(t["transition_id"], local_student_id="S777",
                            actor_user_id=3, db_path=db)
    assert out["decision"] == "accepted"


def test_reject_records_decision_and_tells_the_sender(db, journey):
    tid = _open(db, journey, destination_system="university")[
        "transition_id"]
    transitions.offer_place(tid, local_student_id="U1", db_path=db)
    out = transitions.reject(tid, reason="entry requirements not met",
                             actor_user_id=21, db_path=db)
    assert out["status"] == "cancelled"
    assert out["decision"] == "rejected"
    assert out["decided_by"] == "21"
    assert out["decision_reason"] == "entry requirements not met"
    assert out["cancelled_reason"] == "entry requirements not met"
    # The applicant enrolment is closed, as cancel() would.
    assert enrolments.get_enrolment(out["destination_enrolment_id"],
                                    db_path=db)["status"] == "cancelled"

    rejected = _outbox(db, "progression.rejected")
    assert len(rejected) == 1
    assert rejected[0]["target_system"] == "secondary"
    assert _outbox(db, "progression.cancelled") == []
    assert transitions.list_transition_events(
        tid, db_path=db)[-1]["step"] == "rejected"
    # No longer in the destination's queue.
    assert tid not in {r["transition_id"] for r in
                       transitions.pending_transitions("university",
                                                       db_path=db)}


def test_reject_needs_a_reason(db, journey):
    tid = _open(db, journey)["transition_id"]
    with pytest.raises(transitions.TransitionError):
        transitions.reject(tid, reason="  ", actor_user_id=1, db_path=db)


def test_cancel_after_completion_does_not_touch_the_live_enrolment(
        db, journey):
    tid = _open(db, journey)["transition_id"]
    transitions.admit(tid, local_student_id="SF1", db_path=db)
    done = transitions.complete(tid, db_path=db)
    with pytest.raises(transitions.TransitionError):
        transitions.cancel(tid, reason="mistake", db_path=db)
    assert enrolments.get_enrolment(done["destination_enrolment_id"],
                                    db_path=db)["status"] == "active"


def test_a_stale_read_cannot_move_the_transition_twice(db, journey,
                                                       monkeypatch):
    tid = _open(db, journey)["transition_id"]
    transitions.offer_place(tid, db_path=db)
    stale = transitions.get_transition(tid, db_path=db)
    transitions.accept_place(tid, db_path=db)

    # A second caller that read the row before the first moved it.
    real = transitions.get_transition
    monkeypatch.setattr(
        transitions, "get_transition",
        lambda t, *, db_path=None: dict(stale) if t == tid else real(
            t, db_path=db_path))
    with pytest.raises(transitions.TransitionError, match="changed"):
        transitions.accept_place(tid, db_path=db)
    monkeypatch.undo()
    events = transitions.list_transition_events(tid, db_path=db)
    assert [e["step"] for e in events].count("accepted") == 1


# ── Acknowledgement ─────────────────────────────────────────────────

def test_acknowledge_stamps_ticks_and_tells_the_sender(db, journey):
    tid = _open(db, journey)["transition_id"]
    transitions.approve_handover(tid, _handover(), db_path=db)
    out = transitions.acknowledge(tid, actor_user_id=11, note="all there",
                                  db_path=db)
    assert out["acknowledged_by"] == "11"
    assert out["acknowledged_at"]
    assert out["status"] == "handover_approved"   # not a workflow step
    received = next(i for i in out["checklist"]
                    if i["key"] == "documents_received")
    assert received["done"] and received["done_by"] == "11"

    events = _outbox(db, "handover.acknowledged")
    assert [e["target_system"] for e in events] == ["secondary"]
    # The note is staff free text; it stays off the bus.
    assert "all there" not in events[0]["payload_json"]

    again = transitions.acknowledge(tid, actor_user_id=99, db_path=db)
    assert again["acknowledged_by"] == "11"
    assert len(_outbox(db, "handover.acknowledged")) == 1


def test_acknowledge_needs_an_approved_handover(db, journey):
    tid = _open(db, journey)["transition_id"]
    with pytest.raises(transitions.TransitionError):
        transitions.acknowledge(tid, actor_user_id=1, db_path=db)


# ── Checklist ───────────────────────────────────────────────────────

def test_checklist_is_seeded_from_the_boundary(db, journey):
    tid = _open(db, journey)["transition_id"]
    keys = [i["key"] for i in transitions.get_checklist(tid, db_path=db)]
    assert keys == list(handover.SECONDARY_TO_SIXTH_FORM.checklist_keys())
    assert all(not i["done"] for i in transitions.get_checklist(
        tid, db_path=db))


def test_undeclared_boundary_gets_the_default_checklist(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="secondary",
        destination_system="external", db_path=db)
    keys = [i["key"] for i in transitions.get_checklist(
        t["transition_id"], db_path=db)]
    assert keys == [i.key for i in handover.DEFAULT_CHECKLIST]


def test_tick_and_untick(db, journey):
    tid = _open(db, journey)["transition_id"]
    items = transitions.tick_checklist_item(tid, "interview_held",
                                            actor_user_id=4, db_path=db)
    ticked = next(i for i in items if i["key"] == "interview_held")
    assert ticked["done"] and ticked["done_by"] == "4" and ticked["done_at"]
    # Persisted, and on the audit trail.
    assert next(i for i in transitions.get_checklist(tid, db_path=db)
                if i["key"] == "interview_held")["done"]
    assert transitions.list_transition_events(
        tid, db_path=db)[-1]["step"] == "checklist"

    # Re-ticking is a no-op, not a second event.
    before = len(transitions.list_transition_events(tid, db_path=db))
    transitions.tick_checklist_item(tid, "interview_held", actor_user_id=4,
                                    db_path=db)
    assert len(transitions.list_transition_events(tid, db_path=db)) == before

    items = transitions.tick_checklist_item(tid, "interview_held",
                                            actor_user_id=4, done=False,
                                            db_path=db)
    assert not next(i for i in items if i["key"] == "interview_held")["done"]


def test_tick_unknown_item_raises(db, journey):
    tid = _open(db, journey)["transition_id"]
    with pytest.raises(transitions.TransitionError, match="No checklist"):
        transitions.tick_checklist_item(tid, "made_up", actor_user_id=1,
                                        db_path=db)


# ── Effective date and reminders ────────────────────────────────────

def test_effective_date_is_validated(db, journey):
    with pytest.raises(transitions.TransitionError):
        _open(db, journey, effective_date="next september")


def test_complete_adopts_start_date_as_effective_date(db, journey):
    tid = _open(db, journey)["transition_id"]
    transitions.admit(tid, local_student_id="SF1", db_path=db)
    done = transitions.complete(tid, start_date="2026-09-01", db_path=db)
    assert done["effective_date"] == "2026-09-01"


def test_reminder_is_queued_for_later(db, journey):
    due = date.today() + timedelta(days=60)
    t = _open(db, journey, effective_date=due.isoformat())
    reminders = _outbox(db, "transition.reminder")
    assert len(reminders) == 1
    assert reminders[0]["target_system"] == "sixth_form"
    assert reminders[0]["available_at"].startswith(
        (due - timedelta(days=transitions.REMINDER_DAYS_BEFORE)).isoformat())
    assert json.loads(reminders[0]["payload_json"])["effective_date"] == \
        due.isoformat()

    # Accepting re-offers the same reminder, which is idempotent.
    tid = t["transition_id"]
    transitions.offer_place(tid, db_path=db)
    transitions.accept_place(tid, db_path=db)
    assert transitions.schedule_transition_reminder(tid, db_path=db) == \
        reminders[0]["event_id"]
    assert len(_outbox(db, "transition.reminder")) == 1


def test_moving_the_date_queues_a_new_reminder(db, journey):
    first = date.today() + timedelta(days=60)
    t = _open(db, journey, effective_date=first.isoformat())
    moved = transitions.set_effective_date(
        t["transition_id"], (first + timedelta(days=7)).isoformat(),
        actor_user_id=2, db_path=db)
    assert moved["effective_date"] == (first + timedelta(days=7)).isoformat()
    assert len(_outbox(db, "transition.reminder")) == 2
    assert transitions.list_transition_events(
        t["transition_id"], db_path=db)[-1]["step"] == "effective_date"


def test_no_reminder_without_a_future_date(db, journey):
    t = _open(db, journey)
    assert transitions.schedule_transition_reminder(
        t["transition_id"], db_path=db) is None
    past = _open(db, journey, destination_system="fe_college",
                 effective_date="2020-01-01")
    assert transitions.schedule_transition_reminder(
        past["transition_id"], db_path=db) is None
    assert _outbox(db, "transition.reminder") == []


def test_no_reminder_once_the_handover_is_approved(db, journey):
    due = (date.today() + timedelta(days=60)).isoformat()
    t = _open(db, journey)
    transitions.approve_handover(t["transition_id"], _handover(),
                                 effective_date=due, db_path=db)
    assert transitions.schedule_transition_reminder(
        t["transition_id"], db_path=db) is None


# ── Schema migration ────────────────────────────────────────────────

def test_new_columns_reach_an_existing_table(tmp_path):
    """A DB whose learner_transition predates these columns gains them."""
    path = str(tmp_path / "old.db")
    enrolment_schema.reset_schema_cache_for_test()
    from education_system.platform.identity.auth.schema import (
        initialise_auth_db,
    )
    initialise_auth_db(path)
    conn = connect(path)
    try:
        conn.execute(
            """CREATE TABLE learner_transition (
                   transition_id TEXT PRIMARY KEY, journey_id TEXT NOT NULL,
                   source_enrolment_id TEXT, source_system TEXT,
                   destination_system TEXT NOT NULL,
                   destination_enrolment_id TEXT,
                   status TEXT NOT NULL DEFAULT 'expected',
                   initiated_at TEXT NOT NULL DEFAULT (datetime('now')),
                   completed_at TEXT, reason TEXT, actor_user_id INTEGER,
                   handover_json TEXT, handover_approved_at TEXT,
                   consent_reference TEXT, cancelled_reason TEXT,
                   updated_at TEXT NOT NULL DEFAULT (datetime('now')))""")
        conn.commit()
    finally:
        conn.close()
    enrolment_schema.ensure_enrolment_schema(path)
    enrolment_schema.reset_schema_cache_for_test()
    enrolment_schema.ensure_enrolment_schema(path)   # idempotent
    conn = connect(path)
    try:
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(learner_transition)").fetchall()}
    finally:
        conn.close()
    enrolment_schema.reset_schema_cache_for_test()
    assert {"effective_date", "decision", "decided_by", "decided_at",
            "decision_reason", "acknowledged_by", "acknowledged_at",
            "checklist_json"} <= cols
