"""
Course-evaluation authoring service.

Backs features 1-8 of the Course Evaluation Survey Designer:

1. Template library    — list / clone / import / export
2. Question bank       — reusable questions with tags
3. Branching logic     — parent_question_id + show_if_op/value
4. Multi-question types — likert, nps, matrix, ranking, slider, text, file, mcq
5. Required/optional   — validate() helper
6. Multi-language      — per-locale question text with fallback
7. Accessibility check — WCAG-flavoured static checks
8. Version history     — full JSON snapshots with diff
"""

from __future__ import annotations

import json
from datetime import datetime
from difflib import unified_diff
from typing import Any, Iterable

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)

SUPPORTED_TYPES = (
    "likert", "nps", "matrix", "ranking", "slider",
    "text", "file", "mcq",
)
SUPPORTED_OPS = ("eq", "neq", "gt", "lt", "in")


# ---------- Question bank (feature 2) ----------

def add_bank_question(text: str, qtype: str, *, category: str = "",
                      scale_min: int = 1, scale_max: int = 5,
                      options: list | None = None, department: str = "",
                      tags: Iterable[str] = (), created_by: str = "") -> int:
    if qtype not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported question type: {qtype}")
    opts = json.dumps(options) if options else None
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_question_bank
               (question_text, question_type, question_category,
                scale_min, scale_max, options_json, department, created_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (text, qtype, category, scale_min, scale_max, opts, department, created_by),
        )
        bank_id = cur.lastrowid
        for tag in {t.strip().lower() for t in tags if t.strip()}:
            conn.execute(
                "INSERT OR IGNORE INTO evaluation_question_tags (bank_id, tag) VALUES (?,?)",
                (bank_id, tag),
            )
        conn.commit()
        return bank_id


def list_bank(*, tag: str | None = None, department: str | None = None,
              search: str | None = None) -> list[dict]:
    sql = ["SELECT b.* FROM evaluation_question_bank b"]
    args: list[Any] = []
    where: list[str] = []
    if tag:
        sql.append("JOIN evaluation_question_tags t ON t.bank_id = b.bank_id")
        where.append("t.tag = ?")
        args.append(tag.lower())
    if department:
        where.append("b.department = ?")
        args.append(department)
    if search:
        where.append("b.question_text LIKE ?")
        args.append(f"%{search}%")
    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("ORDER BY b.created_at DESC")
    with get_connection() as conn:
        rows = conn.execute(" ".join(sql), args).fetchall()
        return [dict(r) for r in rows]


def get_bank_tags(bank_id: int) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT tag FROM evaluation_question_tags WHERE bank_id=? ORDER BY tag",
            (bank_id,),
        ).fetchall()
        return [r[0] for r in rows]


def add_tag(bank_id: int, tag: str) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO evaluation_question_tags (bank_id, tag) VALUES (?,?)",
            (bank_id, tag.strip().lower()),
        )
        conn.commit()


def remove_tag(bank_id: int, tag: str) -> None:
    with transaction() as conn:
        conn.execute(
            "DELETE FROM evaluation_question_tags WHERE bank_id=? AND tag=?",
            (bank_id, tag.strip().lower()),
        )
        conn.commit()


def insert_bank_question_into_template(bank_id: int, template_id: int,
                                       *, display_order: int | None = None,
                                       required: bool = True) -> int:
    """Materialise a bank question into a template's question list."""
    with transaction() as conn:
        bank = conn.execute(
            "SELECT * FROM evaluation_question_bank WHERE bank_id=?", (bank_id,)
        ).fetchone()
        if not bank:
            raise ValueError(f"Bank question {bank_id} not found")
        if display_order is None:
            row = conn.execute(
                "SELECT COALESCE(MAX(display_order), 0) FROM evaluation_questions WHERE template_id=?",
                (template_id,),
            ).fetchone()
            display_order = (row[0] or 0) + 1
        cur = conn.execute(
            """INSERT INTO evaluation_questions
               (template_id, question_text, question_type, question_category,
                scale_min, scale_max, display_order, is_required,
                options_json, bank_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (template_id, bank["question_text"], bank["question_type"],
             bank["question_category"], bank["scale_min"], bank["scale_max"],
             display_order, 1 if required else 0,
             bank["options_json"], bank_id),
        )
        conn.commit()
        return cur.lastrowid


# ---------- Branching logic (feature 3) ----------

def set_branching(question_id: int, parent_id: int, op: str, value: str) -> None:
    if op not in SUPPORTED_OPS:
        raise ValueError(f"Unsupported branching op: {op}")
    with transaction() as conn:
        conn.execute(
            """UPDATE evaluation_questions
               SET parent_question_id=?, show_if_op=?, show_if_value=?
               WHERE question_id=?""",
            (parent_id, op, value, question_id),
        )
        conn.commit()


def clear_branching(question_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE evaluation_questions
               SET parent_question_id=NULL, show_if_op=NULL, show_if_value=NULL
               WHERE question_id=?""",
            (question_id,),
        )
        conn.commit()


