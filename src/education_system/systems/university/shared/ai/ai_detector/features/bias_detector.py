"""Are some groups of students flagged more than others?

AI-writing indicators are known to fall harder on some writers (second-
language writers above all). :func:`bias_report` checks the readings this
university actually took, group by group, for every characteristic it
holds: from ``students`` (gender, nationality, fee status, mode of study,
entry route), from the equality and diversity records ``ed_people``
(ethnicity, disability, age group) and from ``student_demographics``
(first language, age group) where those are filled in.

For each group: how many students and readings, the share of readings at
or above the review threshold, referred, and upheld after a case — each
compared with everyone else by a two-proportion z-test. A group flagged at
1.25 times the rate of the rest or more, with p < 0.05, gets a plain
warning. Groups of fewer than 10 students are not reported (they could
identify people, and their rates mean little).

There is **no automatic correction** of anyone's score: adjusting
individual readings by group would be its own unfairness. A disparity is a
reason to review the indicators and how they are used.
Integrity officers only.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

MIN_GROUP = 10
RATIO_WARNING = 1.25
P_WARNING = 0.05
CORRECTION_NOTE = ("No automatic correction is applied to any reading. If the bias report "
                   "shows a disparity, review the indicators and how they are used.")

_SOURCES = (
    ("students", "student_id", ("gender", "nationality", "fee_status", "mode_of_study",
                                "entry_route"), ""),
    ("ed_people", "student_id", ("ethnicity", "disability", "age_group"),
     " AND deleted_at IS NULL AND student_id IS NOT NULL"),
    ("student_demographics", "student_id", ("native_language", "age_group", "gender"), ""),
)


def _access():
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    return integrity_access


def _columns(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _z_test(k1, n1, k2, n2) -> float | None:
    """Two-sided p-value of the difference between two proportions."""
    if not n1 or not n2:
        return None
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    z = (k1 / n1 - k2 / n2) / se
    return round(math.erfc(abs(z) / math.sqrt(2)), 4)


def _readings(conn, threshold) -> list[tuple]:
    have_cases = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'integrity_cases'"
                              ).fetchone()
    from education_system.systems.university.application.integrity import (
        review as integrity_review,
    )
    upheld = ",".join(f"'{o}'" for o in integrity_review.UPHELD)
    case = (f"CASE WHEN c.outcome IN ({upheld}) AND c.status <> 'dismissed' THEN 1 ELSE 0 END"
            if have_cases else "0")
    join = "LEFT JOIN integrity_cases c ON c.id = v.case_id" if have_cases else ""
    return conn.execute(
        f"SELECT s.student_id, CASE WHEN r.ai_score >= ? THEN 1 ELSE 0 END, "  # nosec B608
        f"CASE WHEN v.decision = 'refer' THEN 1 ELSE 0 END, {case} FROM ai_detector_results r "
        f"JOIN ai_detector_submissions s ON s.id = r.submission_id LEFT JOIN "
        f"integrity_ai_reviews v ON v.ai_result_id = r.id {join} WHERE COALESCE(r.level, '') "
        "NOT LIKE 'not %'", (threshold,)).fetchall()


def _attribute(conn, table, key, column, extra, readings) -> dict | None:
    if column not in _columns(conn, table):
        return None
    groups = {str(r[0]): str(r[1]).strip() for r in conn.execute(
        f'SELECT "{key}", "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL AND '  # nosec B608
        f'TRIM("{column}") <> \'\'{extra}')}
    if not groups:
        return None
    totals = {"n": 0, "flagged": 0, "referred": 0, "upheld": 0}
    by_group: dict[str, dict] = {}
    for student, flagged, referred, upheld in readings:
        group = groups.get(str(student))
        if group is None:
            continue
        g = by_group.setdefault(group, {"students": set(), "n": 0, "flagged": 0,
                                        "referred": 0, "upheld": 0})
        g["students"].add(student)
        for name, value in (("n", 1), ("flagged", flagged), ("referred", referred),
                            ("upheld", upheld)):
            g[name] += value
            totals[name] += value
    rows, suppressed = [], 0
    for group, g in sorted(by_group.items()):
        if len(g["students"]) < MIN_GROUP:
            suppressed += 1
            continue
        rest_n = totals["n"] - g["n"]
        rate = g["flagged"] / g["n"] if g["n"] else 0.0
        rest_rate = (totals["flagged"] - g["flagged"]) / rest_n if rest_n else None
        p = _z_test(g["flagged"], g["n"], totals["flagged"] - g["flagged"], rest_n)
        ratio = (rate / rest_rate) if rest_rate else None
        row = {"group": group, "students": len(g["students"]), "readings": g["n"],
               "flag_rate": round(rate, 4),
               "rest_flag_rate": None if rest_rate is None else round(rest_rate, 4),
               "ratio": None if ratio is None else round(ratio, 3), "p_value": p,
               "referral_rate": round(g["referred"] / g["n"], 4) if g["n"] else 0.0,
               "upheld_rate": round(g["upheld"] / g["n"], 4) if g["n"] else 0.0,
               "referral_p_value": _z_test(g["referred"], g["n"],
                                           totals["referred"] - g["referred"], rest_n)}
        if ratio and ratio >= RATIO_WARNING and p is not None and p < P_WARNING:
            row["warning"] = (f"Students recorded as '{group}' ({column.replace('_', ' ')}) are "
                              f"flagged at {ratio:.1f} times the rate of other students "
                              f"(p = {p:.3f}). Review the indicators before relying on them "
                              "for this group.")
        rows.append(row)
    return {"attribute": column, "source": table, "groups": rows,
            "groups_suppressed": suppressed, "readings_matched": totals["n"]}


def bias_report(conn, who, *, threshold=None) -> Dict[str, Any]:
    access = _access()
    access.require(who is not None and access.is_officer(conn, who),
                   "Only an integrity officer can run the bias report")
    access.ensure(conn)
    threshold = float(threshold if threshold is not None
                      else access.number(conn, "ai_review_threshold"))
    readings = _readings(conn, threshold)
    attributes = []
    for table, key, columns, extra in _SOURCES:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone():
            continue
        for column in columns:
            found = _attribute(conn, table, key, column, extra, readings)
            if found:
                attributes.append(found)
    warnings = [g["warning"] for a in attributes for g in a["groups"] if g.get("warning")]
    reported = sum(len(a["groups"]) for a in attributes)
    if not readings:
        summary = "No readings have been taken yet."
    elif not reported:
        summary = (f"No group has {MIN_GROUP} or more students with readings yet, so nothing "
                   "can be compared.")
    elif warnings:
        summary = f"{len(warnings)} group(s) are flagged disproportionately."
    else:
        summary = "No group is flagged disproportionately on the data held."
    return {"threshold": threshold, "readings": len(readings), "attributes": attributes,
            "warnings": warnings, "summary": summary, "minimum_group": MIN_GROUP,
            "correction": CORRECTION_NOTE}


class BiasDetector:
    """The detector's handle on the bias report (its own short connections)."""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.bias_metrics: Dict = {}

    def analyze_detection_bias(self, demographic_data: Dict[str, str] = None) -> Dict[str, Any]:
        """The bias report for the signed-in officer. ``demographic_data``
        (older callers) is ignored: every characteristic held is checked."""
        conn = self.detector._safe_db_connect()
        try:
            who = _access().from_user(conn, getattr(self.detector, "current_user", None))
            self.bias_metrics = bias_report(conn, who)
            return self.bias_metrics
        except PermissionError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            logger.error(f"Bias report failed: {exc}")
            return {"error": f"The bias report could not be produced: {exc}"}
        finally:
            conn.close()

    def apply_bias_correction(self, ai_score: float, student_demographics: Dict = None) -> float:
        """No correction: returns ``ai_score`` unchanged (see
        :data:`CORRECTION_NOTE`)."""
        return ai_score
