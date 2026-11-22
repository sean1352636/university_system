"""Exam entries (domain.exam_entries) on a temporary Secondary database."""

from __future__ import annotations

import csv
import datetime as dt
import re

import pytest

from education_system.systems.secondary import SYSTEM_KEY
from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ee_teach", role="teacher")
OTHER = Principal(username="other", role="teacher")
TODAY = dt.date.today()


@pytest.fixture
def env(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    UserAuth(db_path=str(tmp_path / "auth.db")).provision_user(
        "ee_teach", "Teach!ng-Pass-123", display_name="Ms Maths", email="m@s.org",
        systems=[(SYSTEM_KEY, "teacher")])
    monkeypatch.setattr(EE, "_today", lambda: TODAY)
    ava, ben, cat = (P.create_pupil({
        "legal_first_name": n, "legal_last_name": "Exam", "date_of_birth": "2010-01-15",
        "gender": "Female", "year_group": 11, "admission_date": "2021-09-01"}, actor=ADMIN)
        for n in ("Ava", "Ben", "Cat"))
    maths = S.create({"code": "MATH", "name": "Maths", "is_core": True, "exam_board": "AQA",
                      "spec_code": "8300"}, actor=ADMIN)
    eng = S.create({"code": "ENGL", "name": "English Language", "is_core": True,
                    "exam_board": "AQA", "spec_code": "8700"}, actor=ADMIN)
    g = TG.create({"code": "11x/Ma1", "subject_id": maths.subject_id, "year_group": 11,
                   "teacher_username": "ee_teach"}, actor=ADMIN)
    TG.add_pupils([ava.pupil_id, ben.pupil_id], g.group_id, actor=ADMIN)
    g2 = TG.create({"code": "11x/En1", "subject_id": eng.subject_id, "year_group": 11},
                   actor=ADMIN)
    TG.add_pupils([ava.pupil_id, ben.pupil_id, cat.pupil_id], g2.group_id, actor=ADMIN)
    series = EE.create_series({"season": "June", "exam_year": TODAY.year + 1,
                               "entry_deadline": (TODAY + dt.timedelta(days=10)).isoformat(),
                               "late_deadline": (TODAY + dt.timedelta(days=40)).isoformat()},
                              actor=ADMIN)
    EE.specs_from_subjects(actor=ADMIN)
    mx = EE.update_spec(EE.find_spec("8300").spec_id, {
        "tiered": True, "foundation_code": "8300F", "higher_code": "8300H", "fee": 45.5,
        "late_fee": 90}, actor=ADMIN)
    en = EE.update_spec(EE.find_spec("8700").spec_id, {"fee": 40, "late_fee": 60},
                        actor=ADMIN)
    EE.update_centre({"centre_number": "12345", "officer_name": "Mr Exams"}, actor=ADMIN)
    yield {"ava": ava, "ben": ben, "cat": cat, "maths": maths, "eng": eng, "series": series,
           "mx": mx, "en": en, "path": tmp_path, "mp": monkeypatch}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _entry(env, pupil, spec, **kw):
    return EE.create_entry({"series_id": env["series"].series_id, "pupil_id": pupil.pupil_id,
                            "spec_id": spec.spec_id, **kw}, actor=ADMIN)


def _days(env, n):
    env["mp"].setattr(EE, "_today", lambda: TODAY + dt.timedelta(days=n))


# ── Set-up ───────────────────────────────────────────────────────────

def test_series_and_spec_rules(env):
    s = env["series"]
    assert s.name == f"June {TODAY.year + 1}" and EE.deadline_state(s) == "standard"
    with pytest.raises(EE.ValidationError):
        EE.create_series({"season": "June", "exam_year": TODAY.year + 1}, actor=ADMIN)  # dup
    with pytest.raises(EE.ValidationError):
        EE.create_series({"exam_year": 2030, "entry_deadline": "2030-03-01",
                          "late_deadline": "2030-02-01"}, actor=ADMIN)
    with pytest.raises(EE.PermissionDenied):
        EE.create_series({"exam_year": 2031}, actor=TEACHER)
    assert env["mx"].code_for("Higher") == "8300H" and env["en"].code_for("N/A") == "8700"
    with pytest.raises(EE.ValidationError):  # tiered needs both codes
        EE.create_spec({"subject_id": env["maths"].subject_id, "exam_board": "OCR",
                        "spec_code": "J560", "tiered": True}, actor=ADMIN)
    _entry(env, env["ava"], env["en"])
    with pytest.raises(EE.ValidationError):  # in use: board can't change
        EE.update_spec(env["en"].spec_id, {"exam_board": "OCR"}, actor=ADMIN)
    with pytest.raises(EE.ValidationError):
        EE.delete_spec(env["en"].spec_id, actor=ADMIN)
    with pytest.raises(EE.ValidationError):
        EE.delete_series(env["series"].series_id, actor=ADMIN)


def test_candidate_numbers(env):
    c = EE.set_candidate(env["ava"].pupil_id, actor=ADMIN)
    assert c.candidate_number == "0001"
    assert EE.set_candidate(env["ben"].pupil_id, actor=ADMIN).candidate_number == "0002"
    with pytest.raises(EE.ValidationError):  # taken
        EE.set_candidate(env["cat"].pupil_id, candidate_number="0001", actor=ADMIN)
    with pytest.raises(EE.ValidationError):
        EE.set_candidate(env["cat"].pupil_id, candidate_number="12", uci="short",
                         actor=ADMIN)
    with pytest.raises(EE.PermissionDenied):
        EE.set_candidate(env["cat"].pupil_id, actor=TEACHER)
    assert EE.assign_numbers([p.pupil_id for p in (env["ava"], env["cat"])],
                             actor=ADMIN) == 1


# ── Entries ──────────────────────────────────────────────────────────

def test_generate_uses_groups_and_mock_tiers(env):
    ms = MX.create_series({"name": "Y11 Nov", "year_group": 11, "start_date": TODAY.isoformat(),
                           "end_date": TODAY.isoformat()}, actor=ADMIN)
    MX.set_tiers(ms.series_id, env["maths"].subject_id, {env["ava"].pupil_id: "Higher"},
                 actor=ADMIN)
    r = EE.generate(env["series"].series_id, 11, actor=ADMIN)
    assert r["created"] == 5 and r["tiers"] == 1  # 2 maths + 3 English
    assert EE.generate(env["series"].series_id, 11, actor=ADMIN)["created"] == 0
    tiers = {(e.pupil_id, e.subject_code): e.tier
             for e in EE.list_entries(series_id=env["series"].series_id)}
    assert tiers[(env["ava"].pupil_id, "MATH")] == "Higher"
    assert tiers[(env["ben"].pupil_id, "MATH")] == "N/A"
    assert all(e.entry_status == "Provisional"
               for e in EE.list_entries(series_id=env["series"].series_id))


def test_entry_validation(env):
    _entry(env, env["ava"], env["mx"], tier="Higher")
    with pytest.raises(EE.ValidationError):  # same spec twice
        _entry(env, env["ava"], env["mx"], tier="Higher")
    with pytest.raises(EE.ValidationError):  # untiered spec with a tier
        _entry(env, env["ben"], env["en"], tier="Higher")
    with pytest.raises(EE.ValidationError):
        _entry(env, env["ben"], env["mx"], tier="Middle")
    with pytest.raises(EE.ValidationError):  # Final needs a candidate number
        _entry(env, env["ben"], env["en"], entry_status="Final")
    with pytest.raises(EE.PermissionDenied):
        EE.create_entry({"series_id": env["series"].series_id,
                         "pupil_id": env["ben"].pupil_id, "spec_id": env["en"].spec_id},
                        actor=TEACHER)


def test_final_needs_tier_and_number_and_finalise_reports(env):
    a = _entry(env, env["ava"], env["mx"], tier="Higher")
    b = _entry(env, env["ben"], env["mx"])  # no tier yet
    EE.assign_series_numbers(env["series"].series_id, actor=ADMIN)
    r = EE.finalise(env["series"].series_id, actor=ADMIN)
    assert r["made"] == 1 and [e.entry_id for e, _why in r["skipped"]] == [b.entry_id]
    a = EE.get_entry(a.entry_id)
    assert a.entry_status == "Final" and a.fee == 45.5 and not a.late
    assert a.entry_code == "8300H"


def test_teacher_sets_tier_only_for_own_provisional_pupils(env):
    e = _entry(env, env["ben"], env["mx"])
    with pytest.raises(EE.PermissionDenied):
        EE.set_tier(e.entry_id, "Foundation", actor=OTHER)
    assert EE.set_tier(e.entry_id, "Foundation", actor=TEACHER).tier == "Foundation"
    EE.set_candidate(env["ben"].pupil_id, actor=ADMIN)
    EE.set_status(e.entry_id, "Final", actor=ADMIN)
    with pytest.raises(EE.PermissionDenied):
        EE.set_tier(e.entry_id, "Higher", actor=TEACHER)


def test_fees_late_withdraw_refund_and_manual(env):
    for p in (env["ava"], env["ben"]):
        EE.set_candidate(p.pupil_id, actor=ADMIN)
    w = _entry(env, env["ava"], env["en"], entry_status="Final")
    w = EE.set_status(w.entry_id, "Withdrawn", actor=ADMIN)
    assert w.fee == 0.0  # withdrawn by the entry deadline
    _days(env, 20)  # after the entry deadline
    late = _entry(env, env["ben"], env["en"], entry_status="Final")
    assert late.late and late.fee == 60
    late2 = EE.set_status(late.entry_id, "Withdrawn", actor=ADMIN)
    assert late2.fee == 60  # withdrawn late: still charged
    m = EE.update_entry(late.entry_id, {"fee": "12.50", "fee_payer": "Parent"}, actor=ADMIN)
    assert m.fee == 12.5 and m.fee_manual and m.fee_payer == "Parent"
    m = EE.update_entry(late.entry_id, {"fee": ""}, actor=ADMIN)
    assert m.fee == 60 and not m.fee_manual
    s = EE.cohort_summary(series_id=env["series"].series_id)
    assert s["billed"] == 60 and s["late"] == 1
    _days(env, 50)  # after the late deadline
    with pytest.raises(EE.ValidationError):
        _entry(env, env["ava"], env["mx"], tier="Higher", entry_status="Final")


def test_status_moves_and_delete(env):
    EE.set_candidate(env["ava"].pupil_id, actor=ADMIN)
    e = _entry(env, env["ava"], env["en"])
    with pytest.raises(EE.ValidationError):  # Provisional -> Withdrawn isn't a move
        EE.set_status(e.entry_id, "Withdrawn", actor=ADMIN)
    EE.set_status(e.entry_id, "Final", actor=ADMIN)
    with pytest.raises(EE.ValidationError):
        EE.delete(e.entry_id, actor=ADMIN)
    EE.set_status(e.entry_id, "Provisional", actor=ADMIN)  # never sent: allowed
    EE.set_status(e.entry_id, "Cancelled", actor=ADMIN)
    assert EE.delete(e.entry_id, actor=ADMIN)


# ── Board files ──────────────────────────────────────────────────────

def test_board_file_new_amend_withdraw(env):
    for p in (env["ava"], env["ben"]):
        EE.set_candidate(p.pupil_id, actor=ADMIN)
    a = _entry(env, env["ava"], env["mx"], tier="Higher", entry_status="Final")
    b = _entry(env, env["ben"], env["en"], entry_status="Final")
    path = env["path"] / "aqa.csv"
    assert EE.export_board_file(env["series"].series_id, "AQA", path, actor=ADMIN) == 2
    rows = list(csv.DictReader(open(path)))
    assert {r["Action"] for r in rows} == {"New"} and rows[0]["Centre number"] == "12345"
    assert EE.unsent_by_board(env["series"].series_id) == {}
    with pytest.raises(EE.ValidationError):  # nothing new
        EE.export_board_file(env["series"].series_id, "AQA", path, actor=ADMIN)
    with pytest.raises(EE.ValidationError):  # sent: can't go back to Provisional
        EE.set_status(a.entry_id, "Provisional", actor=ADMIN)
    EE.update_entry(a.entry_id, {"tier": "Foundation"}, actor=ADMIN)
    assert EE.get_entry(a.entry_id).unsent
    EE.update_entry(a.entry_id, {"tier": "Higher"}, actor=ADMIN)  # back as sent
    assert not EE.get_entry(a.entry_id).unsent
    EE.update_entry(a.entry_id, {"tier": "Foundation"}, actor=ADMIN)
    EE.set_status(b.entry_id, "Withdrawn", actor=ADMIN)
    EE.export_board_file(env["series"].series_id, "AQA", path, actor=ADMIN)
    acts = {(r["Entry code"], r["Action"]) for r in csv.DictReader(open(path))}
    assert acts == {("8300F", "Amend"), ("8700", "Withdraw")}
    with pytest.raises(EE.ValidationError):  # number can't change once sent
        EE.set_candidate(env["ava"].pupil_id, candidate_number="0099", actor=ADMIN)


def test_board_file_needs_centre_and_close_needs_everything_sent(env):
    EE.set_candidate(env["ava"].pupil_id, actor=ADMIN)
    _entry(env, env["ava"], env["en"], entry_status="Final")
    with pytest.raises(EE.ValidationError):
        EE.set_series_status(env["series"].series_id, "Closed", actor=ADMIN)
    EE.update_centre({"centre_number": ""}, actor=ADMIN)
    with pytest.raises(EE.ValidationError):
        EE.export_board_file(env["series"].series_id, "AQA", env["path"] / "x.csv",
                             actor=ADMIN)


# ── Checks, statements, portal, CSV ──────────────────────────────────

def test_checks(env):
    _entry(env, env["ben"], env["mx"])
    texts = [c["text"] for c in EE.checks(env["series"].series_id, year_group=11)]
    assert any("no candidate number" in t for t in texts)
    assert any("no tier chosen" in t for t in texts)
    assert any("taught it but not entered" in t for t in texts)


def test_statements_portal_and_privacy(env):
    ava = env["ava"]
    EE.set_candidate(ava.pupil_id, actor=ADMIN)
    _entry(env, ava, env["mx"], tier="Higher", entry_status="Final")
    _entry(env, ava, env["en"])  # provisional: not on the statement
    C.add_contact(ava.pupil_id, {"full_name": "Mum Exam", "relationship": "Mother",
                                 "email": "mum@home.org"}, actor=ADMIN)
    acct = PAC.create_for_pupil(ava.pupil_id, actor=ADMIN, send_welcome=False)
    text = EE.statement_text(EE.statement(ava.pupil_id, env["series"].series_id))
    assert "8300H" in text and "8700" not in text
    r = EE.send_statements(env["series"].series_id, actor=ADMIN)
    assert r["emails"] == 2 and r["nobody"] == []
    with pytest.raises(EE.PermissionDenied):
        EE.send_statements(env["series"].series_id, actor=TEACHER)
    d = PT.exams(Principal(acct.account.username, "student"), ava.pupil_id)
    assert [e.entry_code for e in d["statements"][0]["entries"]] == ["8300H"]
    with pytest.raises(PT.PermissionDenied):
        PT.exams(Principal(acct.account.username, "student"), env["ben"].pupil_id)
    log = (env["path"] / "activity.log").read_text()
    assert not re.search(r"[\w.]+@[\w.]+", log)


def test_import_all_or_nothing(env):
    s = env["series"].series_id
    bad = env["path"] / "bad.csv"
    bad.write_text("Admission no,Spec code,Tier\n"
                   f"{env['cat'].admission_no},8300F,\nSEC999999,XXXX,\n,,\n")
    with pytest.raises(EE.ValidationError) as ex:
        EE.import_entries(s, bad, actor=ADMIN)
    assert len(ex.value.problems) == 2 and EE.list_entries(series_id=s) == []
    good = env["path"] / "good.csv"
    good.write_text(f"Admission no,Spec code,Notes\n{env['cat'].admission_no},8300F,resit\n")
    assert EE.import_entries(s, good, actor=ADMIN) == 1
    e = EE.list_entries(series_id=s)[0]
    assert e.tier == "Foundation" and e.notes == "resit"
    out = env["path"] / "out.csv"
    assert EE.export_entries(s, out, actor=TEACHER) == 1
