"""
Admin/ops service (features 44-50).

44. Bulk import (CSV)
45. Approval workflow for new evaluation forms
46. A/B test two question wordings
47. Soft-delete with restore
48. Print/PDF export of an evaluation result
49. Bias-language linter
50. Pulse / micro-survey scheduler
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- 44. Bulk import ----------

_REQUIRED_HEADERS = {"evaluation_id", "question_id", "answer_value"}


def import_csv(path_or_text: str, *, is_text: bool = False) -> dict:
    """Import historical answers from a CSV.

    Required headers: evaluation_id, question_id, answer_value
    Optional headers: response_id, numeric_value, student_id, time_taken_minutes
    Rows that reference a missing response_id auto-create the response row.
    """
    if is_text:
        text = path_or_text
        source = "<inline>"
    else:
        with open(path_or_text, "r", encoding="utf-8") as fh:
            text = fh.read()
        source = path_or_text

    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    if not _REQUIRED_HEADERS.issubset(headers):
        missing = _REQUIRED_HEADERS - headers
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    seen = imported = errored = 0
    with transaction() as conn:
        response_cache: dict[tuple, int] = {}
        for row in reader:
            seen += 1
            try:
                eval_id = int(row["evaluation_id"])
                qid = int(row["question_id"])
                ans = row["answer_value"] or None
                num = row.get("numeric_value")
                num_val = float(num) if num not in (None, "") else None
                rid_raw = row.get("response_id")
                if rid_raw:
                    rid = int(rid_raw)
                else:
                    key = (eval_id, row.get("student_id") or f"_imp_{seen}")
                    if key in response_cache:
                        rid = response_cache[key]
                    else:
                        cur = conn.execute(
                            """INSERT INTO evaluation_responses
                                 (evaluation_id, student_id, is_complete, time_taken_minutes)
                               VALUES (?,?,1,?)""",
                            (eval_id, row.get("student_id"),
                             int(row.get("time_taken_minutes") or 0) or None),
                        )
                        rid = cur.lastrowid
                        response_cache[key] = rid
                conn.execute(
                    """INSERT INTO evaluation_answers
                         (response_id, question_id, answer_value, numeric_value)
                       VALUES (?,?,?,?)""",
                    (rid, qid, ans, num_val),
                )
                imported += 1
            except Exception:
                errored += 1
        conn.execute(
            """INSERT INTO evaluation_imports
                 (source_path, rows_seen, rows_imported, rows_errored)
               VALUES (?,?,?,?)""",
            (source, seen, imported, errored),
        )
        conn.commit()
    return {"seen": seen, "imported": imported, "errored": errored}


# ---------- 45. Approval workflow ----------

_STAGES = ("draft", "review", "approved", "rejected")


def set_stage(template_id: int, stage: str, *, actor: str = "",
              comment: str = "") -> int:
    if stage not in _STAGES:
        raise ValueError(f"stage must be one of {_STAGES}")
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_approvals (template_id, stage, actor, comment)
               VALUES (?,?,?,?)""",
            (template_id, stage, actor, comment),
        )
        conn.commit()
        return cur.lastrowid


def current_stage(template_id: int) -> str:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT stage FROM evaluation_approvals WHERE template_id=?
               ORDER BY approval_id DESC LIMIT 1""",
            (template_id,),
        ).fetchone()
    return row[0] if row else "draft"


def approval_history(template_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_approvals WHERE template_id=? "
            "ORDER BY approval_id", (template_id,),
        ).fetchall()]


# ---------- 46. A/B tests ----------

def create_ab_test(question_id: int, variant_a: str, variant_b: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_ab_tests (question_id, variant_a, variant_b)
               VALUES (?,?,?)""",
            (question_id, variant_a, variant_b),
        )
        conn.commit()
        return cur.lastrowid


