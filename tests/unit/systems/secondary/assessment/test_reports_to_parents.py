"""Reports to parents (domain.reports_to_parents)."""

from __future__ import annotations

import csv

import pytest

from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.assessment.domain import reports_to_parents as RP
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TUTOR = Principal(username="tutor1", role="teacher")
HEAD = Principal(username="head1", role="teacher")
OTHER = Principal(username="other1", role="teacher")
MUM = Principal(username="mum1", role="parent")
NAMES = {"tutor1": "ms tutor", "head1": "mr head", "other1": "mx other"}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    # Who's who without real logins: username -> name on the form / year group.
    monkeypatch.setattr(RP, "_me", lambda a: {a.username, NAMES.get(a.username, "")} - {""})
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "admission_date": "2021-09-01", **extra}, actor=ADMIN)


@pytest.fixture
def school():
    FG.create({"name": "10A", "year_group": 10, "tutor_name": "Ms Tutor"}, actor=ADMIN)
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    maths = S.create({"code": "MATH", "name": "Mathematics", "is_core": True}, actor=ADMIN)
    g = TG.create({"code": "10A/Ma", "subject_id": maths.subject_id, "year_group": 10},
                  actor=ADMIN)
    ava, ben = _pupil(form_group="10A", preferred_name="Ava"), _pupil(form_group="10A")
    TG.add_pupils([ava.pupil_id, ben.pupil_id], g.group_id, actor=ADMIN)
    pt = AP.create_point({"name": "Autumn", "year_groups": "10", "collect_comment": True,
                          "collect_homework": True}, actor=ADMIN)
    AP.set_status(pt.point_id, "Open", actor=ADMIN)
    AP.save_sheet(pt.point_id, g.group_id, {ava.pupil_id: {
        "working_at": "6", "predicted": "7", "attitude": 1, "homework": 2,
        "comment": "Ava works hard <and> asks good questions."}}, actor=ADMIN)
    TGR.upsert({"pupil": ava.admission_no, "subject": "MATH", "target_grade": "7"},
               actor=ADMIN)
    return {"ava": ava, "ben": ben, "point": pt, "group": g, "maths": maths}


def _cycle(school, **extra):
    return RP.create_cycle({"name": "Autumn report", "point_id": school["point"].point_id,
                            "include_hoy": True, **extra}, actor=ADMIN)


def _writing(school, **extra):
    c = _cycle(school, **extra)
    return RP.set_cycle_status(c.cycle_id, "Writing", actor=ADMIN)


def _publish(school):
    AP.set_status(school["point"].point_id, "Closed", actor=ADMIN)
    AP.set_status(school["point"].point_id, "Published", actor=ADMIN)


GOOD = "{first_name} has had a strong term and should be proud."


# ── Cycles ───────────────────────────────────────────────────────────

def test_cycle_rules(school):
    c = _cycle(school)
    assert c.years == (10,) and c.academic_year == school["point"].academic_year
    assert c.include_tutor and c.include_hoy and c.status == "Draft"
    with pytest.raises(RP.ValidationError):
        _cycle(school)  # same name, same year
    with pytest.raises(RP.ValidationError) as e:
        RP.create_cycle({"name": "Y8", "point_id": school["point"].point_id,
                         "year_groups": "8"}, actor=ADMIN)
    assert "doesn't cover" in e.value.problems[0]
    with pytest.raises(RP.ValidationError):
        RP.create_cycle({"name": "No point"}, actor=ADMIN)
    with pytest.raises(RP.PermissionDenied):
        RP.create_cycle({"name": "X", "point_id": school["point"].point_id}, actor=TUTOR)
    with pytest.raises(RP.ValidationError):
        RP.set_cycle_status(c.cycle_id, "Closed", actor=ADMIN)  # Draft -> Closed
    assert RP.update_cycle(c.cycle_id, {"year_groups": "10", "intro": "Hello"},
                           actor=ADMIN).intro == "Hello"
    assert RP.delete_cycle(c.cycle_id, actor=ADMIN)


# ── Comments ─────────────────────────────────────────────────────────

def test_who_writes_which_comment(school):
    ava = school["ava"]
    c = _cycle(school)
    with pytest.raises(RP.ValidationError):  # still Draft
        RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=TUTOR)
    RP.set_cycle_status(c.cycle_id, "Writing", actor=ADMIN)
    saved = RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=TUTOR)
    assert saved.startswith("Ava has had")
    with pytest.raises(RP.PermissionDenied):
        RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=OTHER)
    with pytest.raises(RP.PermissionDenied):
        RP.set_comment(c.cycle_id, ava.pupil_id, "hoy", GOOD, actor=TUTOR)
    RP.set_comment(c.cycle_id, ava.pupil_id, "hoy", GOOD, actor=HEAD)
    with pytest.raises(RP.ValidationError):
        RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", "Good.", actor=TUTOR)
    with pytest.raises(RP.ValidationError) as e:
        RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", "{nickname} did well this term.",
                       actor=TUTOR)
    assert "{nickname}" in e.value.problems[0]
    assert [p.pupil_id for p in RP.my_pupils(c.cycle_id, TUTOR)] == [
        ava.pupil_id, school["ben"].pupil_id]
    assert RP.my_pupils(c.cycle_id, OTHER) == []
    assert RP.set_comment(c.cycle_id, ava.pupil_id, "hoy", "", actor=HEAD) is None
    assert (ava.pupil_id, "hoy") not in RP.comments(c.cycle_id)


