"""Exam results (domain.exam_results) on a temporary Secondary database."""

from __future__ import annotations

import csv
import datetime as dt
import re

import pytest

from education_system.systems.secondary import SYSTEM_KEY
from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="er_teach", role="teacher")
TODAY = dt.date.today()


@pytest.fixture
def env(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    # Releasing passes results on to sixth form applications on the
    # platform's post-16 board: keep that on a temp platform DB too.
    from education_system.platform.identity.auth import db as auth_db
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", str(tmp_path / "platform_auth.db"))
    initialise_auth_db(str(tmp_path / "platform_auth.db"))
    UserAuth(db_path=str(tmp_path / "auth.db")).provision_user(
        "er_teach", "Teach!ng-Pass-123", display_name="Ms Maths", email="m@s.org",
        systems=[(SYSTEM_KEY, "teacher")])
    monkeypatch.setattr(EE, "_today", lambda: TODAY)
    monkeypatch.setattr(ER, "_today", lambda: TODAY)
    ava, ben, cat = (P.create_pupil({
        "legal_first_name": n, "legal_last_name": "Exam", "date_of_birth": "2010-01-15",
        "gender": "Female", "year_group": 11, "admission_date": "2021-09-01"}, actor=ADMIN)
        for n in ("Ava", "Ben", "Cat"))
    maths = S.create({"code": "MATH", "name": "Maths", "is_core": True, "exam_board": "AQA",
                      "spec_code": "8300"}, actor=ADMIN)
    eng = S.create({"code": "ENGL", "name": "English Language", "is_core": True,
                    "exam_board": "AQA", "spec_code": "8700"}, actor=ADMIN)
    series = EE.create_series({"season": "June", "exam_year": TODAY.year + 1,
                               "entry_deadline": (TODAY + dt.timedelta(days=10)).isoformat(),
                               "late_deadline": (TODAY + dt.timedelta(days=40)).isoformat()},
                              actor=ADMIN)
    EE.specs_from_subjects(actor=ADMIN)
    mx = EE.update_spec(EE.find_spec("8300").spec_id, {
        "tiered": True, "foundation_code": "8300F", "higher_code": "8300H", "fee": 45},
        actor=ADMIN)
    en = EE.update_spec(EE.find_spec("8700").spec_id, {"fee": 40}, actor=ADMIN)
    EE.update_centre({"centre_number": "12345", "officer_name": "Mr Exams"}, actor=ADMIN)
    for p in (ava, ben, cat):
        EE.set_candidate(p.pupil_id, actor=ADMIN)

    def final(p, spec, **kw):
        return EE.create_entry({"series_id": series.series_id, "pupil_id": p.pupil_id,
                                "spec_id": spec.spec_id, "entry_status": "Final", **kw},
                               actor=ADMIN)
    e = {"ava_m": final(ava, mx, tier="Higher"), "ava_e": final(ava, en),
         "ben_m": final(ben, mx, tier="Foundation"), "ben_e": final(ben, en),
         "cat_e": final(cat, en)}
    yield {"ava": ava, "ben": ben, "cat": cat, "maths": maths, "eng": eng, "series": series,
           "sid": series.series_id, "e": e, "path": tmp_path, "mp": monkeypatch}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _record(env, key, grade, **kw):
    return ER.record_for_entry(env["e"][key].entry_id, grade, actor=ADMIN, **kw)


def _gcse(pupil):
    """What is stored in the GCSE record (embargoed rows too)."""
    with database.connect() as conn:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT s.code, g.grade FROM gcse_results g JOIN subjects s USING (subject_id) "
            "WHERE g.pupil_id = ?", (pupil.pupil_id,))}


def _cand(env, pupil):
    return EE.candidate(pupil.pupil_id).candidate_number


# ── Recording ────────────────────────────────────────────────────────

