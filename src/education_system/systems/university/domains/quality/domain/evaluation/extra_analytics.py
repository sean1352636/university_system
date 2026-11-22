"""
Extra analytics (features 26-28).

26. Demographic cuts with k-anonymity threshold
27. Custom dashboard builder
28. Statistical significance flags
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from statistics import mean, pstdev
from typing import Iterable

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- Settings helpers ----------

_K_ANON_KEY = "demographic.k_anonymity"
_DEFAULT_K = 5


def set_k_anonymity(k: int) -> None:
    if k < 1:
        raise ValueError("k must be >= 1")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO evaluation_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (_K_ANON_KEY, str(k)),
        )
        conn.commit()


def get_k_anonymity() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM evaluation_settings WHERE key=?", (_K_ANON_KEY,),
        ).fetchone()
    try:
        return int(row[0]) if row else _DEFAULT_K
    except (TypeError, ValueError):
        return _DEFAULT_K


# ---------- Demographics (26) ----------

def attach_demographics(response_id: int, attributes: dict[str, str]) -> int:
    rows = [(response_id, k, str(v)) for k, v in attributes.items() if v not in (None, "")]
    with transaction() as conn:
        conn.executemany(
            "INSERT INTO evaluation_demographics (response_id, dimension, value) VALUES (?,?,?)",
            rows,
        )
        conn.commit()
    return len(rows)


def demographic_cut(evaluation_id: int, dimension: str,
                    *, k: int | None = None) -> list[dict]:
    """Average numeric score broken down by a demographic dimension.

    Groups whose `n` is below the k-anonymity threshold are suppressed
    and returned with `suppressed=True` and no scores.
    """
    threshold = k if k is not None else get_k_anonymity()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT d.value AS bucket, a.numeric_value
               FROM evaluation_demographics d
               JOIN evaluation_responses r ON r.response_id = d.response_id
               JOIN evaluation_answers a ON a.response_id = r.response_id
               WHERE r.evaluation_id=? AND d.dimension=? AND r.is_complete=1
                 AND a.numeric_value IS NOT NULL""",
            (evaluation_id, dimension),
        ).fetchall()
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        buckets[r["bucket"]].append(r["numeric_value"])
    out: list[dict] = []
    for bucket, values in sorted(buckets.items()):
        n = len(values)
        if n < threshold:
            out.append({"bucket": bucket, "n": n, "suppressed": True,
                        "mean": None, "stdev": None,
                        "reason": f"below k={threshold}"})
        else:
            out.append({"bucket": bucket, "n": n, "suppressed": False,
                        "mean": round(mean(values), 3),
                        "stdev": round(pstdev(values), 3) if n > 1 else 0.0})
    return out


# ---------- Dashboard builder (27) ----------

_ALLOWED_WIDGETS = {
    "response_rate", "score_average", "trend", "wordcloud",
    "sentiment", "flags", "demographic_cut", "benchmark",
}


