"""Recurring bulk jobs: cron schedules that actually run.

``bulk_schedules`` rows (created by :func:`ops_records.create_schedule`
/ "Schedule recurring job") name a bulk operation, its parameters and a
standard five-field cron expression. :func:`run_due_schedules` — run by
the sixth form scheduler — calls the operation for every enabled
schedule whose ``next_run_at`` has passed, stamps ``last_run_at`` /
``last_job_id`` / ``last_status`` / ``last_error``, and moves
``next_run_at`` to the next cron time *after now*, so a schedule missed
while the app was closed runs once, not once per missed slot.

Targets: an operation that takes ``student_ids`` reads them from the
schedule's parameters at run time —

* ``student_ids`` — a list or comma-separated ids;
* ``cohort`` — an Advanced Search cohort name or id (its members *at
  the time of the run*);
* ``audience = on_roll`` — every learner currently on roll.

Other parameters are passed by name and converted to the type the
operation's signature declares. Irreversible operations (GDPR
redaction, anonymisation, undo) cannot be scheduled.
"""

from __future__ import annotations

import datetime as _dt
import importlib
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    OPERATIONS,
    ValidationError,
    _connect,
    init_db,
)

logger = logging.getLogger(__name__)

NOT_SCHEDULABLE: frozenset[str] = frozenset({
    "schedule_recurring", "undo_job", "gdpr_redact", "anonymise_alumni",
})

_OPS_MODULES = ("ops_comms", "ops_attendance", "ops_academic", "ops_behaviour",
                "ops_finance", "ops_records")
_FUNCTION_ALIASES = {"exam_timetables": "bulk_export_exam_timetables"}
_FMT = "%Y-%m-%d %H:%M"


def validate_cron(expr: str | None) -> str:
    from croniter import croniter
    expr = " ".join((expr or "").split())
    if not expr:
        raise ValidationError("A cron expression is required (e.g. '0 9 * * 1')")
    if len(expr.split()) != 5 or not croniter.is_valid(expr):
        raise ValidationError(
            f"Not a valid five-field cron expression: {expr!r} "
            "(minute hour day-of-month month day-of-week, e.g. '0 9 * * 1')")
    return expr


def validate_when(value: str) -> str:
    s = (value or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s, fmt).strftime(_FMT)
        except ValueError:
            continue
    raise ValidationError("First run must be YYYY-MM-DD HH:MM")


def next_run(expr: str, after: _dt.datetime | None = None) -> str:
    from croniter import croniter
    base = (after or _dt.datetime.now()).replace(second=0, microsecond=0)
    return croniter(expr, base).get_next(_dt.datetime).strftime(_FMT)


def operation_function(operation: str) -> Callable[..., Any]:
    if operation not in OPERATIONS:
        raise ValidationError(f"Unknown operation {operation!r}")
    name = _FUNCTION_ALIASES.get(operation, f"bulk_{operation}")
    for mod_name in _OPS_MODULES:
        mod = importlib.import_module(
            "education_system.systems.sixth_form.domain.learners."
            f"bulk_operations.{mod_name}")
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    raise ValidationError(f"Operation {operation!r} has no bulk function")


def check_schedulable(operation: str) -> None:
    if operation in NOT_SCHEDULABLE:
        raise ValidationError(
            f"{operation!r} cannot be scheduled — it is irreversible or "
            "meta; run it by hand")
    operation_function(operation)


# ── Parameter handling ──────────────────────────────────────────────

def _as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    if s.startswith("["):
        try:
            return [str(v).strip() for v in json.loads(s) if str(v).strip()]
        except ValueError:
            pass
    return [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]


def _coerce(value: Any, annotation: Any) -> Any:
    ann = str(annotation or "")
    if not isinstance(value, str):
        return value
    v = value.strip()
    if ann.startswith("list") or ann.startswith("tuple"):
        items = _as_list(v)
        return [int(i) for i in items] if "int" in ann else items
    if ann.startswith("dict"):
        return json.loads(v) if v else {}
    if ann.startswith("bool"):
        return v.lower() in ("1", "true", "yes", "y", "on")
    if ann.startswith("int") and v:
        return int(v)
    if ann.startswith("float") and v:
        return float(v)
    if v == "" and "None" in ann:
        return None
    return v


def resolve_targets(params: dict[str, Any]) -> list[str]:
    """The student ids a schedule acts on, worked out now."""
    if params.get("student_ids"):
        return _as_list(params["student_ids"])
    if params.get("cohort"):
        from education_system.systems.sixth_form.domain.learners.advanced_search import (
            history,
        )
        members = history.cohort_members(str(params["cohort"]).strip())
        if not members:
            raise ValidationError(f"Cohort {params['cohort']!r} is empty or unknown")
        return list(members)
    if str(params.get("audience") or "").strip().lower() in ("on_roll", "all", "all_on_roll"):
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        return [s.student_id for s in _students.list_students()
                if s.status in _students.ON_ROLL_STATUSES]
    raise ValidationError(
        "No targets: give student_ids, cohort or audience=on_roll")


