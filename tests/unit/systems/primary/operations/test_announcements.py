"""Announcements (domain.operations.communications.announcements)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.communications.announcements import (
    announcements as AN,
)

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _new(title="Sports day moved", **extra):
    return AN.create_announcement({"title": title, **extra})


# ── create / read ───────────────────────────────────────────────────

def test_empty_database():
    assert AN.list_announcements() == []
    assert AN.get_announcement(1) is None
    s = AN.summary()
    assert s.total == 0 and s.by_status == {} and s.total_views == 0


def test_create_applies_defaults():
    a = _new()
    assert a.title == "Sports day moved"
    assert a.category == "General"
    assert a.priority == 2
    assert a.priority_label == "Normal"
    assert a.status == "Draft"
    assert a.audiences == "students,staff"
    assert a.audience_list == ["students", "staff"]
    assert a.pinned is False and a.banner is False
    assert a.requires_acknowledgement is False and a.comments_enabled is False
    assert a.view_count == 0
    assert a.body is None and a.publish_on is None
    assert a.created_on == a.updated_on


def test_create_stores_every_field():
    a = _new("  KS2 SATs week  ", body=" Bring pencils ", summary="SATs",
             category="SATs & Assessments", priority="4", audiences="parents, staff",
             pinned=1, banner=True, author=" Mrs Head ", publish_on=_d(1),
             expires_on=_d(8), requires_acknowledgement=True, comments_enabled=True,
             view_count="3", attachments_ref="doc:12", linked_to="event:5",
             status="Scheduled", notes="n")
    got = AN.get_announcement(a.announcement_id)
    assert got == a
    assert a.title == "KS2 SATs week"
    assert a.body == "Bring pencils"
    assert a.author == "Mrs Head"
    assert a.category == "SATs & Assessments"
    assert a.priority == 4 and a.priority_label == "High"
    assert a.audience_list == ["parents", "staff"]
    assert a.pinned and a.banner and a.requires_acknowledgement and a.comments_enabled
    assert a.view_count == 3
    assert (a.publish_on, a.expires_on) == (_d(1), _d(8))
    assert a.attachments_ref == "doc:12" and a.linked_to == "event:5"


def test_audiences_accept_a_list():
    assert _new(audiences=["governors", "public"]).audiences == "governors,public"


def test_priority_label_helper():
    assert AN.priority_label(None) == "—"
    assert AN.priority_label(5) == "Urgent"
    assert AN.priority_label(1) == "Low"
    assert AN.priority_label(9) == "Unknown"


# ── validation ──────────────────────────────────────────────────────

def test_title_is_required():
    with pytest.raises(AN.ValidationError, match="Title is required"):
        _new("   ")


def test_category_must_be_a_primary_category():
    with pytest.raises(AN.ValidationError, match="Category must be one of"):
        _new(category="Sixth Form")


@pytest.mark.parametrize("priority", [6, -1, "high"])
def test_priority_must_be_1_to_5(priority):
    with pytest.raises(AN.ValidationError, match="Priority must be 1-5"):
        _new(priority=priority)


def test_status_must_be_known():
    with pytest.raises(AN.ValidationError, match="Status must be one of"):
        _new(status="Live")


@pytest.mark.parametrize("field,label", [("publish_on", "Publish on"),
                                         ("expires_on", "Expires on"),
                                         ("published_on", "Published on")])
def test_dates_must_be_iso(field, label):
    with pytest.raises(AN.ValidationError, match=f"{label} must be YYYY-MM-DD"):
        _new(**{field: "01/02/2026"})


def test_expiry_cannot_be_before_publish_date():
    with pytest.raises(AN.ValidationError, match="Expires on must be on or after"):
        _new(publish_on="2026-05-10", expires_on="2026-05-09")
    assert _new(publish_on="2026-05-10", expires_on="2026-05-10").expires_on == "2026-05-10"


def test_unknown_audience_is_refused():
    with pytest.raises(AN.ValidationError, match="Audience 'pupils' must be one of"):
        _new(audiences="students,pupils")


def test_empty_audience_list_is_refused():
    with pytest.raises(AN.ValidationError, match="At least one audience"):
        _new(audiences=" , ")
    with pytest.raises(AN.ValidationError, match="At least one audience"):
        _new(audiences=[])


def test_audience_of_wrong_type_is_refused():
    with pytest.raises(AN.ValidationError, match="list or comma-separated"):
        _new(audiences=42)


def test_view_count_must_be_a_non_negative_integer():
    with pytest.raises(AN.ValidationError, match="View count must be an integer"):
        _new(view_count="lots")
    with pytest.raises(AN.ValidationError, match="View count must be >= 0"):
        _new(view_count=-1)


# ── update / delete ─────────────────────────────────────────────────

def test_update_replaces_the_record():
    a = _new()
    b = AN.update_announcement(a.announcement_id, {"title": "Sports day cancelled",
                                                   "priority": 5, "category": "Sport"})
    assert b.title == "Sports day cancelled"
    assert b.priority == 5 and b.category == "Sport"
    assert b.created_on == a.created_on


def test_update_unknown_id_is_refused():
    with pytest.raises(AN.ValidationError, match="No announcement with id 99"):
        AN.update_announcement(99, {"title": "x"})


def test_delete():
    a = _new()
    assert AN.delete_announcement(a.announcement_id) is True
    assert AN.get_announcement(a.announcement_id) is None
    assert AN.delete_announcement(a.announcement_id) is False


# ── workflow ────────────────────────────────────────────────────────

def test_publish_sets_status_and_date():
    a = AN.publish(_new().announcement_id)
    assert a.status == "Published" and a.is_published
    assert a.published_on == TODAY.isoformat()
    b = AN.publish(_new("Other").announcement_id, published_on="2026-02-03")
    assert b.published_on == "2026-02-03"


def test_schedule_sets_publish_on_and_status():
    a = AN.schedule(_new().announcement_id, publish_on=_d(5))
    assert a.status == "Scheduled"
    assert a.publish_on == _d(5)
    assert a.is_scheduled_future is True


def test_schedule_refuses_a_bad_date():
    a = _new()
    with pytest.raises(AN.ValidationError, match="Publish on must be YYYY-MM-DD"):
        AN.schedule(a.announcement_id, publish_on="next week")


def test_withdraw_archive_expire_and_set_status():
    a = _new()
    assert AN.withdraw(a.announcement_id).status == "Withdrawn"
    assert AN.archive(a.announcement_id).status == "Archived"
    assert AN.expire(a.announcement_id).status == "Expired"
    assert AN.set_status(a.announcement_id, "Draft").status == "Draft"
    with pytest.raises(AN.ValidationError, match="Status must be one of"):
        AN.set_status(a.announcement_id, "Gone")


def test_toggles_flip_pin_and_banner():
    a = _new()
    assert AN.toggle_pin(a.announcement_id).pinned is True
    assert AN.toggle_pin(a.announcement_id).pinned is False
    assert AN.toggle_banner(a.announcement_id).banner is True


def test_increment_views_never_goes_backwards():
    a = _new()
    assert AN.increment_views(a.announcement_id).view_count == 1
    assert AN.increment_views(a.announcement_id, 4).view_count == 5
    assert AN.increment_views(a.announcement_id, -10).view_count == 5


@pytest.mark.parametrize("fn", [AN.publish, AN.withdraw, AN.archive, AN.expire,
                                AN.toggle_pin, AN.toggle_banner, AN.increment_views])
def test_workflow_on_missing_id_is_refused(fn):
    with pytest.raises(AN.ValidationError, match="No announcement with id 404"):
        fn(404)


def test_schedule_and_set_status_on_missing_id_are_refused():
    with pytest.raises(AN.ValidationError, match="No announcement"):
        AN.schedule(404, publish_on=_d(1))
    with pytest.raises(AN.ValidationError, match="No announcement"):
        AN.set_status(404, "Draft")


# ── live / expired properties ───────────────────────────────────────

def test_is_live_needs_published_and_inside_window():
    live = AN.publish(_new("live", publish_on=_d(-1), expires_on=_d(1)).announcement_id)
    future = AN.publish(_new("future", publish_on=_d(2)).announcement_id)
    past = AN.publish(_new("past", publish_on=_d(-9), expires_on=_d(-1)).announcement_id)
    draft = _new("draft")
    assert live.is_live is True
    assert future.is_live is False
    assert past.is_live is False and past.is_expired is True
    assert draft.is_live is False


def test_archived_is_never_reported_as_expired():
    a = AN.archive(_new(expires_on=_d(-3)).announcement_id)
    assert a.is_expired is False


def test_auto_expire_moves_only_published_past_expiry():
    gone = AN.publish(_new("gone", publish_on=_d(-5), expires_on=_d(-1)).announcement_id)
    today = AN.publish(_new("today", publish_on=_d(-5), expires_on=_d(0)).announcement_id)
    draft_old = _new("draft", publish_on=_d(-5), expires_on=_d(-1))
    assert AN.auto_expire() == 1
    assert AN.get_announcement(gone.announcement_id).status == "Expired"
    assert AN.get_announcement(today.announcement_id).status == "Published"
    assert AN.get_announcement(draft_old.announcement_id).status == "Draft"
    assert AN.auto_expire() == 0


# ── listing ─────────────────────────────────────────────────────────

def test_list_orders_pinned_then_priority_then_date():
    low = _new("low", priority=1, publish_on="2026-01-01")
    high_old = _new("high old", priority=4, publish_on="2026-01-01")
    high_new = _new("high new", priority=4, publish_on="2026-02-01")
    pinned_low = _new("pinned", priority=1, pinned=True, publish_on="2025-01-01")
    order = [a.title for a in AN.list_announcements()]
    assert order == [pinned_low.title, high_new.title, high_old.title, low.title]


def test_list_filters():
    a = AN.publish(_new("a", category="Sport", priority=3, audiences="parents",
                        author="Mr Bat", pinned=True, publish_on=_d(-1)).announcement_id)
    b = _new("b", category="KS1", priority=5, audiences="staff", banner=True)
    c = AN.schedule(_new("c", category="Sport", priority=1).announcement_id,
                    publish_on=_d(3))

    def titles(**kw):
        return {x.title for x in AN.list_announcements(**kw)}

    assert titles(category="Sport") == {"a", "c"}
    assert titles(status="Draft") == {"b"}
    assert titles(priority=5) == {"b"}
    assert titles(priority_min=3) == {"a", "b"}
    assert titles(audience="parents") == {"a"}
    assert titles(author_like="bat") == {"a"}
    assert titles(title_like="b") == {"b"}
    assert titles(published_only=True) == {"a"}
    assert titles(live_only=True) == {"a"}
    assert titles(pinned_only=True) == {"a"}
    assert titles(banner_only=True) == {"b"}
    assert titles(scheduled_only=True) == {"c"}
    assert c.title == "c"


def test_list_expired_unarchived_and_date_range():
    exp = AN.publish(_new("exp", publish_on="2026-01-01",
                          expires_on="2026-01-05").announcement_id)
    AN.withdraw(_new("withdrawn", publish_on="2026-01-01",
                     expires_on="2026-01-05").announcement_id)
    _new("feb", publish_on="2026-02-10")
    assert [a.title for a in AN.list_announcements(expired_unarchived=True)
            if a.expires_on < TODAY.isoformat()] == ["exp"]
    assert {a.title for a in AN.list_announcements(date_from="2026-02-01",
                                                   date_to="2026-02-28")} == {"feb"}
    assert exp.status == "Published"


def test_list_refuses_unknown_audience_and_bad_dates():
    with pytest.raises(AN.ValidationError, match="Audience must be one of"):
        AN.list_announcements(audience="aliens")
    with pytest.raises(AN.ValidationError, match="From must be YYYY-MM-DD"):
        AN.list_announcements(date_from="1/1/26")
    with pytest.raises(AN.ValidationError, match="To must be YYYY-MM-DD"):
        AN.list_announcements(date_to="soon")


# ── summary ─────────────────────────────────────────────────────────

def test_summary_counts():
    AN.publish(_new("live", priority=5, pinned=True, view_count=10,
                    audiences="students,parents", publish_on=_d(-1)).announcement_id)
    AN.publish(_new("stale", priority=4, view_count=2, category="Sport",
                    publish_on=_d(-9), expires_on=_d(-2)).announcement_id)
    AN.schedule(_new("soon", banner=True).announcement_id, publish_on=_d(4))
    _new("draft", audiences="staff")
    AN.archive(_new("old", expires_on=_d(-30)).announcement_id)

    s = AN.summary()
    assert s.total == 5
    assert s.drafts == 1
    assert s.scheduled == 1
    assert s.published == 2
    assert s.live_now == 1
    assert s.expired_unarchived == 1        # "stale" only; archived one skipped
    assert s.pinned == 1 and s.banners == 1
    assert s.urgent_count == 2              # priority 4 and 5
    assert s.total_views == 12
    assert s.by_category == {"General": 4, "Sport": 1}
    assert s.by_priority == {5: 1, 4: 1, 2: 3}
    assert s.by_status == {"Published": 2, "Scheduled": 1, "Draft": 1, "Archived": 1}
    assert s.by_audience == {"students": 4, "parents": 1, "staff": 4}
