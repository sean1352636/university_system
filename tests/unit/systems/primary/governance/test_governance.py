"""Governors and governance meetings (domain.governance.governance)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.governance import governance as G

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _gov(name="Jane Chair", **extra):
    return G.create_governor({"full_name": name, **extra})


def _meet(title="Autumn FGB", date="2026-10-01", **extra):
    return G.create_meeting({"title": title, "meeting_date": date, **extra})


# ── governors: create / read ──

def test_create_governor_defaults_role_and_status():
    g = _gov("  Jane Smith  ")
    assert g.full_name == "Jane Smith"
    assert g.role == G.DEFAULT_GOVERNOR_ROLE == "Trustee"
    assert g.status == G.DEFAULT_GOVERNOR_STATUS == "Active"
    assert g.email is None and g.term_start is None and g.notes is None
    assert G.get_governor(g.governor_id) == g


def test_create_governor_stores_every_field():
    g = _gov("Ann Parent", role="Parent governor", email=" ann@x.org ",
             phone="0123", term_start="2025-09-01", term_end="2029-08-31",
             status="On leave", notes="  maternity ")
    assert (g.role, g.email, g.phone) == ("Parent governor", "ann@x.org", "0123")
    assert (g.term_start, g.term_end) == ("2025-09-01", "2029-08-31")
    assert (g.status, g.notes) == ("On leave", "maternity")


def test_get_missing_governor_is_none():
    assert G.get_governor(999) is None


# ── governors: validation ──

def test_governor_name_required():
    with pytest.raises(G.ValidationError, match="Full name is required"):
        G.create_governor({"full_name": "   "})


def test_governor_name_max_length():
    with pytest.raises(G.ValidationError, match="100 chars"):
        _gov("x" * 101)
    assert _gov("x" * 100).full_name == "x" * 100


def test_governor_role_must_be_known():
    with pytest.raises(G.ValidationError, match="Role must be one of"):
        _gov(role="Head boy")


def test_governor_status_must_be_known():
    with pytest.raises(G.ValidationError, match="Status must be one of"):
        _gov(status="Retired")


def test_governor_term_dates_must_be_iso():
    with pytest.raises(G.ValidationError, match="Term start must be YYYY-MM-DD"):
        _gov(term_start="01/09/2025")
    with pytest.raises(G.ValidationError, match="Term end must be YYYY-MM-DD"):
        _gov(term_end="2025-9-1")


def test_governor_term_start_not_after_end():
    with pytest.raises(G.ValidationError, match="Term start cannot be after term end"):
        _gov(term_start="2026-09-01", term_end="2026-08-31")
    g = _gov(term_start="2026-09-01", term_end="2026-09-01")
    assert g.term_start == g.term_end


def test_governor_notes_max_length():
    with pytest.raises(G.ValidationError, match="Notes must be 1000"):
        _gov(notes="n" * 1001)


# ── governors: list / filter ──

def test_list_governors_empty():
    assert G.list_governors() == []


def test_list_governors_sorted_by_status_role_name():
    _gov("Zed", role="Trustee")
    _gov("Amy", role="Trustee")
    _gov("Bob", role="Chair")
    _gov("Cat", role="Chair", status="Resigned")
    names = [g.full_name for g in G.list_governors()]
    assert names == ["Bob", "Amy", "Zed", "Cat"]


def test_list_governors_filters():
    _gov("Amy Chair", role="Chair", email="amy@school.org")
    _gov("Bob Staff", role="Staff governor", status="Ended", notes="left in July")
    assert [g.full_name for g in G.list_governors(role="Chair")] == ["Amy Chair"]
    assert [g.full_name for g in G.list_governors(status="Ended")] == ["Bob Staff"]
    assert [g.full_name for g in G.list_governors(query="school.org")] == ["Amy Chair"]
    assert [g.full_name for g in G.list_governors(query="July")] == ["Bob Staff"]
    assert G.list_governors(status="Active", role="Staff governor") == []


def test_list_governors_rejects_unknown_filter_values():
    with pytest.raises(G.ValidationError):
        G.list_governors(status="Gone")
    with pytest.raises(G.ValidationError):
        G.list_governors(role="Mayor")


# ── governors: update / delete ──

def test_update_governor_partial_keeps_other_fields():
    g = _gov("Jane", role="Chair", email="j@x.org")
    out = G.update_governor(g.governor_id, {"status": "Resigned"})
    assert out.status == "Resigned"
    assert out.role == "Chair" and out.email == "j@x.org" and out.full_name == "Jane"


def test_update_governor_empty_payload_is_noop():
    g = _gov()
    assert G.update_governor(g.governor_id, {}) == g


def test_update_governor_validates():
    g = _gov()
    with pytest.raises(G.ValidationError, match="Full name is required"):
        G.update_governor(g.governor_id, {"full_name": ""})
    with pytest.raises(G.ValidationError, match="Role must be one of"):
        G.update_governor(g.governor_id, {"role": "Boss"})


def test_update_missing_governor_refused():
    with pytest.raises(G.ValidationError, match="No governor #42"):
        G.update_governor(42, {"status": "Ended"})


def test_delete_governor():
    g = _gov()
    assert G.delete_governor(g.governor_id) is True
    assert G.get_governor(g.governor_id) is None
    assert G.delete_governor(g.governor_id) is False


def test_delete_governor_keeps_meetings():
    g = _gov()
    m = _meet(attendees=7)
    G.delete_governor(g.governor_id)
    assert G.get_meeting(m.meeting_id).attendees == 7


# ── meetings: create / validation ──

def test_create_meeting_defaults():
    m = _meet("  Spring FGB ")
    assert m.title == "Spring FGB"
    assert m.kind == "Full board" and m.status == "Scheduled"
    assert m.attendees == 0
    assert m.chair is None and m.minutes_ref is None and m.decisions is None
    assert G.get_meeting(m.meeting_id) == m


def test_create_meeting_all_fields():
    m = _meet(kind="Committee", chair=" Mrs Chair ", attendees="9",
              minutes_ref="MIN-1", decisions="Approve budget", status="Held")
    assert (m.kind, m.chair, m.attendees) == ("Committee", "Mrs Chair", 9)
    assert (m.minutes_ref, m.decisions, m.status) == ("MIN-1", "Approve budget", "Held")


def test_meeting_date_required_and_iso():
    with pytest.raises(G.ValidationError, match="Meeting date is required"):
        G.create_meeting({"title": "x"})
    with pytest.raises(G.ValidationError, match="Meeting date must be YYYY-MM-DD"):
        _meet(date="1 Oct 2026")


def test_meeting_title_required_and_length():
    with pytest.raises(G.ValidationError, match="Title is required"):
        _meet(title=" ")
    with pytest.raises(G.ValidationError, match="200 chars"):
        _meet(title="t" * 201)


def test_meeting_kind_and_status_must_be_known():
    with pytest.raises(G.ValidationError, match="Kind must be one of"):
        _meet(kind="Party")
    with pytest.raises(G.ValidationError, match="Status must be one of"):
        _meet(status="Postponed")


def test_meeting_attendees_rules():
    with pytest.raises(G.ValidationError, match="whole number"):
        _meet(attendees="lots")
    with pytest.raises(G.ValidationError, match="0..1000"):
        _meet(attendees=-1)
    with pytest.raises(G.ValidationError, match="0..1000"):
        _meet(attendees=1001)
    assert _meet(title="blank", attendees="").attendees == 0
    assert _meet(title="max", attendees=1000).attendees == 1000


def test_meeting_decisions_max_length():
    with pytest.raises(G.ValidationError, match="4000"):
        _meet(decisions="d" * 4001)


# ── meetings: list / filter ──

def test_list_meetings_newest_first():
    a = _meet("A", "2026-01-10")
    b = _meet("B", "2026-03-10")
    c = _meet("C", "2026-03-10")
    assert [m.meeting_id for m in G.list_meetings()] == [c.meeting_id, b.meeting_id, a.meeting_id]


def test_list_meetings_filters():
    _meet("Budget committee", "2026-01-10", kind="Committee", status="Held",
          decisions="Agreed the budget")
    _meet("AGM", "2026-06-01", kind="AGM", chair="Mr Big")
    _meet("Cancelled FGB", "2026-09-01", status="Cancelled")
    assert [m.title for m in G.list_meetings(kind="AGM")] == ["AGM"]
    assert [m.title for m in G.list_meetings(status="Held")] == ["Budget committee"]
    assert [m.title for m in G.list_meetings(date_from="2026-02-01", date_to="2026-08-31")] == ["AGM"]
    assert [m.title for m in G.list_meetings(date_from="2026-06-01")] == ["Cancelled FGB", "AGM"]
    assert [m.title for m in G.list_meetings(query="budget")] == ["Budget committee"]
    assert [m.title for m in G.list_meetings(query="Mr Big")] == ["AGM"]


def test_list_meetings_bad_filters_refused():
    with pytest.raises(G.ValidationError):
        G.list_meetings(status="Done")
    with pytest.raises(G.ValidationError):
        G.list_meetings(kind="Disco")
    with pytest.raises(G.ValidationError, match="date_from must be YYYY-MM-DD"):
        G.list_meetings(date_from="yesterday")


# ── meetings: update / delete / mark held ──

def test_update_meeting_partial():
    m = _meet(chair="Ann")
    out = G.update_meeting(m.meeting_id, {"attendees": 12})
    assert out.attendees == 12 and out.chair == "Ann" and out.title == m.title


def test_update_meeting_missing_refused():
    with pytest.raises(G.ValidationError, match="No meeting #5"):
        G.update_meeting(5, {"title": "x"})


def test_update_meeting_empty_payload_is_noop():
    m = _meet()
    assert G.update_meeting(m.meeting_id, {}) == m


def test_delete_meeting():
    m = _meet()
    assert G.delete_meeting(m.meeting_id) is True
    assert G.get_meeting(m.meeting_id) is None
    assert G.delete_meeting(m.meeting_id) is False


def test_mark_held_stamps_outcome():
    m = _meet(chair="Ann")
    out = G.mark_held(m.meeting_id, attendees=11, decisions="Adopted policy",
                      minutes_ref="M-7")
    assert out.status == "Held"
    assert (out.attendees, out.decisions, out.minutes_ref) == (11, "Adopted policy", "M-7")
    assert out.chair == "Ann"


def test_mark_held_without_extras_only_changes_status():
    m = _meet(attendees=4, decisions="old")
    out = G.mark_held(m.meeting_id)
    assert out.status == "Held" and out.attendees == 4 and out.decisions == "old"


def test_mark_held_validates_attendees_and_missing_meeting():
    m = _meet()
    with pytest.raises(G.ValidationError, match="0..1000"):
        G.mark_held(m.meeting_id, attendees=-3)
    with pytest.raises(G.ValidationError, match="No meeting #99"):
        G.mark_held(99)


# ── summary ──

def test_summary_empty():
    s = G.summary()
    assert s.governors_total == 0 and s.governors_active == 0
    assert s.governors_by_role == {r: 0 for r in G.GOVERNOR_ROLES}
    assert s.governors_by_status == {st: 0 for st in G.GOVERNOR_STATUSES}
    assert s.term_expiring_90d == 0
    assert (s.meetings_total, s.meetings_scheduled, s.meetings_held, s.meetings_cancelled) == (0, 0, 0, 0)
    assert s.next_meeting is None and s.last_held is None


def test_summary_counts_governors_and_expiring_terms():
    _gov("A", role="Chair", term_end=_iso(10))           # expiring
    _gov("B", term_end=_iso(90))                          # expiring (boundary)
    _gov("C", term_end=_iso(91))                          # not yet
    _gov("D", term_end=_iso(-1))                          # already past
    _gov("E", status="Resigned", term_end=_iso(5))        # not active
    s = G.summary()
    assert s.governors_total == 5
    assert s.governors_active == 4
    assert s.governors_by_role["Chair"] == 1 and s.governors_by_role["Trustee"] == 4
    assert s.governors_by_status["Resigned"] == 1
    assert s.term_expiring_90d == 2


def test_summary_meetings_next_and_last_held():
    _meet("past scheduled", _iso(-5))
    soon = _meet("soon", _iso(3))
    _meet("later", _iso(30))
    _meet("cancelled", _iso(1), status="Cancelled")
    _meet("held long ago", _iso(-60), status="Held")
    recent = _meet("held recently", _iso(-7), status="Held")
    s = G.summary()
    assert s.meetings_total == 6
    assert (s.meetings_scheduled, s.meetings_held, s.meetings_cancelled) == (3, 2, 1)
    assert s.next_meeting.meeting_id == soon.meeting_id
    assert s.last_held.meeting_id == recent.meeting_id
