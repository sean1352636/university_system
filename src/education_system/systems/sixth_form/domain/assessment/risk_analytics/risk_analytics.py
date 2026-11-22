"""Predictive risk analytics for the Sixth Form System.

This module reads the data other domain modules already capture —
attendance, behaviour, baseline assessments, mock results, predicted
grades and minimum-target (MTE) grades — and distils each student down
to a single explainable **risk score** (0-100) plus a band:

    0-24   Low
    25-49  Medium
    50-74  High
    75-100 Critical

The score is a transparent weighted sum of measurable factors rather
than a black-box model, so staff can see *why* a student is flagged.
Each factor contributes points and a human-readable reason.

Alongside the risk score it produces a **per-subject outcome
prediction**: a forecast A-Level grade blending the student's baseline,
most recent mock and the teacher's predicted grade.

``scan_all(...)`` walks every active student and persists a snapshot to
the ``risk_snapshots`` table so dashboards / the early-warning module /
the parent portal can read the latest picture without recomputing.

All tables live in the shared ``sixthform.db`` file, so the read
queries join straight against the live domain tables.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_RISK_ANALYTICS_DB

# ── Grade scales ─────────────────────────────────────────────────────
# Grades are compared on the scale of the learner's own qualification
# for each subject (A level, BTEC, T Level, GCSE resit ...) via
# grade_scales. The A-level constants stay for callers that import them.
LETTER_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")
GRADE_POINTS: dict[str, int] = {"A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0}
_POINTS_TO_GRADE: dict[int, str] = {v: k for k, v in GRADE_POINTS.items()}


def _pts(grade: str | None, qualification_type: str | None) -> int | None:
    return grade_scales.grade_points(grade, qualification_type)


def _on_scale(grade: str | None, qualification_type: str | None) -> str | None:
    """*grade* if it belongs to the subject's scale, else None."""
    return grade if _pts(grade, qualification_type) is not None else None


def _grade_for_points(points: int, qualification_type: str | None) -> str:
    grades = grade_scales.grades_for(qualification_type)
    top = len(grades) - 1
    return grades[top - max(0, min(top, points))]

# ── Risk bands ───────────────────────────────────────────────────────
BANDS: tuple[str, ...] = ("Low", "Medium", "High", "Critical")