def should_show(question: dict, answers: dict[int, Any]) -> bool:
    """Evaluate a question's branching rule against the answer map so far."""
    parent = question.get("parent_question_id")
    if not parent:
        return True
    op = question.get("show_if_op") or "eq"
    target = question.get("show_if_value")
    given = answers.get(parent)
    if given is None:
        return False
    if op == "eq":
        return str(given) == str(target)
    if op == "neq":
        return str(given) != str(target)
    if op == "gt":
        try:
            return float(given) > float(target)
        except (TypeError, ValueError):
            return False
    if op == "lt":
        try:
            return float(given) < float(target)
        except (TypeError, ValueError):
            return False
    if op == "in":
        allowed = {x.strip() for x in (target or "").split(",")}
        return str(given) in allowed
    return True


# ---------- Question types & required/optional (features 4, 5) ----------

def validate_answer(question: dict, value: Any) -> tuple[bool, str]:
    """Returns (ok, error_message). Empty error_message when ok."""
    required = bool(question.get("is_required", 1))
    qtype = question.get("question_type", "likert")
    empty = value is None or (isinstance(value, str) and not value.strip())
    if empty:
        return (False, "This question is required.") if required else (True, "")

    if qtype in ("likert", "nps", "slider"):
        try:
            num = float(value)
        except (TypeError, ValueError):
            return False, "Numeric answer required."
        lo, hi = question.get("scale_min", 1), question.get("scale_max", 5)
        if num < lo or num > hi:
            return False, f"Value must be between {lo} and {hi}."
    elif qtype == "mcq":
        opts = json.loads(question.get("options_json") or "[]")
        if opts and str(value) not in [str(o) for o in opts]:
            return False, "Selection not in allowed options."
    elif qtype == "matrix":
        if not isinstance(value, dict) or not value:
            return False, "Matrix requires per-row selections."
    elif qtype == "ranking":
        if not isinstance(value, list):
            return False, "Ranking must be an ordered list."
    elif qtype == "file":
        if not isinstance(value, str) or not value.strip():
            return False, "File path required."
    return True, ""


def set_question_type(question_id: int, qtype: str,
                      *, options: list | None = None,
                      scale_min: int | None = None,
                      scale_max: int | None = None) -> None:
    if qtype not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported question type: {qtype}")
    fields = ["question_type=?"]
    args: list[Any] = [qtype]
    if options is not None:
        fields.append("options_json=?")
        args.append(json.dumps(options))
    if scale_min is not None:
        fields.append("scale_min=?")
        args.append(scale_min)
    if scale_max is not None:
        fields.append("scale_max=?")
        args.append(scale_max)
    args.append(question_id)
    with transaction() as conn:
        conn.execute(
            f"UPDATE evaluation_questions SET {','.join(fields)} WHERE question_id=?",
            args,
        )
        conn.commit()


def set_required(question_id: int, required: bool) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE evaluation_questions SET is_required=? WHERE question_id=?",
            (1 if required else 0, question_id),
        )
        conn.commit()


# ---------- Multi-language (feature 6) ----------

