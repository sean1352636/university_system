"""
Course-evaluation analytics service (features 20-25).

20. Live response-rate dashboard data
21. Cross-term trend series for instructor or module
22. Benchmark a course against department / faculty / institution
23. Word-cloud + simple topic clustering on free-text answers
24. Sentiment scoring (lexicon, reuses respondent.sentiment) cached per answer
25. Outlier / suspicious-response detection (straight-lining, speeders)
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from statistics import mean, pstdev
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.domain.academics.services.evaluation.respondent import (
    sentiment,
)


# ---------- Response rate (20) ----------

def response_rate(evaluation_id: int) -> dict:
    with get_connection() as conn:
        roster = conn.execute(
            "SELECT COUNT(*) FROM evaluation_rosters WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()[0]
        responses = conn.execute(
            "SELECT COUNT(*) FROM evaluation_responses WHERE evaluation_id=? AND is_complete=1",
            (evaluation_id,),
        ).fetchone()[0]
        invited = conn.execute(
            "SELECT COUNT(*) FROM evaluation_invitations WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()[0]
    denom = roster or invited
    pct = round(responses * 100 / denom, 1) if denom else 0.0
    return {"evaluation_id": evaluation_id, "responses": responses,
            "roster": roster, "invited": invited, "percent": pct}


def dashboard_summary() -> list[dict]:
    """One row per evaluation for the live response-rate dashboard."""
    with get_connection() as conn:
        evals = conn.execute(
            """SELECT evaluation_id, module_code, academic_year, semester,
                      instructor_id, is_active, start_date, end_date
               FROM course_evaluations
               ORDER BY start_date DESC"""
        ).fetchall()
    out = []
    for e in evals:
        d = dict(e)
        d.update(response_rate(d["evaluation_id"]))
        out.append(d)
    return out


# ---------- Trends across terms (21) ----------

def instructor_trend(instructor_id: str) -> list[dict]:
    return _trend_by("instructor_id", instructor_id)


def module_trend(module_code: str) -> list[dict]:
    return _trend_by("module_code", module_code)


def _trend_by(column: str, value: str) -> list[dict]:
    if column not in ("instructor_id", "module_code"):
        raise ValueError("Unsupported column")
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT e.evaluation_id, e.module_code, e.academic_year, e.semester,
                       e.instructor_id, AVG(a.numeric_value) AS avg_score,
                       COUNT(DISTINCT r.response_id) AS responses
                FROM course_evaluations e
                LEFT JOIN evaluation_responses r ON r.evaluation_id = e.evaluation_id AND r.is_complete = 1
                LEFT JOIN evaluation_answers a ON a.response_id = r.response_id AND a.numeric_value IS NOT NULL
                WHERE e.{column} = ?
                GROUP BY e.evaluation_id
                ORDER BY e.academic_year, e.semester""",
            (value,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- Benchmarks (22) ----------

def _scope_avg(scope_filter: str, args: tuple) -> float | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""SELECT AVG(a.numeric_value)
                FROM evaluation_answers a
                JOIN evaluation_responses r ON r.response_id = a.response_id
                JOIN course_evaluations e ON e.evaluation_id = r.evaluation_id
                WHERE r.is_complete=1 AND a.numeric_value IS NOT NULL AND {scope_filter}""",
            args,
        ).fetchone()
    return row[0]


def benchmark(evaluation_id: int, *, department: str | None = None) -> dict:
    """Compare a single evaluation against department / institution averages."""
    with get_connection() as conn:
        ev = conn.execute(
            "SELECT * FROM course_evaluations WHERE evaluation_id=?", (evaluation_id,),
        ).fetchone()
    if not ev:
        raise ValueError(f"Evaluation {evaluation_id} not found")
    ev = dict(ev)
    course_avg = _scope_avg("e.evaluation_id=?", (evaluation_id,))
    inst_avg = _scope_avg(
        "e.academic_year=? AND e.semester=?",
        (ev["academic_year"], ev["semester"]),
    )
    dept_avg = None
    if department:
        dept_avg = _scope_avg(
            "e.academic_year=? AND e.semester=? AND e.module_code LIKE ?",
            (ev["academic_year"], ev["semester"], f"{department}%"),
        )

    def delta(v):
        if v is None or course_avg is None:
            return None
        return round(course_avg - v, 3)

    return {
        "evaluation_id": evaluation_id,
        "course_avg": round(course_avg, 3) if course_avg is not None else None,
        "department_avg": round(dept_avg, 3) if dept_avg is not None else None,
        "institution_avg": round(inst_avg, 3) if inst_avg is not None else None,
        "vs_department": delta(dept_avg),
        "vs_institution": delta(inst_avg),
    }


# ---------- Word cloud + topics (23) ----------

# Minimal stoplist — kept short so reviewers can audit. For production
# deployments swap in an NLP library.
_STOP = {
    "the", "a", "an", "is", "it", "was", "were", "be", "are", "to", "of",
    "and", "or", "but", "in", "on", "for", "with", "at", "by", "from", "this",
    "that", "these", "those", "i", "we", "you", "he", "she", "they", "them",
    "my", "our", "your", "his", "her", "their", "as", "if", "so", "do", "did",
    "have", "has", "had", "not", "no", "yes", "very", "too", "more", "than",
    "also", "just", "only", "any", "all", "some", "all", "would", "could",
    "should", "about", "into", "out", "up", "down", "over", "under", "much",
    "many", "lot", "really", "good", "bad",  # leave these to sentiment
}


def _tokenise(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z']{3,}", text.lower())
            if w not in _STOP]


def word_frequencies(evaluation_id: int, *, top: int = 50) -> list[tuple[str, int]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.answer_value FROM evaluation_answers a
               JOIN evaluation_responses r ON r.response_id = a.response_id
               JOIN evaluation_questions q ON q.question_id = a.question_id
               WHERE r.evaluation_id=? AND r.is_complete=1
                 AND q.question_type IN ('text','open')
                 AND a.answer_value IS NOT NULL""",
            (evaluation_id,),
        ).fetchall()
    counter: Counter[str] = Counter()
    for r in rows:
        counter.update(_tokenise(r[0] or ""))
    return counter.most_common(top)