def band_for(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


# ── Tunable model weights ────────────────────────────────────────────
# Each factor caps the points it can contribute, so no single signal
# can dominate. Total possible ≈ 100.
WEIGHTS: dict[str, int] = {
    "attendance": 35,   # poor attendance is the strongest predictor
    "behaviour": 20,    # net negative behaviour points
    "grade_gap": 30,    # predicted grade below minimum target
    "mock": 15,         # mock results trailing predictions
}

# Attendance is scored on how far below this threshold the student sits.
ATTENDANCE_FLOOR_PCT: float = 95.0
# Window (days) used for behaviour + attendance recency.
DEFAULT_WINDOW_DAYS: int = 90


@dataclass
class Factor:
    """One contributing component of a risk score."""
    key: str
    points: float
    detail: str


@dataclass
class SubjectPrediction:
    subject: str
    baseline_grade: str | None
    target_grade: str | None
    predicted_grade: str | None
    latest_mock_grade: str | None
    forecast_grade: str | None
    on_target: bool | None
    qualification_type: str | None = None


@dataclass
class RiskAssessment:
    student_id: str
    full_name: str
    score: float
    band: str
    attendance_pct: float | None
    behaviour_points: int
    factors: list[Factor] = field(default_factory=list)
    predictions: list[SubjectPrediction] = field(default_factory=list)
    computed_at: str = ""
    # What is already being done about it: open early-warning alerts and
    # open interventions for this student at the time of the assessment.
    open_alerts: int = 0
    open_interventions: int = 0


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_snapshots (
    snapshot_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    score            REAL NOT NULL,
    band             TEXT NOT NULL,
    attendance_pct   REAL,
    behaviour_points INTEGER NOT NULL DEFAULT 0,
    factors_json     TEXT,
    predictions_json TEXT,
    computed_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_student ON risk_snapshots(student_id);
CREATE INDEX IF NOT EXISTS idx_risk_band    ON risk_snapshots(band);
CREATE INDEX IF NOT EXISTS idx_risk_when    ON risk_snapshots(computed_at);
"""

_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(risk_snapshots)").fetchall()}
        for col in ("open_alerts", "open_interventions"):
            if col not in cols:
                conn.execute(f"ALTER TABLE risk_snapshots "
                             f"ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
    _DB_READY = True
    logger.debug("Risk-analytics schema ready at %s", DB_PATH)


# ── Helpers ──────────────────────────────────────────────────────────

def _today() -> _dt.date:
    return _dt.date.today()


def _window_start(days: int) -> str:
    return (_today() - _dt.timedelta(days=days)).isoformat()


def _student_subjects(conn: sqlite3.Connection, student_id: str) -> list[str]:
    """Subjects the learner is on: active learning aims, else the old slots."""
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        subjects = [a.subject for a in learning_aims.active_aims(student_id)]
        if subjects:
            return list(dict.fromkeys(subjects))
    except Exception:
        logger.debug("learning aims unavailable for %s", student_id, exc_info=True)
    row = conn.execute(
        "SELECT subject_1, subject_2, subject_3 FROM students WHERE student_id=?",
        (student_id,),
    ).fetchone()
    if not row:
        return []
    return [s for s in (row["subject_1"], row["subject_2"], row["subject_3"]) if s]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


# ── Factor computations ──────────────────────────────────────────────

def _attendance_factor(conn: sqlite3.Connection, student_id: str,
                       window_days: int) -> tuple[float | None, Factor | None]:
    """Attendance % over the window and its risk contribution.

    Present/Late count as attending; Absent counts against. Authorised
    absences are excluded from the denominator (they aren't a risk).
    """
    if not _table_exists(conn, "attendance_records"):
        return None, None
    start = _window_start(window_days)
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS n
          FROM attendance_records
         WHERE student_id=? AND date>=?
         GROUP BY status
        """,
        (student_id, start),
    ).fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    attending = counts.get("Present", 0) + counts.get("Late", 0)
    counted = attending + counts.get("Absent", 0)
    if counted == 0:
        return None, None
    pct = round(100.0 * attending / counted, 1)
    # Points scale linearly from the floor (95%) down to 0% capped.
    deficit = max(0.0, ATTENDANCE_FLOOR_PCT - pct)
    points = min(WEIGHTS["attendance"],
                 WEIGHTS["attendance"] * deficit / ATTENDANCE_FLOOR_PCT)
    factor = None
    if points > 0:
        factor = Factor("attendance", round(points, 1),
                        f"Attendance {pct}% (last {window_days}d, target ≥95%)")
    return pct, factor


def _behaviour_factor(conn: sqlite3.Connection, student_id: str,
                      window_days: int) -> tuple[int, Factor | None]:
    if not _table_exists(conn, "behaviour_entries"):
        return 0, None
    start = _window_start(window_days)
    rows = conn.execute(
        """
        SELECT entry_type, COALESCE(SUM(points),0) AS pts, COUNT(*) AS n
          FROM behaviour_entries
         WHERE student_id=? AND entry_date>=?
         GROUP BY entry_type
        """,
        (student_id, start),
    ).fetchall()
    by_type = {r["entry_type"]: (r["pts"], r["n"]) for r in rows}
    neg = by_type.get("Negative", (0, 0))[0]
    pos = by_type.get("Positive", (0, 0))[0]
    net_negative = max(0, neg - pos)
    if net_negative == 0:
        return net_negative, None
    # 5 net negative points → half of the cap; saturates beyond ~10.
    points = min(WEIGHTS["behaviour"], WEIGHTS["behaviour"] * net_negative / 10.0)
    return net_negative, Factor(
        "behaviour", round(points, 1),
        f"{net_negative} net negative behaviour points (last {window_days}d)")


def _grade_gap_factor(predictions: list[SubjectPrediction]) -> Factor | None:
    """Risk from predicted grades sitting below the minimum target."""
    gaps = []
    for p in predictions:
        target = _pts(p.target_grade, p.qualification_type)
        predicted = _pts(p.predicted_grade, p.qualification_type)
        if target is not None and predicted is not None:
            gap = target - predicted
            if gap > 0:
                gaps.append((p.subject, gap))
    if not gaps:
        return None
    total_gap = sum(g for _, g in gaps)
    # Each grade-below-target ≈ 10 points, capped.
    points = min(WEIGHTS["grade_gap"], WEIGHTS["grade_gap"] * total_gap / 3.0)
    worst = ", ".join(f"{s} ({g} below)" for s, g in gaps)
    return Factor("grade_gap", round(points, 1),
                  f"Predicted below target: {worst}")


def _mock_factor(predictions: list[SubjectPrediction]) -> Factor | None:
    """Risk from latest mock grades trailing the predicted grade."""
    gaps = []
    for p in predictions:
        predicted = _pts(p.predicted_grade, p.qualification_type)
        mock = _pts(p.latest_mock_grade, p.qualification_type)
        if predicted is not None and mock is not None:
            gap = predicted - mock
            if gap > 0:
                gaps.append((p.subject, gap))
    if not gaps:
        return None
    total = sum(g for _, g in gaps)
    points = min(WEIGHTS["mock"], WEIGHTS["mock"] * total / 3.0)
    worst = ", ".join(f"{s} ({g} below)" for s, g in gaps)
    return Factor("mock", round(points, 1),
                  f"Mocks trailing prediction: {worst}")


# ── Outcome prediction ───────────────────────────────────────────────

def _latest_mock_grade(conn: sqlite3.Connection, student_id: str,
                       subject: str,
                       qualification_type: str | None = None) -> str | None:
    if not (_table_exists(conn, "mock_results") and _table_exists(conn, "mock_exams")):
        return None
    row = conn.execute(
        """
        SELECT r.grade
          FROM mock_results r
          JOIN mock_exams  e ON e.mock_id = r.mock_id
         WHERE r.student_id=? AND e.subject=? AND r.grade IS NOT NULL
         ORDER BY e.date_sat DESC
         LIMIT 1
        """,
        (student_id, subject),
    ).fetchone()
    return _on_scale(row["grade"], qualification_type) if row else None


def _forecast(baseline: str | None, mock: str | None,
              predicted: str | None,
              qualification_type: str | None = None) -> str | None:
    """Blend available signals into a single forecast grade.

    Weighting favours hard evidence: latest mock 50%, teacher prediction
    35%, baseline 15%. Missing signals are dropped and the remaining
    weights renormalised. Returns None when nothing is known.
    """
    parts = [(mock, 0.50), (predicted, 0.35), (baseline, 0.15)]
    usable = [(_pts(g, qualification_type), w) for g, w in parts]
    usable = [(p, w) for p, w in usable if p is not None]
    if not usable:
        return None
    total_w = sum(w for _, w in usable)
    pts = sum(p * w for p, w in usable) / total_w
    return _grade_for_points(round(pts), qualification_type)


def _qualification_type(student_id: str, subject: str) -> str | None:
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        return learning_aims.qualification_type_for(student_id, subject)
    except Exception:
        return None


def _predictions_for(conn: sqlite3.Connection, student_id: str) -> list[SubjectPrediction]:
    out: list[SubjectPrediction] = []
    for subject in _student_subjects(conn, student_id):
        qtype = _qualification_type(student_id, subject)
        predicted = None
        if _table_exists(conn, "predicted_grades"):
            r = conn.execute(
                "SELECT grade FROM predicted_grades WHERE student_id=? AND subject=?",
                (student_id, subject),
            ).fetchone()
            predicted = _on_scale(r["grade"], qtype) if r else None
        target = None
        if _table_exists(conn, "targets"):
            r = conn.execute(
                "SELECT mte_grade FROM targets WHERE student_id=? AND subject_name=?",
                (student_id, subject),
            ).fetchone()
            target = _on_scale(r["mte_grade"], qtype) if r else None
        baseline = None
        if _table_exists(conn, "baseline_records"):
            r = conn.execute(
                """
                SELECT baseline_grade FROM baseline_records
                 WHERE student_id=? AND subject_name=? AND baseline_grade IS NOT NULL
                 ORDER BY is_primary DESC, assessment_date DESC LIMIT 1
                """,
                (student_id, subject),
            ).fetchone()
            baseline = _on_scale(r["baseline_grade"], qtype) if r else None
        mock = _latest_mock_grade(conn, student_id, subject, qtype)
        forecast = _forecast(baseline, mock, predicted, qtype)
        on_target = None
        if forecast and target:
            on_target = _pts(forecast, qtype) >= _pts(target, qtype)
        out.append(SubjectPrediction(
            subject=subject, baseline_grade=baseline, target_grade=target,
            predicted_grade=predicted, latest_mock_grade=mock,
            forecast_grade=forecast, on_target=on_target,
            qualification_type=qtype))
    return out


# ── Public API ───────────────────────────────────────────────────────

def assess_student(student_id: str, *, window_days: int = DEFAULT_WINDOW_DAYS,
                   conn: sqlite3.Connection | None = None) -> RiskAssessment:
    """Compute a live risk assessment for one student (no persistence)."""
    init_db()
    own = conn is None
    conn = conn or _connect()
    try:
        srow = conn.execute(
            "SELECT first_name, last_name FROM students WHERE student_id=?",
            (student_id,),
        ).fetchone()
        if not srow:
            raise ValueError(f"Unknown student: {student_id}")
        full_name = f"{srow['first_name']} {srow['last_name']}".strip()

        predictions = _predictions_for(conn, student_id)
        att_pct, att_factor = _attendance_factor(conn, student_id, window_days)
        beh_points, beh_factor = _behaviour_factor(conn, student_id, window_days)
        gap_factor = _grade_gap_factor(predictions)
        mock_factor = _mock_factor(predictions)

        factors = [f for f in (att_factor, beh_factor, gap_factor, mock_factor) if f]
        score = round(min(100.0, sum(f.points for f in factors)), 1)
        open_alerts, open_ivs = _open_action_counts(conn, student_id)
        return RiskAssessment(
            student_id=student_id, full_name=full_name, score=score,
            band=band_for(score), attendance_pct=att_pct,
            behaviour_points=beh_points, factors=factors,
            predictions=predictions, computed_at=_dt.datetime.now().isoformat(timespec="seconds"),
            open_alerts=open_alerts, open_interventions=open_ivs)
    finally:
        if own:
            conn.close()


# Open statuses as the owning modules define them (early_warning /
# intervention_tracking). Kept here as SQL literals because the scan runs
# on one shared connection.
_OPEN_ALERT_STATUSES = ("Open", "Acknowledged", "Escalated")
_OPEN_INTERVENTION_STATUSES = ("Planned", "Active", "Paused")


def _open_action_counts(conn: sqlite3.Connection,
                        student_id: str) -> tuple[int, int]:
    alerts = ivs = 0
    if _table_exists(conn, "early_warning_alerts"):
        ph = ",".join("?" * len(_OPEN_ALERT_STATUSES))
        alerts = conn.execute(
            f"SELECT COUNT(*) FROM early_warning_alerts "
            f"WHERE student_id=? AND status IN ({ph})",
            (student_id, *_OPEN_ALERT_STATUSES)).fetchone()[0]
    if _table_exists(conn, "interventions"):
        ph = ",".join("?" * len(_OPEN_INTERVENTION_STATUSES))
        ivs = conn.execute(
            f"SELECT COUNT(*) FROM interventions "
            f"WHERE student_id=? AND status IN ({ph})",
            (student_id, *_OPEN_INTERVENTION_STATUSES)).fetchone()[0]
    return alerts, ivs


@dataclass
class RiskPicture:
    """A student's risk score next to what is being done about it."""
    assessment: RiskAssessment
    latest_snapshot: dict[str, Any] | None
    open_alerts: list[Any] = field(default_factory=list)
    open_interventions: list[Any] = field(default_factory=list)

    @property
    def unanswered_alerts(self) -> list[Any]:
        """Open alerts that have not opened (or been linked to) an
        intervention yet."""
        live = {iv.intervention_id for iv in self.open_interventions}
        return [a for a in self.open_alerts
                if a.linked_intervention_id not in live]


def student_risk_picture(student_id: str, *,
                         window_days: int = DEFAULT_WINDOW_DAYS) -> RiskPicture:
    """Live assessment + latest snapshot + open alerts and interventions,
    read from the early-warning and intervention modules (no copies)."""
    from education_system.systems.sixth_form.domain.assessment.early_warning import (
        early_warning as _ew,
    )
    from education_system.systems.sixth_form.domain.assessment.intervention_tracking import (
        intervention_tracking as _iv,
    )
    assessment = assess_student(student_id, window_days=window_days)
    snap = next((s for s in latest_snapshots() if s["student_id"] == student_id),
                None)
    return RiskPicture(
        assessment=assessment,
        latest_snapshot=snap,
        open_alerts=[a for a in _ew.alerts_for_student(student_id) if a.is_open],
        open_interventions=_iv.open_interventions_for_student(student_id),
    )


def _active_student_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT student_id FROM students WHERE COALESCE(status,'Active')='Active' "
        "ORDER BY last_name, first_name"
    ).fetchall()
    return [r["student_id"] for r in rows]


def scan_all(*, window_days: int = DEFAULT_WINDOW_DAYS,
             persist: bool = True,
             errors: list[str] | None = None) -> list[RiskAssessment]:
    """Assess every active student. When ``persist`` is set, write one
    snapshot row per student into ``risk_snapshots`` (highest risk first
    is the natural read order via the band/score indexes).

    A student whose assessment fails is left out of the results; pass a
    list as ``errors`` to get one line per failure (the scheduled scan
    does, so failures show in the job history instead of vanishing)."""
    init_db()
    results: list[RiskAssessment] = []
    with _connect() as conn:
        for sid in _active_student_ids(conn):
            try:
                results.append(assess_student(sid, window_days=window_days, conn=conn))
            except Exception as e:
                logger.exception("Risk assessment failed for %s", sid)
                if errors is not None:
                    errors.append(f"{sid}: {type(e).__name__}: {e}")
        if persist:
            for r in results:
                conn.execute(
                    """
                    INSERT INTO risk_snapshots
                        (student_id, score, band, attendance_pct,
                         behaviour_points, factors_json, predictions_json,
                         open_alerts, open_interventions)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (r.student_id, r.score, r.band, r.attendance_pct,
                     r.behaviour_points,
                     json.dumps([f.__dict__ for f in r.factors]),
                     json.dumps([p.__dict__ for p in r.predictions]),
                     r.open_alerts, r.open_interventions),
                )
            conn.commit()
    results.sort(key=lambda r: r.score, reverse=True)
    logger.info("Risk scan complete: %d students, %d high+",
                len(results), sum(1 for r in results if r.band in ("High", "Critical")))
    return results


def latest_snapshots(*, band: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    """Most recent snapshot per student, optionally filtered to a band,
    ordered by score descending."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.*, st.first_name, st.last_name
              FROM risk_snapshots s
              JOIN students st ON st.student_id = s.student_id
              JOIN (SELECT student_id, MAX(snapshot_id) AS mx
                      FROM risk_snapshots GROUP BY student_id) latest
                ON latest.student_id = s.student_id AND latest.mx = s.snapshot_id
             ORDER BY s.score DESC
            """
        ).fetchall()
    out = []
    for r in rows:
        if band and r["band"] != band:
            continue
        out.append({
            "student_id": r["student_id"],
            "full_name": f"{r['first_name']} {r['last_name']}".strip(),
            "score": r["score"], "band": r["band"],
            "attendance_pct": r["attendance_pct"],
            "behaviour_points": r["behaviour_points"],
            "factors": json.loads(r["factors_json"] or "[]"),
            "predictions": json.loads(r["predictions_json"] or "[]"),
            "computed_at": r["computed_at"],
            "open_alerts": r["open_alerts"],
            "open_interventions": r["open_interventions"],
        })
    return out[:limit]


def summary() -> dict[str, int]:
    """Count of students in each band from the latest snapshots."""
    counts = {b: 0 for b in BANDS}
    for snap in latest_snapshots():
        counts[snap["band"]] = counts.get(snap["band"], 0) + 1
    return counts
