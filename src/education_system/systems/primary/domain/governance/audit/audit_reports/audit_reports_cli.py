"""CLI flows for Primary School Audit Reports."""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _td
from typing import Any, Callable
from education_system.systems.primary.domain.governance.audit.audit_reports import (
    audit_reports as data,
)
from education_system.systems.primary.domain.governance.audit.audit_reports.audit_reports import (
    DEFAULT_EXPORT_FORMAT,
    EXPORT_FORMATS,
    REPORT_DESCRIPTIONS,
    REPORT_LABELS,
    REPORT_TYPES,
    ReportDef,
    ReportResult,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
           allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
               default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_report_type(default: str | None = None) -> str:
    print("\n  Report types:")
    for i, rt in enumerate(REPORT_TYPES, 1):
        marker = " *" if rt == default else "  "
        print(f"    {marker}{i:>2}) {REPORT_LABELS[rt]}  ({rt})")
        print(f"          {REPORT_DESCRIPTIONS[rt]}")
    while True:
        raw = _input(f"Pick #1..{len(REPORT_TYPES)} or key",
                     default=default or "", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(REPORT_TYPES):
                return REPORT_TYPES[n - 1]
        if raw in REPORT_TYPES:
            return raw
        print("    No matching report type.")


def _collect_filters(report_type: str,
                     existing: dict[str, Any] | None = None
                     ) -> dict[str, Any]:
    existing = existing or {}
    print("\n  Filters (blank = skip):")
    needs_entity = report_type == "entity_history"
    fmt_today = _date.today().isoformat()
    fmt_30d = (_date.today() - _td(days=30)).isoformat()
    p: dict[str, Any] = {}
    p["date_from"] = _input(
        "From (YYYY-MM-DD)",
        default=str(existing.get("date_from") or fmt_30d))
    p["date_to"] = _input(
        "To   (YYYY-MM-DD)",
        default=str(existing.get("date_to") or fmt_today))
    p["actor"] = _input("Actor (username)",
                          default=str(existing.get("actor") or ""))
    p["action"] = _input("Action (e.g. create / update / delete)",
                           default=str(existing.get("action") or ""))
    p["entity_type"] = _input(
        "Entity type (e.g. student / staff)",
        default=str(existing.get("entity_type") or ""))
    p["entity_id"] = _input(
        f"Entity id{' (required)' if needs_entity else ''}",
        default=str(existing.get("entity_id") or ""),
        allow_empty=not needs_entity)
    p["severity"] = _input(
        "Severity (info / audit / warning / error)",
        default=str(existing.get("severity") or ""))
    p["source"] = _input(
        "Source (cli / gui / api / system / background)",
        default=str(existing.get("source") or ""))
    p["summary_like"] = _input(
        "Summary contains",
        default=str(existing.get("summary_like") or ""))
    p["limit"] = _input("Row limit (max 10000)",
                          default=str(existing.get("limit") or "5000"))
    return p


# ── Print helpers ──────────────────────────────────────────────────

def _print_result(result: ReportResult) -> None:
    headers = result.headers
    rows = result.rows
    print(f"\n  ── {result.label}  ({result.report_type}) ──")
    print(f"  Generated: {result.generated_at}")
    if result.filters:
        print("  Filters: "
              + ", ".join(f"{k}={v}" for k, v in result.filters.items()))
    if not rows:
        print("\n  (no rows)")
        return
    widths = [
        max([len(str(h))] + [len(str(r[i])) for r in rows])
        for i, h in enumerate(headers)
    ]
    widths = [min(w, 36) for w in widths]
    print()
    print("  " + "  ".join(
        str(h).ljust(widths[i])[:widths[i]] for i, h in enumerate(headers)))
    print("  " + "  ".join("-" * widths[i] for i in range(len(headers))))
    for r in rows[:200]:
        print("  " + "  ".join(
            str(c if c is not None else "")[:widths[i]].ljust(widths[i])
            for i, c in enumerate(r)))
    if len(rows) > 200:
        print(f"  ... ({len(rows) - 200} more rows truncated)")
    print(f"\n  {len(rows)} row(s).")


def _print_defs(defs: list[ReportDef]) -> None:
    if not defs:
        print("\n  (no saved reports)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<28}  {'Type':<22}  Description")
    print("  " + "-" * 100)
    for d in defs:
        print(f"  {d.def_id:>4}  {d.name[:28]:<28}  "
              f"{d.type_label[:22]:<22}  "
              f"{(d.description or '')[:40]}")
    print(f"\n  {len(defs)} saved report(s).")


def _print_runs(runs: list[data.ReportRun]) -> None:
    if not runs:
        print("\n  (no past runs)")
        return
    print()
    print(f"  {'#':>4}  {'When':<19}  {'Type':<22}  "
          f"{'Name':<28}  {'Rows':>6}  By")
    print("  " + "-" * 110)
    for r in runs:
        print(f"  {r.run_id:>4}  {r.run_at:<19}  "
              f"{REPORT_LABELS.get(r.report_type, r.report_type)[:22]:<22}  "
              f"{r.name[:28]:<28}  {r.row_count:>6}  {r.run_by or '—'}")
    print(f"\n  {len(runs)} run(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_types() -> None:
    print("\n═══ Available Report Types ═══")
    for rt in REPORT_TYPES:
        print(f"\n  {REPORT_LABELS[rt]}  ({rt})")
        print(f"    {REPORT_DESCRIPTIONS[rt]}")
    _pause()


def quick_run() -> None:
    print("\n═══ Run a Report ═══")
    try:
        rt = _pick_report_type()
        filters = _collect_filters(rt)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        result = data.run_report(rt, filters=filters)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(result)
    try:
        save_q = _input("Save snapshot? (y/n)", default="n").lower()
        if save_q in ("y", "yes"):
            by = _input("Run by (optional)")
            notes = _input("Notes (optional)")
            data.save_run(result, run_by=by or None,
                          notes=notes or None)
            print("  ✓ Snapshot saved.")
        exp_q = _input("Export to file? (y/n)", default="n").lower()
        if exp_q in ("y", "yes"):
            fmt = _pick_from("Format", list(EXPORT_FORMATS),
                             default=DEFAULT_EXPORT_FORMAT)
            ext = "md" if fmt == "markdown" else fmt
            default = f"audit_{rt}_{_date.today().isoformat()}.{ext}"
            path = _input("File path", default=default,
                          allow_empty=False)
            res = data.export(result, path, fmt=fmt)
            print(f"  ✓ Wrote {res['row_count']} row(s) → {res['path']}")
    except _UserAbort:
        pass
    _pause()


def new_saved() -> None:
    print("\n═══ Save a Report Definition ═══")
    try:
        name = _input("Name", allow_empty=False)
        rt = _pick_report_type()
        desc = _input("Description (optional)")
        filters = _collect_filters(rt)
        by = _input("Created by (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        d = data.create_def({
            "name": name, "report_type": rt,
            "description": desc, "filters": filters,
            "created_by": by or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Saved as #{d.def_id} ({d.name})")
    _pause()


def list_saved() -> None:
    print("\n═══ Saved Reports ═══")
    _print_defs(data.list_defs())
    _pause()


def edit_saved() -> None:
    print("\n═══ Edit Saved Report ═══")
    try:
        did = int(_input("Saved-report ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_def(did)
    if existing is None:
        print(f"  ✗ No saved report #{did}")
        _pause()
        return
    try:
        name = _input("Name", default=existing.name, allow_empty=False)
        rt = _pick_report_type(default=existing.report_type)
        desc = _input("Description",
                       default=existing.description or "")
        filters = _collect_filters(rt, existing.filters)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_def(did, {
            "name": name, "report_type": rt,
            "description": desc, "filters": filters,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{did}")
    _pause()


def run_saved() -> None:
    print("\n═══ Run a Saved Report ═══")
    defs = data.list_defs()
    if not defs:
        print("  (no saved reports yet)")
        _pause()
        return
    _print_defs(defs)
    try:
        did = int(_input("Saved-report ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        result = data.run_def(did)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(result)
    try:
        save_q = _input("Save snapshot? (y/n)", default="n").lower()
        if save_q in ("y", "yes"):
            by = _input("Run by (optional)")
            notes = _input("Notes (optional)")
            data.save_run(result, def_id=did,
                          run_by=by or None, notes=notes or None)
            print("  ✓ Snapshot saved.")
    except _UserAbort:
        pass
    _pause()


def delete_saved() -> None:
    print("\n═══ Delete Saved Report ═══")
    try:
        did = int(_input("Saved-report ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_def(did) is None:
        print(f"  ✗ No saved report #{did}")
        _pause()
        return
    if _input(f"Delete saved report #{did}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_def(did):
        print(f"\n  ✓ Deleted #{did}")
    _pause()


def list_runs_flow() -> None:
    print("\n═══ Past Runs ═══")
    _print_runs(data.list_runs(limit=100))
    _pause()


def view_run() -> None:
    print("\n═══ View Past Run ═══")
    try:
        rid = int(_input("Run ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    run = data.get_run(rid)
    if run is None:
        print(f"  ✗ No run #{rid}")
        _pause()
        return
    _print_result(run.as_result())
    try:
        exp_q = _input("Export to file? (y/n)",
                        default="n").lower()
        if exp_q in ("y", "yes"):
            fmt = _pick_from("Format", list(EXPORT_FORMATS),
                              default=DEFAULT_EXPORT_FORMAT)
            ext = "md" if fmt == "markdown" else fmt
            default = (f"audit_run_{rid}_"
                        f"{run.report_type}.{ext}")
            path = _input("File path", default=default,
                            allow_empty=False)
            res = data.export(run.as_result(), path, fmt=fmt)
            print(f"  ✓ Wrote {res['row_count']} row(s) → {res['path']}")
    except _UserAbort:
        pass
    _pause()


def delete_run_flow() -> None:
    print("\n═══ Delete Past Run ═══")
    try:
        rid = int(_input("Run ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_run(rid) is None:
        print(f"  ✗ No run #{rid}")
        _pause()
        return
    if _input(f"Delete run #{rid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_run(rid):
        print(f"\n  ✓ Deleted #{rid}")
    _pause()


def overview_flow() -> None:
    print("\n═══ Audit Overview ═══")
    o = data.overview()
    print(f"\n  Total events       : {o.total_events}")
    print(f"  Last 24h           : {o.last_24h}")
    print(f"  Last 7 days        : {o.last_7d}")
    print(f"  Last 30 days       : {o.last_30d}")
    print(f"  Failed logins (24h): {o.failed_logins_24h}")
    print(f"  Deletes (24h)      : {o.deletes_24h}")
    print(f"  Saved reports      : {o.saved_report_count}")
    print(f"  Saved run snapshots: {o.saved_run_count}")
    print("\n  By severity:")
    for s, n in o.by_severity.items():
        if n:
            print(f"    {s:<10} : {n}")
    if o.by_action_top:
        print("\n  Top actions:")
        for k, n in o.by_action_top:
            print(f"    {k:<18} : {n}")
    if o.by_actor_top:
        print("\n  Top actors:")
        for k, n in o.by_actor_top:
            print(f"    {k[:24]:<24} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Overview",                 overview_flow),
    ("List Report Types",        list_types),
    ("Run a Report",             quick_run),
    ("Save a Report Definition", new_saved),
    ("List Saved Reports",       list_saved),
    ("Run a Saved Report",       run_saved),
    ("Edit Saved Report",        edit_saved),
    ("Delete Saved Report",      delete_saved),
    ("List Past Runs",           list_runs_flow),
    ("View Past Run",            view_run),
    ("Delete Past Run",          delete_run_flow),
]


def run() -> None:
    while True:
        print("\n── Audit Reports ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Audit-reports CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Audit Reports":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Audit-reports CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
