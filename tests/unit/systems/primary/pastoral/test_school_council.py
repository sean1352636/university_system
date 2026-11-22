"""School council (primary domain.pastoral.school_council.school_council)."""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from education_system import paths
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.school_council import school_council as SC

TODAY = dt.date.today()
_n = 0


def _pupil(year="5"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Council{_n:03d}",
                           "year_group": year, "date_of_birth": "2016-03-01"})


def _member(pupil, **extra):
    return SC.create_member({"student_id": pupil.pupil_id, "role": "Class Rep",
                             "term_start": "2026-09-01", **extra})


def _meeting(**extra):
    return SC.create_meeting({"meeting_date": "2026-10-01", "meeting_type": "Full Council",
                              "title": "Autumn meeting", **extra})


# ── Members: pupil link ──────────────────────────────────────────────

def test_student_exists_reads_pupils_table():
    SC.init_db()
    ava = _pupil()
    assert SC._student_exists(ava.pupil_id) is True
    assert SC._student_exists("NOPE999") is False


def test_member_table_references_pupils():
    SC.init_db()
    conn = sqlite3.connect(paths.PRIMARY_SCHOOL_COUNCIL_DB)
    try:
        fks = conn.execute("PRAGMA foreign_key_list(school_council_members)").fetchall()
    finally:
        conn.close()
    assert [(f[2], f[3], f[4]) for f in fks] == [("pupils", "student_id", "pupil_id")]


def test_member_for_real_pupil_saves_and_unknown_pupil_is_refused():
    ava = _pupil()
    m = _member(ava, portfolio="  Playground  ", notes="", elected_on="2026-08-30")
    got = SC.get_member(m.member_id)
    assert (got.student_id, got.role, got.term_start, got.status) == (
        ava.pupil_id, "Class Rep", "2026-09-01", "Active")
    assert got.portfolio == "Playground" and got.notes is None
    assert got.elected_on == "2026-08-30" and got.term_end is None and got.is_active
    with pytest.raises(SC.ValidationError, match="No student with id GHOST1"):
        SC.create_member({"student_id": "GHOST1", "role": "Member",
                          "term_start": "2026-09-01"})
    assert SC.list_members() == [got]


def test_deleting_pupil_cascades_membership():
    ava = _pupil()
    m = _member(ava)
    assert P.delete_pupil(ava.pupil_id)
    assert SC.get_member(m.member_id) is None


# ── Members: validation ──────────────────────────────────────────────

def test_member_validation_rules():
    ava = _pupil()
    base = {"student_id": ava.pupil_id, "role": "Member", "term_start": "2026-09-01"}
    for bad, msg in (({"student_id": "  "}, "Student is required"),
                     ({"role": "President"}, "Role must be one of"),
                     ({"role": ""}, "Role must be one of"),
                     ({"term_start": ""}, "Term start is required"),
                     ({"term_start": "01/09/2026"}, "Term start must be YYYY-MM-DD"),
                     ({"term_end": "2026-13-01"}, "Term end must be YYYY-MM-DD"),
                     ({"elected_on": "yesterday"}, "Elected on must be YYYY-MM-DD"),
                     ({"term_end": "2026-08-31"}, "Term end must be on or after term start"),
                     ({"status": "Retired"}, "Status must be one of")):
        with pytest.raises(SC.ValidationError, match=msg):
            SC.create_member({**base, **bad})
    assert SC.list_members() == []


def test_term_end_same_day_as_start_is_allowed():
    m = _member(_pupil(), term_end="2026-09-01")
    assert m.term_end == "2026-09-01"


def test_one_active_role_per_pupil():
    ava = _pupil()
    _member(ava, role="Chair")
    with pytest.raises(SC.ValidationError, match="already has an active council role"):
        _member(ava, role="Secretary")
    # Plain members are not limited, nor are non-active rows.
    assert _member(ava, role="Member").role == "Member"
    assert _member(ava, role="Eco Rep", status="Term Ended").status == "Term Ended"


def test_role_holder_blocked_by_active_plain_membership():
    ava = _pupil()
    _member(ava, role="Member")
    with pytest.raises(SC.ValidationError, match="already has an active council role"):
        _member(ava, role="Chair")


def test_updating_own_active_role_is_not_a_clash():
    ava = _pupil()
    m = _member(ava, role="Chair")
    up = SC.update_member(m.member_id, {"student_id": ava.pupil_id, "role": "Vice Chair",
                                        "term_start": "2026-09-01", "portfolio": "Eco"})
    assert (up.role, up.portfolio) == ("Vice Chair", "Eco")
    assert up.created_on == m.created_on


