"""Tests for the cross-system identity service + durable event bus.

Covers Step 1 of the cross-system integration plan:

- ``shared.cross_system.identity_service`` — student_journey lifecycle.
- ``shared.integrations.cross_system_bus`` — durable outbox + dispatch.

The schema lives in the shared auth DB; both modules talk to whatever
``connect(db_path)`` resolves to. We give every test its own throwaway
DB initialised by ``initialise_auth_db`` so they run in parallel under
pytest-xdist without crosstalk.
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.cross_system import identity_service as ids
from education_system.shared.integrations import cross_system_bus as bus


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "auth.db")
    initialise_auth_db(p)
    return p


@pytest.fixture(autouse=True)
def _isolate_subscribers():
    """Each test starts with an empty subscriber registry."""
    bus.clear_subscribers_for_test()
    yield
    bus.clear_subscribers_for_test()


# ── Identity service ─────────────────────────────────────────────────────

class TestJourneyLifecycle:
    def test_create_then_lookup_returns_same_id(self, db_path):
        jid1 = ids.get_or_create_journey(
            first_name="Ada", last_name="Lovelace",
            date_of_birth="2008-12-10", current_system="college",
            db_path=db_path,
        )
        jid2 = ids.get_or_create_journey(
            first_name="Ada", last_name="Lovelace",
            date_of_birth="2008-12-10", current_system="college",
            db_path=db_path,
        )
        assert jid1 == jid2

    def test_match_is_case_insensitive(self, db_path):
        jid1 = ids.get_or_create_journey(
            first_name="Ada", last_name="Lovelace",
            date_of_birth="2008-12-10", current_system="school",
            db_path=db_path,
        )
        jid2 = ids.get_or_create_journey(
            first_name="ADA", last_name="lovelace",
            date_of_birth="2008-12-10", current_system="school",
            db_path=db_path,
        )
        assert jid1 == jid2

    def test_different_dob_creates_new_journey(self, db_path):
        jid1 = ids.get_or_create_journey(
            first_name="Bob", last_name="Smith", date_of_birth="2009-01-01",
            current_system="school", db_path=db_path,
        )
        jid2 = ids.get_or_create_journey(
            first_name="Bob", last_name="Smith", date_of_birth="2010-01-01",
            current_system="school", db_path=db_path,
        )
        assert jid1 != jid2

    def test_unknown_system_rejected(self, db_path):
        with pytest.raises(ids.IdentityError):
            ids.get_or_create_journey(
                first_name="X", last_name="Y", date_of_birth="2000-01-01",
                current_system="bootcamp", db_path=db_path,
            )

    def test_registration_transition_recorded_on_create(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Carol", last_name="Danvers",
            date_of_birth="2007-05-05", current_system="college",
            db_path=db_path,
        )
        transitions = ids.list_transitions(jid, db_path=db_path)
        assert len(transitions) == 1
        assert transitions[0]["from_system"] is None
        assert transitions[0]["to_system"] == "college"
        assert transitions[0]["reason"] == "registration"


class TestAttachSystemRecord:
    def test_attach_then_lookup_by_system_pk(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Dave", last_name="Lister", date_of_birth="2007-06-06",
            current_system="college", db_path=db_path,
        )
        ids.attach_system_record(jid, "college", pk=42, student_id="SFC0042",
                                 db_path=db_path)
        found = ids.find_journey_by_system_pk("college", 42, db_path=db_path)
        assert found is not None
        assert found["journey_id"] == jid
        assert found["college_student_id"] == "SFC0042"

    def test_attach_is_idempotent(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Eve", last_name="Polastri", date_of_birth="1985-04-04",
            current_system="university", db_path=db_path,
        )
        ids.attach_system_record(jid, "university", pk=7, student_id="C0000007",
                                 db_path=db_path)
        ids.attach_system_record(jid, "university", pk=7, student_id="C0000007",
                                 db_path=db_path)  # second call no-ops
        row = ids.get_journey(jid, db_path=db_path)
        assert row["university_pk"] == 7

    def test_conflicting_attach_raises(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Frank", last_name="Pembleton", date_of_birth="1970-03-03",
            current_system="college", db_path=db_path,
        )
        ids.attach_system_record(jid, "college", pk=11, db_path=db_path)
        with pytest.raises(ids.IdentityError):
            ids.attach_system_record(jid, "college", pk=12, db_path=db_path)

    def test_lookup_by_student_id(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Gina", last_name="Linetti", date_of_birth="1989-09-09",
            current_system="college", db_path=db_path,
        )
        ids.attach_system_record(jid, "college", pk=3, student_id="SFC0003",
                                 db_path=db_path)
        found = ids.find_journey_by_student_id("college", "SFC0003",
                                                db_path=db_path)
        assert found and found["journey_id"] == jid


class TestRecordTransition:
    def test_progression_updates_current_system(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Holly", last_name="Hunter", date_of_birth="2006-08-08",
            current_system="college", db_path=db_path,
        )
        ids.record_transition(
            jid, from_system="college", to_system="university",
            reason="progression", actor_user_id=1,
            notes="UCAS firm offer accepted", db_path=db_path,
        )
        row = ids.get_journey(jid, db_path=db_path)
        assert row["current_system"] == "university"
        transitions = ids.list_transitions(jid, db_path=db_path)
        assert [t["to_system"] for t in transitions] == ["college", "university"]

    def test_invalid_reason_rejected(self, db_path):
        jid = ids.get_or_create_journey(
            first_name="Ian", last_name="Malcolm", date_of_birth="1970-01-01",
            current_system="university", db_path=db_path,
        )
        with pytest.raises(ids.IdentityError):
            ids.record_transition(jid, from_system="university",
                                   to_system="alumni", reason="vibes",
                                   db_path=db_path)

    def test_unknown_journey_rejected(self, db_path):
        with pytest.raises(ids.IdentityError):
            ids.record_transition("nonexistent", from_system=None,
                                   to_system="college", reason="registration",
                                   db_path=db_path)


# ── Cross-system bus ─────────────────────────────────────────────────────

class TestPublishCrossSystem:
    def test_publish_writes_outbox_row(self, db_path):
        eid = bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system="college", source_module="test",
            journey_id="abc-123", db_path=db_path,
            extra="payload",
        )
        from education_system.shared.auth.db import connect
        conn = connect(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM cross_system_event_outbox WHERE event_id = ?",
                (eid,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["event_name"] == bus.EVENT_JOURNEY_REGISTERED
        assert row["source_system"] == "college"
        assert row["target_system"] is None  # broadcast
        assert "payload" in row["payload_json"]


class TestPollAndDispatch:
    def test_handler_invoked_with_envelope(self, db_path):
        seen: list[dict] = []
        bus.subscribe(bus.EVENT_JOURNEY_REGISTERED, seen.append,
                      handler_name="test.handler")
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system="college", source_module="test",
            journey_id="j1", target_system="university",
            db_path=db_path, foo=1,
        )
        n = bus.poll_and_dispatch("university", db_path=db_path)
        assert n == 1
        assert len(seen) == 1
        env = seen[0]
        assert env["event_name"] == bus.EVENT_JOURNEY_REGISTERED
        assert env["payload"] == {"foo": 1}
        assert env["journey_id"] == "j1"

    def test_event_dispatched_only_once_per_handler(self, db_path):
        seen: list[dict] = []
        bus.subscribe(bus.EVENT_JOURNEY_REGISTERED, seen.append,
                      handler_name="test.handler")
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system="college", source_module="test",
            target_system="university", db_path=db_path,
        )
        assert bus.poll_and_dispatch("university", db_path=db_path) == 1
        assert bus.poll_and_dispatch("university", db_path=db_path) == 0
        assert len(seen) == 1

    def test_target_system_filter(self, db_path):
        seen: list[dict] = []
        bus.subscribe(bus.EVENT_JOURNEY_REGISTERED, seen.append,
                      handler_name="t")
        # Targeted at university — college poller must not see it.
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system="x", source_module="t",
            target_system="university", db_path=db_path,
        )
        assert bus.poll_and_dispatch("college", db_path=db_path) == 0
        assert seen == []
        assert bus.poll_and_dispatch("university", db_path=db_path) == 1
        assert len(seen) == 1

    def test_broadcast_event_reaches_every_consumer(self, db_path):
        college_seen, uni_seen = [], []
        bus.subscribe(bus.EVENT_GDPR_REDACTION_REQUESTED,
                      college_seen.append, handler_name="college.h")
        bus.subscribe(bus.EVENT_GDPR_REDACTION_REQUESTED,
                      uni_seen.append, handler_name="uni.h")
        bus.publish_cross_system(
            bus.EVENT_GDPR_REDACTION_REQUESTED,
            source_system="shared", source_module="t",
            target_system=None, db_path=db_path,
        )
        # Each consumer system has both handlers registered in this
        # process, but in real life only its own handler would be
        # registered. Filter by name to mimic that.
        bus.clear_subscribers_for_test()
        bus.subscribe(bus.EVENT_GDPR_REDACTION_REQUESTED,
                      college_seen.append, handler_name="college.h")
        assert bus.poll_and_dispatch("college", db_path=db_path) == 1
        bus.clear_subscribers_for_test()
        bus.subscribe(bus.EVENT_GDPR_REDACTION_REQUESTED,
                      uni_seen.append, handler_name="uni.h")
        assert bus.poll_and_dispatch("university", db_path=db_path) == 1
        assert len(college_seen) == 1
        assert len(uni_seen) == 1

    def test_failed_handler_retried_until_max_attempts(self, db_path):
        calls = {"n": 0}

        def flaky(_env):
            calls["n"] += 1
            raise RuntimeError("boom")

        bus.subscribe(bus.EVENT_JOURNEY_REGISTERED, flaky,
                      handler_name="t.flaky")
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system="x", source_module="t",
            target_system="university", db_path=db_path,
        )
        for _ in range(10):
            bus.poll_and_dispatch("university", db_path=db_path,
                                   max_attempts=3)
        assert calls["n"] == 3  # exactly max_attempts

    def test_no_subscriber_no_dispatch(self, db_path):
        # No one subscribed — publish then poll yields nothing.
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system="x", source_module="t",
            target_system="university", db_path=db_path,
        )
        assert bus.poll_and_dispatch("university", db_path=db_path) == 0
