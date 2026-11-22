"""Run the sixth form's due scheduled jobs once, headless (for cron).

    python -m education_system.systems.sixth_form.interfaces.cli.governance.scheduler.run_due_jobs
    python -m ...run_due_jobs --list
    python -m ...run_due_jobs --job backup.nightly      # one job now

A crontab line running every five minutes is enough: each job keeps its
own schedule, a database lock stops it overlapping with the GUI's
background runner or another cron run, and a job missed while nothing
was running runs once on the next call. Exit status is 1 when any job
run failed (or finished Partial), so cron can mail the output.
"""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_due_jobs", description="Run the sixth form's due scheduled jobs.")
    parser.add_argument("--list", action="store_true", help="list jobs and exit")
    parser.add_argument("--job", help="run this one job now (manual run)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from education_system.systems.sixth_form.infrastructure.scheduler import core

    if args.list:
        for j in core.list_jobs():
            print(f"{j.name:26} {j.schedule_label:18} "
                  f"{'on ' if j.enabled else 'off'} next={j.next_due_at or '—':19} "
                  f"last={j.last_status or '—'}")
        return 0
    if args.job:
        try:
            run = core.run_job(args.job, trigger=core.TRIGGER_MANUAL,
                               triggered_by="cron")
        except core.ValidationError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        if run is None:
            print(f"{args.job}: already running elsewhere — not run")
            return 0
        print(f"{run.job_name}: {run.status} — {run.summary}")
        if run.error:
            print(run.error, file=sys.stderr)
        return 0 if run.status == core.SUCCESS else 1

    out = core.run_due_jobs(triggered_by="cron", headless=True)
    failed = False
    for d in out:
        if d.run is None:
            print(f"{d.name}: already running elsewhere — skipped")
            continue
        print(f"{d.name} ({d.trigger}): {d.run.status} — {d.run.summary}")
        if d.run.status != core.SUCCESS:
            failed = True
            if d.run.error:
                print(d.run.error, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
