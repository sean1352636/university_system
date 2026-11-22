"""A student's own check of a draft for AI-writing indicators, before they
submit.

:func:`self_check` gives the same indicators staff see
(``application/integrity/ai_indicators``), with advice on each, so a student can see
what a reader might ask them about. Nothing about the draft is stored: only
a hashed use counter, so a student can check :data:`PER_DAY` drafts a day
(the same limit as similarity draft checks). The result is never seen by
staff and never used in any decision.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

PER_DAY = 3
ADVICE = {
    "artefacts": "Your draft contains text that chat tools produce (for example \"I hope this "
                 "helps\" or \"[insert …]\"). If you used a tool, check your module's rules and "
                 "say how you used it; remove any leftover tool text.",
    "stock_phrases": "Several stock phrases (\"delve into\", \"plays a pivotal role\"…). Say it "
                     "in your own words, and specifically.",
    "sentence_variation": "Your sentences are very similar in length. Mixing short and long "
                          "sentences usually reads better.",
    "paragraph_variation": "Your paragraphs are almost the same length; let each one be as "
                           "long as its point needs.",
    "openers": "Many sentences start with \"Moreover\", \"Furthermore\" or \"Additionally\". "
               "Most sentences don't need a linking word.",
}


def _hash(who) -> str:
    return hashlib.sha256(f"self-check:{who.username}".encode()).hexdigest()[:24]


def _ensure(conn) -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        ai_detector_schema,
    )
    ai_detector_schema.apply_to_connection(conn)


def used_today(conn, who) -> int:
    _ensure(conn)
    return conn.execute("SELECT COUNT(*) FROM self_check_usage WHERE student_hash = ? AND "
                        "timestamp >= ?", (_hash(who), datetime.now().strftime("%Y-%m-%d"))
                        ).fetchone()[0]


def self_check(conn, who, text, file_type="txt") -> Dict[str, Any]:
    """The indicators for a student's draft (no commit). Students only."""
    from education_system.systems.university.application.integrity import ai_indicators
    from education_system.systems.university.application.integrity import access
    access.require(who is not None and who.is_student, "Draft checks are for students")
    if not str(text or "").strip():
        raise ValueError("Paste or load your draft first")
    if used_today(conn, who) >= PER_DAY:
        raise ValueError(f"You can check {PER_DAY} drafts a day")
    reading = ai_indicators.assess(text, file_type, int(access.number(conn, "ai_min_words")))
    band = reading["level"] if reading["strength"] is None else (
        "high" if reading["strength"] >= 0.6 else "medium" if reading["strength"] >= 0.3
        else "low")
    conn.execute("INSERT INTO self_check_usage (student_hash, score_range, timestamp) VALUES "
                 "(?, ?, ?)", (_hash(who), band, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    advice = [ADVICE[i["key"]] for i in reading["indicators"] if i["key"] in ADVICE and (
        (i["key"] == "artefacts")
        or (i["key"] == "stock_phrases" and i["value"] > 2)
        or (i["key"] == "sentence_variation" and i["value"] < 0.35)
        or (i["key"] == "paragraph_variation" and i["value"] < 0.2)
        or (i["key"] == "openers" and i["value"] > 0.25))]
    passages = [{**p, "text": str(text)[p["start"]:p["end"]]} for p in reading["passages"]]
    return {**reading, "passages": passages, "advice": advice,
            "checks_left_today": PER_DAY - used_today(conn, who),
            "note": "Nothing about your draft is kept, and staff never see this check. These are "
                    "indicators, not a judgement."}


class StudentSelfCheckTool:
    """The detector's handle on self-checks (its own short connections)."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def preview_analysis(self, text: str, student_id: str = None) -> Dict[str, Any]:
        """For a signed-in student, their counted self-check. For staff, a
        preview of what a student would see (not counted, not stored).
        ``student_id`` (older callers) is ignored: the signed-in person is
        used."""
        from education_system.systems.university.application.integrity import ai_indicators
        from education_system.systems.university.application.integrity import access
        conn = self.detector._safe_db_connect()
        try:
            who = access.from_user(conn, getattr(self.detector, "current_user", None))
            if who is not None and who.is_student:
                result = self_check(conn, who, text)
                conn.commit()
            else:
                result = ai_indicators.assess(text, "txt",
                                              int(access.number(conn, "ai_min_words")))
                result["note"] = "Staff preview of what a student would see; not stored."
        except (ValueError, PermissionError) as exc:
            conn.rollback()
            return {"error": str(exc), "overall_assessment": "not checked", "suggestions": [],
                    "risk_indicators": []}
        except Exception as exc:
            conn.rollback()
            logger.error(f"Error in self-check analysis: {exc}")
            return {"error": "Analysis temporarily unavailable", "overall_assessment":
                    "not checked", "suggestions": [], "risk_indicators": []}
        finally:
            conn.close()
        return {**result, "overall_assessment": result.get("level"),
                "suggestions": result.get("advice", []),
                "risk_indicators": [{"type": i["label"], "value": i["shown"],
                                     "meaning": i["meaning"]} for i in
                                    result.get("indicators", [])],
                "confidence": None}
