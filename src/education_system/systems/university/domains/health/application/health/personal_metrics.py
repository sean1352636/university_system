"""Personal health metrics a student logs for themselves (weight, blood
pressure, exercise, sleep, water, mood) and the trends over them.

Table: ``personal_health_metrics`` (``infrastructure/health/health_schema``),
keyed on the student number. Only the student logs or removes their own
entries; reading follows the health record rule (the student, or the health
team — :func:`access.require_view`). Functions take an open connection and do
not commit.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from education_system.systems.university.domains.health.application.health import access

#: key -> (label, unit, lowest, highest, label of a second value or None)
METRICS = {
    "weight": ("Weight", "kg", 20, 400, None),
    "blood_pressure": ("Blood pressure", "mmHg", 50, 260, "diastolic"),
    "exercise": ("Exercise", "minutes", 0, 1440, None),
    "sleep": ("Sleep", "hours", 0, 24, None),
    "water": ("Water intake", "litres", 0, 15, None),
    "mood": ("Mood (1-10)", "", 1, 10, None),
    "wellness_assessment": ("Wellness self-assessment", "%", 0, 100, None),
}


def _own(who, student_id) -> str:
    if who is None or not who.is_student or not who.student_id \
            or str(who.student_id) != str(student_id):
        raise PermissionError("Personal health metrics are logged by the student themselves")
    return str(student_id)


def _number(value, metric, what="value") -> float:
    label, _unit, low, high, _second = METRICS[metric]
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label}: enter a number") from None
    if not low <= number <= high:
        raise ValueError(f"{label} {what} must be between {low} and {high}")
    return number


def log(conn, who, student_id, metric, value, value2=None, *, notes=None,
        recorded_on=None) -> int:
    """Record one reading; returns its id. Raises ``PermissionError`` /
    ``ValueError``."""
    student_id = _own(who, student_id)
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric!r}")
    label, unit, _low, _high, second = METRICS[metric]
    number = _number(value, metric)
    other = None
    if second:
        if value2 in (None, ""):
            raise ValueError(f"{label}: the {second} value is required")
        other = _number(value2, metric, second)
        if metric == "blood_pressure" and other >= number:
            raise ValueError("Diastolic must be lower than systolic")
    day = str(recorded_on or date.today().isoformat())[:10]
    datetime.strptime(day, "%Y-%m-%d")
    if day > date.today().isoformat():
        raise ValueError("A reading cannot be dated in the future")
    cur = conn.execute(
        "INSERT INTO personal_health_metrics (student_id, metric, value, value2, unit, notes, "
        "recorded_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (student_id, metric, number, other, unit or None, (notes or "").strip() or None, day))
    return cur.lastrowid


def history(conn, who, student_id, metric=None, *, days=30) -> list[dict]:
    """Readings in the last ``days`` days, newest first."""
    access.require_view(who, student_id)
    since = (date.today() - timedelta(days=int(days))).isoformat()
    sql = ("SELECT id, metric, value, value2, unit, notes, recorded_on FROM "
           "personal_health_metrics WHERE student_id = ? AND recorded_on >= ?")
    args: list = [str(student_id), since]
    if metric:
        sql += " AND metric = ?"
        args.append(metric)
    sql += " ORDER BY recorded_on DESC, id DESC"
    cur = conn.execute(sql, args)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def trends(conn, who, student_id, *, days=30) -> list[dict]:
    """Per metric over ``days`` days: ``{metric, label, unit, count, latest,
    average, lowest, highest, change}`` (``change`` = latest − first)."""
    rows = history(conn, who, student_id, days=days)
    out = []
    for metric, (label, unit, *_rest) in METRICS.items():
        readings = sorted((r for r in rows if r["metric"] == metric),
                          key=lambda r: (r["recorded_on"], r["id"]))
        if not readings:
            continue
        values = [r["value"] for r in readings]
        latest = readings[-1]
        out.append({
            "metric": metric, "label": label, "unit": unit, "count": len(values),
            "latest": latest["value"], "latest2": latest["value2"],
            "latest_on": latest["recorded_on"],
            "average": round(sum(values) / len(values), 1),
            "lowest": min(values), "highest": max(values),
            "change": round(values[-1] - values[0], 1),
            "days_logged": len({r["recorded_on"] for r in readings}),
        })
    return out


def remove(conn, who, entry_id) -> bool:
    """Delete one of the student's own readings."""
    if who is None or not who.student_id:
        raise PermissionError("Personal health metrics are logged by the student themselves")
    cur = conn.execute("DELETE FROM personal_health_metrics WHERE id = ? AND student_id = ?",
                       (int(entry_id), str(who.student_id)))
    return cur.rowcount > 0