def cluster_topics(evaluation_id: int, *, k: int = 4) -> list[dict]:
    """Lightweight topic clustering — co-occurrence-based.

    For each top keyword, group together other keywords that appear in the
    same response. Returns up to `k` clusters keyed by the most common
    keyword. Cheap and audit-friendly; swap for sklearn KMeans/LDA if you
    need real topic modelling.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT r.response_id, a.answer_value
               FROM evaluation_answers a
               JOIN evaluation_responses r ON r.response_id = a.response_id
               JOIN evaluation_questions q ON q.question_id = a.question_id
               WHERE r.evaluation_id=? AND r.is_complete=1
                 AND q.question_type IN ('text','open')
                 AND a.answer_value IS NOT NULL""",
            (evaluation_id,),
        ).fetchall()
    per_response: list[set[str]] = [set(_tokenise(r[1] or "")) for r in rows]
    freq: Counter[str] = Counter()
    for s in per_response:
        freq.update(s)
    seeds = [w for w, _ in freq.most_common(k * 3)]
    clusters: list[dict] = []
    used: set[str] = set()
    for seed in seeds:
        if seed in used or len(clusters) >= k:
            continue
        cooc: Counter[str] = Counter()
        size = 0
        for s in per_response:
            if seed in s:
                size += 1
                cooc.update(s - {seed})
        members = [w for w, _ in cooc.most_common(8) if w not in used]
        clusters.append({"label": seed, "size": size, "members": members})
        used.add(seed)
        used.update(members)
    return clusters


# ---------- Sentiment scoring & caching (24) ----------

