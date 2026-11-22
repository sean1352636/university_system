"""Activity feed (domain.operations.communications.activity_feed)."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from education_system.systems.primary.domain.operations.communications.activity_feed import (
    activity_feed as AF,
)


def _ago(**delta) -> str:
    """A feed timestamp *delta* before now."""
    return (dt.datetime.now() - dt.timedelta(**delta)).replace(
        microsecond=0).isoformat(sep=" ")


def _log(action="create", summary="Pupil added", **extra):
    return AF.log(action, summary, **extra)


# ── empty feed ──────────────────────────────────────────────────────

def test_empty_feed_lists_nothing_and_summary_is_zero():
    assert AF.list_events() == []
    assert AF.recent() == []
    assert AF.get_event(1) is None
    s = AF.summary()
    assert s.total == 0
    assert s.last_24h == s.last_7d == s.last_30d == 0
    assert s.by_action == {}
    assert s.by_severity == {"info": 0, "audit": 0, "warning": 0, "error": 0}
    assert s.by_source == {src: 0 for src in AF.SOURCES}
    assert s.most_recent_ts is None


# ── logging ─────────────────────────────────────────────────────────

def test_log_stores_every_field_and_reads_back():
    e = _log("update", "  Changed class  ", actor=" admin3 ", actor_role="admin",
             entity_type="student", entity_id=1234567, severity="warning",
             source="gui", metadata={"field": "class_name"}, ip_address="10.0.0.1",
             ts="2026-03-02 09:15:00")
    got = AF.get_event(e.event_id)
    assert got == e
    assert got.action == "update"
    assert got.summary == "Changed class"
    assert got.actor == "admin3"
    assert got.actor_role == "admin"
    assert got.entity_type == "student"
    assert got.entity_id == "1234567"
    assert got.severity == "warning"
    assert got.source == "gui"
    assert got.ip_address == "10.0.0.1"
    assert got.ts == "2026-03-02 09:15:00"
    assert got.metadata_dict == {"field": "class_name"}


def test_defaults_are_audit_system_and_now():
    before = _ago(seconds=1)
    e = _log()
    assert e.severity == "audit"
    assert e.source == "system"
    assert e.ts >= before
    assert e.actor is None and e.entity_type is None and e.metadata is None


def test_blank_optional_text_is_stored_as_none():
    e = _log(actor="  ", entity_id="", ip_address=" ")
    assert e.actor is None and e.entity_id is None and e.ip_address is None


def test_create_event_accepts_a_payload_dict():
    e = AF.create_event({"action": "login", "summary": "Signed in", "actor": "t1"})
    assert (e.action, e.summary, e.actor) == ("login", "Signed in", "t1")


@pytest.mark.parametrize("ts", ["2026-01-05", "2026-01-05 10:30", "2026-01-05T10:30:15",
                                "2026-01-05 10:30:15.123", "2026-01-05T10:30:15Z"])
def test_iso_timestamps_are_accepted(ts):
    assert _log(ts=ts).ts == ts


# ── validation ──────────────────────────────────────────────────────

def test_action_is_required():
    with pytest.raises(AF.ValidationError, match="Action is required"):
        _log(action="  ")


def test_summary_is_required():
    with pytest.raises(AF.ValidationError, match="Summary is required"):
        _log(summary="")


def test_unknown_severity_is_refused():
    with pytest.raises(AF.ValidationError, match="Severity must be one of"):
        _log(severity="critical")


def test_unknown_source_is_refused():
    with pytest.raises(AF.ValidationError, match="Source must be one of"):
        _log(source="email")


@pytest.mark.parametrize("ts", ["05/01/2026", "2026-1-5", "yesterday"])
def test_non_iso_timestamp_is_refused(ts):
    with pytest.raises(AF.ValidationError, match="ISO-8601"):
        _log(ts=ts)


def test_metadata_string_that_looks_like_json_must_parse():
    with pytest.raises(AF.ValidationError, match="not valid JSON"):
        _log(metadata="{not json")


def test_metadata_plain_text_and_json_string_are_kept():
    plain = _log(metadata="free text note")
    assert plain.metadata == "free text note"
    assert plain.metadata_dict is None
    js = _log(metadata=' {"a": 1} ')
    assert js.metadata == '{"a": 1}'
    assert js.metadata_dict == {"a": 1}


def test_metadata_non_dict_objects_are_serialised():
    e = _log(metadata=[1, dt.date(2026, 1, 2)])
    assert json.loads(e.metadata) == [1, "2026-01-02"]


def test_nothing_is_stored_when_validation_fails():
    with pytest.raises(AF.ValidationError):
        _log(severity="nope")
    assert AF.list_events() == []


# ── listing and filters ─────────────────────────────────────────────

def _seed():
    a = _log("create", "Pupil Ada added", actor="admin3", actor_role="admin",
             entity_type="student", entity_id="P1", ts="2026-01-10 09:00:00")
    b = _log("update", "Pupil Ada moved class", actor="teacher1", actor_role="teacher",
             entity_type="student", entity_id="P1", severity="info", source="gui",
             ts="2026-01-11 09:00:00")
    c = _log("login_failed", "Bad password", actor="teacher1", severity="warning",
             source="cli", ts="2026-01-12 09:00:00")
    d = _log("delete", "Homework removed", actor="admin3", entity_type="homework",
             entity_id="H9", severity="error", source="api", ts="2026-01-13 09:00:00")
    return a, b, c, d


def test_list_is_newest_first():
    a, b, c, d = _seed()
    assert [e.event_id for e in AF.list_events()] == [d.event_id, c.event_id,
                                                       b.event_id, a.event_id]


def test_same_timestamp_ties_break_on_newest_id():
    x = _log(ts="2026-02-01 08:00:00")
    y = _log(ts="2026-02-01 08:00:00")
    assert [e.event_id for e in AF.list_events()] == [y.event_id, x.event_id]


def test_filters_each_narrow_the_list():
    a, b, c, d = _seed()

    def ids(**kw):
        return {e.event_id for e in AF.list_events(**kw)}

    assert ids(actor="admin3") == {a.event_id, d.event_id}
    assert ids(actor_role="teacher") == {b.event_id}
    assert ids(action="login_failed") == {c.event_id}
    assert ids(entity_type="student") == {a.event_id, b.event_id}
    assert ids(entity_id="H9") == {d.event_id}
    assert ids(severity="warning") == {c.event_id}
    assert ids(source="api") == {d.event_id}
    assert ids(summary_like="Ada") == {a.event_id, b.event_id}
    assert ids(date_from="2026-01-12") == {c.event_id, d.event_id}
    assert ids(date_to="2026-01-11 23:59:59") == {a.event_id, b.event_id}
    assert ids(actor="teacher1", severity="info") == {b.event_id}


def test_filter_with_unknown_severity_or_source_is_refused():
    with pytest.raises(AF.ValidationError, match="Severity"):
        AF.list_events(severity="fatal")
    with pytest.raises(AF.ValidationError, match="Source"):
        AF.list_events(source="fax")


def test_limit_caps_rows_and_is_bounded():
    for i in range(5):
        _log(summary=f"e{i}", ts=f"2026-01-0{i + 1}")
    assert [e.summary for e in AF.list_events(limit=2)] == ["e4", "e3"]
    assert len(AF.recent(3)) == 3
    assert len(AF.list_events(limit=0)) == 5         # 0 → no limit
    with pytest.raises(AF.ValidationError, match="1..10000"):
        AF.list_events(limit=10001)


def test_events_for_entity_and_actor():
    a, b, c, d = _seed()
    assert [e.event_id for e in AF.events_for_entity("student", "P1")] == [b.event_id,
                                                                            a.event_id]
    assert [e.event_id for e in AF.events_for_actor("teacher1")] == [c.event_id, b.event_id]
    assert AF.events_for_entity("student", "nobody") == []


# ── deleting and purging ────────────────────────────────────────────

def test_delete_event_removes_one_row():
    a, b, *_ = _seed()
    assert AF.delete_event(a.event_id) is True
    assert AF.get_event(a.event_id) is None
    assert AF.get_event(b.event_id) is not None
    assert AF.delete_event(a.event_id) is False
    assert AF.delete_event(99999) is False


def test_purge_removes_only_events_older_than_cutoff():
    old = _log(summary="old", ts=_ago(days=40))
    edge = _log(summary="recent", ts=_ago(days=10))
    new = _log(summary="new")
    assert AF.purge(older_than_days=30) == 1
    remaining = {e.event_id for e in AF.list_events()}
    assert remaining == {edge.event_id, new.event_id}
    assert old.event_id not in remaining
    assert AF.purge(older_than_days=30) == 0


@pytest.mark.parametrize("days", [0, -5])
def test_purge_needs_positive_days(days):
    with pytest.raises(AF.ValidationError, match="must be positive"):
        AF.purge(older_than_days=days)


# ── summary ─────────────────────────────────────────────────────────

def test_summary_counts_windows_and_groups():
    _log("login", "in", actor="admin3", source="gui", ts=_ago(hours=1))
    _log("login", "in", actor="admin3", source="gui", ts=_ago(days=3))
    _log("create", "made", actor="teacher1", entity_type="student", ts=_ago(days=20))
    _log("delete", "gone", actor="admin3", entity_type="student", severity="error",
         ts=_ago(days=60))
    _log("system", "boot", severity="info", ts=_ago(days=90))

    s = AF.summary()
    assert s.total == 5
    assert s.last_24h == 1
    assert s.last_7d == 2
    assert s.last_30d == 3
    assert s.by_action == {"login": 2, "create": 1, "delete": 1, "system": 1}
    assert list(s.by_action)[0] == "login"          # most frequent first
    assert s.by_severity == {"info": 1, "audit": 3, "warning": 0, "error": 1}
    assert s.by_source["gui"] == 2 and s.by_source["system"] == 3
    assert s.by_actor == {"admin3": 3, "teacher1": 1}
    assert s.by_entity_type == {"student": 2}
    assert s.most_recent_ts == max(e.ts for e in AF.list_events())


def test_summary_top_actors_is_capped_at_ten():
    for i in range(12):
        for _ in range(i + 1):
            _log(actor=f"user{i:02d}")
    s = AF.summary()
    assert len(s.by_actor) == 10
    assert list(s.by_actor)[0] == "user11"
    assert "user00" not in s.by_actor and "user01" not in s.by_actor