def test_comment_bank(school):
    b = RP.add_bank(GOOD, actor=TUTOR, kind="tutor", category="Praise")
    assert [x.bank_id for x in RP.bank("tutor")] == [b.bank_id]
    assert RP.bank("hoy") == []
    with pytest.raises(RP.ValidationError):
        RP.add_bank("{nickname} is lovely to teach every day.", actor=TUTOR)
    with pytest.raises(RP.PermissionDenied):
        RP.delete_bank(b.bank_id, actor=OTHER)
    assert RP.fill_placeholders(b.text, school["ava"]).startswith("Ava ")
    RP.delete_bank(b.bank_id, actor=TUTOR)
    assert RP.bank() == []


# ── Content, checking ────────────────────────────────────────────────

def test_content_and_problems(school):
    ava, ben = school["ava"], school["ben"]
    c = _writing(school)
    RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=TUTOR)
    got = RP.content(c.cycle_id, ava.pupil_id)
    [m] = got["subjects"]
    assert (m["subject"], m["working_at"], m["predicted"], m["target"], m["progress"],
            m["attitude"], m["homework"]) == ("Mathematics", "6", "7", "7", "Below", 1, 2)
    assert got["pupil"]["tutor"] == "Ms Tutor" and got["comments"]["tutor"].startswith("Ava")
    assert "No head of year comment" in RP.problems(c.cycle_id, ava.pupil_id)
    assert any("isn't published" in x for x in RP.problems(c.cycle_id, ava.pupil_id))
    assert "No grades in Autumn" in RP.problems(c.cycle_id, ben.pupil_id)
    text = RP.render_text(got)
    assert "Mathematics: working at 6, predicted 7, target 7 (Below)" in text
    page = RP.render_html(got)
    assert "&lt;and&gt;" in page and "<and>" not in page
    # Leaving subject comments out removes them.
    RP.update_cycle(c.cycle_id, {"include_subject_comments": False}, actor=ADMIN)
    assert "comment" not in RP.content(c.cycle_id, ava.pupil_id)["subjects"][0]


def test_ready_withhold_reset(school):
    ava, ben = school["ava"], school["ben"]
    c = _writing(school, include_hoy=False)
    RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=TUTOR)
    with pytest.raises(RP.PermissionDenied):
        RP.mark_ready(c.cycle_id, [ava.pupil_id], actor=TUTOR)
    res = RP.mark_ready(c.cycle_id, [ava.pupil_id, ben.pupil_id], actor=ADMIN)
    assert res["ready"] == 1 and list(res["skipped"]) == [ben.admission_no]
    with pytest.raises(RP.ValidationError):  # ready: comments are locked
        RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD + " More.", actor=TUTOR)
    RP.withhold(c.cycle_id, ben.pupil_id, "Court order", actor=ADMIN)
    assert RP.report_for(c.cycle_id, ben.pupil_id).status == "Withheld"
    assert RP.reset(c.cycle_id, ben.pupil_id, actor=ADMIN).status == "Draft"
    assert RP.mark_ready(c.cycle_id, [ben.pupil_id], actor=ADMIN, force=True)["ready"] == 1
    s = RP.summary(c.cycle_id)
    assert s["pupils"] == 2 and s["Ready"] == 2 and s["tutor_done"] == 1


# ── Issuing and families ─────────────────────────────────────────────

def _recipients(message_id):
    with database.connect() as conn:
        return sorted(r[0] for r in conn.execute(
            "SELECT address FROM email_recipients WHERE message_id = ?", (message_id,)))


