"""One AI-writing reading: analyse a text and store it.

Shared by the automatic reading after a submission
(``application/integrity/ai.check_submission`` via its ``_store``), readings
staff take in the Academic Integrity window, and the AI Content Detector
(``CoreAnalysisMixin.analyze_text*``), so every reading has the same shape
whatever took it, without constructing the full ``AIDetector``.

The reading is ``application/integrity/ai_indicators.assess`` (labelled indicators,
never a verdict) plus a ``detector`` section of informational extras:
disguised characters (look-alike letters beside Latin ones, hidden
characters inside words), the active trained model's estimate when there is
one, and — for a full analysis — citation checks, paraphrase-tool and
prompt-artefact patterns. Extras are shown to staff; only the indicators
make up ``strength``.

Stored in ``ai_detector_submissions`` / ``ai_detector_results`` with real
ids (student number, module code, assignment id, the assignment
submission). A reading at or above ``ai_review_threshold`` also opens an
``ai_detector_alerts`` row for the detector's alert queue; reviewing it goes
through ``integrity_ai.review_flag``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from education_system.systems.university.application.integrity import ai_indicators
from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import plagiarism_text as ptext

_LABEL_ID = re.compile(r"\(([^()]+)\)\s*$")
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")


def sentence_breakdown(text, passages) -> list[dict]:
    """The text sentence by sentence: where it is, how many words, which
    indicator passages fall in it (by kind) and what share of it they
    cover. For the Sentences view; informational."""
    text = str(text or "")
    covered = bytearray(len(text))
    for p in passages or ():
        start, end = p.get("start"), p.get("end")
        if start is None or end is None:
            continue
        for i in range(max(0, int(start)), min(int(end), len(text))):
            covered[i] = 1
    out = []
    for match in _SENTENCE.finditer(text):
        start, end = match.span()
        body = text[start:end].strip()
        if not body:
            continue
        kinds: dict = {}
        for p in passages or ():
            if p.get("start") is not None and p["start"] < end and p.get("end", 0) > start:
                kinds[p.get("kind", "stock")] = kinds.get(p.get("kind", "stock"), 0) + 1
        out.append({"index": len(out) + 1, "start": start, "end": end, "text": body,
                    "words": len(body.split()),
                    "share": round(sum(covered[start:end]) / max(1, end - start), 3),
                    "kinds": kinds})
    return out


def threshold(conn) -> float:
    """The one review threshold (integrity settings)."""
    return access.number(conn, "ai_review_threshold")


def coverage(reading) -> float:
    """How much text the reading rests on: 0 for none, 1 from 1,000 words."""
    words = reading.get("words_checked") or 0
    if reading.get("strength") is None:
        return 0.0
    return round(min(1.0, words / 1000), 3)


# ── ids ─────────────────────────────────────────────────────────────────


def normalise_ids(conn, student_id, module_code=None, assignment_id=None) -> tuple:
    """Real ids from what a screen passed. Display labels ("Name (5853694)",
    "ACC-Y1-2 - Management Accounting", "Essay 1 (Due: 2026-09-02)") are
    turned back into ids; anything that is not a known student, module or
    assignment raises ``ValueError``."""
    student = str(student_id or "").strip()
    match = _LABEL_ID.search(student)
    if match and not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                                  (student,)).fetchone():
        student = match.group(1).strip()
    if not student or not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                                       (student,)).fetchone():
        raise ValueError(f"No student {student_id!r}: choose the student from the list")
    module = str(module_code or "").strip() or None
    if module and " - " in module and not conn.execute(
            "SELECT 1 FROM modules WHERE module_code = ?", (module,)).fetchone():
        module = module.split(" - ", 1)[0].strip()
    if module and not conn.execute("SELECT 1 FROM modules WHERE module_code = ?",
                                   (module,)).fetchone():
        raise ValueError(f"No module {module_code!r}: choose the module from the list")
    assignment = None
    if assignment_id not in (None, ""):
        text = str(assignment_id).strip()
        if text.isdigit():
            assignment = int(text)
        else:
            title = text.split(" (Due:", 1)[0].strip()
            rows = conn.execute("SELECT id FROM assignments WHERE title = ? AND "
                                "(? IS NULL OR module_code = ?)", (title, module, module)
                                ).fetchall()
            if len(rows) != 1:
                raise ValueError(f"Assignment {assignment_id!r} not found: choose it from "
                                 "the list")
            assignment = rows[0][0]
        if not conn.execute("SELECT 1 FROM assignments WHERE id = ?", (assignment,)).fetchone():
            raise ValueError(f"No assignment {assignment_id!r}")
    return student, module, assignment


# ── analysis ────────────────────────────────────────────────────────────


def _disguised(text) -> dict:
    count = ptext.fold(text)[1]
    marks = sum(text.count(ch) for ch in ("‮", "‭", "‪", "‫"))
    return {"key": "disguised", "label": "Disguised characters",
            "value": count + marks, "shown": f"{count + marks} found",
            "meaning": "Look-alike letters from another alphabet next to Latin letters, hidden "
                       "characters inside words, or text-direction overrides. These are used "
                       "to get past checks; ordinary Greek or Cyrillic words are not counted."}


def _model_estimate(conn, reading) -> dict | None:
    try:
        from education_system.systems.university.shared.ai.ai_detector.ml import (
            indicator_model,
        )
    except ImportError:
        return None
    found = indicator_model.estimate(conn, reading)
    if not found:
        return None
    return {"key": "model_estimate",
            "label": f"Model estimate (trained on {found.get('trained_on')} reviewed cases)",
            "value": round(float(found["estimate"]), 3),
            "shown": f"{float(found['estimate']):.0%}",
            "meaning": "How often readings like this one were upheld when staff reviewed them "
                       f"(model {found.get('model_version')}"
                       + (f", validation {found['validation']}" if found.get("validation") else "")
                       + "). Informational: it does not change the strength.",
            "model_version": found.get("model_version")}


def analyse(conn, text, file_type="txt", *, full=False, detector=None) -> dict:
    """The reading for ``text``. ``full`` adds the slower extras (citation
    checks, paraphrase-tool and prompt-artefact patterns) from
    ``detector`` (an ``AIDetector``)."""
    reading = ai_indicators.assess(text, file_type, int(access.number(conn, "ai_min_words")))
    extras = {"informational": [_disguised(str(text or ""))]}
    estimate = _model_estimate(conn, reading) if reading.get("strength") is not None else None
    if estimate:
        extras["informational"].append(estimate)
    if full and detector is not None and reading.get("strength") is not None:
        extras.update(detector._full_extras(text))
    reading["detector"] = extras
    reading["coverage"] = coverage(reading)
    return reading


# ── storing ─────────────────────────────────────────────────────────────


def _level_word(conn, strength) -> str:
    if strength is None:
        return "low"
    limit = threshold(conn)
    if strength >= max(limit, 0.85):
        return "high"
    if strength >= limit:
        return "medium"
    return "low"


def _audit(conn, event, payload, actor) -> None:
    try:
        from education_system.systems.university.shared.ai.ai_detector.features import (
            blockchain_audit,
        )
    except ImportError:
        return
    record = getattr(blockchain_audit, "record", None)
    if record is not None:
        record(conn, event, payload, actor)


def store(conn, reading, *, text, student_id, module_code, assignment_id, submission_id,
          title, file_type, checked_by) -> int:
    """Store ``reading`` (from :func:`analyse`); returns the result id. In
    the caller's transaction."""
    from education_system.systems.university.infrastructure.database.schemas import (
        ai_detector_schema,
    )
    ai_detector_schema.apply_to_connection(conn)
    now = access.now()
    cur = conn.execute(
        "INSERT INTO ai_detector_submissions (student_id, submission_text, title, course_code, "
        "assignment_id, submission_date, word_count, character_count, "
        "assignment_submission_id, checked_by, file_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(student_id), str(text), title, module_code,
         None if assignment_id is None else str(assignment_id), now,
         reading["words_checked"], len(str(text)), submission_id, checked_by, file_type))
    reading_sub = cur.lastrowid
    strength = reading.get("strength")
    cur = conn.execute(
        "INSERT INTO ai_detector_results (submission_id, ai_score, confidence, detailed_results, "
        "created_at, method, level) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (reading_sub, 0.0 if strength is None else strength, reading.get("coverage", 0.0),
         json.dumps(reading, default=str), now, reading["method"], reading["level"]))
    result_id = cur.lastrowid
    if strength is not None and strength >= threshold(conn):
        conn.execute(
            "INSERT INTO ai_detector_alerts (submission_id, student_id, submission_title, "
            "risk_level, ai_score, status, created_at, ai_result_id, module_code, "
            "assignment_id) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
            (str(reading_sub), str(student_id), title, _level_word(conn, strength), strength, now,
             result_id, module_code, None if assignment_id is None else str(assignment_id)))
    _audit(conn, "reading_stored", {"ai_result_id": result_id, "student_id": str(student_id),
                                    "module_code": module_code, "strength": strength,
                                    "method": reading["method"]}, checked_by)
    return result_id


def alert_emails(conn, result_id) -> list[tuple]:
    """E-mails to the module's staff about a new alert (send after commit)."""
    row = conn.execute("SELECT a.module_code, a.risk_level FROM ai_detector_alerts a WHERE "
                       "a.ai_result_id = ?", (result_id,)).fetchone()
    if not row:
        return []
    module, level = row[0], row[1]
    addresses = set(access.module_staff_emails(conn, module)) if module else set()
    # Extra recipients set up in the detector (setup_email_alerts).
    for email, levels in conn.execute("SELECT email, risk_levels FROM ai_detector_email_alerts "
                                      "WHERE is_active = 1").fetchall():
        if level in str(levels or "").split(","):
            addresses.add(email)
    return [(address, f"{module or 'AI writing'}: a reading is waiting for review",
             f"AI-writing reading {result_id}{f' on {module}' if module else ''} reached the "
             "review level. Readings are indicators, not evidence: review it in the Academic "
             "Integrity window or the AI Content Detector's alert queue.")
            for address in sorted(addresses)]


def now_iso() -> str:
    return datetime.now().isoformat()