# ── Members: update / delete / lifecycle ─────────────────────────────

def test_update_and_delete_member_missing_ids():
    with pytest.raises(SC.ValidationError, match="No member with id 99"):
        SC.update_member(99, {"student_id": "x", "role": "Member", "term_start": "2026-09-01"})
    assert SC.delete_member(99) is False
    assert SC.get_member(99) is None
    m = _member(_pupil())
    assert SC.delete_member(m.member_id) is True
    assert SC.get_member(m.member_id) is None


def test_end_term_sets_status_and_end_date():
    m = _member(_pupil())
    ended = SC.end_term(m.member_id, ended_on="2027-07-20")
    assert (ended.status, ended.term_end, ended.is_active) == ("Term Ended", "2027-07-20", False)
    with pytest.raises(SC.ValidationError, match="No member with id 404"):
        SC.end_term(404)


def test_end_term_defaults_to_today():
    m = SC.create_member({"student_id": _pupil().pupil_id, "role": "Member",
                          "term_start": (TODAY - dt.timedelta(days=30)).isoformat()})
    assert SC.end_term(m.member_id).term_end == TODAY.isoformat()


def test_end_term_before_start_is_refused():
    m = _member(_pupil())
    with pytest.raises(SC.ValidationError, match="Term end must be on or after"):
        SC.end_term(m.member_id, ended_on="2026-01-01")


def test_set_member_status():
    m = _member(_pupil())
    assert SC.set_member_status(m.member_id, "Suspended").status == "Suspended"
    with pytest.raises(SC.ValidationError, match="Status must be one of"):
        SC.set_member_status(m.member_id, "Gone")
    with pytest.raises(SC.ValidationError, match="No member with id 77"):
        SC.set_member_status(77, "Active")


def test_list_members_filters_and_order():
    ava, ben = _pupil(), _pupil()
    a1 = _member(ava, role="Chair", term_start="2025-09-01", status="Term Ended",
                 term_end="2026-07-20")
    a2 = _member(ava, role="Chair", term_start="2026-09-01")
    b1 = _member(ben, role="Eco Rep", term_start="2026-09-01")
    ids = [m.member_id for m in SC.list_members()]
    assert ids == [b1.member_id, a2.member_id, a1.member_id]
    assert [m.member_id for m in SC.list_members(student_id=ava.pupil_id)] == [
        a2.member_id, a1.member_id]
    assert [m.member_id for m in SC.list_members(role="Eco Rep")] == [b1.member_id]
    assert [m.member_id for m in SC.list_members(status="Term Ended")] == [a1.member_id]
    assert {m.member_id for m in SC.list_members(active_only=True)} == {
        a2.member_id, b1.member_id}


# ── Meetings ─────────────────────────────────────────────────────────

def test_create_meeting_defaults_and_cleaning():
    mt = _meeting(meeting_time="15:30", location="  Hall ", chair="", agenda="Playground")
    got = SC.get_meeting(mt.meeting_id)
    assert (got.meeting_date, got.meeting_time, got.meeting_type, got.title) == (
        "2026-10-01", "15:30", "Full Council", "Autumn meeting")
    assert got.status == "Scheduled" and got.is_open
    assert got.location == "Hall" and got.chair is None and got.agenda == "Playground"


def test_meeting_validation_rules():
    for bad, msg in (({"meeting_date": ""}, "Meeting date is required"),
                     ({"meeting_date": "1/10/2026"}, "Meeting date must be YYYY-MM-DD"),
                     ({"meeting_time": "3pm"}, "Meeting time must be HH:MM"),
                     ({"next_meeting_on": "soon"}, "Next meeting must be YYYY-MM-DD"),
                     ({"meeting_type": "Assembly"}, "Type must be one of"),
                     ({"title": "   "}, "Title is required"),
                     ({"status": "Postponed"}, "Status must be one of")):
        with pytest.raises(SC.ValidationError, match=msg):
            _meeting(**bad)
    assert SC.list_meetings() == []