def test_import_all_or_nothing_then_unchanged(env):
    sid, path = env["sid"], env["path"] / "res.csv"
    a, b = _cand(env, env["ava"]), _cand(env, env["ben"])
    path.write_text("Candidate number,Entry code,Grade,Marks\n"
                    f"{a},8300H,7,180\n{b},8300H,5,\n9999,8700,4,\n{a},8700,10,\n")
    with pytest.raises(ER.ValidationError) as ex:
        ER.import_results(sid, path, actor=ADMIN)
    assert len(ex.value.problems) == 3  # wrong tier, unknown candidate, bad grade
    assert ER.list_results(series_id=sid) == []
    path.write_text("Candidate number,Entry code,Grade,Marks\n"
                    f"{a},8300H,7,180\n{b},8300F,5,\n{b},8700,4,\n")
    assert ER.import_results(sid, path, actor=ADMIN) == {"record": 3, "change": 0,
                                                         "unchanged": 0}
    assert ER.import_results(sid, path, actor=ADMIN)["unchanged"] == 3
    r = ER.get_for_entry(env["e"]["ava_m"].entry_id)
    assert (r.final_grade, r.marks_awarded, r.status) == ("7", 180, "Final")
    assert _gcse(env["ava"]) == {"MATH": "7"} and _gcse(env["ben"]) == {"MATH": "5", "ENGL": "4"}
    with pytest.raises(ER.PermissionDenied):
        ER.import_results(sid, path, actor=TEACHER)


def test_grade_and_status_validation(env):
    with pytest.raises(ER.ValidationError):
        _record(env, "ava_m", "10")
    with pytest.raises(ER.ValidationError):
        _record(env, "ava_m", "5-6")  # double grades are higher first
    with pytest.raises(ER.ValidationError):
        _record(env, "ava_m", "7", status="Pending")
    with pytest.raises(ER.ValidationError):
        _record(env, "ava_m", None, status="Final")
    with pytest.raises(ER.ValidationError):
        _record(env, "ava_m", "7", marks_awarded="90", max_marks="80")
    with pytest.raises(ER.ValidationError):
        _record(env, "ava_m", "8", status="Adjusted")  # only via a review
    p = _record(env, "ava_m", None)
    assert p.status == "Pending" and p.final_grade is None
    assert _record(env, "ava_m", "7").status == "Final"  # status follows the grade
    prov = EE.create_entry({"series_id": env["sid"], "pupil_id": env["cat"].pupil_id,
                            "spec_id": EE.find_spec("8300").spec_id, "tier": "Foundation"},
                           actor=ADMIN)
    with pytest.raises(ER.ValidationError):
        ER.record_for_entry(prov.entry_id, "4", actor=ADMIN)
    with pytest.raises(ER.PermissionDenied):
        ER.record_for_entry(env["e"]["ava_e"].entry_id, "6", actor=TEACHER)


def test_gcse_write_through_and_removal(env):
    ava = env["ava"]
    r = _record(env, "ava_e", "6")
    assert _gcse(ava) == {"ENGL": "6"}
    _record(env, "ava_e", None, status="Withheld")
    assert _gcse(ava) == {}
    _record(env, "ava_e", "5", status="Final")
    assert _gcse(ava) == {"ENGL": "5"}
    _record(env, "ava_e", "X")  # absent: no achieved grade
    assert _gcse(ava) == {}
    _record(env, "ava_e", "4")
    assert ER.delete(r.result_id, actor=ADMIN) and _gcse(ava) == {}
    assert ER.get_for_entry(env["e"]["ava_e"].entry_id) is None


def test_entry_cannot_change_once_resulted(env):
    eid = env["e"]["ava_m"].entry_id
    _record(env, "ava_m", "7")
    with pytest.raises(EE.ValidationError):
        EE.set_status(eid, "Withdrawn", actor=ADMIN)
    with pytest.raises(EE.ValidationError):
        EE.update_entry(eid, {"tier": "Foundation"}, actor=ADMIN)
    assert EE.get_entry(eid).entry_status == "Final"


def test_grade_sheet_all_or_nothing(env):
    e = env["e"]
    with pytest.raises(ER.ValidationError):
        ER.save_sheet(env["sid"], {e["ava_e"].entry_id: {"final_grade": "6"},
                                   e["cat_e"].entry_id: {"final_grade": "Q"}}, actor=ADMIN)
    assert ER.list_results(series_id=env["sid"]) == []
    n = ER.save_sheet(env["sid"], {e["ava_e"].entry_id: {"final_grade": "6"},
                                   e["cat_e"].entry_id: {"final_grade": "4"},
                                   e["ben_e"].entry_id: {"final_grade": ""}}, actor=ADMIN)
    assert n == 2 and len(ER.list_results(series_id=env["sid"])) == 2
    assert ER.save_sheet(env["sid"], {e["ava_e"].entry_id: {"final_grade": "6"}},
                         actor=ADMIN) == 0
    pending = ER.list_pending_for_entries(series_id=env["sid"])
    assert {x.entry_id for x in pending} == {e["ava_m"].entry_id, e["ben_m"].entry_id,
                                             e["ben_e"].entry_id}


# ── Embargo ──────────────────────────────────────────────────────────

