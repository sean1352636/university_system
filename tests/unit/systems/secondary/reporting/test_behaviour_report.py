"""Behaviour Report (modules.reporting.domain.behaviour_report) on a scratch DB."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.modules.reporting.domain import behaviour_report as BR
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")
LOGINS = [{"username": "ann", "display_name": "Ann Teacher", "email": "ann@school.org",
           "role": "teacher"}]
TODAY = dt.date.today()
MON = TODAY - dt.timedelta(days=TODAY.weekday()) - dt.timedelta(days=21)
FRI = MON + dt.timedelta(days=4)


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: LOGINS)
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=10, form="10A", **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female", "year_group": year,
        "form_group": form, "admission_date": "2024-09-01", **extra}, actor=ADMIN)


def _log(p, kind, day, time="10:15", points=None, actor=ADMIN):
    data = {"pupil_id": p.pupil_id, "incident_type": kind, "entry_date": day.isoformat(),
            "entry_time": time, "description": f"{kind} in class"}
    if points is not None:
        data["points"] = points
    return BH.log_incident(data, actor=actor)


def _detention(p, status):
    future = (TODAY + dt.timedelta(days=7 - TODAY.weekday())).isoformat()   # next Monday
    d = DT.create({"pupil_id": p.pupil_id, "detention_date": future, "reason": "Late work",
                   "detention_type": "Lunchtime", "start_time": "12:30"}, actor=ADMIN)
    with database.connect() as conn:     # the scratch DB: put it in the past to mark it
        conn.execute("UPDATE detentions SET detention_date = ? WHERE detention_id = ?",
                     (MON.isoformat(), d.detention_id))
    if status != "Scheduled":
        DT.set_status(d.detention_id, status, actor=ADMIN)
    return d


@pytest.fixture
def school():
    a, b, c = _pupil(), _pupil(), _pupil(year=8, form="8B")
    _log(a, "Achievement", MON, points=3)
    _log(a, "Helping others", FRI, time="14:05")
    _log(b, "Disruption", MON, points=-2)
    _log(b, "Defiance", MON + dt.timedelta(days=1), points=-5)
    _log(c, "Lateness", FRI, time="08:50")
    w = _log(c, "Uniform", FRI)
    BH.set_status(w.entry_id, "Withdrawn", actor=ADMIN)          # never counts
    _detention(b, "Attended")
    _detention(b, "Missed")
    _detention(c, "Missed")
    EX.create_case({"pupil_id": b.pupil_id, "start_date": MON.isoformat(),
                    "end_date": (MON + dt.timedelta(days=1)).isoformat(),
                    "reason": "Fighting", "reason_category": "Physical assault against a pupil",
                    "decision_maker": "Head"}, actor=ADMIN)
    return {"a": a, "b": b, "c": c}


def test_totals_and_rates(school):
    r = BR.build(ADMIN, MON, FRI)
    t = r.totals()
    assert (t["positive"], t["negative"]) == (2, 3)
    assert (t["positive_points"], t["negative_points"], t["net_points"]) == (4, -8, -4)
    assert t["pupils_on_roll"] == 3
    assert t["negative_per_100"] == 100.0 and t["positive_per_100"] == round(200 / 3, 2)
    assert (t["detentions_set"], t["detentions_attended"], t["detentions_missed"]) == (3, 1, 2)
    assert t["detention_attendance_pct"] == 33.0
    assert (t["suspensions"], t["suspension_days"], t["pupils_suspended"]) == (1, 2, 1)
    assert t["suspension_rate"] == round(100 / 3, 2)


def test_breakdowns_and_trend(school):
    r = BR.build(ADMIN, MON, FRI)
    by_type = {g["group"]: g for g in r.breakdown("type")}
    assert "Uniform" not in by_type and by_type["Defiance"]["negative_points"] == -5
    by_day = [g["group"] for g in r.breakdown("weekday")]
    assert by_day[0] == "Monday" and by_day[-1] == "Friday"
    by_hour = {g["group"]: g for g in r.breakdown("hour")}
    assert by_hour["10:00"]["positive"] + by_hour["10:00"]["negative"] == 3
    forms = {g["group"] for g in r.breakdown("form")}
    assert forms == {"10 10A", "8 8B"}
    with pytest.raises(BR.ValidationError):
        r.breakdown("colour")
    weeks = r.weeks()
    assert len(weeks) == 1 and weeks[0]["detentions"] == 3 and weeks[0]["suspensions"] == 1


def test_pupils_of_concern_and_filters(school):
    r = BR.build(ADMIN, MON, FRI)
    concern = r.concern()
    assert concern[0]["pupil_id"] == school["b"].pupil_id
    assert {c["pupil_id"] for c in concern} == {school["b"].pupil_id, school["c"].pupil_id}
    assert concern[0]["missed"] == 1 and concern[0]["suspension_days"] == 2
    r8 = BR.build(ADMIN, MON, FRI, year_group=8)
    assert r8.totals()["negative"] == 1 and r8.totals()["suspensions"] == 0
    rf = BR.build(ADMIN, MON, FRI, form="10A")
    assert rf.totals()["entries"] == 4
    text = BR.pupil_text(r, school["b"].pupil_id)
    assert "Defiance" in text and "Missed" in text


def test_export_and_access(school, scratch):
    r = BR.build(TEACHER, MON, FRI)
    path = scratch / "beh.csv"
    n = BR.export_csv(path, r, "breakdown", actor=TEACHER, by="staff")
    rows = list(csv.reader(open(path, encoding="utf-8")))
    assert rows[0][0] == "Member of staff" and n == len(rows) - 1
    for s in BR.SECTIONS:
        assert BR.table(r, s)[0]
    with pytest.raises(BR.PermissionDenied):
        BR.build(Principal(username="kid", role="student"))


def test_cli_menu(school, scratch, monkeypatch, capsys):
    from education_system.systems.secondary.modules.reporting.cli import behaviour_report_cli as M
    M._state.clear()
    answers = iter(["1", MON.isoformat(), FRI.isoformat(), "", "", "", "3", "1", "",
                    "5", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    M.menu(TEACHER)
    out = capsys.readouterr().out
    assert "Defiance" in out and "Pupils of concern" in out