def score_all_text(evaluation_id: int) -> dict:
    """Run sentiment on every free-text answer and cache the result."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.answer_id, a.answer_value FROM evaluation_answers a
               JOIN evaluation_responses r ON r.response_id = a.response_id
               JOIN evaluation_questions q ON q.question_id = a.question_id
               WHERE r.evaluation_id=? AND r.is_complete=1
                 AND q.question_type IN ('text','open')
                 AND a.answer_value IS NOT NULL""",
            (evaluation_id,),
        ).fetchall()
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    with transaction() as conn:
        for r in rows:
            s = sentiment(r[1] or "")
            counts[s["label"]] += 1
            conn.execute(
                """INSERT INTO evaluation_sentiment (answer_id, polarity, label)
                   VALUES (?,?,?)
                   ON CONFLICT(answer_id) DO UPDATE SET
                     polarity=excluded.polarity, label=excluded.label""",
                (r[0], s["polarity"], s["label"]),
            )
        conn.commit()
    total = sum(counts.values())
    return {"counts": counts, "total": total,
            "net": round((counts["positive"] - counts["negative"]) / total, 3) if total else 0.0}


# ---------- Outlier / suspicious-response detection (25) ----------

def flag_suspicious(evaluation_id: int, *, speed_seconds: int = 30) -> list[dict]:
    """Flag responses that look like straight-lining, speeders, or are
    statistical outliers on their numeric answers."""
    with get_connection() as conn:
        responses = conn.execute(
            """SELECT response_id, time_taken_minutes
               FROM evaluation_responses
               WHERE evaluation_id=? AND is_complete=1""",
            (evaluation_id,),
        ).fetchall()
        if not responses:
            return []
        # Build per-response numeric vectors
        vectors: dict[int, list[float]] = defaultdict(list)
        for rid, val in conn.execute(
            """SELECT a.response_id, a.numeric_value FROM evaluation_answers a
               JOIN evaluation_responses r ON r.response_id = a.response_id
               WHERE r.evaluation_id=? AND a.numeric_value IS NOT NULL""",
            (evaluation_id,),
        ).fetchall():
            vectors[rid].append(val)

    # Cohort mean of per-response averages (for z-score outliers)
    averages = {rid: mean(v) for rid, v in vectors.items() if v}
    cohort_mean = mean(averages.values()) if averages else 0
    cohort_sd = pstdev(averages.values()) if len(averages) > 1 else 0

    flagged: list[dict] = []
    with transaction() as conn:
        conn.execute(
            "DELETE FROM evaluation_response_flags WHERE response_id IN "
            "(SELECT response_id FROM evaluation_responses WHERE evaluation_id=?)",
            (evaluation_id,),
        )
        for r in responses:
            rid, minutes = r["response_id"], r["time_taken_minutes"]
            row_flags: list[tuple[str, float]] = []
            vec = vectors.get(rid, [])

            # Speeder
            if minutes is not None and minutes * 60 < speed_seconds:
                row_flags.append(("speeder", float(minutes or 0)))

            # Straight-lining: zero variance on 3+ numeric answers
            if len(vec) >= 3 and (max(vec) == min(vec)):
                row_flags.append(("straight_lining", 0.0))

            # Numeric outlier
            if vec and cohort_sd > 0:
                z = (mean(vec) - cohort_mean) / cohort_sd
                if abs(z) > 2.5:
                    row_flags.append(("outlier", round(z, 3)))

            for tag, score in row_flags:
                conn.execute(
                    """INSERT INTO evaluation_response_flags
                       (response_id, flag, score) VALUES (?,?,?)""",
                    (rid, tag, score),
                )
                flagged.append({"response_id": rid, "flag": tag, "score": score})
        conn.commit()
    return flagged


def list_flags(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT f.* FROM evaluation_response_flags f
               JOIN evaluation_responses r ON r.response_id = f.response_id
               WHERE r.evaluation_id=?
               ORDER BY f.response_id, f.flag""",
            (evaluation_id,),
        ).fetchall()
    return [dict(r) for r in rows]


__all__ = [
    "response_rate", "dashboard_summary",
    "instructor_trend", "module_trend",
    "benchmark",
    "word_frequencies", "cluster_topics",
    "score_all_text",
    "flag_suspicious", "list_flags",
]