def assign_variant(ab_id: int, response_id: int) -> str:
    """Deterministic 50/50 split keyed on (ab_id, response_id)."""
    variant = "A" if hashlib.md5(f"{ab_id}:{response_id}".encode()).digest()[0] % 2 == 0 else "B"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_ab_assignments (ab_id, response_id, variant)
               VALUES (?,?,?)
               ON CONFLICT(ab_id, response_id) DO NOTHING""",
            (ab_id, response_id, variant),
        )
        conn.commit()
    return variant


def ab_results(ab_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT t.*, q.template_id FROM evaluation_ab_tests t
               LEFT JOIN evaluation_questions q ON q.question_id=t.question_id
               WHERE t.ab_id=?""", (ab_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"A/B test {ab_id} not found")
        qid = row["question_id"]
        counts: dict[str, dict] = {}
        for variant in ("A", "B"):
            vals = [r[0] for r in conn.execute(
                """SELECT a.numeric_value FROM evaluation_answers a
                   JOIN evaluation_ab_assignments x ON x.response_id = a.response_id
                   WHERE a.question_id=? AND x.ab_id=? AND x.variant=?
                     AND a.numeric_value IS NOT NULL""",
                (qid, ab_id, variant),
            ).fetchall()]
            counts[variant] = {
                "n": len(vals),
                "mean": round(sum(vals) / len(vals), 3) if vals else None,
            }
    return {"ab_id": ab_id, "question_id": qid,
            "variant_a_text": row["variant_a"], "variant_b_text": row["variant_b"],
            "results": counts}


def list_ab_tests() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_ab_tests ORDER BY ab_id DESC"
        ).fetchall()]


# ---------- 47. Soft-delete ----------

def soft_delete_template(template_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE evaluation_templates SET deleted_at=datetime('now'), is_active=0 "
            "WHERE template_id=?",
            (template_id,),
        )
        conn.commit()


def restore_template(template_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE evaluation_templates SET deleted_at=NULL, is_active=1 "
            "WHERE template_id=?",
            (template_id,),
        )
        conn.commit()


def soft_delete_evaluation(evaluation_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE course_evaluations SET deleted_at=datetime('now'), is_active=0 "
            "WHERE evaluation_id=?",
            (evaluation_id,),
        )
        conn.commit()


def restore_evaluation(evaluation_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE course_evaluations SET deleted_at=NULL, is_active=1 "
            "WHERE evaluation_id=?",
            (evaluation_id,),
        )
        conn.commit()


def list_trash() -> dict[str, list[dict]]:
    with get_connection() as conn:
        templates = [dict(r) for r in conn.execute(
            "SELECT template_id, template_name, deleted_at FROM evaluation_templates "
            "WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
        ).fetchall()]
        evals = [dict(r) for r in conn.execute(
            "SELECT evaluation_id, module_code, deleted_at FROM course_evaluations "
            "WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
        ).fetchall()]
    return {"templates": templates, "evaluations": evals}


# ---------- 48. Print / PDF export ----------