def test_issue_freezes_emails_and_shows_families(school):
    ava, ben = school["ava"], school["ben"]
    C.add_contact(ava.pupil_id, {"full_name": "Mum", "relationship": "Mother",
                                 "email": "mum@example.org"}, actor=ADMIN)
    C.add_contact(ava.pupil_id, {"full_name": "Childminder", "relationship": "Other",
                                 "priority": 2, "email": "cm@example.org",
                                 "parental_responsibility": False}, actor=ADMIN)
    c = _writing(school, include_hoy=False)
    RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=TUTOR)
    RP.set_cycle_status(c.cycle_id, "Checking", actor=ADMIN)
    RP.mark_ready(c.cycle_id, [ava.pupil_id], actor=ADMIN)
    with pytest.raises(RP.ValidationError) as e:
        RP.issue(c.cycle_id, actor=ADMIN)
    assert "Publish Autumn first" in e.value.problems[0]
    _publish(school)
    res = RP.issue(c.cycle_id, actor=ADMIN)
    [rep] = res["issued"]
    assert rep.status == "Issued" and rep.version == 1
    assert _recipients(res["message_id"]) == ["mum@example.org"]  # parental responsibility only
    # Frozen: a later grade change doesn't alter what was sent.
    AP.set_status(school["point"].point_id, "Closed", actor=ADMIN)
    AP.save_sheet(school["point"].point_id, school["group"].group_id,
                  {ava.pupil_id: {"working_at": "3"}}, actor=ADMIN)
    assert RP.view(c.cycle_id, ava.pupil_id)["subjects"][0]["working_at"] == "6"
    assert RP.content(c.cycle_id, ava.pupil_id)["subjects"][0]["working_at"] == "3"
    # Families see only issued reports; a parent opening one is recorded.
    assert [r.report_id for _c, r in RP.for_family(ava.pupil_id)] == [rep.report_id]
    assert RP.for_family(ben.pupil_id) == []
    got = RP.family_view(rep.report_id, ava.pupil_id, principal=MUM)
    assert got["report"].view_count == 1 and got["report"].first_viewed_at
    with pytest.raises(RP.NotFound):
        RP.family_view(rep.report_id, ben.pupil_id, principal=MUM)
    assert RP.acknowledge(rep.report_id, ava.pupil_id, principal=MUM).acknowledged_by == "mum1"
    with pytest.raises(RP.ValidationError):
        RP.delete_cycle(c.cycle_id, actor=ADMIN)
    with pytest.raises(RP.ValidationError):
        RP.update_cycle(c.cycle_id, {"year_groups": "10, 11"}, actor=ADMIN)
    # Withdraw, correct, issue again as version 2.
    RP.withdraw(rep.report_id, "Wrong grade", actor=ADMIN)
    assert RP.for_family(ava.pupil_id) == []
    RP.mark_ready(c.cycle_id, [ava.pupil_id], actor=ADMIN)
    AP.set_status(school["point"].point_id, "Published", actor=ADMIN)
    again = RP.issue(c.cycle_id, [ava.pupil_id], actor=ADMIN, email=False)
    assert again["message_id"] is None and again["issued"][0].version == 2
    assert again["issued"][0].acknowledged_at is None
    assert RP.view(c.cycle_id, ava.pupil_id)["subjects"][0]["working_at"] == "3"
    assert [h["action"] for h in RP.history(c.cycle_id, pupil_id=ava.pupil_id)][:3] == [
        "issue", "ready", "withdraw"]


def test_issue_skips_unready_and_close(school):
    ava, ben = school["ava"], school["ben"]
    c = _writing(school, include_hoy=False, include_tutor=False)
    RP.set_cycle_status(c.cycle_id, "Checking", actor=ADMIN)
    _publish(school)
    with pytest.raises(RP.ValidationError):
        RP.issue(c.cycle_id, actor=ADMIN)  # nothing ready
    RP.mark_ready(c.cycle_id, [ava.pupil_id], actor=ADMIN)
    res = RP.issue(c.cycle_id, [ava.pupil_id, ben.pupil_id], actor=ADMIN)
    assert len(res["issued"]) == 1 and ben.admission_no in res["skipped"]
    assert res["no_email"] == [P.get_pupil(ava.pupil_id)]
    assert RP.set_cycle_status(c.cycle_id, "Closed", actor=ADMIN).status == "Closed"
    with pytest.raises(RP.ValidationError):
        RP.update_cycle(c.cycle_id, {"intro": "x"}, actor=ADMIN)


def test_progress_and_exports(school, tmp_path):
    ava = school["ava"]
    c = _writing(school)
    RP.set_comment(c.cycle_id, ava.pupil_id, "tutor", GOOD, actor=TUTOR)
    [g] = RP.progress(c.cycle_id)
    assert (g["form_group"], g["tutor"], g["pupils"], g["tutor_done"], g["hoy_done"],
            g["Draft"]) == ("10A", "Ms Tutor", 2, 1, 0, 2)
    path = tmp_path / "r.csv"
    assert RP.export_csv(c.cycle_id, path, actor=ADMIN) == 2
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert rows[0]["tutor_comment"] == "yes" and rows[1]["status"] == "Draft"
    out = tmp_path / "html"
    assert RP.export_html(c.cycle_id, out, actor=ADMIN) == 2
    files = sorted(out.iterdir())
    assert len(files) == 2 and "Mathematics" in files[0].read_text(encoding="utf-8")
    assert RP.for_pupil(ava.pupil_id) == []  # no report row until checked
