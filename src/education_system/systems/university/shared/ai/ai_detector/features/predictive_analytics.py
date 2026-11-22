"""Predictive analytics for the people who review AI-writing readings.

Nothing here scores or profiles a student. Predicting who will "cheat" from
their past readings would turn unreliable indicators into a label that
follows a person, so it is not done; ``predict_student_risk`` stays only so
older callers get a clear "not used" answer.

What is predicted instead:

* :func:`forecast_review_workload` — how many readings will need review per
  module over the coming weeks, from the weekly history (seasonal-naive
  when a year of history exists, else a least-squares trend over recent
  weeks), so reviewers can plan.
* :func:`reviewer_agreement` — for one reading, how often readings like it
  were confirmed by a person: the active model's estimate (trained on human
  outcomes, ``ml/indicator_model``) and the plain historical rate for
  readings of similar strength, with a Wilson 95% interval.

Staff only, limited to the modules the person reviews.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger
from education_system.systems.university.shared.ai.ai_detector.ml import indicator_model as im

HISTORY_WEEKS = 26
TREND_WEEKS = 8
BAND = 0.1
NOT_USED = ("Per-student risk prediction is not used: it would label students from "
            "indicators that are not evidence. See the review workload forecast instead.")


def _access():
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    return integrity_access


def _week(day: datetime) -> str:
    monday = day - timedelta(days=day.weekday())
    return monday.strftime("%Y-%m-%d")


def _parse(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)[:19])
    except (TypeError, ValueError):
        return None


def forecast_review_workload(conn, who, *, weeks_ahead=4, module_code=None,
                             now=None) -> list[dict]:
    """Per module: weekly history of readings at or above the review
    threshold and the expected count for each coming week."""
    access = _access()
    access.require(who is not None and who.is_staff, "Forecasts are for staff")
    access.ensure(conn)
    now = now or datetime.now()
    threshold = access.number(conn, "ai_review_threshold")
    start = now - timedelta(weeks=60)        # a year back, for same-week-last-year
    sql = ("SELECT s.course_code, r.created_at FROM ai_detector_results r JOIN "
           "ai_detector_submissions s ON s.id = r.submission_id WHERE r.ai_score >= ? AND "
           "r.created_at >= ? AND s.course_code IS NOT NULL")
    params: list = [threshold, start.strftime("%Y-%m-%d")]
    modules = access.taught_modules(conn, who)
    if modules is not None:
        sql += f" AND s.course_code IN ({','.join('?' * len(modules)) or 'NULL'})"
        params += modules
    if module_code:
        sql += " AND s.course_code = ?"
        params.append(module_code)
    counts: dict[str, dict[str, int]] = {}
    for module, at in conn.execute(sql, params).fetchall():
        day = _parse(at)
        if day:
            counts.setdefault(module, {}).setdefault(_week(day), 0)
            counts[module][_week(day)] += 1
    this_week = datetime.strptime(_week(now), "%Y-%m-%d")
    out = []
    for module, weekly in sorted(counts.items()):
        history = [(this_week - timedelta(weeks=k)).strftime("%Y-%m-%d")
                   for k in range(HISTORY_WEEKS, 0, -1)]
        series = [weekly.get(w, 0) for w in history]
        method, forecast = _forecast(weekly, series, this_week, weeks_ahead)
        out.append({"module_code": module,
                    "history": [{"week": w, "count": c} for w, c in zip(history, series)],
                    "forecast": forecast, "method": method,
                    "expected_total": round(sum(f["expected"] for f in forecast), 1)})
    return out


def _forecast(weekly, series, this_week, weeks_ahead):
    first = min(weekly) if weekly else None
    have_year = first and datetime.strptime(first, "%Y-%m-%d") <= this_week - timedelta(weeks=52)
    out = []
    if have_year:
        for k in range(weeks_ahead):
            target = this_week + timedelta(weeks=k)
            last_year = (target - timedelta(weeks=52)).strftime("%Y-%m-%d")
            out.append({"week": target.strftime("%Y-%m-%d"),
                        "expected": float(weekly.get(last_year, 0))})
        return "same week last year (seasonal-naive)", out
    recent = series[-TREND_WEEKS:]
    n = len(recent)
    mean_x, mean_y = (n - 1) / 2, sum(recent) / n
    var = sum((x - mean_x) ** 2 for x in range(n))
    slope = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(recent)) / var if var else 0.0
    for k in range(weeks_ahead):
        target = this_week + timedelta(weeks=k)
        value = mean_y + slope * (n - mean_x + k)
        out.append({"week": target.strftime("%Y-%m-%d"), "expected": round(max(0.0, value), 1)})
    return f"trend over the last {TREND_WEEKS} weeks", out


def _wilson(successes, n, z=1.96):
    if not n:
        return None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def reviewer_agreement(conn, who, ai_result_id) -> Dict[str, Any]:
    """How often readings like this one were confirmed by a person."""
    access = _access()
    access.require(who is not None and who.is_staff, "This is for staff")
    access.ensure(conn)
    row = conn.execute("SELECT r.ai_score, r.detailed_results, s.course_code FROM "
                       "ai_detector_results r JOIN ai_detector_submissions s ON "
                       "s.id = r.submission_id WHERE r.id = ?", (ai_result_id,)).fetchone()
    if not row:
        raise ValueError(f"No AI-writing reading {ai_result_id}")
    access.require(access.can_review(conn, who, row[2]), "You cannot see this reading")
    strength = float(row[0] or 0)
    similar = [d for d in im.labelled_set(conn) if d["ai_result_id"] != ai_result_id]
    scores = {r[0]: float(r[1] or 0) for r in conn.execute(
        "SELECT id, ai_score FROM ai_detector_results WHERE id IN "
        f"({','.join('?' * len(similar)) or 'NULL'})",  # nosec B608
        [d["ai_result_id"] for d in similar])}
    near = [d for d in similar if abs(scores.get(d["ai_result_id"], -9) - strength) <= BAND]
    confirmed = sum(d["label"] for d in near)
    return {"ai_result_id": ai_result_id, "strength": strength,
            "model": im.estimate(conn, row[1]),
            "history": {"similar_readings": len(near), "confirmed": confirmed,
                        "rate": round(confirmed / len(near), 4) if near else None,
                        "interval_95": _wilson(confirmed, len(near)),
                        "band": [round(strength - BAND, 2), round(strength + BAND, 2)]},
            "meaning": "Context for the reviewer: how often similar readings were confirmed "
                       "after review. It says nothing about this student."}


class PredictiveAnalytics:
    """The detector's handle on predictions (its own short connections)."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def _who(self, conn):
        return _access().from_user(conn, getattr(self.detector, "current_user", None))

    def _run(self, fn, *args, **kwargs):
        conn = self.detector._safe_db_connect()
        try:
            return fn(conn, self._who(conn), *args, **kwargs)
        finally:
            conn.close()

    @property
    def risk_model(self):
        """Whether an indicator model is active (the only model used)."""
        conn = self.detector._safe_db_connect()
        try:
            return im.active(conn)
        except Exception as exc:
            logger.debug(f"No active model: {exc}")
            return None
        finally:
            conn.close()

    def train_risk_prediction_model(self):
        """Kept for older callers; nothing is trained per student."""
        return {"trained": False, "note": NOT_USED}

    def predict_student_risk(self, student_id: str) -> Dict[str, Any]:
        """Kept for older callers: no per-student prediction is made."""
        return {"risk_score": None, "risk_level": "not_used", "note": NOT_USED}

    def forecast_review_workload(self, weeks_ahead: int = 4, module_code: str = None):
        return self._run(forecast_review_workload, weeks_ahead=weeks_ahead,
                         module_code=module_code)

    def reviewer_agreement(self, ai_result_id: int):
        return self._run(reviewer_agreement, ai_result_id)