def test_embargo_and_release(env):
    sid = env["sid"]
    with pytest.raises(ER.ValidationError):
        ER.release(sid, actor=ADMIN)  # nothing to release
    _record(env, "ava_m", "7")
    assert ER.list_results(series_id=sid, actor=TEACHER) == []
    assert len(ER.list_results(series_id=sid, actor=ADMIN)) == 1
    assert not ER.can_see(TEACHER, sid)
    for fn in (ER.headlines, ER.subject_analysis, ER.pupils_vs_target):
        with pytest.raises(ER.PermissionDenied):
            fn(sid, actor=TEACHER)
    with pytest.raises(ER.ValidationError):
        ER.send_slips(sid, actor=ADMIN)
    with pytest.raises(ER.PermissionDenied):
        ER.release(sid, actor=TEACHER)
    assert ER.release(sid, actor=ADMIN)["by"] == "admin2"
    assert len(ER.list_results(series_id=sid, actor=TEACHER)) == 1
    assert ER.headlines(sid, actor=TEACHER)["candidates"] == 1
    ER.release(sid, actor=ADMIN, on=False)
    assert ER.released(sid) is None and ER.list_results(series_id=sid, actor=TEACHER) == []


# ── Reviews of marking ───────────────────────────────────────────────

def test_review_rules(env):
    r = _record(env, "ava_m", "7", marks_awarded="150")
    with pytest.raises(ER.ValidationError):
        ER.request_review(r.result_id, {"service": "Review of marking"}, actor=ADMIN)
    v = ER.request_review(r.result_id, {"service": "Review of marking", "consent_by": "Ava",
                                        "fee": "45"}, actor=ADMIN)
    assert ER.get_result(r.result_id).status == "Remarked"
    with pytest.raises(ER.ValidationError):  # one open review at a time
        ER.request_review(r.result_id, {"service": "Clerical re-check", "consent_by": "Ava"},
                          actor=ADMIN)
    with pytest.raises(ER.ValidationError):  # grade can't be changed around the review
        _record(env, "ava_m", "8")
    with pytest.raises(ER.ValidationError):
        ER.record_outcome(v.review_id, "Grade raised", new_grade="6", actor=ADMIN)
    with pytest.raises(ER.ValidationError):
        ER.record_outcome(v.review_id, "Unchanged", new_grade="8", actor=ADMIN)
    ER.mark_submitted(v.review_id, actor=ADMIN)
    v = ER.record_outcome(v.review_id, "Grade raised", new_grade="8", new_marks="160",
                          actor=ADMIN)
    assert v.status == "Completed" and v.refunded and (v.grade_before, v.grade_after) == (
        "7", "8")
    r = ER.get_result(r.result_id)
    assert (r.status, r.final_grade, r.original_grade, r.marks_awarded) == (
        "Adjusted", "8", "7", 160)
    assert _gcse(env["ava"]) == {"MATH": "8"}
    with pytest.raises(ER.ValidationError):
        ER.delete(r.result_id, actor=ADMIN)
    v2 = ER.request_review(r.result_id, {"service": "Clerical re-check", "consent_by": "Ava"},
                           actor=ADMIN)
    ER.cancel_review(v2.review_id, actor=ADMIN, reason="changed mind")
    r = ER.get_result(r.result_id)
    assert r.status == "Adjusted" and r.original_grade == "7"
    with pytest.raises(ER.ValidationError):
        ER.cancel_review(v2.review_id, actor=ADMIN)
    with pytest.raises(ER.ValidationError):  # deadline already passed
        ER.request_review(r.result_id, {"service": "Clerical re-check", "consent_by": "Ava",
                                        "deadline": (TODAY - dt.timedelta(days=1)).isoformat()},
                          actor=ADMIN)


def test_lowered_and_unchanged_outcomes(env):
    r = _record(env, "ben_e", "5")
    v = ER.request_review(r.result_id, {"service": "Clerical re-check", "consent_by": "Ben"},
                          actor=ADMIN)
    with pytest.raises(ER.ValidationError):
        ER.record_outcome(v.review_id, "Grade lowered", new_grade="6", actor=ADMIN)
    ER.record_outcome(v.review_id, "Grade lowered", new_grade="4", actor=ADMIN)
    assert _gcse(env["ben"]) == {"ENGL": "4"}
    r2 = _record(env, "cat_e", "6")
    v = ER.request_review(r2.result_id, {"service": "Review of marking", "consent_by": "Cat"},
                          actor=ADMIN)
    v = ER.record_outcome(v.review_id, "Unchanged", actor=ADMIN)
    assert not v.refunded and ER.get_result(r2.result_id).status == "Final"


