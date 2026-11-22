"""Form group rules (domain.form_groups) on a scratch school DB.

auth.db and the activity log are redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
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


def _pupil(year=8, form="", gender="Female", **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": DOB[year], "gender": gender, "year_group": year, "form_group": form,
        "admission_date": "2025-09-01", **extra}, actor=ADMIN)


def _form(name="8K", year=8, **extra):
    return FG.create({"name": name, "year_group": year, **extra}, actor=ADMIN)


# ── Setting up forms ─────────────────────────────────────────────────

def test_create_cleans_and_audits():
    f = _form(" 8k ", 8, tutor_name="Mr  Ahmed", tutor_email="Ahmed@School.org", room="B12",
              capacity="30")
    assert (f.name, f.year_group, f.tutor_name, f.tutor_email, f.room, f.capacity) == (
        "8K", 8, "Mr Ahmed", "ahmed@school.org", "B12", 30)
    assert f.is_active and f.label == "8K (Year 8)" and f.created_by == "admin2"
    assert [h["action"] for h in FG.history(f.form_id)] == ["create"]


@pytest.mark.parametrize("data", [
    {"name": "", "year_group": 8}, {"name": "8K", "year_group": 6},
    {"name": "8K", "year_group": None}, {"name": "ABCDEFGHIJK", "year_group": 8},
    {"name": "8K!", "year_group": 8}, {"name": "8K", "year_group": 8, "capacity": "0"},
    {"name": "8K", "year_group": 8, "capacity": "61"},
    {"name": "8K", "year_group": 8, "tutor_email": "nope"},
    {"name": "8K", "year_group": 8, "colour": "red"},
])
def test_bad_forms_refused(data):
    with pytest.raises(FG.ValidationError):
        FG.create(data, actor=ADMIN)
    assert FG.list_forms() == []


def test_name_unique_within_year_only():
    _form("BLUE", 7)
    _form("BLUE", 8)
    with pytest.raises(FG.ValidationError, match="already has a form"):
        _form("blue", 7)


def test_teacher_can_view_but_not_change():
    f = _form()
    p = _pupil(8)
    for call in (lambda: FG.create({"name": "8P", "year_group": 8}, actor=TEACHER),
                 lambda: FG.update(f.form_id, {"room": "A1"}, actor=TEACHER),
                 lambda: FG.archive(f.form_id, actor=TEACHER),
                 lambda: FG.delete(f.form_id, actor=TEACHER),
                 lambda: FG.assign([p.pupil_id], f.form_id, actor=TEACHER),
                 lambda: FG.remove([p.pupil_id], f.form_id, actor=TEACHER),
                 lambda: FG.set_up_missing(actor=TEACHER)):
        with pytest.raises(FG.PermissionDenied):
            call()
    assert FG.get(f.form_id).room is None and not P.get_pupil(p.pupil_id).form_group
    assert FG.list_forms(8)[0].form_id == f.form_id  # viewing is fine


# ── Changing forms ───────────────────────────────────────────────────

def test_update_reports_changes_and_hides_email_values_in_audit():
    f = _form()
    g, changed, renamed = FG.update(f.form_id, {"tutor_email": "t@school.org", "room": "C3",
                                                "capacity": 28}, actor=ADMIN)
    assert changed == ["capacity", "room", "tutor_email"] and renamed == 0
    assert g.room == "C3" and g.capacity == 28
    detail = FG.history(f.form_id)[0]["detail"]
    assert detail["tutor_email"] == "changed" and detail["room"] == {"from": None, "to": "C3"}
    assert FG.update(f.form_id, {"room": "C3"}, actor=ADMIN)[1] == []


def test_rename_renames_pupils():
    f = _form("8K", 8)
    a, b = _pupil(8, "8K"), _pupil(8, "8K")
    other = _pupil(9, "8K")  # same name, other year: not this form
    g, _c, renamed = FG.update(f.form_id, {"name": "8KA"}, actor=ADMIN)
    assert g.name == "8KA" and renamed == 2
    assert P.get_pupil(a.pupil_id).form_group == "8KA"
    assert P.get_pupil(b.pupil_id).form_group == "8KA"
    assert P.get_pupil(other.pupil_id).form_group == "8K"


def test_form_with_pupils_cannot_change_year():
    f = _form("BLUE", 8)
    _pupil(8, "BLUE")
    with pytest.raises(FG.ValidationError, match="can't change year"):
        FG.update(f.form_id, {"year_group": 9}, actor=ADMIN)
    empty = _form("RED", 8)
    assert FG.update(empty.form_id, {"year_group": 9}, actor=ADMIN)[0].year_group == 9


def test_rename_into_existing_name_refused():
    _form("8K", 8)
    f = _form("8P", 8)
    with pytest.raises(FG.ValidationError, match="already has a form"):
        FG.update(f.form_id, {"name": "8k"}, actor=ADMIN)


def test_archive_restore_delete_need_empty_form():
    f = _form()
    p = _pupil(8, "8K")
    with pytest.raises(FG.ValidationError, match="still has 1 pupil"):
        FG.archive(f.form_id, actor=ADMIN)
    with pytest.raises(FG.ValidationError, match="still has 1 pupil"):
        FG.delete(f.form_id, actor=ADMIN)
    FG.remove([p.pupil_id], f.form_id, actor=ADMIN)
    assert FG.archive(f.form_id, actor=ADMIN).status == "archived"
    assert FG.list_forms() == [] and len(FG.list_forms(include_archived=True)) == 1
    with pytest.raises(FG.ValidationError, match="Archived"):
        FG.update(f.form_id, {"room": "A1"}, actor=ADMIN)
    _form("8K", 8)  # the name is free again
    with pytest.raises(FG.ValidationError, match="already has an open form"):
        FG.restore(f.form_id, actor=ADMIN)
    FG.delete(f.form_id, actor=ADMIN)
    with pytest.raises(FG.NotFound):
        FG.get(f.form_id)
    assert FG.history(f.form_id)[0]["action"] == "delete"  # history kept


# ── Pupils in forms ──────────────────────────────────────────────────

def test_members_and_stats():
    f = _form("8K", 8, capacity=2)
    _pupil(8, "8K", gender="Female", sen_status="K", fsm_eligible=True)
    _pupil(8, "8k", gender="Male", eal=True)
    _pupil(8, "8K", gender="Male", sen_status="E")
    _pupil(8, "8P")
    assert len(FG.members(f)) == 3
    s = FG.stats()[f.form_id]
    assert (s.on_roll, s.female, s.male, s.sen, s.fsm, s.eal) == (3, 1, 2, 2, 1, 1)
    assert s.spaces == -1 and s.over_capacity


def test_assign_rules():
    f = _form("8K", 8)
    ok = _pupil(8, "8P")
    wrong_year = _pupil(9)
    already = _pupil(8, "8K")
    gone = _pupil(8)
    EN.record_leaver(gone.pupil_id, leaving_date="2026-10-20", reason=EN.MOVED_SCHOOL,
                     details={"destination_school": "Hilltop"}, actor=ADMIN, today=TODAY)
    done, refused = FG.assign([ok.pupil_id, wrong_year.pupil_id, already.pupil_id,
                               gone.pupil_id, 99999, ok.pupil_id], f.form_id, actor=ADMIN)
    assert [p.pupil_id for p in done] == [ok.pupil_id]
    assert P.get_pupil(ok.pupil_id).form_group == "8K"
    why = dict(refused)
    assert why[wrong_year.admission_no] == "in Year 9, not Year 8"
    assert why[already.admission_no] == "already in 8K"
    assert why[P.get_pupil(gone.pupil_id).admission_no] == "not on roll"
    assert why["99999"] == "no such pupil"


def test_assign_respects_capacity_unless_allowed():
    f = _form("8K", 8, capacity=1)
    a, b = _pupil(8), _pupil(8)
    with pytest.raises(FG.ValidationError, match="room for 1 more"):
        FG.assign([a.pupil_id, b.pupil_id], f.form_id, actor=ADMIN)
    assert not P.get_pupil(a.pupil_id).form_group
    done, _ = FG.assign([a.pupil_id, b.pupil_id], f.form_id, actor=ADMIN,
                        allow_over_capacity=True)
    assert len(done) == 2


def test_remove_only_touches_members():
    f = _form("8K", 8)
    a, b = _pupil(8, "8K"), _pupil(8, "8P")
    assert FG.remove([a.pupil_id, b.pupil_id], f.form_id, actor=ADMIN) == 1
    assert not P.get_pupil(a.pupil_id).form_group
    assert P.get_pupil(b.pupil_id).form_group == "8P"


def test_not_set_up_and_set_up_missing():
    _form("8K", 8)
    _pupil(8, "8K")
    _pupil(8, "8P")
    _pupil(8, "8P")
    _pupil(9, "9A")
    assert FG.not_set_up() == [(8, "8P", 2), (9, "9A", 1)]
    made = FG.set_up_missing(actor=ADMIN)
    assert sorted(f.label for f in made) == ["8P (Year 8)", "9A (Year 9)"]
    assert FG.not_set_up() == []


def test_distribution_balances_size_and_gender_within_capacity():
    a = _form("8A", 8, capacity=3)
    b = _form("8B", 8, capacity=3)
    _pupil(8, "8A", gender="Female")
    for g in ("Female", "Female", "Male", "Male", "Male", "Female"):
        _pupil(8, gender=g)
    plan, unplaced = FG.plan_distribution(8)
    assert len(plan) == 5 and len(unplaced) == 1  # 6 seats, 1 taken
    total = FG.apply_distribution(plan, actor=ADMIN)[0]
    assert total == 5
    s = FG.stats(8)
    assert s[a.form_id].on_roll == 3 and s[b.form_id].on_roll == 3
    assert abs(s[a.form_id].female - s[b.form_id].female) <= 1
    assert FG.plan_distribution(8)[0] == []


def test_export_class_list(tmp_path):
    f = _form("8K", 8, tutor_name="Ms Lee")
    _pupil(8, "8K", preferred_name="=cmd", sen_status="K")
    out = tmp_path / "list.csv"
    assert FG.export_class_list(f.form_id, out, actor=TEACHER) == 1
    rows = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert rows[0] == ["Form 8K", "Year 8", "Tutor: Ms Lee"]
    assert "SEN" not in rows[1]
    assert rows[2][3] == "'=cmd"  # formula escaped
    with pytest.raises(FG.PermissionDenied):
        FG.export_class_list(f.form_id, out, actor=TEACHER, include_needs=True)
    FG.export_class_list(f.form_id, out, actor=ADMIN, include_needs=True)
    rows = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert rows[1][-3:] == ["SEN", "FSM", "EAL"] and rows[2][-3] == "K"


# ── Year-end rollover ────────────────────────────────────────────────

def test_rollover_moves_forms_with_their_pupils():
    y7 = _form("7K", 7, tutor_name="Mr Ahmed")
    y8 = _form("BLUE", 8)
    y10 = _form("10A", 10)
    y11 = _form("11A", 11)
    p7 = _pupil(7, "7K")
    _pupil(11, "11A")
    year_rollover.run_if_due(today=TODAY)  # first run = baseline only
    year_rollover.run_if_due(today=dt.date(2027, 9, 2))
    assert (FG.get(y7.form_id).name, FG.get(y7.form_id).year_group) == ("8K", 8)
    assert FG.get(y7.form_id).tutor_name == "Mr Ahmed"
    assert (FG.get(y8.form_id).name, FG.get(y8.form_id).year_group) == ("BLUE", 9)
    assert (FG.get(y10.form_id).name, FG.get(y10.form_id).year_group) == ("11A", 11)
    assert FG.get(y11.form_id).status == "archived"
    assert P.get_pupil(p7.pupil_id).form_group == "8K"
    assert [m.pupil_id for m in FG.members(FG.get(y7.form_id))] == [p7.pupil_id]
    assert FG.not_set_up() == []
    assert FG.history(y7.form_id)[0]["action"] == "rollover"


# ── Pupil record form choice and e-mail details ──────────────────────

def test_choices_for_lists_open_forms_of_the_year_and_keeps_current():
    _form("8A", 8)
    _form("8B", 8)
    _form("9A", 9)
    old = _form("8Z", 8)
    FG.archive(old.form_id, actor=ADMIN)
    assert FG.choices_for(8) == ["8A", "8B"]
    assert FG.choices_for("8", "8q") == ["8A", "8B", "8Q"]  # not set up, but theirs
    assert FG.choices_for(None) == [] and FG.choices_for(12) == []


def test_check_choice():
    _form("8A", 8)
    FG.check_choice(8, "8a")
    FG.check_choice(8, "")
    FG.check_choice(8, "OLD", current="old")  # unchanged, though not set up
    for year, form in ((8, "9A"), (9, "8A"), (8, "OLD")):
        with pytest.raises(FG.ValidationError, match="isn't set up"):
            FG.check_choice(year, form)


def test_details_for_email():
    _form("8K", 8, tutor_name="Ms Lee", tutor_email="lee@school.org", room="B12")
    d = FG.details_for(_pupil(8, "8K"))
    assert (d["form_group"], d["form_tutor"], d["form_tutor_email"], d["form_room"]) == (
        "8K", "Ms Lee", "lee@school.org", "B12")
    assert "8K (Year 8)" in d["form_details"] and "Ms Lee (lee@school.org)" in d["form_details"]
    assert "B12" in d["form_details"]
    assert "not set yet" in FG.details_for(_pupil(8))["form_details"]
    bare = FG.details_for(_pupil(8, "8Q"))  # not set up: name only
    assert bare["form_tutor"] == "" and "8Q (Year 8)" in bare["form_details"]


@pytest.mark.parametrize("name", ["welcome_pupil", "record_updated"])
def test_templates_show_form_details(name):
    from education_system.systems.secondary.modules.communication.domain import email_templates
    _form("8K", 8, tutor_name="Ms Lee")
    values = {"pupil_first_name": "Ava", "pupil_name": "Ava Stone", "username": "u",
              "password": "p", "school_email": "a@s.org", "changes": "  - Form group",
              "updated_date": "3 November 2026", **FG.details_for(_pupil(8, "8K"))}
    _subject, body = email_templates.load_template(name).render(values)
    assert "Your form group:" in body and "8K (Year 8)" in body and "Ms Lee" in body
    # Callers that don't pass form values still render (defaults).
    values = {k: v for k, v in values.items() if not k.startswith("form")}
    assert "not set yet" in email_templates.load_template(name).render(values)[1]


def test_bulk_form_update_only_to_set_up_forms():
    from education_system.systems.secondary.modules.pupils.domain import bulk_import as B
    _form("8A", 8)
    a, b = _pupil(8, "8B"), _pupil(9, "9A")
    checks = {c.pupil.pupil_id: c for c in B.preview_update("form_group", "8A",
                                                            [a, b])}
    assert checks[a.pupil_id].changes and checks[a.pupil_id].after == "8A"
    assert "isn't set up" in checks[b.pupil_id].problem
    assert B.preview_update("form_group", "", [a])[0].after is None  # clearing is fine
