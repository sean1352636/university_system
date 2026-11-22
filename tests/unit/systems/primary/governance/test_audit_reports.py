"""Audit reports over the activity feed (domain.governance.audit.audit_reports.audit_reports)."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from education_system.systems.primary.domain.governance.audit.audit_reports import (
    audit_reports as AR,
)
from education_system.systems.primary.domain.operations.communications.activity_feed import (
    activity_feed as AF,
)

NOW = dt.datetime.now().replace(microsecond=0)


def _ago(**kw) -> str:
    return (NOW - dt.timedelta(**kw)).isoformat(sep=" ")


def _ev(action="update", ts="2026-03-01 09:00:00", **extra):
    extra.setdefault("summary", f"{action} something")
    return AF.log(action, extra.pop("summary"), ts=ts, **extra)


def _seed():
    """A small fixed log: 6 events over two days."""
    _ev("login", "2026-03-01 08:00:00", actor="ann", source="gui", ip_address="10.0.0.1",
        severity="info")
    _ev("update", "2026-03-01 09:00:00", actor="ann", entity_type="pupil", entity_id="P1")
    _ev("delete", "2026-03-01 10:00:00", actor="bob", entity_type="pupil", entity_id="P1",
        severity="warning", source="cli")
    _ev("login_failed", "2026-03-02 07:00:00", actor="eve", ip_address="6.6.6.6",
        severity="warning", source="api")
    _ev("update", "2026-03-02 08:00:00", actor="ann", entity_type="staff", entity_id="S1")
    _ev("system", "2026-03-02 09:00:00", severity="error", summary="backup failed")


# ── catalogue ──

def test_every_report_type_has_label_description_and_builder():
    assert set(AR.REPORT_LABELS) == set(AR.REPORT_TYPES)
    assert set(AR.REPORT_DESCRIPTIONS) == set(AR.REPORT_TYPES)
    for rt in AR.REPORT_TYPES:
        kw = {"filters": {"entity_id": "x"}} if rt == "entity_history" else {}
        res = AR.run_report(rt, **kw)
        assert res.rows == [] or rt in ("severity_breakdown", "source_breakdown")
        assert res.label == AR.REPORT_LABELS[rt]


# ── run_report: validation ──

def test_unknown_report_type_refused():
    with pytest.raises(AR.ValidationError, match="Report type must be one of"):
        AR.run_report("everything")
    with pytest.raises(AR.ValidationError, match="Report type is required"):
        AR.run_report("")


def test_entity_history_needs_entity_id():
    with pytest.raises(AR.ValidationError, match="entity_history requires an entity_id"):
        AR.run_report("entity_history")


def test_filter_validation_and_normalising():
    with pytest.raises(AR.ValidationError, match="date_from must be YYYY-MM-DD"):
        AR.run_report("events_timeline", filters={"date_from": "March"})
    with pytest.raises(AR.ValidationError, match="limit must be a whole number"):
        AR.run_report("events_timeline", filters={"limit": "lots"})
    res = AR.run_report("events_timeline", filters={
        "actor": " ann ", "action": "", "bogus": 1, "limit": 0,
        "date_from": "2026-03-01 08:30"})
    assert res.filters == {"actor": "ann", "limit": 1, "date_from": "2026-03-01 08:30"}
    assert AR.run_report("events_timeline", filters={"limit": 99999}).filters == {"limit": 10000}


def test_run_report_name_defaults_to_label():
    assert AR.run_report("deletes").name == "Deletions"
    assert AR.run_report("deletes", name="  Weekly deletes ").name == "Weekly deletes"


# ── builders ──

def test_actions_by_user():
    _seed()
    res = AR.run_report("actions_by_user")
    assert res.headers == ["Actor", "Events", "Most recent"]
    assert res.rows == [
        ["ann", 3, "2026-03-02 08:00:00"],
        ["(system)", 1, "2026-03-02 09:00:00"],
        ["bob", 1, "2026-03-01 10:00:00"],
        ["eve", 1, "2026-03-02 07:00:00"],
    ]
    assert res.row_count == 4


def test_actions_by_type():
    _seed()
    assert AR.run_report("actions_by_type").rows == [
        ["update", 2], ["delete", 1], ["login", 1], ["login_failed", 1], ["system", 1]]


def test_events_timeline_and_filters():
    _seed()
    res = AR.run_report("events_timeline", filters={"actor": "ann"})
    assert [r[0] for r in res.rows] == ["2026-03-02 08:00:00", "2026-03-01 09:00:00",
                                        "2026-03-01 08:00:00"]
    assert res.rows[0] == ["2026-03-02 08:00:00", "ann", "update", "audit", "system",
                           "staff#S1", "update something"]
    assert res.rows[2][5] == "—#—"
    only_errors = AR.run_report("events_timeline", filters={"severity": "error"})
    assert [r[1] for r in only_errors.rows] == ["—"]
    window = AR.run_report("events_timeline", filters={"date_from": "2026-03-01 09:30",
                                                       "date_to": "2026-03-02 07:30"})
    assert [r[2] for r in window.rows] == ["login_failed", "delete"]
    assert AR.run_report("events_timeline", filters={"summary_like": "backup"}).row_count == 1
    assert AR.run_report("events_timeline", filters={"limit": 2}).row_count == 2


def test_date_to_includes_the_whole_day():
    _seed()
    res = AR.run_report("events_timeline",
                        filters={"date_from": "2026-03-01", "date_to": "2026-03-01"})
    assert res.row_count == 3


def test_deletes_and_failed_logins():
    _seed()
    d = AR.run_report("deletes")
    assert [r[1] for r in d.rows] == ["bob"] and d.rows[0][5] == "pupil#P1"
    f = AR.run_report("failed_logins")
    assert f.headers == ["When", "Attempted user", "IP", "Source", "Summary"]
    assert f.rows == [["2026-03-02 07:00:00", "eve", "6.6.6.6", "api", "login_failed something"]]


def test_security_events():
    _seed()
    rows = AR.run_report("security_events").rows
    assert [r[2] for r in rows] == ["system", "login_failed", "delete", "login"]
    assert rows[-1][5] == "10.0.0.1" and rows[0][5] == "—"


def test_severity_breakdown_percentages():
    _seed()
    rows = AR.run_report("severity_breakdown").rows
    assert rows == [["info", 1, "16.7%"], ["audit", 2, "33.3%"],
                    ["warning", 2, "33.3%"], ["error", 1, "16.7%"]]


def test_breakdowns_on_empty_feed_are_zero():
    assert AR.run_report("severity_breakdown").rows == [[s, 0, "0.0%"] for s in AF.SEVERITIES]
    assert AR.run_report("source_breakdown").rows == [[s, 0, "0.0%"] for s in AF.SOURCES]


def test_source_breakdown():
    _seed()
    rows = {r[0]: (r[1], r[2]) for r in AR.run_report("source_breakdown").rows}
    assert rows == {"cli": (1, "16.7%"), "gui": (1, "16.7%"), "api": (1, "16.7%"),
                    "system": (3, "50.0%"), "background": (0, "0.0%")}


def test_daily_summary():
    _seed()
    assert AR.run_report("daily_summary").rows == [
        ["2026-03-01", 3, 1, 1, 1, 0],
        ["2026-03-02", 3, 0, 1, 1, 1],
    ]


def test_entity_history():
    _seed()
    res = AR.run_report("entity_history", filters={"entity_id": "P1", "entity_type": "pupil"})
    assert [r[2] for r in res.rows] == ["delete", "update"]
    assert res.headers == ["When", "Actor", "Action", "Severity", "Source", "Summary"]


# ── saved definitions ──

def test_create_def_and_read_back():
    d = AR.create_def({"name": "  Deletes this term ", "report_type": "deletes",
                       "filters": {"date_from": "2026-01-01", "junk": 1},
                       "description": " for governors ", "created_by": " admin3 "})
    assert d.name == "Deletes this term" and d.type_label == "Deletions"
    assert d.filters == {"date_from": "2026-01-01"}
    assert (d.description, d.created_by) == ("for governors", "admin3")
    assert AR.get_def(d.def_id) == d
    assert AR.get_def_by_name(" Deletes this term ") == d
    assert AR.get_def(999) is None and AR.get_def_by_name("nope") is None


def test_create_def_validation():
    with pytest.raises(AR.ValidationError, match="Name is required"):
        AR.create_def({"report_type": "deletes"})
    with pytest.raises(AR.ValidationError, match="Report type must be one of"):
        AR.create_def({"name": "x", "report_type": "secret"})
    with pytest.raises(AR.ValidationError, match="entity_id"):
        AR.create_def({"name": "x", "report_type": "entity_history"})
    AR.create_def({"name": "dup", "report_type": "deletes"})
    with pytest.raises(AR.ValidationError, match="already exists"):
        AR.create_def({"name": "dup", "report_type": "failed_logins"})


def test_list_defs_sorted_and_filtered():
    AR.create_def({"name": "beta", "report_type": "deletes"})
    AR.create_def({"name": "Alpha", "report_type": "failed_logins"})
    assert [d.name for d in AR.list_defs()] == ["Alpha", "beta"]
    assert [d.name for d in AR.list_defs(report_type="deletes")] == ["beta"]


def test_update_def():
    d = AR.create_def({"name": "a", "report_type": "deletes", "description": "keep"})
    out = AR.update_def(d.def_id, {"filters": {"actor": "bob"}})
    assert out.filters == {"actor": "bob"} and out.description == "keep" and out.name == "a"
    out = AR.update_def(d.def_id, {"report_type": "actions_by_user", "description": " "})
    assert out.report_type == "actions_by_user" and out.description is None
    AR.create_def({"name": "b", "report_type": "deletes"})
    with pytest.raises(AR.ValidationError, match="already exists"):
        AR.update_def(d.def_id, {"name": "b"})
    with pytest.raises(AR.ValidationError, match="Name is required"):
        AR.update_def(d.def_id, {"name": "  "})
    with pytest.raises(AR.ValidationError, match="No saved report #77"):
        AR.update_def(77, {})


def test_delete_def_and_run_def():
    _seed()
    d = AR.create_def({"name": "Eve", "report_type": "failed_logins",
                       "filters": {"actor": "eve"}})
    res = AR.run_def(d.def_id)
    assert res.name == "Eve" and res.row_count == 1 and res.filters == {"actor": "eve"}
    assert AR.delete_def(d.def_id) is True
    assert AR.delete_def(d.def_id) is False
    with pytest.raises(AR.ValidationError, match="No saved report"):
        AR.run_def(d.def_id)


# ── run snapshots ──

def test_save_and_reload_run():
    _seed()
    d = AR.create_def({"name": "types", "report_type": "actions_by_type"})
    res = AR.run_def(d.def_id)
    run = AR.save_run(res, def_id=d.def_id, run_by=" admin3 ", notes=" for FGB ")
    assert (run.def_id, run.report_type, run.name) == (d.def_id, "actions_by_type", "types")
    assert run.headers == res.headers and run.rows == res.rows and run.row_count == 5
    assert (run.run_by, run.notes) == ("admin3", "for FGB")
    again = run.as_result()
    assert again.rows == res.rows and again.generated_at == run.run_at
    assert AR.get_run(run.run_id) == run
    assert AR.get_run(9999) is None


def test_runs_survive_def_deletion():
    d = AR.create_def({"name": "x", "report_type": "deletes"})
    run = AR.save_run(AR.run_def(d.def_id), def_id=d.def_id)
    AR.delete_def(d.def_id)
    assert AR.get_run(run.run_id).def_id is None


def test_list_runs_filters_and_delete():
    a = AR.save_run(AR.run_report("deletes"))
    b = AR.save_run(AR.run_report("failed_logins"))
    assert [r.run_id for r in AR.list_runs()] == [b.run_id, a.run_id]
    assert [r.run_id for r in AR.list_runs(report_type="deletes")] == [a.run_id]
    assert [r.run_id for r in AR.list_runs(limit=1)] == [b.run_id]
    assert AR.list_runs(def_id=1) == []
    assert AR.delete_run(a.run_id) is True
    assert AR.delete_run(a.run_id) is False


# ── render / export ──

def _small():
    return AR.ReportResult(report_type="actions_by_type", name="Types",
                           headers=["Action", "Events"],
                           rows=[["a|b", 2], ["x,y", None], [True, "line\nbreak"]],
                           filters={"actor": "ann"}, generated_at="2026-03-03 10:00:00")


def test_render_csv_and_tsv():
    assert AR.render(_small()) == 'Action,Events\na|b,2\n"x,y",\ntrue,"line\nbreak"\n'
    assert AR.render(_small(), fmt="TSV").splitlines()[0] == "Action\tEvents"


def test_render_json():
    body = json.loads(AR.render(_small(), fmt="json"))
    assert body["name"] == "Types" and body["filters"] == {"actor": "ann"}
    assert body["rows"][0] == ["a|b", 2]


def test_render_markdown():
    md = AR.render(_small(), fmt="markdown")
    lines = md.splitlines()
    assert lines[0] == "# Types"
    assert "**Filters:** `actor=ann`" in lines
    assert "| Action | Events |" in lines and "|---|---|" in lines
    assert "| a\\|b | 2 |" in lines
    assert "| true | line ⏎ break |" in lines
    empty = AR.ReportResult("deletes", "D", ["A"], [], {}, "now")
    assert AR.render(empty, fmt="markdown").endswith("_(no rows)_\n")


def test_render_unknown_format_refused():
    with pytest.raises(AR.ValidationError, match="Format must be one of"):
        AR.render(_small(), fmt="pdf")


def test_export_picks_format_from_suffix(tmp_path):
    info = AR.export(_small(), tmp_path / "out" / "r.md")
    assert info["fmt"] == "markdown" and info["row_count"] == 3
    assert (tmp_path / "out" / "r.md").read_text(encoding="utf-8").startswith("# Types")
    assert AR.export(_small(), tmp_path / "r.xyz")["fmt"] == "csv"
    assert AR.export(_small(), tmp_path / "noext")["fmt"] == "csv"
    j = AR.export(_small(), tmp_path / "r.txt", fmt="json")
    assert j["fmt"] == "json" and j["bytes_written"] == len(AR.render(_small(), fmt="json"))


# ── overview ──

def test_overview_empty():
    o = AR.overview()
    assert (o.total_events, o.last_24h, o.last_7d, o.last_30d) == (0, 0, 0, 0)
    assert o.by_severity == {s: 0 for s in AF.SEVERITIES}
    assert o.by_action_top == [] and o.by_actor_top == []
    assert (o.saved_report_count, o.saved_run_count) == (0, 0)


def test_overview_windows_and_counts():
    _ev("login_failed", _ago(hours=1), actor="eve", severity="warning")
    _ev("delete", _ago(hours=2), actor="bob")
    _ev("delete", _ago(days=3), actor="bob")
    _ev("update", _ago(days=10), actor="ann")
    _ev("update", _ago(days=40), actor="ann")
    AR.create_def({"name": "d", "report_type": "deletes"})
    AR.save_run(AR.run_report("deletes"))
    o = AR.overview()
    assert o.total_events == 5
    assert (o.last_24h, o.last_7d, o.last_30d) == (2, 3, 4)
    assert (o.failed_logins_24h, o.deletes_24h) == (1, 1)
    assert o.by_severity == {"info": 0, "audit": 4, "warning": 1, "error": 0}
    assert dict(o.by_action_top) == {"delete": 2, "update": 2, "login_failed": 1}
    assert o.by_actor_top[-1] == ("eve", 1)
    assert (o.saved_report_count, o.saved_run_count) == (1, 1)
