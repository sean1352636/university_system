"""Teaching group rules (domain.teaching_groups) on a scratch school DB.

auth.db (for picking a teacher's login) and the activity log are redirected,
so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="tg_teacher", role="teacher")
DOB = {y: f"{2026 - y - 4}-01-15" for y in P.YEAR_GROUPS}  # age-right in 2026/27


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
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


@pytest.fixture
def maths():
    return S.create({"code": "MATH", "name": "Mathematics", "is_core": True}, actor=ADMIN)


def _group(subject, code="8x/Ma1", year=8, **extra):
    return TG.create({"code": code, "subject_id": subject.subject_id, "year_group": year,
                      **extra}, actor=ADMIN)


def _teacher_login(username="tg_teacher", name="Ms Teacher", email="teacher@school.org"):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.systems.secondary import SYSTEM_KEY
    UserAuth(db_path=accounts._override).provision_user(
        username, "Teach!ng-Pass-123", display_name=name, email=email,
        systems=[(SYSTEM_KEY, "teacher")])


# ── Setting up groups ────────────────────────────────────────────────

def test_create_defaults_to_this_year(maths):
    g = _group(maths, kind="set", set_number="1", room="M4", capacity="30")
    assert g.academic_year == TG.current_year() and g.is_current and g.is_active
    assert (g.kind, g.set_number, g.kind_label, g.room, g.capacity) == ("Set", 1, "Set 1",
                                                                         "M4", 30)
    assert [h["action"] for h in TG.history(g.group_id)] == ["create"]
    assert S.usage(maths.subject_id) == [("teaching group(s)", 1)]
    with pytest.raises(S.ValidationError, match="make it inactive"):
        S.delete(maths.subject_id, actor=ADMIN)


@pytest.mark.parametrize("extra, msg", [
    ({"code": ""}, "code is required"), ({"code": "x" * 21}, "20 characters"),
    ({"code": "8x;Ma"}, "letters, digits"), ({"year_group": 6}, "Year group"),
    ({"subject_id": 9999}, "Choose a subject"), ({"kind": "Stream"}, "Kind must be"),
    ({"kind": "Set"}, "set number"), ({"capacity": "41"}, "Capacity"),
    ({"lessons_per_week": "0"}, "Lessons per week"), ({"teacher_email": "x"}, "e-mail"),
    ({"kind": "Option"}, "Years 10 and 11"), ({"teacher_username": "nobody"}, "staff login"),
])
def test_bad_groups_refused(maths, extra, msg):
    data = {"code": "8x/Ma1", "subject_id": maths.subject_id, "year_group": 8, **extra}
    with pytest.raises(TG.ValidationError, match=msg):
        TG.create(data, actor=ADMIN)


def test_subject_must_be_active_and_taught_in_the_year(maths):
    sci = S.create({"code": "SCI", "name": "Science", "key_stage": "KS3"}, actor=ADMIN)
    with pytest.raises(TG.ValidationError, match="isn't taught in Year 10"):
        _group(sci, "10/Sc", 10)
    S.toggle_active(maths.subject_id, actor=ADMIN)
    with pytest.raises(TG.ValidationError, match="inactive"):
        _group(maths)


def test_code_unique_in_the_year_ignoring_case(maths):
    _group(maths, "8x/Ma1")
    with pytest.raises(TG.ValidationError, match="already a group"):
        _group(maths, "8X/MA1")


def test_teacher_login_fills_name_and_email(maths):
    _teacher_login()
    assert any(t["username"] == "tg_teacher" for t in TG.teacher_choices())
    g = _group(maths, teacher_username="TG_TEACHER")
    assert (g.teacher_username, g.teacher_name, g.teacher_email) == (
        "tg_teacher", "Ms Teacher", "teacher@school.org")
    assert [x.group_id for x in TG.list_groups(teacher="tg_teacher")] == [g.group_id]


def test_teacher_can_view_but_not_change(maths):
    g = _group(maths)
    p = _pupil(8)
    for call in (lambda: TG.create({"code": "8y", "subject_id": maths.subject_id,
                                     "year_group": 8}, actor=TEACHER),
                 lambda: TG.update(g.group_id, {"room": "A1"}, actor=TEACHER),
                 lambda: TG.archive(g.group_id, actor=TEACHER),
                 lambda: TG.delete(g.group_id, actor=TEACHER),
                 lambda: TG.add_pupils([p.pupil_id], g.group_id, actor=TEACHER),
                 lambda: TG.remove_pupils([p.pupil_id], g.group_id, actor=TEACHER),
                 lambda: TG.create_from_forms(maths.subject_id, 8, actor=TEACHER)):
        with pytest.raises(TG.PermissionDenied):
            call()
    assert TG.members(g.group_id) == [] and TG.list_groups()[0].room is None


def test_group_with_pupils_cannot_change_subject_or_year(maths):
    eng = S.create({"code": "ENG", "name": "English"}, actor=ADMIN)
    g = _group(maths)
    TG.add_pupils([_pupil(8).pupil_id], g.group_id, actor=ADMIN)
    with pytest.raises(TG.ValidationError, match="can't change subject or year"):
        TG.update(g.group_id, {"subject_id": eng.subject_id}, actor=ADMIN)
    g2, changed = TG.update(g.group_id, {"code": "8x/Ma2", "room": "M1"}, actor=ADMIN)
    assert changed == ["code", "room"] and g2.code == "8x/Ma2"


# ── Pupils ───────────────────────────────────────────────────────────

def test_add_rules(maths):
    g = _group(maths)
    ok, wrong_year, gone = _pupil(8), _pupil(9), _pupil(8)
    EN.record_leaver(gone.pupil_id, leaving_date=dt.date.today().isoformat(),
                     reason=EN.MOVED_SCHOOL, details={"destination_school": "Hilltop"},
                     actor=ADMIN)
    added, refused = TG.add_pupils([ok.pupil_id, wrong_year.pupil_id, gone.pupil_id, 99999,
                                    ok.pupil_id], g.group_id, actor=ADMIN)
    assert [p.pupil_id for p in added] == [ok.pupil_id]
    why = dict(refused)
    assert why[wrong_year.admission_no] == "in Year 9, not Year 8"
    assert why[P.get_pupil(gone.pupil_id).admission_no] == "not on roll"
    assert why["99999"] == "no such pupil"
    assert TG.add_pupils([ok.pupil_id], g.group_id, actor=ADMIN)[1] == [
        (ok.admission_no, "already in 8x/Ma1")]


def test_one_group_per_subject_unless_moved(maths):
    a, b = _group(maths, "8x/Ma1"), _group(maths, "8x/Ma2")
    eng = S.create({"code": "ENG", "name": "English"}, actor=ADMIN)
    e = _group(eng, "8x/En1")
    p = _pupil(8)
    TG.add_pupils([p.pupil_id], a.group_id, actor=ADMIN)
    TG.add_pupils([p.pupil_id], e.group_id, actor=ADMIN)  # other subject: fine
    assert TG.add_pupils([p.pupil_id], b.group_id, actor=ADMIN)[1] == [
        (p.admission_no, "already in 8x/Ma1 for this subject")]
    added, _ = TG.add_pupils([p.pupil_id], b.group_id, actor=ADMIN, move=True)
    assert len(added) == 1 and TG.members(a.group_id) == []
    assert [x.group.code for x in TG.groups_for_pupil(p.pupil_id)] == ["8x/En1", "8x/Ma2"]
    assert TG.history(a.group_id)[0]["action"] == "move_out"
    assert TG.history(b.group_id)[0]["action"] == "move_in"


def test_capacity(maths):
    g = _group(maths, capacity=1)
    a, b = _pupil(8), _pupil(8)
    with pytest.raises(TG.ValidationError, match="room for 1 more"):
        TG.add_pupils([a.pupil_id, b.pupil_id], g.group_id, actor=ADMIN)
    assert TG.members(g.group_id) == []
    added, _ = TG.add_pupils([a.pupil_id, b.pupil_id], g.group_id, actor=ADMIN,
                             allow_over_capacity=True)
    i = TG.info([g])[0]
    assert len(added) == 2 and i.pupils == 2 and i.spaces == -1


def test_remove_and_candidates(maths):
    a, b = _group(maths, "8x/Ma1"), _group(maths, "8x/Ma2")
    p, q, r = _pupil(8, "8K"), _pupil(8, "8P"), _pupil(8)
    TG.add_pupils([p.pupil_id], a.group_id, actor=ADMIN)
    TG.add_pupils([q.pupil_id], b.group_id, actor=ADMIN)
    assert [x.pupil_id for x, _o in TG.candidates(a.group_id)] == [r.pupil_id]
    with_grouped = dict((x.pupil_id, o) for x, o in TG.candidates(a.group_id,
                                                                  include_grouped=True))
    assert with_grouped == {q.pupil_id: "8x/Ma2", r.pupil_id: ""}
    assert TG.remove_pupils([p.pupil_id, q.pupil_id], a.group_id, actor=ADMIN) == 1
    assert TG.members(a.group_id) == []


def test_add_form_and_wrong_year_flag(maths):
    f = FG.create({"name": "8K", "year_group": 8}, actor=ADMIN)
    p1, p2 = _pupil(8, "8K"), _pupil(8, "8K")
    _pupil(8, "8P")
    g = _group(maths)
    added, _ = TG.add_form(f.form_id, g.group_id, actor=ADMIN)
    assert {p.pupil_id for p in added} == {p1.pupil_id, p2.pupil_id}
    P.update_pupil(p1.pupil_id, {"year_group": 9, "form_group": ""}, actor=ADMIN)
    assert [p.pupil_id for p in TG.wrong_year(g.group_id)] == [p1.pupil_id]


def test_leavers_drop_out_of_counts_but_stay_in_history(maths):
    g = _group(maths)
    p = _pupil(8)
    TG.add_pupils([p.pupil_id], g.group_id, actor=ADMIN)
    EN.record_leaver(p.pupil_id, leaving_date=dt.date.today().isoformat(),
                     reason=EN.MOVED_SCHOOL, details={"destination_school": "Hilltop"},
                     actor=ADMIN)
    assert TG.members(g.group_id) == [] and TG.info([g])[0].pupils == 0
    assert [x.pupil_id for x in TG.members(g.group_id, include_left=True)] == [p.pupil_id]


# ── Archive / delete / past years ────────────────────────────────────

def test_archive_empties_and_delete_only_if_never_used(maths):
    g = _group(maths)
    p = _pupil(8)
    TG.add_pupils([p.pupil_id], g.group_id, actor=ADMIN)
    with pytest.raises(TG.ValidationError, match="archive it instead"):
        TG.delete(g.group_id, actor=ADMIN)
    a = TG.archive(g.group_id, actor=ADMIN)
    assert a.status == "archived" and TG.members(g.group_id, include_left=True) == []
    assert TG.history(g.group_id)[0]["detail"] == {"pupils_removed": 1}
    assert TG.list_groups() == [] and len(TG.list_groups(include_archived=True)) == 1
    with pytest.raises(TG.ValidationError, match="Archived"):
        TG.update(g.group_id, {"room": "A1"}, actor=ADMIN)
    assert TG.restore(g.group_id, actor=ADMIN).is_active
    empty = _group(maths, "8x/Ma9")
    TG.delete(empty.group_id, actor=ADMIN)
    with pytest.raises(TG.NotFound):
        TG.get(empty.group_id)


def test_past_years_are_read_only(maths):
    with database.connect() as conn:
        gid = conn.execute("INSERT INTO teaching_groups (academic_year, code, subject_id, "
                           "year_group) VALUES ('2020/21', '7A/Ma', ?, 7)",
                           (maths.subject_id,)).lastrowid
    g = TG.get(gid)
    assert not g.is_current and TG.list_groups() == []
    assert [x.group_id for x in TG.list_groups(academic_year="2020/21")] == [gid]
    assert TG.academic_years() == [TG.current_year(), "2020/21"]
    for call in (lambda: TG.update(gid, {"room": "A"}, actor=ADMIN),
                 lambda: TG.archive(gid, actor=ADMIN),
                 lambda: TG.delete(gid, actor=ADMIN),
                 lambda: TG.add_pupils([_pupil(7).pupil_id], gid, actor=ADMIN)):
        with pytest.raises(TG.ValidationError, match="past years"):
            call()
    _group(maths, "7A/Ma", 7)  # the same code is free this year


# ── Bulk set-up and coverage ─────────────────────────────────────────

def test_create_from_forms(maths):
    FG.create({"name": "8K", "year_group": 8, "room": "B1"}, actor=ADMIN)
    FG.create({"name": "8P", "year_group": 8}, actor=ADMIN)
    k1, k2, p1 = _pupil(8, "8K"), _pupil(8, "8K"), _pupil(8, "8P")
    made, notes = TG.create_from_forms(maths.subject_id, 8, actor=ADMIN)
    assert sorted(g.code for g in made) == ["8K/MATH", "8P/MATH"] and notes == []
    k = TG.find("8k/math")
    assert k.room == "B1" and {p.pupil_id for p in TG.members(k.group_id)} == {
        k1.pupil_id, k2.pupil_id}
    again, notes = TG.create_from_forms(maths.subject_id, 8, actor=ADMIN)
    assert again == [] and "8K/MATH already exists" in notes
    assert TG.create_from_forms(maths.subject_id, 7, actor=ADMIN)[1] == [
        "Year 7 has no forms set up"]


def test_coverage_lists_core_pupils_without_a_group(maths):
    art = S.create({"code": "ART", "name": "Art"}, actor=ADMIN)  # not core
    S.set_lessons(maths.subject_id, {8: 4}, actor=ADMIN)
    g = _group(maths)
    _group(art, "8/Ar")
    a, b = _pupil(8), _pupil(8)
    _pupil(9)  # Y9 maths has no group and no lessons planned: not listed
    TG.add_pupils([a.pupil_id], g.group_id, actor=ADMIN)
    gaps = TG.coverage()
    assert [(s.code, y, [p.pupil_id for p in ps]) for s, y, ps in gaps] == [
        ("MATH", 8, [b.pupil_id])]


def test_export_class_list(tmp_path, maths):
    g = _group(maths, teacher_name="Mr Lee")
    TG.add_pupils([_pupil(8, preferred_name="@sum", sen_status="K").pupil_id], g.group_id,
                  actor=ADMIN)
    out = tmp_path / "g.csv"
    assert TG.export_class_list(g.group_id, out, actor=TEACHER) == 1
    rows = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert rows[0][:3] == ["Group 8x/Ma1", "Mathematics", "Year 8"]
    assert "SEN" not in rows[1] and rows[2][3] == "'@sum"
    with pytest.raises(TG.PermissionDenied):
        TG.export_class_list(g.group_id, out, actor=TEACHER, include_needs=True)
    TG.export_class_list(g.group_id, out, actor=ADMIN, include_needs=True)
    assert list(csv.reader(out.open(encoding="utf-8-sig")))[2][-3] == "K"