def build_call(operation: str, params: dict[str, Any], *,
               ran_by: str) -> tuple[Callable[..., Any], list[Any], dict[str, Any]]:
    fn = operation_function(operation)
    sig = inspect.signature(fn)
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    reserved = {"student_ids", "cohort", "audience"}
    for pname, prm in sig.parameters.items():
        if pname == "student_ids":
            targets = resolve_targets(params)
            if prm.kind in (prm.POSITIONAL_ONLY, prm.POSITIONAL_OR_KEYWORD):
                args.append(targets)
            else:
                kwargs[pname] = targets
            continue
        if pname == "dry_run":
            kwargs[pname] = False
            continue
        if pname == "ran_by":
            kwargs[pname] = ran_by
            continue
        if pname in params:
            value = _coerce(params[pname], prm.annotation)
            if prm.kind in (prm.POSITIONAL_ONLY, prm.POSITIONAL_OR_KEYWORD) \
                    and prm.default is prm.empty:
                args.append(value)
            else:
                kwargs[pname] = value
        elif prm.default is prm.empty and prm.kind not in (prm.VAR_POSITIONAL,
                                                           prm.VAR_KEYWORD):
            raise ValidationError(f"Parameter {pname!r} is required for {operation}")
    unknown = set(params) - set(sig.parameters) - reserved
    if unknown:
        raise ValidationError(
            f"{operation} does not take: {', '.join(sorted(unknown))}")
    return fn, args, kwargs


# ── Running ─────────────────────────────────────────────────────────

@dataclass
class ScheduleRun:
    schedule_id: int
    name: str
    operation: str
    ok: bool
    job_id: int | None = None
    successes: int = 0
    failures: int = 0
    error: str | None = None


@dataclass
class RecurringReport:
    runs: list[ScheduleRun] = field(default_factory=list)
    initialised: int = 0

    @property
    def errors(self) -> list[str]:
        out = []
        for r in self.runs:
            if not r.ok:
                out.append(f"Schedule #{r.schedule_id} {r.name!r}: {r.error}")
            elif r.failures:
                out.append(f"Schedule #{r.schedule_id} {r.name!r}: "
                           f"{r.failures} target(s) failed (bulk job #{r.job_id})")
        return out

    @property
    def summary(self) -> str:
        ok = sum(1 for r in self.runs if r.ok)
        return (f"{len(self.runs)} recurring bulk job(s) run, {ok} completed, "
                f"{len(self.runs) - ok} failed"
                + (f"; {self.initialised} new schedule(s) given a first run time"
                   if self.initialised else ""))


def _store(schedule_id: int, **fields: Any) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(f"UPDATE bulk_schedules SET {sets} WHERE schedule_id = ?",
                     (*fields.values(), schedule_id))
        conn.commit()


def run_schedule(schedule_id: int, *, now: _dt.datetime | None = None) -> ScheduleRun:
    """Run one schedule now and move it to its next cron time."""
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        ops_records,
    )
    now = now or _dt.datetime.now()
    sch = ops_records.get_schedule(schedule_id)
    if sch is None:
        raise ValidationError(f"No schedule #{schedule_id}")
    run = ScheduleRun(schedule_id=sch.schedule_id, name=sch.name,
                      operation=sch.operation, ok=False)
    try:
        check_schedulable(sch.operation)
        fn, args, kwargs = build_call(sch.operation, sch.parameters,
                                      ran_by=f"schedule#{sch.schedule_id}")
        result = fn(*args, **kwargs)
        run.ok = True
        run.job_id = getattr(result, "job_id", None)
        run.successes = int(getattr(result, "success_count", 0) or 0)
        run.failures = int(getattr(result, "failure_count", 0) or 0)
    except Exception as e:  # noqa: BLE001 - recorded on the schedule and reported
        run.error = str(e) or type(e).__name__
        logger.exception("Recurring bulk schedule #%d failed", sch.schedule_id)
    try:
        nxt = next_run(validate_cron(sch.cron_expr), now)
    except ValidationError as e:
        nxt = None
        run.error = run.error or str(e)
    _store(sch.schedule_id,
           last_run_at=now.strftime(_FMT),
           last_job_id=run.job_id if run.job_id is not None else sch.last_job_id,
           last_status=("Completed" if run.ok and not run.failures else
                        "Completed with failures" if run.ok else "Failed"),
           last_error=run.error,
           next_run_at=nxt,
           # A schedule whose cron can no longer be read stops rather
           # than failing every tick.
           enabled=1 if nxt else 0)
    return run


def run_due_schedules(*, now: _dt.datetime | None = None) -> RecurringReport:
    init_db()
    now = (now or _dt.datetime.now()).replace(second=0, microsecond=0)
    stamp = now.strftime(_FMT)
    report = RecurringReport()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT schedule_id, cron_expr, next_run_at FROM bulk_schedules "
            "WHERE enabled = 1 ORDER BY schedule_id").fetchall()
    for r in rows:
        if not r["next_run_at"]:
            try:
                _store(r["schedule_id"], next_run_at=next_run(
                    validate_cron(r["cron_expr"]), now))
                report.initialised += 1
            except ValidationError as e:
                _store(r["schedule_id"], enabled=0, last_status="Failed",
                       last_error=str(e))
            continue
        try:
            due = validate_when(r["next_run_at"]) <= stamp
        except ValidationError:
            due = True
        if due:
            report.runs.append(run_schedule(r["schedule_id"], now=now))
    return report
