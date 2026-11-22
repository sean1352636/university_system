"""Enrolment & Leavers rules (domain.enrolment) on a scratch school DB.

auth.db and the activity log are redirected too, so nothing touches live data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import year_rollover
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
TODAY = dt.date(2026, 11, 3)


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _pupil(first="Ava", last="Stone", year=8, dob="2014-01-15", admitted="2026-09-01"):
    return P.create_pupil({
        "legal_first_name": first, "legal_last_name": last, "date_of_birth": dob,
        "gender": "Female", "year_group": year, "admission_date": admitted,
    }, actor=ADMIN)


def _leave(pupil, reason=EN.MOVED_SCHOOL, date="2026-10-20", **details):
    if reason == EN.MOVED_SCHOOL:
        details.setdefault("destination_school", "Hilltop Academy")
    return EN.record_leaver(pupil.pupil_id, leaving_date=date, reason=reason,
                            details=details, actor=ADMIN, today=TODAY)


# ── Recording a leaver ───────────────────────────────────────────────

def test_record_leaver_takes_pupil_off_roll_and_keeps_details():
    p = _pupil()
    view = _leave(p, destination_urn="123456")
    assert view.pupil.roll_status == "left"
    assert view.pupil.leaving_date == "2026-10-20"
    assert view.pupil.leaving_reason == EN.MOVED_SCHOOL
    assert view.leaving.destination_school == "Hilltop Academy"
    assert view.leaving.destination_urn == "123456"
    assert view.leaving.recorded_by == "admin2"


def test_teacher_cannot_record_leaver():
    p = _pupil()
    with pytest.raises(EN.PermissionDenied):
        EN.record_leaver(p.pupil_id, leaving_date="2026-10-20", reason=EN.MOVED_AWAY,
                         actor=TEACHER, today=TODAY)
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"


@pytest.mark.parametrize("date, reason, details, expect", [
    ("2026-12-01", EN.MOVED_AWAY, {}, "future"),
    ("2026-08-01", EN.MOVED_AWAY, {}, "before"),
    ("", EN.MOVED_AWAY, {}, "Leaving date"),
    ("2026-10-20", "Bored", {}, "leaving reason"),
    ("2026-10-20", EN.MOVED_SCHOOL, {}, "school the pupil has moved to"),
    ("2026-10-20", EN.OTHER, {}, "notes"),
    ("2026-10-20", EN.MOVED_AWAY, {"destination_urn": "12AB"}, "6 digits"),
    ("2026-10-20", EN.MOVED_AWAY, {"post16_destination": "Apprenticeship"}, "Year 11"),
    ("2026-10-20", EN.END_OF_Y11, {}, "Only a Year 11"),
    ("2026-10-20", EN.MOVED_AWAY, {"ctf_sent_date": "2026-10-01"}, "CTF sent date"),
    ("2026-10-20", EN.MOVED_AWAY, {"colour": "red"}, "Unknown field"),
])
def test_record_leaver_validation(date, reason, details, expect):
    p = _pupil()
    with pytest.raises(EN.ValidationError) as e:
        EN.record_leaver(p.pupil_id, leaving_date=date, reason=reason, details=details,
                         actor=ADMIN, today=TODAY)
    assert any(expect.lower() in msg.lower() for msg in e.value.problems), e.value.problems
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"
    assert EN.leaving_history(p.pupil_id) == []


def test_cannot_leave_twice():
    p = _pupil()
    _leave(p)
    with pytest.raises(EN.ValidationError):
        _leave(p)


def test_unknown_pupil():
    with pytest.raises(EN.NotFound):
        EN.record_leaver(9999, leaving_date="2026-10-20", reason=EN.MOVED_AWAY, actor=ADMIN,
                         today=TODAY)


# ── Follow-up actions ────────────────────────────────────────────────

def test_ctf_action_until_sent_then_overdue():
    p = _pupil()
    view = _leave(p, date="2026-10-01")
    assert any("Common Transfer File" in a and "2026-10-22" in a
               for a in view.actions(today=dt.date(2026, 10, 5)))
    assert any("overdue" in a for a in view.actions(today=TODAY))
    done = EN.record_details(p.pupil_id, {"ctf_sent_date": "2026-10-10"}, actor=ADMIN,
                             today=TODAY)
    assert done.actions(today=TODAY) == []


@pytest.mark.parametrize("reason, phrase", [
    (EN.MOVED_AWAY, "child missing education"),
    (EN.EHE, "elective home education"),
    (EN.EXCLUSION, "permanent exclusion"),
])
def test_local_authority_actions(reason, phrase):
    p = _pupil()
    view = _leave(p, reason=reason)
    assert any(phrase in a for a in view.actions(today=TODAY))
    done = EN.record_details(p.pupil_id, {"la_notified_date": "2026-10-21"}, actor=ADMIN,
                             today=TODAY)
    assert done.actions(today=TODAY) == []


def test_moved_away_with_known_school_needs_ctf_not_cme():
    p = _pupil()
    actions = _leave(p, reason=EN.MOVED_AWAY, destination_school="Far School").actions(
        today=TODAY)
    assert any("Common Transfer File" in a for a in actions)
    assert not any("missing education" in a for a in actions)


def test_year_11_leaver_needs_post16_destination():
    p = _pupil(first="Ben", year=11, dob="2011-01-15")
    view = _leave(p, reason=EN.END_OF_Y11)
    assert view.actions(today=TODAY) == ["Record post-16 destination"]
    done = EN.record_details(p.pupil_id, {"post16_destination": "FE college"}, actor=ADMIN,
                             today=TODAY)
    assert done.actions(today=TODAY) == []


def test_marked_left_on_pupil_form_shows_missing_details_and_can_add_them():
    p = _pupil()
    P.update_pupil(p.pupil_id, {"roll_status": "left", "leaving_date": "2026-10-20",
                                "leaving_reason": EN.MOVED_AWAY}, actor=ADMIN)
    [view] = EN.list_leavers()
    assert view.actions() == ["Leaving details not recorded"]
    added = EN.record_details(p.pupil_id, {"la_notified_date": "2026-10-21"}, actor=ADMIN,
                              today=TODAY)
    assert added.leaving.reason == EN.MOVED_AWAY
    assert added.leaving.leaving_date == "2026-10-20"
    assert added.actions(today=TODAY) == []


def test_record_details_refused_for_pupil_on_roll():
    p = _pupil()
    with pytest.raises(EN.ValidationError):
        EN.record_details(p.pupil_id, {"notes": "x"}, actor=ADMIN, today=TODAY)


def test_record_details_keeps_fields_not_mentioned():
    p = _pupil()
    _leave(p, destination_urn="123456")
    EN.record_details(p.pupil_id, {"notes": "Parent phoned"}, actor=ADMIN, today=TODAY)
    lv = EN.current_leaving(p.pupil_id)
    assert lv.destination_urn == "123456" and lv.notes == "Parent phoned"


# ── Reinstating ─────────────────────────────────────────────────────

def test_reinstate_puts_pupil_back_and_keeps_history():
    p = _pupil()
    _leave(p)
    back = EN.reinstate(p.pupil_id, actor=ADMIN, note="Move fell through", year_group=8)
    assert back.roll_status == "on_roll"
    assert back.leaving_date is None and back.leaving_reason is None
    assert EN.current_leaving(p.pupil_id) is None
    [old] = EN.leaving_history(p.pupil_id)
    assert old.status == "reinstated" and old.reinstate_note == "Move fell through"
    # They can leave again; both leavings are kept.
    _leave(p, reason=EN.MOVED_AWAY, date="2026-11-02")
    assert [lv.status for lv in EN.leaving_history(p.pupil_id)] == ["left", "reinstated"]


def test_reinstate_needs_a_reason_and_a_leaver():
    p = _pupil()
    with pytest.raises(EN.ValidationError):
        EN.reinstate(p.pupil_id, actor=ADMIN, note="x")  # on roll
    _leave(p)
    with pytest.raises(EN.ValidationError):
        EN.reinstate(p.pupil_id, actor=ADMIN, note="  ")
    with pytest.raises(EN.PermissionDenied):
        EN.reinstate(p.pupil_id, actor=TEACHER, note="Back")


# ── Lists and summary ────────────────────────────────────────────────

def test_lists_and_summary():
    stay = _pupil(first="Cara")
    gone = _pupil(first="Dan")
    gone2 = _pupil(first="Eve", last="Moss")
    _leave(gone, date="2026-10-01")  # CTF due 2026-10-22: overdue
    _leave(gone2, reason=EN.EHE, date="2026-10-02", la_notified_date="2026-10-03")

    year = "2026/27"
    assert {v.pupil.pupil_id for v in EN.list_leavers(academic_year=year)} == {
        gone.pupil_id, gone2.pupil_id}
    assert [v.pupil.pupil_id for v in EN.list_leavers(reason=EN.EHE)] == [gone2.pupil_id]
    assert [v.pupil.pupil_id for v in EN.list_leavers(search="Moss")] == [gone2.pupil_id]
    assert [v.pupil.pupil_id for v in EN.list_leavers(actions_only=True)] == [gone.pupil_id]
    assert EN.list_leavers(academic_year="2025/26") == []
    assert len(EN.list_joiners(year)) == 3

    s = EN.roll_summary(year)
    assert s.on_roll == 1 and s.on_roll_by_year[8] == 1
    assert s.joiners == 3 and s.leavers == 2
    assert s.leavers_by_reason == {EN.MOVED_SCHOOL: 1, EN.EHE: 1}
    assert s.actions_due == 1
    assert stay.pupil_id not in {v.pupil.pupil_id for v in EN.list_leavers()}


# ── Year-end rollover writes leaving details for Year 11 ───────────────

def test_rollover_year_11_leavers_get_post16_action():
    y11 = _pupil(first="Finn", year=11, dob="2011-01-15")
    y8 = _pupil(first="Gail")
    year_rollover.run_if_due(today=TODAY)  # first run = baseline only
    year_rollover.run_if_due(today=dt.date(2027, 9, 2))
    assert P.get_pupil(y8.pupil_id).year_group == 9
    [view] = EN.list_leavers()
    assert view.pupil.pupil_id == y11.pupil_id
    assert view.leaving.reason == EN.END_OF_Y11
    assert view.leaving.leaving_date == "2027-08-31"
    assert view.actions() == ["Record post-16 destination"]
