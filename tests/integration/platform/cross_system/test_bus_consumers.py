"""The shared bus consumers and the linked-platform services behind them.

Covers the event catalogue additions, ``list_events``, the webhook
forwarder (ids only, once per event), the notification handler (audiences,
preferences, idempotency, email), dead-letter alerts, the platform drainer,
calendar sync, transition message threads, the task list, admin alerts,
all-systems analytics and the cross-system role mapping.

Every database is a temp file. The dispatch db_path is carried to the
shared consumers through ``cross_system_bus.current_dispatch_db_path``, so
nothing here reaches the live auth.db, webhooks.db or calendar.
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from education_system.platform.cross_system import identity_service, transitions
from education_system.platform.cross_system import enrolment_schema
from education_system.platform.features.calendar import transition_sync
from education_system.platform.features.notifications import event_notifications
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.integrations.external import bus_drainer, cross_system_bus
from education_system.platform.integrations.webhooks import bus_forwarder

SUPERADMIN_SYSTEMS = ("university", "sixth_form", "secondary", "primary")


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    identity_service._initialised.discard(path)
    enrolment_schema._initialised.discard(path)
    cross_system_bus.clear_subscribers_for_test()
    # Registration flags are per process; start each test unregistered and
    # with no alert adapters left over from another test.
    bus_forwarder.reset_for_test()
    event_notifications.reset_for_test()
    transition_sync.reset_for_test()
    monkeypatch.setattr(cross_system_bus, "_delivery_alert_handlers", [])
    monkeypatch.setattr(bus_forwarder, "BACKGROUND_DELIVERY", False)
    yield path
    cross_system_bus.clear_subscribers_for_test()
    bus_forwarder.reset_for_test()
    event_notifications.reset_for_test()
    transition_sync.reset_for_test()


def _user(db, username, systems, email=None):
    conn = sqlite3.connect(db)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name, email, is_active) "
        "VALUES (?, 'x', ?, ?, 1)", (username, username, email))
    uid = cur.lastrowid
    for system, role in systems:
        conn.execute("INSERT INTO user_systems (user_id, system_key, role) "
                     "VALUES (?, ?, ?)", (uid, system, role))
    conn.commit()
    conn.close()
    return uid


def _notifications(db, user_ids):
    conn = sqlite3.connect(db)
    marks = ",".join("?" * len(user_ids))
    rows = conn.execute(
        f"SELECT recipient_user_id, title, message FROM cross_system_notifications "
        f"WHERE recipient_user_id IN ({marks}) ORDER BY id", list(user_ids)).fetchall()
    conn.close()
    return rows


def _journey(db, sid="SF100", system="sixth_form"):
    return identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2008-12-10",
        system=system, student_id=sid, db_path=db)


# ── Catalogue and list_events ────────────────────────────────────────────

def test_published_names_are_catalogued():
    assert "enrolment.changed" in cross_system_bus.KNOWN_EVENTS
    assert "post16.application.status_changed" in cross_system_bus.KNOWN_EVENTS


def test_list_events_filters_and_rolls_up_status(auth_db):
    ok_id = cross_system_bus.publish_cross_system(
        "place.offered", source_system="sixth_form", source_module="t",
        target_system="university", journey_id="J1", db_path=auth_db,
        transition_id="T1")
    bad_id = cross_system_bus.publish_cross_system(
        "application.submitted", source_system="secondary", source_module="t",
        target_system="university", journey_id="J2", db_path=auth_db)
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    later_id = cross_system_bus.publish_cross_system(
        "transition.reminder", source_system="secondary", source_module="t",
        target_system="university", available_at=future, db_path=auth_db)

    cross_system_bus.subscribe("place.offered", lambda env: None, handler_name="t.ok")

    def boom(env):
        raise RuntimeError("nope")

    cross_system_bus.subscribe("application.submitted", boom, handler_name="t.bad")
    cross_system_bus.poll_and_dispatch("university", max_attempts=1, db_path=auth_db)

    by_id = {e["event_id"]: e for e in cross_system_bus.list_events(db_path=auth_db)}
    assert by_id[ok_id]["delivery_status"] == "delivered"
    assert by_id[bad_id]["delivery_status"] == "dead_letter"
    assert by_id[later_id]["delivery_status"] == "scheduled"

    # CamelCase plan names resolve to the dotted names.
    offered = cross_system_bus.list_events(event_name="ProgressionAccepted",
                                           db_path=auth_db)
    assert offered == []  # ProgressionAccepted -> place.accepted, none published
    assert [e["event_id"] for e in cross_system_bus.list_events(
        transition_id="T1", db_path=auth_db)] == [ok_id]
    assert [e["event_id"] for e in cross_system_bus.list_events(
        status="dead_letter", db_path=auth_db)] == [bad_id]
    # Scoping by system: sixth_form sees only the event that names it.
    scoped = cross_system_bus.list_events(systems={"sixth_form"}, db_path=auth_db)
    assert [e["event_id"] for e in scoped] == [ok_id]
    assert "payload" not in cross_system_bus.list_events(
        include_payload=False, db_path=auth_db)[0]
    with pytest.raises(ValueError):
        cross_system_bus.list_events(status="bogus", db_path=auth_db)


# ── Webhook forwarder ────────────────────────────────────────────────────

def test_webhook_forwarder_sends_ids_only_once(auth_db):
    from education_system.platform.integrations.webhooks.webhook_service import (
        WebhookService,
    )
    wh_db = str(Path(auth_db).with_name("webhooks.db"))
    WebhookService(db_path=wh_db)
    conn = sqlite3.connect(wh_db)
    # Inserted directly: subscribe() would DNS-resolve the URL.
    conn.execute("INSERT INTO webhook_subscriptions (url, event_types, system_key, secret) "
                 "VALUES ('https://example.invalid/hook', '[\"place.offered\"]', "
                 "'sixth_form', 's3cret')")
    conn.execute("INSERT INTO webhook_subscriptions (url, event_types, system_key, secret) "
                 "VALUES ('https://example.invalid/other', '[\"place.offered\"]', "
                 "'primary', 's3cret')")
    conn.commit()
    conn.close()

    bus_forwarder.register_consumer()
    cross_system_bus.publish_cross_system(
        "place.offered", source_system="sixth_form", source_module="t",
        journey_id="J9", db_path=auth_db, target_system=None,
        transition_id="T9", first_name="Ada", status="offered",
        included=["send_needs"])
    # Broadcast: dispatched once per consumer system, forwarded once.
    cross_system_bus.poll_and_dispatch("sixth_form", db_path=auth_db)
    cross_system_bus.poll_and_dispatch("university", db_path=auth_db)

    conn = sqlite3.connect(wh_db)
    rows = conn.execute("SELECT event_type, payload, status FROM webhook_deliveries").fetchall()
    conn.close()
    # One delivery: the sixth-form subscription matches the event's source,
    # the primary one matches neither end, and the second dispatch of the
    # same broadcast event queued nothing new.
    assert len(rows) == 1
    body = json.loads(rows[0][1])
    assert body["event_name"] == "place.offered"
    assert body["journey_id"] == "J9"
    assert body["data"] == {"transition_id": "T9", "status": "offered"}
    assert "Ada" not in rows[0][1]
    assert "send_needs" not in rows[0][1]
    assert rows[0][2] == "pending"


def test_webhook_payload_builder_drops_nested_data():
    payload = bus_forwarder.build_webhook_payload({
        "event_id": "E", "event_name": "x", "payload": {
            "student_id": "S1", "journey_ids": ["J1", "J2"],
            "handover": {"medical": "…"}, "course_ids": [{"id": 1}],
            "last_name": "Hopper"}})
    assert payload["data"] == {"student_id": "S1", "journey_ids": ["J1", "J2"]}


# ── Notifications ────────────────────────────────────────────────────────

def test_application_notifies_receiving_admissions_staff_once(auth_db):
    uni_admin = _user(auth_db, "t_uni_admin", [("university", "admin")])
    uni_teacher = _user(auth_db, "t_uni_teacher", [("university", "teacher")])
    sf_admin = _user(auth_db, "t_sf_admin", [("sixth_form", "admin")])
    jid = _journey(auth_db)

    event_notifications.register_consumer()
    t = transitions.start_transition(journey_id=jid, source_system="sixth_form",
                                     destination_system="university", db_path=auth_db)
    transitions.record_application(t["transition_id"], application_reference="UCAS1",
                                   db_path=auth_db)
    cross_system_bus.poll_and_dispatch("university", db_path=auth_db)
    # The platform drainer sees the same event again; nothing is duplicated.
    bus_drainer.drain_platform_once(db_path=auth_db)

    got = _notifications(auth_db, [uni_admin, uni_teacher, sf_admin])
    assert [r[0] for r in got] == [uni_admin]
    assert "Sixth Form" in got[0][1] and "University" in got[0][1]
    assert t["transition_id"] in got[0][2]


def test_offer_reaches_sending_staff_learner_and_parent(auth_db):
    from education_system.platform.services.parent_child_link import (
        ParentChildLinkService,
        init_parent_links_db,
    )
    sf_staff = _user(auth_db, "t_sf_office", [("sixth_form", "staff")])
    learner = _user(auth_db, "SF100", [("sixth_form", "student")])
    parent = _user(auth_db, "t_parent", [("sixth_form", "parent")])
    init_parent_links_db(auth_db)
    ParentChildLinkService(auth_db).link_child(
        parent_user_id=parent, child_student_id="SF100", child_system_key="sixth_form")
    jid = _journey(auth_db)

    event_notifications.register_consumer()
    t = transitions.start_transition(journey_id=jid, source_system="sixth_form",
                                     destination_system="university", db_path=auth_db)
    transitions.offer_place(t["transition_id"], db_path=auth_db)
    cross_system_bus.poll_and_dispatch("university", db_path=auth_db)

    got = {r[0]: r for r in _notifications(auth_db, [sf_staff, learner, parent])}
    assert set(got) == {sf_staff, learner, parent}
    assert got[learner][1] == "You have been offered a place at University"
    # Personal notices carry no ids or workflow detail.
    assert got[parent][2] == "Sign in to see the details."


def test_preferences_can_switch_a_category_off(auth_db):
    from education_system.platform.features.notifications.preferences import (
        NotificationPreferences,
    )
    uni_admin = _user(auth_db, "t_uni_admin2", [("university", "admin")])
    NotificationPreferences(auth_db).set_preference(
        uni_admin, "applications", "in_app", False)
    jid = _journey(auth_db)
    event_notifications.register_consumer()
    t = transitions.start_transition(journey_id=jid, source_system="sixth_form",
                                     destination_system="university", db_path=auth_db)
    transitions.record_application(t["transition_id"], db_path=auth_db)
    cross_system_bus.poll_and_dispatch("university", db_path=auth_db)
    assert _notifications(auth_db, [uni_admin]) == []


def test_email_channel_sends_once(auth_db):
    from education_system.platform.features.notifications.preferences import (
        NotificationPreferences,
    )
    uni_admin = _user(auth_db, "t_uni_admin3", [("university", "admin")],
                      email="admissions@example.test")
    NotificationPreferences(auth_db).set_preference(uni_admin, "handover", "email", True)
    sent = []
    notifier = event_notifications.EventNotifier(
        auth_db, email_sender=lambda to, subject, body: sent.append((to, subject)))
    envelope = {"event_id": "E-1", "event_name": "handover.approved",
                "source_system": "sixth_form", "target_system": "university",
                "journey_id": None, "actor_user_id": None, "payload": {}}
    assert notifier.handle(envelope) >= 2  # in-app + email for this user
    notifier.handle(envelope)
    assert sent == [("admissions@example.test",
                     "Handover approved: Sixth Form College to University")]


def test_actor_is_not_notified_of_their_own_action(auth_db):
    uni_admin = _user(auth_db, "t_uni_admin4", [("university", "admin")])
    other = _user(auth_db, "t_uni_admin5", [("university", "admin")])
    notifier = event_notifications.EventNotifier(auth_db)
    envelope = {"event_id": "E-2", "event_name": "application.submitted",
                "source_system": "sixth_form", "target_system": "university",
                "journey_id": None, "actor_user_id": uni_admin, "payload": {}}
    # Asserted on the audience rather than a count: the dev seed puts its own
    # university admins into every fresh auth DB.
    recipients = notifier.recipients(envelope)
    assert uni_admin not in recipients
    assert other in recipients


# ── Dead letters ─────────────────────────────────────────────────────────

def test_dead_letter_alerts_superadmins(auth_db):
    boss = _user(auth_db, "t_boss", [(s, "admin") for s in SUPERADMIN_SYSTEMS])
    plain = _user(auth_db, "t_plain_admin", [("secondary", "admin")])
    event_notifications.register_delivery_alerts()

    def boom(env):
        raise RuntimeError("down")

    cross_system_bus.subscribe("learner.updated", boom, handler_name="t.always_fails")
    cross_system_bus.publish_cross_system(
        "learner.updated", source_system="secondary", source_module="t", db_path=auth_db)
    cross_system_bus.poll_and_dispatch("secondary", max_attempts=1, db_path=auth_db)

    got = _notifications(auth_db, [boss, plain])
    assert [r[0] for r in got] == [boss]
    assert "learner.updated" in got[0][1]

    # The admin alerts feed sees it too, read-only.
    from education_system.platform.delivery.portals.admin.admin_service import AdminService
    alerts = AdminService(db_paths={}, auth_db=auth_db).get_alerts()
    bus_alerts = [a for a in alerts if a["category"] == "bus"]
    assert len(bus_alerts) == 1 and bus_alerts[0]["action"] == "events"


# ── Calendar ─────────────────────────────────────────────────────────────

def test_calendar_mirrors_reminders_and_start_dates(auth_db):
    from education_system.platform.features.calendar.calendar_service import (
        CrossSystemCalendarService,
    )
    jid = _journey(auth_db, sid="Y11A", system="secondary")
    t = transitions.start_transition(journey_id=jid, source_system="secondary",
                                     destination_system="sixth_form", db_path=auth_db)
    tid = t["transition_id"]
    future = datetime.now(UTC) + timedelta(days=5)
    cross_system_bus.publish_cross_system(
        "transition.reminder", source_system="secondary", source_module="t",
        journey_id=jid, target_system="sixth_form", available_at=future.isoformat(),
        db_path=auth_db, transition_id=tid, destination_system="sixth_form")
    transitions.admit(tid, local_student_id="SF-9", start_date="2027-09-06",
                      db_path=auth_db)

    first = transition_sync.sync_transition_dates(db_path=auth_db)
    again = transition_sync.sync_transition_dates(db_path=auth_db)
    assert first == again == {"transitions": 1, "reminders": 1}

    cal = CrossSystemCalendarService(db_path=auth_db)
    effective = cal.get_sourced_events(f"transition:{tid}")
    assert len(effective) == 1 and effective[0]["event_date"] == "2027-09-06"
    reminders = cal.get_sourced_events("reminder:")
    assert len(reminders) == 1
    assert reminders[0]["event_date"] == future.date().isoformat()
    assert "Ada" not in json.dumps(effective + reminders)

    transitions.cancel(tid, reason="changed mind", db_path=auth_db)
    transition_sync.sync_transition(tid, db_path=auth_db)
    assert cal.get_sourced_events(f"transition:{tid}") == []


# ── Messaging ────────────────────────────────────────────────────────────

def test_transition_message_thread(auth_db):
    from education_system.platform.features.messaging.messaging_service import (
        InterSystemMessagingService,
        TransitionMessageError,
    )
    jid = _journey(auth_db)
    t = transitions.start_transition(journey_id=jid, source_system="sixth_form",
                                     destination_system="university", db_path=auth_db)
    svc = InterSystemMessagingService(db_path=auth_db)
    msg = svc.send_transition_message(
        t["transition_id"], sender_id=1, sender_system="sixth_form",
        subject="Access arrangements", body="Sent with the handover.")
    assert msg["recipient_system"] == "university"
    assert msg["recipient_scope"] == "institution"
    assert msg["student_id"] == jid and msg["student_name"] == ""
    svc.send_transition_message(
        t["transition_id"], sender_id=2, sender_system="university",
        recipient_id=1, subject="Re: access arrangements", body="Received.")

    thread = svc.list_by_transition(t["transition_id"])
    assert [m["sender_system"] for m in thread] == ["sixth_form", "university"]
    assert len(svc.get_institution_inbox("university")) == 1
    with pytest.raises(TransitionMessageError):
        svc.send_transition_message(t["transition_id"], sender_id=3,
                                    sender_system="primary", subject="x", body="y")


# ── Tasks, monitor, analytics ────────────────────────────────────────────

def test_task_list_scopes_by_permission(auth_db):
    from education_system.platform.features.calendar.cross_system_tasks import list_tasks
    jid = _journey(auth_db)
    t = transitions.start_transition(journey_id=jid, source_system="sixth_form",
                                     destination_system="university", db_path=auth_db)
    transitions.record_application(t["transition_id"], db_path=auth_db)  # uni must act

    everything = list_tasks(None, db_path=auth_db)
    assert any(x["kind"] == "transition" and x["system"] == "university"
               for x in everything)
    uni_admin = [{"system_key": "university", "role": "admin"}]
    assert any(x["kind"] == "transition" for x in list_tasks(uni_admin, db_path=auth_db))
    sf_teacher = [{"system_key": "sixth_form", "role": "teacher"}]
    assert not any(x["kind"] == "transition"
                   for x in list_tasks(sf_teacher, db_path=auth_db))


def test_transfer_monitor_never_returns_handover(auth_db):
    from education_system.platform.features.analytics import transfer_monitor as tm
    jid = _journey(auth_db)
    t = transitions.start_transition(journey_id=jid, source_system="sixth_form",
                                     destination_system="university", db_path=auth_db)
    tm.perform_action("approve", t["transition_id"],
                      handover={"medical_notes": "asthma"}, db_path=auth_db)
    row = tm.get_transition(t["transition_id"], db_path=auth_db)
    assert row["status"] == "handover_approved"
    assert row["has_handover"] is True and "handover_json" not in row
    detail = tm.transition_detail(t["transition_id"], db_path=auth_db)
    assert "asthma" not in json.dumps(detail, default=str)
    # ...and the bus never carried it.
    conn = sqlite3.connect(auth_db)
    blobs = [r[0] for r in conn.execute("SELECT payload_json FROM cross_system_event_outbox")]
    conn.close()
    assert not any("asthma" in b for b in blobs)


def test_all_systems_analytics_and_warehouse(auth_db):
    from education_system.paths import SYSTEM_ORDER
    from education_system.platform.features.analytics import journey_analytics
    from education_system.platform.features.analytics.warehouse import Warehouse
    jid = _journey(auth_db, sid="N1", system="nursery")
    t = transitions.start_transition(journey_id=jid, source_system="nursery",
                                     destination_system="primary", db_path=auth_db)
    transitions.complete(t["transition_id"], db_path=auth_db)

    flow = journey_analytics.cohort_flow_all_systems(db_path=auth_db)
    assert [s["system"] for s in flow["stage_presence"]] == list(SYSTEM_ORDER)
    nursery = next(s for s in flow["stage_presence"] if s["system"] == "nursery")
    assert nursery["reached"] == 1
    route = next(b for b in flow["boundaries"] if b["destination"] == "primary")
    assert route["completed"] == 1 and route["completion_rate"] == 100.0
    outcomes = journey_analytics.destination_outcomes(db_path=auth_db)
    assert outcomes["source"] in ("destinations", "transitions")

    wh = Warehouse(db_paths={}, auth_db=auth_db)
    funnel = wh.retention_funnel()
    assert set(SYSTEM_ORDER) <= set(funnel)  # used to KeyError on fe_college
    assert "sixth_form->university" in wh.progression_rates()


# ── Roles ────────────────────────────────────────────────────────────────

def test_apprenticeship_roles_and_capabilities(auth_db):
    from education_system.platform.identity.auth import role_manager as rm
    uid = _user(auth_db, "t_employer", [])
    manager = rm.RoleManager(auth_db)
    for role in ("apprentice", "employer", "end_point_assessor"):
        manager.grant_system_access(uid, "apprenticeships", role)  # used to raise
    assert rm.capability_for("apprenticeships", "end_point_assessor") == "external_assessor"
    assert rm.capability_for("apprenticeships", "staff") == "staff"
    assert rm.capability_for("secondary", "staff") == "manager"
    assert rm.capability_for("college", "parent") == "guardian"

    boss = [{"system_key": s, "role": "admin"} for s in SUPERADMIN_SYSTEMS]
    school_admin = [{"system_key": "school", "role": "admin"}]  # legacy key
    assert rm.has_cross_system_permission(boss, rm.PERM_IDENTITY_MERGE)
    assert not rm.has_cross_system_permission(school_admin, rm.PERM_IDENTITY_MERGE)
    assert rm.has_cross_system_permission(school_admin, rm.PERM_TRANSFER_APPROVE,
                                          "secondary")
    assert not rm.has_cross_system_permission(school_admin, rm.PERM_TRANSFER_APPROVE,
                                              "university")
    assert rm.cross_system_permissions(boss)[rm.PERM_EVENTS_VIEW] == ["*"]