def render_results_text(evaluation_id: int) -> str:
    """Produce a plain-text results report. Plain text renders identically
    via tk.print or filed as a .txt — and is what most institutional
    print pipelines accept. PDF generation should be handled by the
    caller (reportlab/wkhtmltopdf) using this string as input."""
    with get_connection() as conn:
        ev = conn.execute(
            "SELECT * FROM course_evaluations WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()
        if not ev:
            raise ValueError(f"Evaluation {evaluation_id} not found")
        ev = dict(ev)
        qrows = conn.execute(
            """SELECT q.question_id, q.question_text, q.question_type
               FROM evaluation_questions q
               JOIN evaluation_responses r ON r.evaluation_id=?
               WHERE q.template_id=(SELECT template_id FROM course_evaluations WHERE evaluation_id=?)
               GROUP BY q.question_id ORDER BY q.display_order""",
            (evaluation_id, evaluation_id),
        ).fetchall()
        n_responses = conn.execute(
            "SELECT COUNT(*) FROM evaluation_responses WHERE evaluation_id=? AND is_complete=1",
            (evaluation_id,),
        ).fetchone()[0]
    lines = []
    lines.append("Course Evaluation Report")
    lines.append("=" * 60)
    lines.append(f"Module:        {ev['module_code']}")
    lines.append(f"Year/Sem:      {ev['academic_year']} / {ev['semester']}")
    lines.append(f"Instructor:    {ev['instructor_id']}")
    lines.append(f"Responses:     {n_responses}")
    lines.append(f"Generated:     {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    with get_connection() as conn:
        for q in qrows:
            lines.append(f"Q{q['question_id']}: {q['question_text']}  [{q['question_type']}]")
            if q["question_type"] in ("likert", "nps", "slider"):
                row = conn.execute(
                    """SELECT AVG(numeric_value), COUNT(numeric_value)
                       FROM evaluation_answers a
                       JOIN evaluation_responses r ON r.response_id=a.response_id
                       WHERE r.evaluation_id=? AND a.question_id=? AND r.is_complete=1
                         AND numeric_value IS NOT NULL""",
                    (evaluation_id, q["question_id"]),
                ).fetchone()
                avg, n = row
                lines.append(f"    avg={round(avg, 2) if avg else 'n/a'}  n={n}")
            else:
                texts = conn.execute(
                    """SELECT answer_value FROM evaluation_answers a
                       JOIN evaluation_responses r ON r.response_id=a.response_id
                       WHERE r.evaluation_id=? AND a.question_id=? AND r.is_complete=1
                         AND answer_value IS NOT NULL LIMIT 5""",
                    (evaluation_id, q["question_id"]),
                ).fetchall()
                for t in texts:
                    lines.append(f"    - {t[0][:120]}")
            lines.append("")
    return "\n".join(lines)


def export_results_pdf(evaluation_id: int, path: str) -> str:
    """Write a printable file. Uses reportlab if available, falls back to
    plain .txt so this never fails on a fresh environment."""
    text = render_results_text(evaluation_id)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(path, pagesize=letter)
        width, height = letter
        y = height - 50
        for line in text.splitlines():
            c.drawString(40, y, line[:110])
            y -= 14
            if y < 50:
                c.showPage()
                y = height - 50
        c.save()
        return path
    except ImportError:
        if not path.endswith(".txt"):
            path = path + ".txt"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


# ---------- 49. Bias-language linter ----------

# A short, audit-friendly checklist. Production deployments should swap in
# a curated set vetted by their EDI office.
_BIAS_RULES: tuple[tuple[str, str, str], ...] = (
    ("gendered.assumption", r"\b(he|she)\s+is\s+(a\s+)?(student|professor|lecturer|tutor)\b",
     "Prefer 'they' or 'the student/professor'."),
    ("ableist", r"\b(crazy|insane|lame|dumb)\b",
     "Choose a precise descriptor — 'unexpected', 'difficult', 'unclear'."),
    ("loaded", r"\b(failure|incompetent|hopeless)\b",
     "Describe the observed behaviour, not a verdict."),
    ("double_barreled", r"\band\b.*\band\b",
     "Possible double-barrelled question — split into two."),
    ("leading", r"\b(don't you (agree|think))\b",
     "Leading phrasing — rephrase neutrally."),
    ("absolutist", r"\b(always|never|every|all of|none of)\b",
     "Absolutist wording — soften to 'often/rarely/most'."),
)


def lint_text(text: str) -> list[dict]:
    out = []
    for cat, pat, suggestion in _BIAS_RULES:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            out.append({"category": cat, "snippet": m.group(0),
                        "suggestion": suggestion})
    return out


def lint_template(template_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT question_id, question_text FROM evaluation_questions WHERE template_id=?",
            (template_id,),
        ).fetchall()
    findings = []
    with transaction() as conn:
        conn.execute("DELETE FROM evaluation_bias_findings WHERE template_id=?",
                     (template_id,))
        for q in rows:
            for f in lint_text(q["question_text"] or ""):
                cur = conn.execute(
                    """INSERT INTO evaluation_bias_findings
                         (template_id, question_id, category, snippet, suggestion)
                       VALUES (?,?,?,?,?)""",
                    (template_id, q["question_id"], f["category"],
                     f["snippet"], f["suggestion"]),
                )
                f["finding_id"] = cur.lastrowid
                f["question_id"] = q["question_id"]
                findings.append(f)
        conn.commit()
    return findings


# ---------- 50. Pulse / micro-surveys ----------

def create_pulse(module_code: str, question_text: str,
                 *, question_type: str = "likert",
                 cadence_days: int = 7,
                 start_at: datetime | None = None) -> int:
    nxt = (start_at or datetime.now()).isoformat()
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_pulses
                 (module_code, question_text, question_type, cadence_days, next_run)
               VALUES (?,?,?,?,?)""",
            (module_code, question_text, question_type, cadence_days, nxt),
        )
        conn.commit()
        return cur.lastrowid


def list_pulses(*, module_code: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_pulses WHERE active=1"
    args: list = []
    if module_code:
        sql += " AND module_code=?"
        args.append(module_code)
    sql += " ORDER BY pulse_id DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def deactivate_pulse(pulse_id: int) -> None:
    with transaction() as conn:
        conn.execute("UPDATE evaluation_pulses SET active=0 WHERE pulse_id=?",
                     (pulse_id,))
        conn.commit()


def submit_pulse(pulse_id: int, respondent_id: str,
                 *, rating_value: int | None = None,
                 text_value: str | None = None) -> int:
    h = hashlib.sha256(f"pulse:{pulse_id}:{respondent_id}".encode()).hexdigest()[:32]
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_pulse_responses
                 (pulse_id, respondent_hash, rating_value, text_value)
               VALUES (?,?,?,?)""",
            (pulse_id, h, rating_value, text_value),
        )
        conn.commit()
        return cur.lastrowid


def advance_pulse(pulse_id: int) -> None:
    """Bump `next_run` to now + cadence_days. Called by the runner after firing."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT cadence_days FROM evaluation_pulses WHERE pulse_id=?",
            (pulse_id,),
        ).fetchone()
        if not row:
            return
        nxt = (datetime.now() + timedelta(days=row[0])).isoformat()
        conn.execute("UPDATE evaluation_pulses SET next_run=? WHERE pulse_id=?",
                     (nxt, pulse_id))
        conn.commit()


def due_pulses(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM evaluation_pulses WHERE active=1 AND next_run <= ?",
            (now.isoformat(),),
        ).fetchall()
    return [dict(r) for r in rows]


def pulse_results(pulse_id: int) -> dict:
    with get_connection() as conn:
        ratings = [r[0] for r in conn.execute(
            "SELECT rating_value FROM evaluation_pulse_responses "
            "WHERE pulse_id=? AND rating_value IS NOT NULL",
            (pulse_id,),
        ).fetchall()]
        texts = [r[0] for r in conn.execute(
            "SELECT text_value FROM evaluation_pulse_responses "
            "WHERE pulse_id=? AND text_value IS NOT NULL AND text_value != ''",
            (pulse_id,),
        ).fetchall()]
    return {
        "pulse_id": pulse_id,
        "ratings_n": len(ratings),
        "ratings_mean": round(sum(ratings) / len(ratings), 3) if ratings else None,
        "texts": texts[:20],
    }


__all__ = [
    "import_csv",
    "set_stage", "current_stage", "approval_history",
    "create_ab_test", "assign_variant", "ab_results", "list_ab_tests",
    "soft_delete_template", "restore_template",
    "soft_delete_evaluation", "restore_evaluation", "list_trash",
    "render_results_text", "export_results_pdf",
    "lint_text", "lint_template",
    "create_pulse", "list_pulses", "deactivate_pulse",
    "submit_pulse", "advance_pulse", "due_pulses", "pulse_results",
]
