"""School Census (modules.reporting.domain.census) on a scratch DB."""

from __future__ import annotations

import csv
import datetime as dt
from xml.etree import ElementTree as ET

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.reporting.domain import census as CE
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")
YEAR = "2026/27"


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _upn(body: str) -> str:
    return P.upn_check_letter(body) + body


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2012-01-15", "gender": "Female", "year_group": 10,
        "form_group": "10A", "admission_date": "2024-09-01", **extra}, actor=ADMIN)


@pytest.fixture
def school():
    a = _pupil(upn=_upn("820123456789"), postcode="AB1 2CD", fsm_eligible=True)
    b = _pupil(sen_status="K", eal=True, gender="Male")
    c = _pupil(postcode="AB1 2CD", sen_status="E")
    SEN.save(c.pupil_id, {"primary_need": "ASD"}, actor=ADMIN)
    with database.connect() as conn:   # a malformed UPN from an old import (scratch DB)
        conn.execute("UPDATE pupils SET upn = 'A820123456780' WHERE pupil_id = ?",
                     (c.pupil_id,))
    gone = _pupil(postcode="AB1 2CD")
    P.update_pupil(gone.pupil_id, {"roll_status": "left", "leaving_date": "2026-07-20",
                                   "leaving_reason": "Moved away"}, actor=ADMIN)
    AT.record_mark(a.pupil_id, "2026-06-01", "AM", "I", actor=ADMIN)
    AT.record_mark(a.pupil_id, "2026-06-01", "PM", "\\", actor=ADMIN)
    AT.record_mark(a.pupil_id, "2026-06-02", "AM", "G", actor=ADMIN)
    EX.create_case({"pupil_id": b.pupil_id, "start_date": "2026-03-02",
                    "end_date": "2026-03-03", "reason": "Fight",
                    "reason_category": "Physical assault against a pupil",
                    "decision_maker": "Head"}, actor=ADMIN)
    EX.create_case({"pupil_id": a.pupil_id, "start_date": "2025-11-03",
                    "end_date": "2025-11-03", "reason": "Outside window",
                    "reason_category": "Damage", "decision_maker": "Head"}, actor=ADMIN)
    return {"a": a, "b": b, "c": c, "gone": gone}


def test_census_days_and_periods():
    assert CE.census_date("Autumn", YEAR) == dt.date(2026, 10, 1)
    assert CE.census_date("spring", YEAR) == dt.date(2027, 1, 21)
    assert CE.census_date("Summer", YEAR) == dt.date(2027, 5, 20)
    p = CE.periods("Autumn", YEAR)
    assert p["attendance_term"] == "Summer 2025/26" and p["attendance_from"] == "2026-04-06"
    assert p["exclusions_term"] == "Spring 2025/26" and p["exclusions_to"] == "2026-04-05"
    p = CE.periods("Summer", YEAR)
    assert p["attendance_term"] == "Spring 2026/27" and p["exclusions_term"] == "Autumn 2026/27"
    with pytest.raises(CE.ValidationError):
        CE.census_date("Winter", YEAR)


def test_build_fields_attendance_exclusions(school):
    ret = CE.build("Autumn", YEAR, actor=ADMIN)
    ids = {r["pupil_id"] for r in ret.pupils}
    assert ids == {school["a"].pupil_id, school["b"].pupil_id, school["c"].pupil_id}
    row = next(r for r in ret.pupils if r["pupil_id"] == school["a"].pupil_id)
    assert (row["gender"], row["fsm"], row["ncyear"], row["first_language"]) == \
        ("F", "Y", 10, "ENB")
    assert next(r for r in ret.pupils if r["pupil_id"] == school["b"].pupil_id)[
        "first_language"] == "OTB"
    assert next(r for r in ret.pupils if r["pupil_id"] == school["c"].pupil_id)[
        "sen_need_1"] == "ASD"
    att = next(x for x in ret.attendance if x["pupil_id"] == school["a"].pupil_id)
    assert (att["possible"], att["authorised"], att["unauthorised"]) == (3, 1, 1)
    assert att["codes"]["I"] == 1 and att["codes"]["G"] == 1
    assert [x["pupil_id"] for x in ret.exclusions] == [school["b"].pupil_id]
    x = ret.exclusions[0]
    assert (x["category"], x["sessions"], x["start_date"]) == ("SUSP", 4, "2026-03-02")
    c = ret.counts()
    assert (c["pupils"], c["sen_k"], c["sen_e"], c["fsm"], c["suspensions"]) == (3, 1, 1, 1, 1)


