"""The audit log viewer (modules.administration.domain.audit_log)."""

from __future__ import annotations

import csv

import pytest

from education_system.systems.secondary.modules.administration.domain import audit_log as AL
from education_system.systems.secondary.modules.administration.domain import settings as ST
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")


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


def _seed():
    p = P.create_pupil({"legal_first_name": "Ava", "legal_last_name": "Stone",
                        "date_of_birth": "2012-03-04", "gender": "Female", "year_group": 9,
                        "admission_date": "2023-09-01"}, actor=ADMIN)
    P.update_pupil(p.pupil_id, {"form_group": "9B"}, actor=ADMIN)
    with pytest.raises(P.PermissionDenied):
        P.update_pupil(p.pupil_id, {"form_group": "9C"}, actor=ANN)
    ST.set_setting("school_name", "Oak Hill", actor=ADMIN)
    activity_log.record("menu.open", target="Audit Log", outcome="denied", principal=ANN)
    return p


def test_parse_line_round_trip(tmp_path):
    activity_log.record("pupil.update", target="SEC000004", principal=ADMIN,
                        fields="form_group,year_group")
    line = (tmp_path / "activity.log").read_text().splitlines()[-1]
    e = AL.parse_line(line, 1)
    assert (e.user, e.role, e.action, e.target, e.outcome) == (
        "admin2", "admin", "pupil.update", "SEC000004", "ok")
    assert e.detail == {"fields": "form_group,year_group"} and e.area == "pupil"
    assert AL.parse_line("rubbish") is None


def test_tables_are_discovered_and_merged():
    p = _seed()
    tables = AL.audit_tables()
    assert {"pupil_audit", "settings_audit", "exclusion_audit"} <= set(tables)
    page = AL.search(actor=ADMIN)
    sources = {e.source for e in page.entries}
    assert {AL.ACTIVITY, "pupil_audit", "settings_audit"} <= sources
    # newest first
    assert [e.at for e in page.entries] == sorted((e.at for e in page.entries), reverse=True)
    rows = AL.search({"area": "pupil_audit"}, actor=ADMIN).entries
    assert {e.action for e in rows} == {"create", "update"}
    assert all(e.target == str(p.pupil_id) for e in rows)
    by_target = AL.search({"target": p.admission_no}, actor=ADMIN).entries
    assert by_target and all(e.source == AL.ACTIVITY for e in by_target)
    assert AL.search({"target": str(p.pupil_id), "area": "pupil_audit"}, actor=ADMIN).total == 2


def test_filters_paging_failures_and_summary():
    _seed()
    assert AL.search({"user": "ann"}, actor=ADMIN).total >= 2
    assert all(e.action.startswith("pupil.")
               for e in AL.search({"action": "pupil."}, actor=ADMIN).entries)
    fails = AL.failures(actor=ADMIN).entries
    assert fails and all(e.failed for e in fails)
    assert {e.outcome for e in fails} == {"denied"}
    p1 = AL.search(actor=ADMIN, page=1, page_size=2)
    p2 = AL.search(actor=ADMIN, page=2, page_size=2)
    assert len(p1.entries) == 2 and p1.pages >= 2 and p1.entries[0] != p2.entries[0]
    s = AL.summary(actor=ADMIN)
    assert s["failed"] >= 2 and dict(s["by_user"])["ann"] >= 2
    with pytest.raises(AL.ValidationError):
        AL.search({"date_from": "2026-02-30"}, actor=ADMIN)
    assert AL.search({"date_from": "2999-01-01"}, actor=ADMIN).total == 0
    assert "admin2" in AL.users() and AL.ACTIVITY in AL.areas()


def test_detail_and_csv_export(tmp_path):
    _seed()
    e = AL.search({"area": "settings_audit"}, actor=ADMIN).entries[0]
    full = AL.get_entry(e.source, e.row_id, actor=ADMIN)
    assert full.detail["new_value"] == "Oak Hill"
    with pytest.raises(AL.NotFound):
        AL.get_entry("not_a_table", 1, actor=ADMIN)
    activity_log.record("pupil.search", target="=cmd|' /C calc'!A0", principal=ADMIN)
    path = tmp_path / "audit.csv"
    n = AL.export_csv(path, actor=ADMIN)
    rows = list(csv.reader(path.open()))
    assert rows[0] == AL.CSV_COLUMNS and len(rows) == n + 1
    assert any(r[6].startswith("'=") for r in rows[1:])


def test_admin_only_and_reads_are_logged(tmp_path):
    with pytest.raises(AL.PermissionDenied):
        AL.search(actor=ANN)
    with pytest.raises(AL.PermissionDenied):
        AL.export_csv(tmp_path / "x.csv", actor=ANN)
    AL.search(actor=ADMIN)
    log = (tmp_path / "activity.log").read_text()
    assert "audit_log.search | target=- | outcome=denied" in log
    assert "audit_log.search | target=- | outcome=ok" in log


def test_read_only_over_the_trails():
    _seed()
    before = {t: AL._table_entries(t, AL.Filters()) for t in AL.audit_tables()}
    AL.search(actor=ADMIN)
    AL.summary(actor=ADMIN)
    AL.run_report("deletes", actor=ADMIN)
    after = {t: AL._table_entries(t, AL.Filters()) for t in AL.audit_tables()}
    assert before == after


def test_reports_saved_definitions_and_runs(tmp_path):
    p = _seed()
    for rtype in AL.REPORT_TYPES:
        if rtype == "entity_history":
            with pytest.raises(AL.ValidationError):
                AL.run_report(rtype, actor=ADMIN)
            r = AL.run_report(rtype, {"target": p.admission_no}, actor=ADMIN)
        else:
            r = AL.run_report(rtype, actor=ADMIN)
        assert r.columns and isinstance(r.rows, list)
    by_user = AL.run_report("actions_by_user", actor=ADMIN)
    assert {row[0] for row in by_user.rows} >= {"admin2", "ann"}
    sec = AL.run_report("security_events", actor=ADMIN)
    assert any(row[3] == "menu.open" for row in sec.rows)
    d = AL.create_def({"name": "Refusals", "report_type": "Security events",
                       "filters": {"user": "ann"}}, actor=ADMIN)
    assert d.report_type == "security_events" and d.filters == {"user": "ann"}
    with pytest.raises(AL.ValidationError):
        AL.create_def({"name": "refusals", "report_type": "deletes"}, actor=ADMIN)
    d = AL.update_def(d.report_id, {"description": "Weekly"}, actor=ADMIN)
    res = AL.run_def(d.report_id, actor=ADMIN)
    assert res.title.startswith("Refusals")
    run = AL.save_run(res, actor=ADMIN)
    assert AL.get_run(run.run_id, actor=ADMIN).rows == [list(r) for r in res.rows]
    assert AL.list_runs(actor=ADMIN)[0].run_id == run.run_id
    assert AL.export_report(res, tmp_path / "r.txt", actor=ADMIN) == len(res.rows)
    assert "Refusals" in (tmp_path / "r.txt").read_text()
    AL.delete_run(run.run_id, actor=ADMIN)
    AL.delete_def(d.report_id, actor=ADMIN)
    assert AL.list_defs(actor=ADMIN) == [] and AL.list_runs(actor=ADMIN) == []
    ov = AL.overview(actor=ADMIN)
    assert ov["events"] > 0 and any(t == "pupil_audit" for t, _n in ov["trails"])