def test_meeting_lifecycle():
    mt = _meeting()
    assert SC.confirm_meeting(mt.meeting_id).status == "Confirmed"
    done = SC.complete_meeting(mt.meeting_id, minutes="Discussed lunch",
                               decisions="More fruit", actions="Ask cook")
    assert (done.status, done.minutes, done.decisions, done.actions) == (
        "Completed", "Discussed lunch", "More fruit", "Ask cook")
    assert not done.is_open
    # complete without new text keeps the old text
    again = SC.complete_meeting(mt.meeting_id)
    assert again.minutes == "Discussed lunch"
    other = _meeting(title="Spring")
    assert SC.cancel_meeting(other.meeting_id).status == "Cancelled"
    assert SC.set_meeting_status(other.meeting_id, "Scheduled").status == "Scheduled"
    with pytest.raises(SC.ValidationError, match="Status must be one of"):
        SC.set_meeting_status(other.meeting_id, "Done")
    for fn in (SC.confirm_meeting, SC.complete_meeting, SC.cancel_meeting):
        with pytest.raises(SC.ValidationError, match="No meeting with id 999"):
            fn(999)
    with pytest.raises(SC.ValidationError, match="No meeting with id 999"):
        SC.set_meeting_status(999, "Confirmed")


def test_update_and_delete_meeting():
    mt = _meeting()
    up = SC.update_meeting(mt.meeting_id, {"meeting_date": "2026-10-02",
                                           "meeting_type": "AGM", "title": "AGM"})
    assert (up.meeting_date, up.meeting_type, up.title) == ("2026-10-02", "AGM", "AGM")
    with pytest.raises(SC.ValidationError, match="No meeting with id 5"):
        SC.update_meeting(5, {"meeting_date": "2026-10-02", "meeting_type": "AGM",
                              "title": "x"})
    assert SC.delete_meeting(mt.meeting_id) is True
    assert SC.delete_meeting(mt.meeting_id) is False
    assert SC.get_meeting(mt.meeting_id) is None


def test_list_meetings_filters():
    future = (TODAY + dt.timedelta(days=10)).isoformat()
    past = (TODAY - dt.timedelta(days=10)).isoformat()
    m_past = _meeting(meeting_date=past, chair="Mrs Green")
    m_fut = _meeting(meeting_date=future, meeting_type="Executive", chair="Mr Brown")
    m_fut_cancel = _meeting(meeting_date=future, status="Cancelled")
    assert [m.meeting_id for m in SC.list_meetings()] == [
        m_fut_cancel.meeting_id, m_fut.meeting_id, m_past.meeting_id]
    assert [m.meeting_id for m in SC.list_meetings(upcoming_only=True)] == [m_fut.meeting_id]
    assert [m.meeting_id for m in SC.list_meetings(meeting_type="Executive")] == [
        m_fut.meeting_id]
    assert [m.meeting_id for m in SC.list_meetings(status="Cancelled")] == [
        m_fut_cancel.meeting_id]
    assert [m.meeting_id for m in SC.list_meetings(chair_like="green")] == [m_past.meeting_id]
    assert [m.meeting_id for m in SC.list_meetings(date_to=TODAY.isoformat())] == [
        m_past.meeting_id]
    assert {m.meeting_id for m in SC.list_meetings(date_from=TODAY.isoformat())} == {
        m_fut.meeting_id, m_fut_cancel.meeting_id}
    with pytest.raises(SC.ValidationError, match="From must be YYYY-MM-DD"):
        SC.list_meetings(date_from="today")
    with pytest.raises(SC.ValidationError, match="To must be YYYY-MM-DD"):
        SC.list_meetings(date_to="later")


# ── Motions ──────────────────────────────────────────────────────────

def test_add_motion_numbers_per_meeting():
    a, b = _meeting(), _meeting(title="Other")
    m1 = SC.add_motion(a.meeting_id, {"title": "Longer playtime", "proposer": " Ava ",
                                      "votes_for": "3"})
    m2 = SC.add_motion(a.meeting_id, {"title": "Pet day"})
    m3 = SC.add_motion(b.meeting_id, {"title": "Book fair"})
    assert (m1.motion_number, m2.motion_number, m3.motion_number) == (1, 2, 1)
    assert (m1.proposer, m1.votes_for, m1.votes_against, m1.outcome) == ("Ava", 3, 0, "Pending")
    assert not m1.is_decided and m1.decided_on is None
    with pytest.raises(SC.ValidationError, match="No meeting with id 42"):
        SC.add_motion(42, {"title": "x"})