def test_validation_report(school):
    ret = CE.build("Autumn", YEAR, actor=ADMIN)
    by = {}
    for p in ret.problems:
        by.setdefault(p.pupil_id, []).append((p.severity, p.field, p.message))
    a, b, c = (by[school[k].pupil_id] for k in "abc")
    assert not any(f == "UPN" for _s, f, _m in a)
    assert ("Error", "UPN", "UPN missing") in b
    assert any(f == "UPN" and "check letter" in m for _s, f, m in c)
    assert any(f == "SEN need" for _s, f, _m in b)
    assert any(f == "EHC plan" for _s, f, _m in c)          # E, no plan reference
    assert any(f == "Postcode" for _s, f, _m in b)
    assert any(f == "First language" for _s, f, _m in b)
    assert all(any(f == "Ethnicity" for _s, f, _m in x) for x in (a, b, c))
    assert any(f == "Attendance" for _s, f, _m in b)        # no marks at all
    head, rows = CE.table(ret, "problems")
    assert rows[0][0] == "Error"


def test_runs_files_and_workflow(school, scratch):
    ret = CE.build("Autumn", YEAR, actor=ADMIN)
    rid = CE.save_run(ret, actor=ADMIN, notes="first try")
    run = CE.get_run(ADMIN, rid)
    assert (run["return_type"], run["status"], run["pupils"], run["errors"]) == \
        ("School Census - Autumn", "Draft", 3, len(ret.errors))
    assert "Pupil" not in str(run)                          # counts only, no pupil data
    assert CE.export_csv(ret, scratch / "c.csv", "attendance", actor=ADMIN) == len(
        ret.attendance)
    head = next(csv.reader(open(scratch / "c.csv", encoding="utf-8")))
    assert head[:4] == ["UPN", "Admission no", "Pupil", "Sessions possible"]
    CE.export_xml(ret, scratch / "c.xml", actor=ADMIN, laestab="1234567")
    root = ET.parse(scratch / "c.xml").getroot()
    assert root.find("Header/LAEstab").text == "1234567"
    assert len(root.findall("Pupils/Pupil")) == 3
    assert root.find("Pupils/Pupil/TermlyAttendance/SessionsPossible") is not None
    assert "xml" in CE.get_run(ADMIN, rid)["exported_as"]
    with pytest.raises(CE.ValidationError):
        CE.move(rid, "accept", actor=ADMIN)                 # not submitted yet
    for action, status in (("validate", "Validated"), ("submit", "Submitted"),
                           ("reject", "Rejected"), ("resubmit", "Resubmitted"),
                           ("accept", "Accepted")):
        assert CE.move(rid, action, actor=ADMIN)["status"] == status
    assert CE.get_run(ADMIN, rid)["accepted_on"]
    with pytest.raises(CE.ValidationError):
        CE.delete_return(rid, actor=ADMIN)
    other = CE.create_return({"return_type": "Workforce Census", "academic_year": YEAR,
                              "deadline": "2020-01-01"}, actor=ADMIN)
    assert CE.list_runs(ADMIN, overdue_only=True)[0]["return_id"] == other["return_id"]
    with pytest.raises(CE.ValidationError):
        CE.update_return(other["return_id"], {"window_opens": "2026-02-01",
                                              "window_closes": "2026-01-01"}, actor=ADMIN)
    assert CE.delete_return(other["return_id"], actor=ADMIN)
    s = CE.runs_summary(ADMIN)
    assert (s["total"], s["accepted"]) == (1, 1)


def test_only_data_managers(school):
    for call in (lambda: CE.build("Autumn", YEAR, actor=TEACHER),
                 lambda: CE.list_runs(TEACHER),
                 lambda: CE.create_return({"academic_year": YEAR}, actor=TEACHER)):
        with pytest.raises(CE.PermissionDenied):
            call()


def test_cli_menu(school, scratch, monkeypatch, capsys):
    from education_system.systems.secondary.modules.reporting.cli import census_cli as M
    M._state.clear()
    answers = iter(["32", "1", YEAR, "", "", "33", "", "37", "", "", "1", "", "12", "1", "",
                    "30", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    M.menu(ADMIN)
    out = capsys.readouterr().out
    assert "Autumn census 2026/27" in out and "UPN missing" in out
    assert "now Validated" in out and "Total" in out
    capsys.readouterr()
    answers2 = iter(["1", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers2))
    M.menu(TEACHER)
    assert "Only the data manager" in capsys.readouterr().out