def set_locale_text(question_id: int, locale: str, text: str,
                    *, aria_label: str | None = None,
                    options: list | None = None) -> None:
    opts = json.dumps(options) if options else None
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_question_locales
                 (question_id, locale, question_text, aria_label, options_json)
               VALUES (?,?,?,?,?)
               ON CONFLICT(question_id, locale) DO UPDATE SET
                 question_text=excluded.question_text,
                 aria_label=excluded.aria_label,
                 options_json=excluded.options_json""",
            (question_id, locale, text, aria_label, opts),
        )
        conn.commit()


def get_locales(question_id: int) -> dict[str, dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT locale, question_text, aria_label, options_json "
            "FROM evaluation_question_locales WHERE question_id=?",
            (question_id,),
        ).fetchall()
        return {r["locale"]: dict(r) for r in rows}


def render_question(question: dict, locale: str | None = None) -> dict:
    """Return question dict with text/aria/options swapped to `locale` if a
    translation exists; otherwise the base row is returned (fallback)."""
    if not locale:
        return question
    with get_connection() as conn:
        row = conn.execute(
            "SELECT question_text, aria_label, options_json "
            "FROM evaluation_question_locales WHERE question_id=? AND locale=?",
            (question["question_id"], locale),
        ).fetchone()
    if not row:
        return question
    out = dict(question)
    out["question_text"] = row["question_text"] or question["question_text"]
    if row["aria_label"]:
        out["aria_label"] = row["aria_label"]
    if row["options_json"]:
        out["options_json"] = row["options_json"]
    return out


# ---------- Accessibility checker (feature 7) ----------

# Approximation of WCAG 2.1 relative-luminance contrast ratio.
def _rel_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return 1.0
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def chan(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = _rel_luminance(fg), _rel_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def audit_template(template_id: int,
                   *, fg: str = "#000000", bg: str = "#f0f0f0") -> list[dict]:
    """Run accessibility checks; persist + return findings."""
    findings: list[dict] = []

    ratio = contrast_ratio(fg, bg)
    if ratio < 4.5:
        findings.append({
            "rule": "wcag.contrast",
            "severity": "error" if ratio < 3.0 else "warning",
            "message": f"Foreground/background contrast {ratio:.2f}:1 is below WCAG AA 4.5:1.",
            "question_id": None,
        })

    with get_connection() as conn:
        questions = conn.execute(
            "SELECT * FROM evaluation_questions WHERE template_id=? ORDER BY display_order",
            (template_id,),
        ).fetchall()

    for q in questions:
        qd = dict(q)
        qid = qd["question_id"]
        text = (qd.get("question_text") or "").strip()
        aria = (qd.get("aria_label") or "").strip()

        if not text:
            findings.append({"rule": "a11y.empty_label", "severity": "error",
                             "question_id": qid,
                             "message": "Question has no visible label."})
        if not aria and qd.get("question_type") in ("file", "slider", "ranking", "matrix"):
            findings.append({"rule": "a11y.aria_label", "severity": "warning",
                             "question_id": qid,
                             "message": "Complex control should have an explicit aria-label."})
        if text and text.isupper() and len(text) > 10:
            findings.append({"rule": "a11y.shouting", "severity": "info",
                             "question_id": qid,
                             "message": "Screen readers may read all-caps as initialisms."})
        if qd.get("question_type") == "mcq":
            try:
                opts = json.loads(qd.get("options_json") or "[]")
                if len(opts) < 2:
                    findings.append({"rule": "a11y.mcq_options", "severity": "error",
                                     "question_id": qid,
                                     "message": "MCQ needs at least 2 options."})
            except json.JSONDecodeError:
                findings.append({"rule": "a11y.mcq_options", "severity": "error",
                                 "question_id": qid,
                                 "message": "MCQ options are not valid JSON."})

    # Persist
    with transaction() as conn:
        conn.execute("DELETE FROM evaluation_accessibility_audits WHERE template_id=?",
                     (template_id,))
        for f in findings:
            conn.execute(
                """INSERT INTO evaluation_accessibility_audits
                   (template_id, rule, severity, message, question_id)
                   VALUES (?,?,?,?,?)""",
                (template_id, f["rule"], f["severity"], f["message"], f["question_id"]),
            )
        conn.commit()
    return findings


# ---------- Version history & diff (feature 8) ----------

def _snapshot(template_id: int) -> dict:
    with get_connection() as conn:
        t = conn.execute("SELECT * FROM evaluation_templates WHERE template_id=?",
                         (template_id,)).fetchone()
        qs = conn.execute(
            "SELECT * FROM evaluation_questions WHERE template_id=? ORDER BY display_order",
            (template_id,),
        ).fetchall()
    return {
        "template": dict(t) if t else None,
        "questions": [dict(q) for q in qs],
    }


def save_version(template_id: int, *, change_summary: str = "",
                 changed_by: str = "") -> int:
    snap = _snapshot(template_id)
    with transaction() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM evaluation_template_versions WHERE template_id=?",
            (template_id,),
        ).fetchone()
        next_v = (row[0] or 0) + 1
        cur = conn.execute(
            """INSERT INTO evaluation_template_versions
               (template_id, version_number, snapshot_json, change_summary, changed_by)
               VALUES (?,?,?,?,?)""",
            (template_id, next_v, json.dumps(snap, default=str), change_summary, changed_by),
        )
        conn.commit()
        return cur.lastrowid


def list_versions(template_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT version_id, version_number, change_summary, changed_by, changed_at
               FROM evaluation_template_versions
               WHERE template_id=? ORDER BY version_number DESC""",
            (template_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_version(version_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evaluation_template_versions WHERE version_id=?",
            (version_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["snapshot"] = json.loads(d.pop("snapshot_json"))
        return d


def diff_versions(version_a: int, version_b: int) -> str:
    a, b = get_version(version_a), get_version(version_b)
    if not (a and b):
        raise ValueError("One or both versions not found.")
    text_a = json.dumps(a["snapshot"], indent=2, sort_keys=True, default=str).splitlines()
    text_b = json.dumps(b["snapshot"], indent=2, sort_keys=True, default=str).splitlines()
    return "\n".join(unified_diff(
        text_a, text_b,
        fromfile=f"v{a['version_number']} @ {a['changed_at']}",
        tofile=f"v{b['version_number']} @ {b['changed_at']}",
        lineterm="",
    ))


# ---------- Template library (feature 1) ----------

def list_templates(*, template_type: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_templates"
    args: list[Any] = []
    if template_type:
        sql += " WHERE template_type=?"
        args.append(template_type)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


def clone_template(template_id: int, new_name: str, *, created_by: str = "") -> int:
    snap = _snapshot(template_id)
    if not snap["template"]:
        raise ValueError(f"Template {template_id} not found.")
    t = snap["template"]
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_templates
                 (template_name, template_type, description, created_by)
               VALUES (?,?,?,?)""",
            (new_name, t["template_type"], t.get("description", ""), created_by),
        )
        new_id = cur.lastrowid
        for q in snap["questions"]:
            conn.execute(
                """INSERT INTO evaluation_questions
                     (template_id, question_text, question_type, question_category,
                      scale_min, scale_max, display_order, is_required,
                      options_json, bank_id, parent_question_id, show_if_op,
                      show_if_value, aria_label)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (new_id, q["question_text"], q["question_type"], q.get("question_category"),
                 q.get("scale_min", 1), q.get("scale_max", 5),
                 q.get("display_order", 0), q.get("is_required", 1),
                 q.get("options_json"), q.get("bank_id"),
                 q.get("parent_question_id"), q.get("show_if_op"),
                 q.get("show_if_value"), q.get("aria_label")),
            )
        conn.commit()
    save_version(new_id, change_summary=f"Cloned from template {template_id}",
                 changed_by=created_by)
    return new_id


def export_template(template_id: int) -> str:
    snap = _snapshot(template_id)
    snap["exported_at"] = datetime.now().isoformat()
    return json.dumps(snap, indent=2, default=str)


__all__ = [
    "SUPPORTED_TYPES", "SUPPORTED_OPS",
    "add_bank_question", "list_bank", "get_bank_tags",
    "add_tag", "remove_tag", "insert_bank_question_into_template",
    "set_branching", "clear_branching", "should_show",
    "validate_answer", "set_question_type", "set_required",
    "set_locale_text", "get_locales", "render_question",
    "contrast_ratio", "audit_template",
    "save_version", "list_versions", "get_version", "diff_versions",
    "list_templates", "clone_template", "export_template",
]
