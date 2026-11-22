"""Attendance Report (modules.reporting.domain.attendance_report) on a scratch DB."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.reporting.domain import attendance_report as AR
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")
PARENT = Principal(username="mum", role="parent")
TODAY = dt.date.today()
MON = TODAY - dt.timedelta(days=TODAY.weekday()) - dt.timedelta(days=21)
DAYS = [MON + dt.timedelta(days=i) for i in range(5)]


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


_n = 0


def _pupil(year=10, form="10A", **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female", "year_group": year,
        "form_group": form, "admission_date": "2024-09-01", **extra}, actor=ADMIN)


def _marks(p, codes):
    """codes: 10 codes, AM/PM for MON..FRI."""
    for i, code in enumerate(codes):
        day, session = DAYS[i // 2], ("AM", "PM")[i % 2]
        if code == "/" and session == "PM":
            code = "\\"
        AT.record_mark(p.pupil_id, day.isoformat(), session, code, actor=ADMIN)


@pytest.fixture
def school():
    a, b, c = _pupil(), _pupil(sen_status="K"), _pupil(gender="Male")
    d = _pupil(year=8, form="8B")
    _marks(a, ["/"] * 10)
    _marks(b, ["/"] * 5 + ["I", "I", "I", "O", "O"])
    _marks(c, ["/"] * 9 + ["G"])
    return {"a": a, "b": b, "c": c, "d": d}


def test_figures_bands_and_lists(school):
    r = AR.build(ADMIN, MON, DAYS[-1])
    assert r.school_days == 5
    o = r.overall
    assert (o.possible, o.attended, o.authorised, o.unauthorised) == (30, 24, 3, 3)
    assert o.unmarked == 10                         # pupil d has no marks
    assert o.attendance_pct == 80.0
    figs = {p.pupil_id: s for p, s in r.pupils}
    assert figs[school["b"].pupil_id].band == "severe"
    assert figs[school["c"].pupil_id].band == "persistent"
    assert figs[school["a"].pupil_id].band == ""
    assert {p.pupil_id for p, _s in r.persistent} == {school["b"].pupil_id,
                                                       school["c"].pupil_id}
    assert [p.pupil_id for p, _s in r.severe] == [school["b"].pupil_id]
    summary = dict(r.dfe_summary())
    assert summary["Possible sessions"] == 30
    assert summary["Authorised absence rate %"] == 10.0
    assert summary["Persistent absence rate %"] == round(100 * 2 / 3, 1)


def test_codes_weekdays_weeks_and_groups(school):
    r = AR.build(ADMIN, MON, DAYS[-1])
    codes = {c["code"]: c for c in r.by_code}
    assert codes["I"]["sessions"] == 3 and codes["O"]["pupils"] == 1
    assert codes["G"]["category"] == "Unauthorised absence"
    fri_pm = next(w for w in r.by_weekday if w["weekday"] == "Friday" and w["session"] == "PM")
    assert (fri_pm["possible"], fri_pm["attended"]) == (3, 1)   # a present, b O, c G
    assert len(r.by_week) == 1 and r.by_week[0]["week"] == MON.isoformat()
    groups = {g.group: g for g in r.groups}
    assert groups["SEN support (K)"].persistent == 1
    assert groups["Male"].summary.possible == 10
    years = {g.group: g for g in r.years}
    assert years["Year 10"].pupils == 3 and years["Year 8"].pupils == 0


def test_filters_and_drill_down(school):
    r = AR.build(ADMIN, MON, DAYS[-1], year_group=8)
    assert r.scope == "Year 8" and [p.pupil_id for p, _ in r.pupils] == [school["d"].pupil_id]
    r = AR.build(ADMIN, MON, DAYS[-1], form="10A")
    assert len(r.pupils) == 3
    d = AR.pupil_detail(ADMIN, school["b"].pupil_id, MON, DAYS[-1])
    assert d["summary"].attendance_pct == 50.0 and len(d["absences"]) == 5
    assert "severe" in AR.pupil_text(d)
    with pytest.raises(AR.NotFound):
        AR.pupil_detail(ADMIN, 99999)


def test_leaver_counts_only_while_on_roll(school):
    P.update_pupil(school["a"].pupil_id, {"roll_status": "left",
                                          "leaving_date": DAYS[1].isoformat(),
                                          "leaving_reason": "Moved away"}, actor=ADMIN)
    r = AR.build(ADMIN, MON, DAYS[-1])
    figs = {p.pupil_id: s for p, s in r.pupils}
    assert school["a"].pupil_id in figs                 # still in the range
    assert figs[school["a"].pupil_id].unmarked == 0


def test_rules_and_export(school, scratch):
    with pytest.raises(AR.PermissionDenied):
        AR.build(PARENT)
    with pytest.raises(AR.ValidationError):
        AR.build(ADMIN, DAYS[-1], MON)
    r = AR.build(TEACHER, MON, DAYS[-1])
    path = scratch / "pa.csv"
    assert AR.export_csv(path, r, "persistent", actor=TEACHER) == 2
    rows = list(csv.reader(open(path, encoding="utf-8")))
    assert rows[0][0] == "Admission no" and len(rows) == 3
    for section in AR.SECTIONS:
        head, _rows = AR.table(r, section)
        assert head
    with pytest.raises(AR.ValidationError):
        AR.table(r, "nope")
    log = (scratch / "activity.log").read_text()
    assert "attendance_report.export" in log and "Pupil1" not in log


def test_cli_menu(school, scratch, monkeypatch, capsys):
    from education_system.systems.secondary.modules.reporting.cli import attendance_report_cli as M
    M._state.clear()
    answers = iter(["1", MON.isoformat(), DAYS[-1].isoformat(), "", "", "", "4", "",
                    "13", "3", str(scratch / "cli.csv"), "", "99", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    M.menu(TEACHER)
    out = capsys.readouterr().out
    assert "Persistent absence" in out and "Exported 2 row(s)" in out