def save_dashboard(owner: str, name: str, widgets: list[dict],
                   *, role: str = "*") -> int:
    for w in widgets:
        if w.get("type") not in _ALLOWED_WIDGETS:
            raise ValueError(f"Unknown widget type: {w.get('type')}")
    payload = json.dumps({"widgets": widgets})
    with transaction() as conn:
        # If an owner+role+name already exists, update in place.
        row = conn.execute(
            """SELECT dashboard_id FROM evaluation_dashboards
               WHERE owner=? AND role=? AND name=?""",
            (owner, role, name),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE evaluation_dashboards
                   SET layout_json=?, updated_at=datetime('now')
                   WHERE dashboard_id=?""",
                (payload, row[0]),
            )
            conn.commit()
            return row[0]
        cur = conn.execute(
            """INSERT INTO evaluation_dashboards (owner, role, name, layout_json)
               VALUES (?,?,?,?)""",
            (owner, role, name, payload),
        )
        conn.commit()
        return cur.lastrowid


def list_dashboards(*, owner: str | None = None,
                    role: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_dashboards"
    args: list = []
    where: list[str] = []
    if owner:
        where.append("owner=?")
        args.append(owner)
    if role:
        where.append("(role=? OR role='*')")
        args.append(role)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC"
    with get_connection() as conn:
        out = []
        for r in conn.execute(sql, args).fetchall():
            d = dict(r)
            d["layout"] = json.loads(d.pop("layout_json"))
            out.append(d)
        return out


def delete_dashboard(dashboard_id: int) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM evaluation_dashboards WHERE dashboard_id=?",
                     (dashboard_id,))
        conn.commit()


# ---------- Statistical significance (28) ----------

# Two-sample Welch's t-test approximation using a survival-function
# upper-bound. We deliberately avoid scipy here to keep the dependency
# graph tight; for production analysis swap in scipy.stats.

def _welch_t(a: list[float], b: list[float]) -> tuple[float, float, float]:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return (0.0, 0.0, 1.0)
    ma, mb = mean(a), mean(b)
    va = pstdev(a) ** 2 if na > 1 else 0
    vb = pstdev(b) ** 2 if nb > 1 else 0
    se = math.sqrt(va / na + vb / nb) if (va + vb) > 0 else 0
    if se == 0:
        return (0.0, 0.0, 1.0)
    t = (ma - mb) / se
    # Welch–Satterthwaite df
    num = (va / na + vb / nb) ** 2
    denom = (va ** 2) / (na ** 2 * max(na - 1, 1)) + (vb ** 2) / (nb ** 2 * max(nb - 1, 1))
    df = num / denom if denom > 0 else 1
    # Approximate two-tailed p-value via a normal tail (df-corrected for small samples).
    # erfc(|t|/sqrt(2)) is the normal two-tailed p; multiply by a mild
    # small-sample inflation factor for very low df.
    p_norm = math.erfc(abs(t) / math.sqrt(2))
    inflate = 1.0 + max(0.0, (5 - df) * 0.05)
    p = min(1.0, p_norm * inflate)
    return (t, df, p)


def significance(evaluation_id: int, question_id: int,
                 *, against: str = "institution",
                 alpha: float = 0.05) -> dict:
    """Test the per-question mean against a wider scope (department by
    module-code prefix, institution = same year/sem).

    `against` is "institution" or a department prefix (e.g. "CS")."""
    with get_connection() as conn:
        ev = conn.execute(
            "SELECT academic_year, semester, module_code FROM course_evaluations WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()
        if not ev:
            raise ValueError("Evaluation not found")
        # Course sample
        course = [r[0] for r in conn.execute(
            """SELECT a.numeric_value FROM evaluation_answers a
               JOIN evaluation_responses r ON r.response_id=a.response_id
               WHERE r.evaluation_id=? AND a.question_id=? AND a.numeric_value IS NOT NULL
                 AND r.is_complete=1""",
            (evaluation_id, question_id),
        ).fetchall()]
        if against == "institution":
            scope = [r[0] for r in conn.execute(
                """SELECT a.numeric_value FROM evaluation_answers a
                   JOIN evaluation_responses r ON r.response_id=a.response_id
                   JOIN course_evaluations e ON e.evaluation_id=r.evaluation_id
                   WHERE e.academic_year=? AND e.semester=? AND a.question_id=?
                     AND r.is_complete=1 AND a.numeric_value IS NOT NULL""",
                (ev["academic_year"], ev["semester"], question_id),
            ).fetchall()]
        else:
            scope = [r[0] for r in conn.execute(
                """SELECT a.numeric_value FROM evaluation_answers a
                   JOIN evaluation_responses r ON r.response_id=a.response_id
                   JOIN course_evaluations e ON e.evaluation_id=r.evaluation_id
                   WHERE e.academic_year=? AND e.semester=?
                     AND e.module_code LIKE ?
                     AND a.question_id=? AND r.is_complete=1
                     AND a.numeric_value IS NOT NULL""",
                (ev["academic_year"], ev["semester"], f"{against}%", question_id),
            ).fetchall()]
    t, df, p = _welch_t(course, scope)
    sig = p < alpha and len(course) >= 2 and len(scope) >= 2
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_significance
                 (evaluation_id, question_id, comparison, n, statistic, p_value, significant)
               VALUES (?,?,?,?,?,?,?)""",
            (evaluation_id, question_id, f"vs:{against}",
             len(course), t, p, 1 if sig else 0),
        )
        conn.commit()
    return {
        "evaluation_id": evaluation_id, "question_id": question_id,
        "n_course": len(course), "n_scope": len(scope),
        "t": round(t, 3), "df": round(df, 2),
        "p_value": round(p, 4), "significant": sig,
        "underpowered": len(course) < 5 or len(scope) < 5,
    }


def list_significance(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_significance WHERE evaluation_id=? "
            "ORDER BY computed_at DESC", (evaluation_id,),
        ).fetchall()]


__all__ = [
    "set_k_anonymity", "get_k_anonymity",
    "attach_demographics", "demographic_cut",
    "save_dashboard", "list_dashboards", "delete_dashboard",
    "significance", "list_significance",
]
