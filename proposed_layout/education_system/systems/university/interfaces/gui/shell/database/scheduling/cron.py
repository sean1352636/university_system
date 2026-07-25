"""Cron expression parsing and scheduling utilities."""
import datetime

from education_system.systems.university.interfaces.gui.shell.database.config import (
    config, save_config, _cron_schedule_lock, _next_cron_run,
)
from education_system.systems.university.interfaces.gui.shell.database.shared_imports import logger


def _expand_cron_field(field_value, minimum, maximum):
    """Expand a single cron field into a sorted set of integers."""
    values = set()
    for token in field_value.split(','):
        token = token.strip()
        if not token:
            raise ValueError("Empty cron field token detected")

        step = 1
        if '/' in token:
            token, step_part = token.split('/', 1)
            if not step_part.isdigit():
                raise ValueError(f"Invalid cron step value '{step_part}'")
            step = int(step_part)
            if step <= 0:
                raise ValueError("Cron step value must be positive")

        if token == '*' or token == '':
            start, end = minimum, maximum
        elif '-' in token:
            start_str, end_str = token.split('-', 1)
            if not start_str.isdigit() or not end_str.isdigit():
                raise ValueError(f"Invalid cron range '{token}'")
            start, end = int(start_str), int(end_str)
        else:
            if not token.isdigit():
                raise ValueError(f"Invalid cron value '{token}'")
            start = end = int(token)

        if start < minimum or end > maximum:
            raise ValueError(f"Cron value '{token}' out of bounds ({minimum}-{maximum})")

        if start > end:
            raise ValueError(f"Cron range start greater than end in '{token}'")

        for value in range(start, end + 1, step):
            values.add(value)

    if not values:
        raise ValueError("Cron field did not produce any values")

    return sorted(values)


def _compute_cron_occurrences(cron_expr, base_time=None, occurrences=1):
    """Compute the next occurrence(s) from a cron expression."""
    base = (base_time or datetime.datetime.now()).replace(second=0, microsecond=0)
    try:
        from croniter import croniter  # type: ignore
    except Exception:
        croniter = None

    if croniter is not None:
        iterator = croniter(cron_expr, base)
        return [iterator.get_next(datetime.datetime) for _ in range(occurrences)]

    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("Cron expression must have exactly 5 fields")

    minutes = _expand_cron_field(parts[0], 0, 59)
    hours = _expand_cron_field(parts[1], 0, 23)
    days = _expand_cron_field(parts[2], 1, 31)
    months = _expand_cron_field(parts[3], 1, 12)
    weekdays = _expand_cron_field(parts[4], 0, 6)

    results = []
    candidate = base + datetime.timedelta(minutes=1)
    attempts = 0
    max_attempts = 525600  # Search up to one year ahead

    while len(results) < occurrences and attempts < max_attempts:
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in days
            and candidate.month in months
            and candidate.weekday() in weekdays
        ):
            results.append(candidate)
        candidate += datetime.timedelta(minutes=1)
        attempts += 1

    if not results:
        raise ValueError("Unable to compute next run time from cron expression within a year")

    return results


def _set_next_cron_run(next_run):
    """Store the next cron run timestamp with thread safety."""
    import education_system.systems.university.interfaces.gui.shell.database.config as cfg
    with cfg._cron_schedule_lock:
        cfg._next_cron_run = next_run


def parse_cron_schedule(cron_expr):
    """Parse cron expression and schedule backup"""
    try:
        expr = (cron_expr or "").strip()
        if not expr:
            _set_next_cron_run(None)
            config["cron_schedule"] = ""
            save_config()
            logger.info("Cleared cron schedule; scheduler will use frequency-based configuration.")
            return None

        upcoming = _compute_cron_occurrences(expr, datetime.datetime.now(), occurrences=5)
        next_run = upcoming[0]
        _set_next_cron_run(next_run)
        config["cron_schedule"] = expr
        save_config()

        preview = ", ".join(dt.strftime("%Y-%m-%d %H:%M") for dt in upcoming[:3])
        logger.info(
            "Cron schedule parsed successfully. Next run at %s. Upcoming executions: %s",
            next_run.strftime("%Y-%m-%d %H:%M"),
            preview,
        )
        return next_run
    except Exception as e:
        logger.error(f"Error parsing cron schedule: {e}")
        return False