def test_motion_validation_rules():
    mt = _meeting()
    for bad, msg in (({"title": ""}, "Motion title is required"),
                     ({"outcome": "Carried"}, "Outcome must be one of"),
                     ({"decided_on": "tomorrow"}, "Decided on must be YYYY-MM-DD"),
                     ({"votes_for": "lots"}, "votes for must be an integer"),
                     ({"votes_against": -1}, "votes against must be >= 0"),
                     ({"votes_abstain": "x"}, "votes abstain must be an integer")):
        with pytest.raises(SC.ValidationError, match=msg):
            SC.add_motion(mt.meeting_id, {"title": "T", **bad})
    assert SC.list_motions() == []


def test_record_vote_outcomes_and_totals():
    mt = _meeting()
    m = SC.add_motion(mt.meeting_id, {"title": "Longer playtime"})
    passed = SC.record_vote(m.motion_id, votes_for=7, votes_against=3, votes_abstain=2,
                            decided_on="2026-10-01")
    assert (passed.outcome, passed.total_votes, passed.decided_on) == ("Passed", 12, "2026-10-01")
    assert passed.is_decided
    tie = SC.record_vote(m.motion_id, votes_for=4, votes_against=4)
    assert tie.outcome == "Failed" and tie.decided_on == TODAY.isoformat()
    with pytest.raises(SC.ValidationError, match="Vote counts must be >= 0"):
        SC.record_vote(m.motion_id, votes_for=-1, votes_against=0)
    with pytest.raises(SC.ValidationError, match="No motion with id 8"):
        SC.record_vote(8, votes_for=1, votes_against=0)


def test_update_delete_and_list_motions():
    a, b = _meeting(), _meeting(title="Other")
    m1 = SC.add_motion(a.meeting_id, {"title": "One"})
    m2 = SC.add_motion(a.meeting_id, {"title": "Two", "outcome": "Withdrawn"})
    m3 = SC.add_motion(b.meeting_id, {"title": "Three"})
    up = SC.update_motion(m1.motion_id, {"title": "One (amended)", "outcome": "Deferred"})
    assert (up.title, up.outcome, up.motion_number) == ("One (amended)", "Deferred", 1)
    with pytest.raises(SC.ValidationError, match="No motion with id 50"):
        SC.update_motion(50, {"title": "x"})
    assert [m.motion_id for m in SC.list_motions()] == [m3.motion_id, m1.motion_id, m2.motion_id]
    assert [m.motion_id for m in SC.list_motions(meeting_id=a.meeting_id)] == [
        m1.motion_id, m2.motion_id]
    assert [m.motion_id for m in SC.list_motions(outcome="Withdrawn")] == [m2.motion_id]
    assert [m.motion_id for m in SC.list_motions(pending_only=True)] == [m3.motion_id]
    assert SC.delete_motion(m3.motion_id) is True
    assert SC.delete_motion(m3.motion_id) is False
    assert SC.get_motion(m3.motion_id) is None


def test_deleting_meeting_cascades_motions():
    mt = _meeting()
    m = SC.add_motion(mt.meeting_id, {"title": "One"})
    SC.delete_meeting(mt.meeting_id)
    assert SC.get_motion(m.motion_id) is None


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    s = SC.summary()
    assert (s.total_members, s.active_members, s.total_meetings, s.total_motions) == (0, 0, 0, 0)
    assert s.by_role == {} and s.by_meeting_type == {} and s.by_outcome == {}


def test_summary_counts():
    ava, ben, cal = _pupil(), _pupil(), _pupil()
    _member(ava, role="Chair")
    _member(ben, role="Class Rep")
    _member(cal, role="Class Rep", status="Resigned")
    m1 = _meeting()
    m2 = _meeting(meeting_type="Executive", status="Completed")
    _meeting(meeting_type="Executive")
    mo1 = SC.add_motion(m1.meeting_id, {"title": "A"})
    mo2 = SC.add_motion(m1.meeting_id, {"title": "B"})
    SC.add_motion(m2.meeting_id, {"title": "C"})
    SC.record_vote(mo1.motion_id, votes_for=5, votes_against=1, decided_on="2026-10-01")
    SC.record_vote(mo2.motion_id, votes_for=1, votes_against=5, decided_on="2026-10-01")
    s = SC.summary()
    assert (s.total_members, s.active_members) == (3, 2)
    assert (s.total_meetings, s.completed_meetings) == (3, 1)
    assert (s.total_motions, s.motions_passed, s.motions_failed, s.motions_pending) == (3, 1, 1, 1)
    assert s.by_role == {"Chair": 1, "Class Rep": 2}
    assert s.by_meeting_type == {"Full Council": 1, "Executive": 2}
    assert s.by_outcome == {"Passed": 1, "Failed": 1, "Pending": 1}