# ── Analysis, slips and the portal ───────────────────────────────────

def test_analysis(env):
    TGR.upsert({"pupil_id": env["ava"].pupil_id, "subject_id": env["maths"].subject_id,
                "target_grade": "6"}, actor=ADMIN)
    TGR.upsert({"pupil_id": env["ben"].pupil_id, "subject_id": env["eng"].subject_id,
                "target_grade": "5"}, actor=ADMIN)
    for key, g in (("ava_m", "8"), ("ava_e", "5"), ("ben_m", "3"), ("ben_e", "5"),
                   ("cat_e", "4")):
        _record(env, key, g)
    ER.release(env["sid"], actor=ADMIN)
    h = ER.headlines(env["sid"], actor=TEACHER)
    assert h["candidates"] == 3 and h["english_maths_4"] == 1 and h["english_maths_5"] == 1
    assert h["average"] == 5.0 and h["vs_target"] == {"above": 1, "met": 1}
    by = {x["code"]: x for x in ER.subject_analysis(env["sid"], actor=TEACHER)}
    assert by["MATH"]["average"] == 5.5 and by["MATH"]["pct_4"] == 50.0
    assert by["ENGL"]["vs_target"] == 0
    gaps = {x["name"]: x["average_gap"] for x in ER.pupils_vs_target(env["sid"],
                                                                     actor=TEACHER)}
    assert gaps[env["ava"].display_name] == 2 and gaps[env["cat"].display_name] is None
    s = ER.cohort_summary(series_id=env["sid"], actor=TEACHER)
    assert s["graded"] == 5 and s["pass_rate_pct"] == 80.0 and s["pending"] == 0


def test_slips_portal_export_and_privacy(env):
    ava = env["ava"]
    _record(env, "ava_m", "7")
    C.add_contact(ava.pupil_id, {"full_name": "Mum Exam", "relationship": "Mother",
                                 "email": "mum@home.org"}, actor=ADMIN)
    acct = PAC.create_for_pupil(ava.pupil_id, actor=ADMIN, send_welcome=False)
    me = Principal(acct.account.username, "student")
    assert PT.exams(me, ava.pupil_id)["results"] == []  # embargoed
    ER.release(env["sid"], actor=ADMIN)
    text = ER.slip_text(ER.slip(ava.pupil_id, env["sid"]))
    assert "Maths" in text and "7" in text and "awaited" in text.lower()  # English to come
    r = ER.send_slips(env["sid"], actor=ADMIN)
    assert r["emails"] == 2 and r["nobody"] == []
    with pytest.raises(ER.PermissionDenied):
        ER.send_slips(env["sid"], actor=TEACHER)
    d = PT.exams(me, ava.pupil_id)["results"]
    assert [x.final_grade for x in d[0]["results"]] == ["7"] and len(d[0]["awaited"]) == 1
    out = env["path"] / "out.csv"
    assert ER.export_results(env["sid"], out, actor=TEACHER) == 1
    with out.open(newline="") as f:
        assert next(csv.DictReader(f))["Grade"] == "7"
    log = (env["path"] / "activity.log").read_text()
    assert "exam.result.record" in log and not re.search(r"[\w.]+@[\w.]+", log)


def test_gcse_record_hides_embargoed_grades(env):
    ava, sid = env["ava"], env["sid"]
    _record(env, "ava_m", "7")
    assert _gcse(ava) == {"MATH": "7"}  # written through...
    assert G.for_pupil(ava.pupil_id) == [] and G.summary_line(ava.pupil_id) is None
    assert G.list_results() == [] and G.handover_list(ava.pupil_id) == []
    with pytest.raises(G.ValidationError) as ex:  # ...and can't be overwritten by hand
        G.record(ava.pupil_id, {"subject": "MATH", "grade": "9"}, actor=ADMIN)
    assert "under embargo" in ex.value.problems[0]
    G.record(ava.pupil_id, {"subject": "ENGL", "grade": "6"}, actor=ADMIN)  # not embargoed
    assert G.summary_line(ava.pupil_id) == "ENGL 6"
    ER.release(sid, actor=ADMIN)
    assert {g.subject_code: g.grade for g in G.for_pupil(ava.pupil_id)} == {"MATH": "7",
                                                                           "ENGL": "6"}
    assert G.summary(ava.pupil_id)["passes"] == 2
