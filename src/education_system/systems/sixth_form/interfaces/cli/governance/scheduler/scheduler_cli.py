"""CLI: Scheduled Jobs — list, enable/disable, change schedule, run now,
history with errors, and the exam results inbox log.

Open to ADMIN or GOVERNANCE. Jobs run as the scheduler's system
principal; the signed-in user is recorded as who triggered a manual run.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.infrastructure.scheduler import core
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

logger = logging.getLogger(__name__)

MENU_LABEL = "Scheduled Jobs"


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _ms(ms: int | None) -> str:
    if ms is None:
        return "—"
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.1f} s"


def _pick_job() -> core.JobState | None:
    jobs = core.list_jobs()
    for i, j in enumerate(jobs, 1):
        print(f"  {i:>2}) {j.title} ({j.name})")
    raw = _input("Job number or name")
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(jobs):
        return jobs[int(raw) - 1]
    match = next((j for j in jobs if j.name == raw), None)
    if match is None:
        print("  No such job.")
    return match


def list_flow() -> None:
    print(f"\n═══ {MENU_LABEL} ═══")
    from education_system.systems.sixth_form.infrastructure.scheduler import (
        background,
    )
    bg = background.instance()
    print("  Background runner in this process: "
          + ("on" if bg is not None and bg.running else "off")
          + ("  (switched off by EDU_SIXTHFORM_SCHEDULER)"
             if background.disabled_by_env() else ""))
    print(f"\n  {'#':>2}  {'Job':<34} {'Schedule':<17} {'On':<3} "
          f"{'Next due':<19} {'Last status':<11} Last run")
    print("  " + "-" * 118)
    for i, j in enumerate(core.list_jobs(), 1):
        status = core.RUNNING if j.running else (j.last_status or "—")
        print(f"  {i:>2}  {j.title[:34]:<34} {j.schedule_label[:17]:<17} "
              f"{'yes' if j.enabled else 'no':<3} "
              f"{(j.next_due_at or '—') if j.enabled else '—':<19} "
              f"{status:<11} {j.last_started_at or 'never'}")
    _pause()


def detail_flow() -> None:
    j = _pick_job()
    if j is None:
        return
    print(f"\n  {j.title} ({j.name}) — {j.category}")
    print(f"  {j.description}")
    print(f"  Schedule : {j.schedule_label}"
          + ("" if (j.daily_at == j.default_daily_at
                    and j.interval_minutes == j.default_interval) else "  (changed)"))
    print(f"  Enabled  : {'yes' if j.enabled else 'no'}")
    print(f"  Next due : {j.next_due_at or '—'}")
    print(f"  Last run : {j.last_started_at or 'never'} — {j.last_status or '—'} "
          f"({_ms(j.last_duration_ms)})")
    if j.last_error:
        print("  Last error:\n    " + j.last_error[-1500:].replace("\n", "\n    "))
    _pause()


def toggle_flow() -> None:
    j = _pick_job()
    if j is None:
        return
    new = not j.enabled
    core.set_enabled(j.name, new, by=access.current().username or None)
    print(f"\n  ✓ {j.title} {'enabled' if new else 'disabled'}.")
    _pause()


def schedule_flow() -> None:
    j = _pick_job()
    if j is None:
        return
    print(f"\n  Current: {j.schedule_label}. Enter HH:MM (daily), a number of "
          "minutes (interval), or 'default'.")
    raw = _input("New schedule")
    if not raw:
        return
    by = access.current().username or None
    try:
        if raw.lower() == "default":
            j = core.set_schedule(j.name, by=by)
        elif ":" in raw:
            j = core.set_schedule(j.name, daily_at=raw, by=by)
        else:
            j = core.set_schedule(j.name, interval_minutes=raw, by=by)
    except core.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {j.title}: {j.schedule_label}; next due {j.next_due_at}.")
    _pause()


def run_now_flow() -> None:
    j = _pick_job()
    if j is None:
        return
    print(f"\n  Running {j.title}…")
    run = core.run_job(j.name, trigger=core.TRIGGER_MANUAL,
                       triggered_by=access.current().username or None)
    if run is None:
        print("  ! Already running elsewhere (another window, instance or cron) — "
              "not run again.")
    else:
        mark = "✓" if run.status == core.SUCCESS else "✗"
        print(f"  {mark} {run.status} in {_ms(run.duration_ms)}: {run.summary}")
        if run.error:
            print("    " + run.error[-2000:].replace("\n", "\n    "))
    _pause()


def run_due_flow() -> None:
    print("\n  Running every job that is due now…")
    out = core.run_due_jobs(triggered_by=access.current().username or None)
    if not out:
        print("  Nothing is due.")
    for d in out:
        if d.run is None:
            print(f"  - {d.name}: already running elsewhere")
        else:
            print(f"  - {d.name} ({d.trigger}): {d.run.status} — {d.run.summary}")
    _pause()


def history_flow(*, problems_only: bool = False) -> None:
    name = None
    if not problems_only:
        raw = _input("Job name (blank = all jobs)")
        name = raw or None
    runs = core.list_runs(job_name=name, problems_only=problems_only, limit=50)
    if not runs:
        print("\n  (no runs)")
        _pause()
        return
    print(f"\n  {'Run':>5}  {'Job':<26} {'Trigger':<9} {'Status':<9} "
          f"{'Started':<19} {'Took':>8}  Summary")
    print("  " + "-" * 118)
    for r in runs:
        print(f"  {r.run_id:>5}  {r.job_name[:26]:<26} {r.trigger[:9]:<9} "
              f"{r.status:<9} {r.started_at:<19} {_ms(r.duration_ms):>8}  "
              f"{(r.summary or '')[:60]}")
    raw = _input("Run number for the full detail (blank = back)")
    if raw.isdigit():
        r = core.get_run(int(raw))
        if r is None:
            print("  No such run.")
        else:
            print(f"\n  Run #{r.run_id} {r.job_name} — {r.status} "
                  f"({r.trigger}{', by ' + r.triggered_by if r.triggered_by else ''})")
            print(f"  {r.started_at} → {r.finished_at or '—'} ({_ms(r.duration_ms)})")
            print(f"  Summary: {r.summary or '—'}")
            if r.error:
                print("  Errors:\n    " + r.error.replace("\n", "\n    "))
    _pause()


def inbox_flow() -> None:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_inbox,
    )
    print(f"\n  Results inbox: {results_inbox.inbox_dir()}")
    print("  Name files (or their folder) with season, year and — for EDI — board,"
          " e.g. AQA_Summer_2026_results.txt.")
    rows = results_inbox.list_files(limit=30)
    if not rows:
        print("  (nothing processed yet)")
    for r in rows:
        print(f"  #{r.file_id:<4} {r.processed_at:<19} {r.status:<9} {r.file_name}")
        if r.embargo_note:
            print(f"        {r.embargo_note}")
        if r.error:
            print(f"        ✗ {r.error[:200]}")
    _pause()


_MENU = [
    ("List jobs", list_flow),
    ("Job detail", detail_flow),
    ("Enable / disable a job", toggle_flow),
    ("Change a job's schedule", schedule_flow),
    ("Run a job now", run_now_flow),
    ("Run everything that is due", run_due_flow),
    ("History", history_flow),
    ("Problems (failed / partial / abandoned runs)",
     lambda: history_flow(problems_only=True)),
    ("Exam results inbox", inbox_flow),
]


def run() -> None:
    p = access.current()
    if not (p.can(access.ADMIN) or p.can(access.GOVERNANCE)):
        print("\n  ✗ Scheduled Jobs is for administrators and governance staff.")
        _pause()
        return
    while True:
        print(f"\n── {MENU_LABEL} ──")
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
        if not choice.isdigit() or not 1 <= int(choice) <= len(_MENU):
            print("  Invalid selection.")
            continue
        try:
            _MENU[int(choice) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except (ValueError, PermissionError) as e:
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("Scheduled Jobs CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != MENU_LABEL:
        return False
    run()
    return True
