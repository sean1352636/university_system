"""The audit log in the terminal (read-only; admin only).

The old Audit Reports menu keeps its options in place: 1 Overview, 2 List
Report Types, 3 Run a Report, 4 Save a Report Definition, 5 List Saved
Reports, 6 Run a Saved Report, 7 Edit Saved Report, 8 Delete Saved Report,
9 List Past Runs, 10 View Past Run, 11 Delete Past Run. New: 12 Search
events, 13 Failed / denied, 14 Summary, 15 Entry detail, 16 Export CSV.
Rules live in :mod:`modules.administration.domain.audit_log`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.administration.domain import audit_log as AL
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AL.ValidationError, AL.PermissionDenied, AL.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _filters(current: dict[str, Any] | None = None) -> dict[str, str]:
    """Ask each filter; Enter keeps the current one (none), '-' clears."""
    cur = dict(current or {})
    print("  Filters (Enter = none/keep, '-' = clear). Dates YYYY-MM-DD; action exact or "
          "prefix ending in '.'")
    for key, label in (("date_from", "From"), ("date_to", "To"), ("user", "User"),
                       ("action", "Action"), ("area", "Area / table"), ("target", "Target"),
                       ("outcome", "Outcome (ok, denied, failed...)"), ("text", "Text")):
        v = prompts.ask(label, cur.get(key))
        if v is not None:
            cur[key] = v
    return {k: v for k, v in cur.items() if v}


def _entries(page: AL.Page) -> None:
    if not page.entries:
        print("  (nothing found)")
        return
    for e in page.entries:
        print(f"  {e.at:<19} {e.source[:18]:<18} {e.user[:10]:<10} {e.action[:26]:<26} "
              f"{e.target[:12]:<12} {e.outcome:<8} #{e.row_id}  {e.detail_text()[:40]}")
    print(f"  Page {page.page} of {page.pages} ({page.total} entries)")


def _browse(principal: Principal, fn) -> None:
    f = _filters()
    page = 1
    while True:
        _entries(fn(f, actor=principal, page=page, page_size=25))
        nxt = _prompt("  n = next, p = previous, Enter = done: ").lower()
        if nxt == "n":
            page += 1
        elif nxt == "p" and page > 1:
            page -= 1
        else:
            return


def _report_table(res: AL.ReportResult) -> None:
    print("\n" + AL.render(res))


def _choose_type() -> str | None:
    label = _pick("Report", [AL.REPORT_LABELS[t] for t in AL.REPORT_TYPES])
    return next((k for k, v in AL.REPORT_LABELS.items() if label in (k, v)), None)


def _after_run(res: AL.ReportResult, principal: Principal) -> None:
    _report_table(res)
    if _yes("  Save a snapshot of this run?"):
        print(f"  Saved as run #{AL.save_run(res, actor=principal).run_id}.")
    path = _prompt("  Export to file (.csv or .txt; blank = no): ")
    if path:
        print(f"  Wrote {AL.export_report(res, path, actor=principal)} row(s).")


# ── The old options ──────────────────────────────────────────────────

def _overview(principal: Principal) -> None:
    ov = AL.overview(actor=principal)
    print(f"\n  Since {ov['since']}: {ov['events']} events, {ov['failed']} refused/failed, "
          f"{ov['users']} people")
    print("  Most active: " + ", ".join(f"{u} ({n})" for u, n in ov["top_users"]))
    print("  Most common: " + ", ".join(f"{a} ({n})" for a, n in ov["top_actions"]))
    print("  Audit tables:")
    for t, n in ov["trails"]:
        print(f"    {t:<34} {n}")
    print(f"  Activity log: {len(ov['log_files'])} file(s), {ov['log_bytes'] // 1024} KB")


def _types(_principal: Principal) -> None:
    for t in AL.REPORT_TYPES:
        print(f"  {AL.REPORT_LABELS[t]:<26} {AL.REPORT_DESCRIPTIONS[t]}")


def _run(principal: Principal) -> None:
    rtype = _choose_type()
    if rtype:
        _after_run(AL.run_report(rtype, _filters(), actor=principal), principal)


def _def_form(cur: AL.ReportDef | None = None) -> dict[str, Any]:
    name = prompts.ask("Name", cur.name if cur else None, required=cur is None)
    rtype = _choose_type() or (cur.report_type if cur else None)
    desc = prompts.ask("Description", cur.description if cur else None)
    out: dict[str, Any] = {"report_type": rtype, "filters": _filters(cur.filters if cur
                                                                    else None)}
    if name is not None:
        out["name"] = name
    if desc is not None:
        out["description"] = desc
    return out


def _save_def(principal: Principal) -> None:
    d = AL.create_def(_def_form(), actor=principal)
    print(f"  Saved report #{d.report_id} ({d.name}).")


def _list_defs(principal: Principal) -> None:
    defs = AL.list_defs(actor=principal)
    if not defs:
        print("  (no saved reports)")
    for d in defs:
        print(f"  #{d.report_id:<4} {d.name:<30} {AL.REPORT_LABELS[d.report_type]:<24} "
              + ", ".join(f"{k}={v}" for k, v in d.filters.items()))


def _run_def(principal: Principal) -> None:
    rid = _int("  Saved report ID: ")
    if rid:
        _after_run(AL.run_def(rid, actor=principal), principal)


def _edit_def(principal: Principal) -> None:
    rid = _int("  Saved report ID: ")
    if rid:
        d = AL.update_def(rid, _def_form(AL.get_def(rid)), actor=principal)
        print(f"  Saved {d.name}.")


def _delete_def(principal: Principal) -> None:
    rid = _int("  Saved report ID: ")
    if rid and _yes(f"  Delete saved report #{rid}?"):
        AL.delete_def(rid, actor=principal)
        print("  Deleted.")


def _list_runs(principal: Principal) -> None:
    runs = AL.list_runs(actor=principal)
    if not runs:
        print("  (no saved runs)")
    for r in runs:
        print(f"  #{r.run_id:<4} {r.run_at}  {r.title[:40]:<40} {r.row_count:>5} rows  "
              f"{r.run_by or ''}")


def _view_run(principal: Principal) -> None:
    rid = _int("  Run ID: ")
    if rid:
        _report_table(AL.get_run(rid, actor=principal).as_result())


def _delete_run(principal: Principal) -> None:
    rid = _int("  Run ID: ")
    if rid and _yes(f"  Delete run #{rid}?"):
        AL.delete_run(rid, actor=principal)
        print("  Deleted.")


# ── New ──────────────────────────────────────────────────────────────

def _search(principal: Principal) -> None:
    _browse(principal, AL.search)


def _failed(principal: Principal) -> None:
    _browse(principal, AL.failures)


def _summary(principal: Principal) -> None:
    s = AL.summary(_filters(), actor=principal)
    print(f"\n  {s['total']} entries, {s['failed']} refused/failed, {s['users']} people")
    for key, title in (("by_user", "By user"), ("by_action", "By action"),
                       ("by_area", "By area"), ("by_outcome", "By outcome")):
        print(f"  {title}:")
        for name, n in s[key][:15]:
            print(f"    {name[:40]:<40} {n}")


def _detail(principal: Principal) -> None:
    source = _pick("Trail", AL.sources(), AL.ACTIVITY)
    rid = _int("  Entry # (row id / line number): ")
    if not (source and rid):
        return
    e = AL.get_entry(source, rid, actor=principal)
    for label, v in (("Time", e.at), ("Trail", e.source), ("User", e.user), ("Role", e.role),
                     ("Interface", e.interface), ("Session", e.session),
                     ("Action", e.action), ("Target", e.target), ("Outcome", e.outcome)):
        if v:
            print(f"  {label + ':':<11} {v}")
    for k, v in e.detail.items():
        print(f"    {k}: {v}")


def _export(principal: Principal) -> None:
    f = _filters()
    path = _prompt("  Save CSV to (e.g. audit_log.csv): ")
    if path:
        print(f"  Exported {AL.export_csv(path, f, actor=principal)} entries.")


_OPTIONS = {"1": _overview, "2": _types, "3": _run, "4": _save_def, "5": _list_defs,
            "6": _run_def, "7": _edit_def, "8": _delete_def, "9": _list_runs, "10": _view_run,
            "11": _delete_run, "12": _search, "13": _failed, "14": _summary, "15": _detail,
            "16": _export}


def menu(principal: Principal) -> None:
    if not AL.can_read(principal):
        activity_log.record("audit_log.open", outcome="denied", principal=principal)
        print("\n  Only a system administrator can read the audit log.")
        _pause()
        return
    while True:
        activity_log.record("audit_log.open")
        print("\n  ── Audit Log ──")
        print("    1) Overview\n    2) List Report Types\n    3) Run a Report\n    4) Save a "
              "Report Definition\n    5) List Saved Reports\n    6) Run a Saved Report"
              "\n    7) Edit Saved Report\n    8) Delete Saved Report\n    9) List Past Runs"
              "\n   10) View Past Run\n   11) Delete Past Run")
        print("  More")
        print("   12) Search events\n   13) Failed / denied\n   14) Summary\n   15) Entry "
              "detail\n   16) Export CSV")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except (*_ERRORS, OSError) as e:
            _problem(e)
        _pause()
