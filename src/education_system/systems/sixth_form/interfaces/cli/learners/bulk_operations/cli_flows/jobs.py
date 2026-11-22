"""CLI flows for the job log, undo, schedules, logs and summary.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

import json

from education_system.systems.sixth_form.domain.learners.bulk_operations import base as bulk_base
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_records as bulk_ops_records
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import OPERATIONS
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _print_jobs,
    _print_result,
    _UserAbort,
    _yes_no,
)


def bulk_undo_job_flow() -> None:
    print("\n═══ Undo Job (best-effort rollback) ═══")
    print(f"  Undoable: {', '.join(bulk_ops_records._UNDOABLE)}")
    try:
        jid = int(_input("Job id to undo", allow_empty=False))
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_records.bulk_undo_job(jid, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_schedule_create_flow() -> None:
    print("\n═══ Create Recurring Bulk Schedule ═══")
    try:
        name = _input("Schedule name", allow_empty=False)
        op = _input(f"Operation ({'/'.join(bulk_base.OPERATIONS)})",
                       allow_empty=False)
        cron_expr = _input(
            "Cron expression (e.g. '0 9 * * 1')", allow_empty=False)
        next_run = _input(
            "First run (YYYY-MM-DD HH:MM, optional)") or None
        params_raw = _input("Parameters (k=v,...; optional)") or ""
        by = _input("Created by") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    params: dict = {}
    for pair in params_raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    try:
        r = bulk_ops_records.bulk_schedule_recurring(
            name=name, operation=op, cron_expr=cron_expr,
            parameters=params, next_run_at=next_run,
            created_by=by, dry_run=False,
        )
    except (ValidationError, KeyError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=False)


def bulk_schedule_list_flow() -> None:
    print("\n═══ Recurring Schedules ═══")
    rows = bulk_ops_records.list_schedules()
    if not rows:
        print("  (none)")
        _pause()
        return
    print(f"\n  {'#':>4}  {'On':<3}  {'Name':<24}  {'Op':<20}  "
          f"{'Cron':<20}  Next run")
    print("  " + "-" * 100)
    for s in rows:
        on = "yes" if s.enabled else "no"
        print(f"  {s.schedule_id:>4}  {on:<3}  {s.name[:24]:<24}  "
              f"{s.operation[:20]:<20}  {s.cron_expr[:20]:<20}  "
              f"{s.next_run_at or '—'}")
    print(f"\n  {len(rows)} schedule(s).")
    _pause()


def bulk_schedule_toggle_flow() -> None:
    print("\n═══ Enable / Disable Schedule ═══")
    try:
        sid_raw = _input("Schedule id", allow_empty=False)
        sid = int(sid_raw)
        enable = _yes_no("Enable?", default=True)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        s = bulk_ops_records.set_schedule_enabled(sid, enable)
        print(f"  ✓ #{s.schedule_id} {s.name}: "
              f"enabled={s.enabled}")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def bulk_logs_flow() -> None:
    print("\n═══ Bulk Operation Logs ═══")
    try:
        level = _input("Level filter (DEBUG/INFO/WARNING/ERROR; blank=all)") or None
        op = _input("Operation filter (blank=all)") or None
        n = int(_input("Limit", default="50"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = bulk_base.list_logs(level=level, operation=op, limit=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no logs)")
        _pause()
        return
    print()
    print(f"  {'#':>5}  {'When':<19}  {'Level':<8}  "
          f"{'Op':<22}  {'Job':>5}  Message")
    print("  " + "-" * 110)
    for r in rows:
        print(f"  {r.log_id:>5}  {r.ts[:19]:<19}  {r.level:<8}  "
              f"{(r.operation or '—')[:22]:<22}  "
              f"{str(r.job_id or '—'):>5}  {r.message[:60]}")
    print(f"\n  {len(rows)} log row(s).")
    _pause()


def bulk_logs_clear_flow() -> None:
    print("\n═══ Clear Logs ═══")
    try:
        raw = _input(
            "Delete logs older than N days (blank = ALL logs)") or ""
        days = int(raw) if raw else None
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    label = (f"older than {days} days" if days is not None
             else "ALL logs")
    if _input(f"Delete {label}? Type 'yes'",
                default="no").lower() != "yes":
        print("  Cancelled.")
        return
    try:
        n = bulk_base.clear_logs(older_than_days=days)
        print(f"  ✓ Deleted {n} row(s).")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def bulk_schedule_delete_flow() -> None:
    print("\n═══ Delete Schedule ═══")
    try:
        sid = int(_input("Schedule id", allow_empty=False))
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    if _input(f"Delete schedule #{sid}? Type 'yes'",
                default="no").lower() != "yes":
        print("  Cancelled.")
        return
    if bulk_ops_records.delete_schedule(sid):
        print(f"  ✓ Deleted #{sid}")
    else:
        print(f"  ✗ No schedule #{sid}")
    _pause()


# ── Job log ───────────────────────────────────────────────────────

def list_jobs_flow() -> None:
    print("\n═══ Bulk Job Log ═══")
    try:
        op = _input(f"Operation filter ({'/'.join(OPERATIONS)})") or None
        n = int(_input("Limit", default="100"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        rows = bulk_base.list_jobs(operation=op, limit=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_jobs(rows)
    _pause()


def view_job() -> None:
    print("\n═══ View Job ═══")
    try:
        jid = int(_input("Job id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    j = bulk_base.get_job(jid)
    if j is None:
        print(f"  ✗ No job #{jid}")
        _pause()
        return
    print()
    print(f"    Job id      : #{j.job_id}")
    print(f"    When        : {j.ran_at}")
    print(f"    Operation   : {j.operation}")
    print(f"    Summary     : {j.summary}")
    print(f"    Targets     : {j.target_count}")
    print(f"    Successes   : {j.success_count}")
    print(f"    Failures    : {j.failure_count}")
    print(f"    Ran by      : {j.ran_by or '—'}")
    if j.parameters:
        print("\n    Parameters:")
        for line in json.dumps(j.parameters, indent=2).splitlines():
            print(f"      {line}")
    if j.success_ids:
        print(f"\n    Success ids ({len(j.success_ids)}):")
        for sid in j.success_ids[:20]:
            print(f"      {sid}")
        if len(j.success_ids) > 20:
            print(f"      ... +{len(j.success_ids) - 20} more")
    if j.failures:
        print(f"\n    Failures ({len(j.failures)}):")
        for sid, reason in j.failures[:20]:
            print(f"      {sid}: {reason}")
        if len(j.failures) > 20:
            print(f"      ... +{len(j.failures) - 20} more")
    _pause()


def delete_job_flow() -> None:
    print("\n═══ Delete Job ═══")
    try:
        jid = int(_input("Job id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if bulk_base.get_job(jid) is None:
        print(f"  ✗ No job #{jid}")
        _pause()
        return
    if _input(f"Delete job #{jid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if bulk_base.delete_job(jid):
        print(f"\n  ✓ Deleted #{jid}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Bulk Operations Summary ═══")
    summ = bulk_ops_records.summary()
    print(f"\n  Total jobs         : {summ.total_jobs}")
    print(f"  Total targets      : {summ.total_targets}")
    print(f"  Total successes    : {summ.total_successes}")
    print(f"  Total failures     : {summ.total_failures}")
    print(f"  Most recent        : {summ.most_recent_ts or '—'}")
    print("\n  By operation:")
    for op in OPERATIONS:
        n = summ.by_operation.get(op, 0)
        if n:
            print(f"    {op:<22} : {n}")
    _pause()
