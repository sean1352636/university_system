"""Notifications (domain.operations.communications.notifications)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.communications.notifications import (
    notifications as NT,
)

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _new(title="Reading book due", recipient_id="P1", **extra):
    return NT.create_notification({"recipient_id": recipient_id, "title": title, **extra})


# ── create / read ───────────────────────────────────────────────────

def test_empty_database():
    assert NT.list_notifications() == []
    assert NT.get_notification(1) is None
    assert NT.unread_count_for("Student", "P1") == 0
    assert NT.summary().total == 0


def test_create_applies_defaults():
    n = _new()
    assert n.recipient_type == "Student"
    assert n.notification_type == "Info"
    assert n.channel == "In-App"
    assert n.priority == 2 and n.priority_label == "Normal"
    assert n.status == "Draft"
    assert n.requires_action is False and n.action_completed is False
    assert n.is_pending is True and n.is_active is False and n.is_read is False


def test_create_stores_every_field():
    n = _new("  Consent form  ", recipient_id=" P7 ", recipient_type="Parent",
             recipient_name=" Mrs Smith ", body=" Please sign ",
             notification_type="Action Required", priority="5", channel="Email",
             icon="pen", url="/forms/1", linked_to="trip:3", requires_action=1,
             action_label="Sign", action_url="/sign", sent_by="admin3",
             scheduled_for="2026-03-01T09:00", sent_at="2026-03-01T09:00:00",
             expires_on="2026-03-10", status="Sent", notes="n")
    got = NT.get_notification(n.notification_id)
    assert got == n
    assert n.title == "Consent form" and n.recipient_id == "P7"
    assert n.recipient_name == "Mrs Smith" and n.body == "Please sign"
    assert (n.recipient_type, n.notification_type, n.channel) == (
        "Parent", "Action Required", "Email")
    assert n.priority == 5 and n.priority_label == "Urgent"
    assert n.requires_action is True
    assert n.needs_action is True
    assert n.scheduled_for == "2026-03-01T09:00"


def test_priority_label_helper():
    assert NT.priority_label(None) == "—"
    assert NT.priority_label(3) == "Important"
    assert NT.priority_label(0) == "Unknown"


# ── validation ──────────────────────────────────────────────────────

def test_recipient_id_and_title_required():
    with pytest.raises(NT.ValidationError, match="Recipient id is required"):
        _new(recipient_id="  ")
    with pytest.raises(NT.ValidationError, match="Title is required"):
        _new(title="")


@pytest.mark.parametrize("field,value,msg", [
    ("recipient_type", "Alumni", "Recipient type must be one of"),
    ("notification_type", "Spam", "Notification type must be one of"),
    ("channel", "Pager", "Channel must be one of"),
    ("status", "Opened", "Status must be one of"),
    ("priority", 7, "Priority must be 1-5"),
    ("priority", "urgent", "Priority must be 1-5"),
])
def test_allowed_values(field, value, msg):
    with pytest.raises(NT.ValidationError, match=msg):
        _new(**{field: value})


@pytest.mark.parametrize("field,label", [
    ("scheduled_for", "Scheduled for"), ("sent_at", "Sent at"),
    ("delivered_at", "Delivered at"), ("read_at", "Read at"),
    ("acknowledged_at", "Acknowledged at"), ("dismissed_at", "Dismissed at"),
])
def test_timestamps_must_be_iso(field, label):
    with pytest.raises(NT.ValidationError, match=f"{label} must be YYYY-MM-DD"):
        _new(**{field: "next Tuesday"})


def test_expiry_must_be_a_date():
    with pytest.raises(NT.ValidationError, match="Expires on must be YYYY-MM-DD"):
        _new(expires_on="10/03/2026")


# ── update / delete ─────────────────────────────────────────────────

def test_update_and_delete():
    n = _new()
    u = NT.update_notification(n.notification_id, {"recipient_id": "P2", "title": "New",
                                                   "priority": 4})
    assert (u.recipient_id, u.title, u.priority) == ("P2", "New", 4)
    assert NT.delete_notification(n.notification_id) is True
    assert NT.get_notification(n.notification_id) is None
    assert NT.delete_notification(n.notification_id) is False
    with pytest.raises(NT.ValidationError, match="No notification with id 9"):
        NT.update_notification(9, {"recipient_id": "x", "title": "y"})


# ── lifecycle ───────────────────────────────────────────────────────

def test_schedule():
    n = NT.schedule(_new().notification_id, scheduled_for="2026-05-01T08:30")
    assert n.status == "Scheduled" and n.scheduled_for == "2026-05-01T08:30"
    assert n.is_pending is True
    with pytest.raises(NT.ValidationError, match="Scheduled for must be"):
        NT.schedule(n.notification_id, scheduled_for="soon")


def test_sent_delivered_read_acknowledged():
    n = _new()
    s = NT.mark_sent(n.notification_id, sent_at="2026-05-01T08:00:00")
    assert s.status == "Sent" and s.sent_at == "2026-05-01T08:00:00" and s.is_active
    d = NT.mark_delivered(n.notification_id, delivered_at="2026-05-01T08:01:00")
    assert d.status == "Delivered" and d.delivered_at == "2026-05-01T08:01:00"
    r = NT.mark_read(n.notification_id, read_at="2026-05-01T09:00:00")
    assert r.status == "Read" and r.is_read
    a = NT.acknowledge(n.notification_id, ack_at="2026-05-01T10:00:00")
    assert a.status == "Acknowledged"
    assert a.acknowledged_at == "2026-05-01T10:00:00"
    assert a.read_at == "2026-05-01T09:00:00"        # first read kept


def test_lifecycle_defaults_stamp_now():
    n = _new()
    before = dt.datetime.now().replace(microsecond=0).isoformat()
    s = NT.mark_sent(n.notification_id)
    assert s.sent_at >= before
    assert NT.dismiss(n.notification_id).dismissed_at >= before


def test_delivered_and_read_do_not_change_other_statuses():
    n = _new()                                   # Draft
    d = NT.mark_delivered(n.notification_id, delivered_at="2026-05-01")
    assert d.status == "Draft" and d.delivered_at == "2026-05-01"
    r = NT.mark_read(n.notification_id, read_at="2026-05-02")
    assert r.status == "Draft" and r.read_at == "2026-05-02"


def test_acknowledge_unread_stamps_read_too():
    n = NT.mark_sent(_new().notification_id)
    a = NT.acknowledge(n.notification_id, ack_at="2026-05-03T12:00:00")
    assert a.read_at == "2026-05-03T12:00:00"


def test_dismiss_fail_action_and_set_status():
    n = _new(requires_action=True)
    NT.mark_sent(n.notification_id)
    assert NT.get_notification(n.notification_id).needs_action is True
    done = NT.mark_action_completed(n.notification_id)
    assert done.action_completed is True and done.needs_action is False
    assert NT.dismiss(n.notification_id, dismissed_at="2026-05-04").status == "Dismissed"
    assert NT.mark_failed(n.notification_id).status == "Failed"
    assert NT.set_status(n.notification_id, "Expired").status == "Expired"
    with pytest.raises(NT.ValidationError, match="Status must be one of"):
        NT.set_status(n.notification_id, "Lost")


@pytest.mark.parametrize("fn", [NT.mark_sent, NT.mark_delivered, NT.mark_read,
                                NT.acknowledge, NT.dismiss, NT.mark_action_completed,
                                NT.mark_failed])
def test_lifecycle_on_missing_id_is_refused(fn):
    with pytest.raises(NT.ValidationError, match="No notification with id 404"):
        fn(404)


def test_schedule_and_set_status_on_missing_id_are_refused():
    with pytest.raises(NT.ValidationError, match="No notification"):
        NT.schedule(404, scheduled_for="2026-01-01")
    with pytest.raises(NT.ValidationError, match="No notification"):
        NT.set_status(404, "Sent")


def test_is_expired_property():
    assert _new(expires_on=_d(-1)).is_expired is True
    assert _new(expires_on=_d(0)).is_expired is False
    assert _new().is_expired is False


def test_auto_expire_skips_finished_states():
    old_sent = NT.mark_sent(_new("a", expires_on=_d(-2)).notification_id)
    old_draft = _new("b", expires_on=_d(-2))
    old_ack = NT.acknowledge(_new("c", expires_on=_d(-2)).notification_id)
    old_dismissed = NT.dismiss(_new("d", expires_on=_d(-2)).notification_id)
    fresh = NT.mark_sent(_new("e", expires_on=_d(1)).notification_id)
    assert NT.auto_expire() == 2
    status = {n.title: n.status for n in NT.list_notifications()}
    assert status == {"a": "Expired", "b": "Expired", "c": "Acknowledged",
                      "d": "Dismissed", "e": "Sent"}
    assert NT.auto_expire() == 0
    assert (old_sent.title, old_draft.title, old_ack.title, old_dismissed.title,
            fresh.title) == ("a", "b", "c", "d", "e")


# ── listing ─────────────────────────────────────────────────────────

def test_list_orders_by_priority_then_newest():
    low = _new("low", priority=1)
    hi_old = _new("hi old", priority=4, sent_at="2026-01-01")
    hi_new = _new("hi new", priority=4, sent_at="2026-02-01")
    assert [n.title for n in NT.list_notifications()] == [hi_new.title, hi_old.title,
                                                          low.title]


def test_list_filters():
    a = NT.mark_sent(_new("a", recipient_type="Parent", recipient_id="M1", priority=5,
                          notification_type="Alert", channel="SMS", sent_by="office",
                          requires_action=True).notification_id,
                     sent_at="2026-03-05")
    b = NT.mark_read(NT.mark_sent(_new("b", recipient_id="P1").notification_id,
                                  sent_at="2026-03-10").notification_id)
    c = _new("c", recipient_type="Staff", recipient_id="T1", priority=3)

    def titles(**kw):
        return {n.title for n in NT.list_notifications(**kw)}

    assert titles(recipient_type="Parent") == {"a"}
    assert titles(recipient_id="P1") == {"b"}
    assert titles(notification_type="Alert") == {"a"}
    assert titles(channel="SMS") == {"a"}
    assert titles(status="Draft") == {"c"}
    assert titles(priority=3) == {"c"}
    assert titles(priority_min=3) == {"a", "c"}
    assert titles(unread_only=True) == {"a"}
    assert titles(needs_action_only=True) == {"a"}
    assert titles(urgent_only=True) == {"a"}
    assert titles(pending_only=True) == {"c"}
    assert titles(sent_by_like="off") == {"a"}
    assert titles(title_like="b") == {"b"}
    assert titles(date_from="2026-03-06", date_to="2026-03-31") == {"b"}
    assert (a.title, b.title, c.title) == ("a", "b", "c")


def test_list_refuses_bad_date_filters():
    with pytest.raises(NT.ValidationError, match="From must be YYYY-MM-DD"):
        NT.list_notifications(date_from="x")
    with pytest.raises(NT.ValidationError, match="To must be YYYY-MM-DD"):
        NT.list_notifications(date_to="y")


def test_notifications_for_and_unread_count():
    NT.mark_sent(_new("one", recipient_id="P1").notification_id)
    NT.mark_sent(_new("two", recipient_id="P1").notification_id)
    NT.mark_read(NT.mark_sent(_new("three", recipient_id="P1").notification_id)
                 .notification_id)
    _new("draft", recipient_id="P1")
    NT.mark_sent(_new("other", recipient_id="P2").notification_id)
    assert {n.title for n in NT.notifications_for("Student", "P1")} == {
        "one", "two", "three", "draft"}
    assert NT.unread_count_for("Student", "P1") == 2
    assert NT.unread_count_for("Parent", "P1") == 0


# ── broadcast ───────────────────────────────────────────────────────

def test_broadcast_creates_one_row_per_recipient():
    rows = NT.broadcast(recipients=[("Parent", "M1", "Mrs A"), ("Parent", "M2", None),
                                    ("Staff", "T1", "Mr C")],
                        title="Snow closure", body="School closed", priority=5,
                        notification_type="Alert", channel="SMS", sent_by="head",
                        status="Sent", expires_on="2026-12-01", linked_to="closure:1")
    assert len(rows) == 3
    assert [(n.recipient_type, n.recipient_id, n.recipient_name) for n in rows] == [
        ("Parent", "M1", "Mrs A"), ("Parent", "M2", None), ("Staff", "T1", "Mr C")]
    assert all(n.title == "Snow closure" and n.priority == 5 and n.status == "Sent"
               and n.channel == "SMS" and n.linked_to == "closure:1" for n in rows)
    assert NT.broadcast(recipients=[], title="nobody") == []


def test_broadcast_stops_on_an_invalid_recipient():
    with pytest.raises(NT.ValidationError, match="Recipient type must be one of"):
        NT.broadcast(recipients=[("Parent", "M1", None), ("Martian", "X", None)],
                     title="t")
    assert [n.recipient_id for n in NT.list_notifications()] == ["M1"]


# ── summary ─────────────────────────────────────────────────────────

def test_summary_counts():
    NT.mark_sent(_new("urgent unread", priority=5, requires_action=True).notification_id)
    NT.mark_read(NT.mark_sent(_new("read", recipient_id="P2",
                                   channel="Email").notification_id).notification_id)
    NT.schedule(_new("sched", recipient_type="Staff", recipient_id="T1").notification_id,
                scheduled_for="2026-12-01")
    _new("draft old", expires_on=_d(-3), notification_type="Reminder")
    NT.dismiss(_new("dismissed old", expires_on=_d(-3)).notification_id)

    s = NT.summary()
    assert s.total == 5
    assert s.unread == 1
    assert s.pending == 2
    assert s.scheduled == 1
    assert s.sent == 2
    assert s.needs_action == 1
    assert s.urgent_unread == 1
    assert s.expired_unprocessed == 1
    assert s.distinct_recipients == 3               # (Student,P1) (Student,P2) (Staff,T1)
    assert s.by_type == {"Info": 4, "Reminder": 1}
    assert s.by_priority == {5: 1, 2: 4}
    assert s.by_channel == {"In-App": 4, "Email": 1}
    assert s.by_status == {"Sent": 1, "Read": 1, "Scheduled": 1, "Draft": 1,
                           "Dismissed": 1}
    assert s.by_recipient_type == {"Student": 4, "Staff": 1}
