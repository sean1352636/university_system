"""Year group rules (domain.year_groups) on a scratch school DB.

auth.db and the activity log are redirected, so nothing touches live data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
TODAY = dt.date(2026, 11, 3)
# Born in the right window for each year group in 2026/27.
DOB = {7: "2015-01-15", 8: "2014-01-15", 9: "2013-01-15", 10: "2012-01-15", 11: "2011-01-15"}


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=8, form="8K", dob=None, gender="Female", admitted="2025-09-01", **extra):
    global _n
    _n += 1
    data = {"legal_first_name": f"Pupil{_n}", "legal_last_name": "Test",
            "date_of_birth": dob or DOB[year], "gender": gender, "year_group": year,
            "form_group": form, "admission_date": admitted, **extra}
    return P.create_pupil(data, actor=ADMIN)


# ── Settings ─────────────────────────────────────────────────────────

def test_all_five_years_listed_even_when_empty():
    groups = YG.list_all()
    assert [g.year_group for g in groups] == [7, 8, 9, 10, 11]
    assert all(g.head_of_year is None and g.capacity is None for g in groups)
    assert [g.key_stage for g in groups] == ["KS3", "KS3", "KS3", "KS4", "KS4"]
    assert groups[0].label == "Year 7"


def test_update_saves_and_reports_changed_fields():
    g, changed = YG.update(9, {"head_of_year": "  Ms Patel ", "capacity": "180",
                               "head_of_year_email": "Patel@School.org"}, actor=ADMIN)
    assert changed == ["capacity", "head_of_year", "head_of_year_email"]
    assert (g.head_of_year, g.capacity, g.head_of_year_email) == (
        "Ms Patel", 180, "patel@school.org")
    assert g.updated_by == "admin2"
    _g, again = YG.update(9, {"capacity": 180}, actor=ADMIN)
    assert again == []
    # Fields left out keep their value; "" clears.
    g, changed = YG.update(9, {"capacity": ""}, actor=ADMIN)
    assert changed == ["capacity"] and g.capacity is None and g.head_of_year == "Ms Patel"


@pytest.mark.parametrize("changes", [
    {"capacity": "-1"}, {"capacity": "501"}, {"capacity": "lots"},
    {"head_of_year_email": "not-an-email"}, {"year_group": 10},
])
def test_bad_settings_refused(changes):
    with pytest.raises(YG.ValidationError):
        YG.update(8, changes, actor=ADMIN)
    assert YG.get(8).capacity is None


@pytest.mark.parametrize("year", [6, 12, "x", None])
def test_unknown_year_refused(year):
    with pytest.raises(YG.ValidationError):
        YG.get(year)


def test_teacher_can_view_but_not_change():
    assert YG.get(7).year_group == 7
    with pytest.raises(YG.PermissionDenied):
        YG.update(7, {"head_of_year": "Mr X"}, actor=TEACHER)
    with pytest.raises(YG.PermissionDenied):
        YG.clear(7, actor=TEACHER)
    p = _pupil(year=7, form="7A")
    with pytest.raises(YG.PermissionDenied):
        YG.move_pupils([p.pupil_id], 8, actor=TEACHER)
    assert YG.get(7).head_of_year is None
    assert P.get_pupil(p.pupil_id).year_group == 7


def test_clear_empties_settings_and_is_audited():
    YG.update(10, {"head_of_year": "Mr Okafor", "notes": "Mock exams in Jan"}, actor=ADMIN)
    g = YG.clear(10, actor=ADMIN)
    assert g.head_of_year is None and g.notes is None
    actions = [h["action"] for h in YG.history(10)]
    assert actions == ["clear", "update"]


def test_history_records_from_and_to():
    YG.update(11, {"capacity": 200}, actor=ADMIN)
    YG.update(11, {"capacity": 210}, actor=ADMIN)
    latest = YG.history(11)[0]
    assert latest["actor"] == "admin2"
    assert latest["detail"] == {"capacity": {"from": 200, "to": 210}}
    assert YG.history(7) == []


# ── Profile ──────────────────────────────────────────────────────────

def test_profile_counts():
    YG.update(8, {"capacity": 3}, actor=ADMIN)
    _pupil(year=8, form="8K", gender="Female", sen_status="K", fsm_eligible=True)
    _pupil(year=8, form="8K", gender="Male", sen_status="E", eal=True)
    _pupil(year=8, form="8P", gender="Male", admitted="2026-09-03")
    _pupil(year=8, form="", gender="Female")
    _pupil(year=9, form="9A")
    pr = YG.profile(8, TODAY)
    assert pr.on_roll == 4
    assert pr.by_gender == {"Female": 2, "Male": 2}
    assert pr.forms == {"8K": 2, "8P": 1} and pr.no_form == 1
    assert (pr.sen_support, pr.ehcp, pr.fsm, pr.eal) == (1, 1, 1, 1)
    assert pr.joined_this_year == 1
    assert pr.capacity == 3 and pr.spaces == -1 and pr.over_capacity
    assert YG.profile(9, TODAY).on_roll == 1
    assert not YG.profile(7, TODAY).over_capacity  # no capacity set


def test_leavers_counted_this_year_not_on_roll():
    p = _pupil(year=11, form="11B")
    _pupil(year=11, form="11B")
    EN.record_leaver(p.pupil_id, leaving_date="2026-10-20", reason=EN.END_OF_Y11,
                     details={}, actor=ADMIN, today=TODAY)
    pr = YG.profile(11, TODAY)
    assert pr.on_roll == 1 and pr.left_this_year == 1


def test_out_of_year_pupils_flagged():
    _pupil(year=8)
    held_back = _pupil(year=8, dob=DOB[9], form="8K")
    pr = YG.profile(8, TODAY)
    assert [(p.pupil_id, exp) for p, exp in pr.out_of_year] == [(held_back.pupil_id, 9)]


def test_overview_pairs_every_year():
    _pupil(year=7, form="7A")
    rows = YG.overview(TODAY)
    assert [g.year_group for g, _ in rows] == [7, 8, 9, 10, 11]
    assert {g.year_group: pr.on_roll for g, pr in rows}[7] == 1


# ── Moving pupils ────────────────────────────────────────────────────

@pytest.mark.parametrize("form, old, new, expected", [
    ("8K", 8, 9, None), ("8", 8, 9, None), ("Tutor K", 8, 9, "Tutor K"),
    ("10A", 10, 11, None), ("10A", 1, 2, "10A"), ("", 8, 9, ""), (None, 8, 9, None),
])
def test_form_after_move(form, old, new, expected):
    assert YG.form_after_move(form, old, new) == expected


def test_move_pupils_changes_year_and_clears_year_named_form():
    a = _pupil(year=8, form="8K")
    b = _pupil(year=8, form="BLUE")
    moved, refused = YG.move_pupils([a.pupil_id, b.pupil_id, a.pupil_id], 9, actor=ADMIN)
    assert refused == [] and len(moved) == 2
    assert P.get_pupil(a.pupil_id).year_group == 9
    assert not P.get_pupil(a.pupil_id).form_group
    assert P.get_pupil(b.pupil_id).form_group == "BLUE"
    h = YG.history(9)[0]
    assert h["action"] == "move_pupils"
    assert h["detail"] == {"moved_in": 2, "from_years": {"8": 2}}


def test_move_refusals():
    same = _pupil(year=9, form="9A")
    gone = _pupil(year=8, form="8K")
    EN.record_leaver(gone.pupil_id, leaving_date="2026-10-20", reason=EN.MOVED_SCHOOL,
                     details={"destination_school": "Hilltop"}, actor=ADMIN, today=TODAY)
    moved, refused = YG.move_pupils([same.pupil_id, gone.pupil_id, 99999], 9, actor=ADMIN)
    assert moved == []
    reasons = dict(refused)
    assert reasons[same.admission_no] == "already in Year 9"
    assert reasons[P.get_pupil(gone.pupil_id).admission_no] == "not on roll"
    assert reasons["99999"] == "no such pupil"
    assert YG.history(9) == []  # nothing moved, nothing audited


def test_move_to_bad_year_refused():
    p = _pupil(year=8)
    with pytest.raises(YG.ValidationError):
        YG.move_pupils([p.pupil_id], 12, actor=ADMIN)
