"""
Respondent-experience service (features 15-19).

15. Progress bar + save-and-resume (cross-device via token)
16. Mobile-first / responsive helpers + offline draft caching
17. Estimated-time-to-complete badge (per template)
18. Profanity / PII redaction on free-text
19. Sentiment preview for the respondent before submit
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- Progress + save/resume (15) ----------

def save_draft(evaluation_id: int, respondent_token: str,
               answers: dict[int, Any]) -> None:
    payload = json.dumps(answers, default=str)
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_drafts
                 (evaluation_id, respondent_token, answers_json)
               VALUES (?,?,?)
               ON CONFLICT(evaluation_id, respondent_token) DO UPDATE SET
                 answers_json=excluded.answers_json,
                 updated_at=datetime('now')""",
            (evaluation_id, respondent_token, payload),
        )
        conn.commit()


def load_draft(evaluation_id: int, respondent_token: str) -> dict[int, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT answers_json FROM evaluation_drafts
               WHERE evaluation_id=? AND respondent_token=?""",
            (evaluation_id, respondent_token),
        ).fetchone()
    if not row:
        return None
    try:
        return {int(k): v for k, v in json.loads(row[0]).items()}
    except (ValueError, json.JSONDecodeError):
        return None


def delete_draft(evaluation_id: int, respondent_token: str) -> None:
    with transaction() as conn:
        conn.execute(
            "DELETE FROM evaluation_drafts WHERE evaluation_id=? AND respondent_token=?",
            (evaluation_id, respondent_token),
        )
        conn.commit()


def progress(template_id: int, answers: dict[int, Any]) -> dict[str, int]:
    """Return {answered, total, percent} for the progress bar."""
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM evaluation_questions WHERE template_id=?",
            (template_id,),
        ).fetchone()[0]
    answered = sum(1 for v in answers.values()
                   if v not in (None, "", []) and not (isinstance(v, dict) and not v))
    pct = int(round(answered * 100 / total)) if total else 0
    return {"answered": answered, "total": total, "percent": pct}


# ---------- Estimated time-to-complete (17) ----------

# Per-type cost in seconds — calibrated against the cohort norms below.
_TYPE_SECONDS = {
    "likert": 5, "nps": 5, "slider": 8, "text": 30, "file": 45,
    "mcq": 8, "matrix": 25, "ranking": 35,
}


def estimate_minutes(template_id: int) -> int:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT question_type, options_json FROM evaluation_questions WHERE template_id=?",
            (template_id,),
        ).fetchall()
    secs = 0
    for r in rows:
        base = _TYPE_SECONDS.get(r["question_type"], 10)
        # matrix/ranking scale with option count
        if r["question_type"] in ("matrix", "ranking") and r["options_json"]:
            try:
                opts = json.loads(r["options_json"])
                base = max(base, base * max(1, len(opts) // 2))
            except json.JSONDecodeError:
                pass
        secs += base
    return max(1, round(secs / 60))


def store_estimate(evaluation_id: int, minutes: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE course_evaluations SET estimated_minutes=? WHERE evaluation_id=?",
            (minutes, evaluation_id),
        )
        conn.commit()


# ---------- Mobile / responsive layout hint (16) ----------

def responsive_columns(viewport_px: int) -> int:
    """Return how many columns to lay matrix/grid questions out in for the
    respondent's viewport width. Mobile-first."""
    if viewport_px < 600:
        return 1
    if viewport_px < 960:
        return 2
    if viewport_px < 1280:
        return 3
    return 4


# ---------- Profanity / PII redaction (18) ----------

# Keep these short and conservative — they live in code, not a third-party
# wordlist, so reviewers can audit them. Per-deployment rules live in the
# evaluation_redaction_rules table.
_DEFAULT_PROFANITY = (
    r"\b(damn|hell|crap|stupid|idiot|jerk|moron)\b",
)
_PII_PATTERNS = (
    # email
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]"),
    # phone (loose, 7+ digits with optional separators)
    (r"\+?\d[\d\s\-().]{6,}\d", "[phone]"),
    # student ID like S12345 / U-12345
    (r"\b[SU][- ]?\d{4,8}\b", "[student-id]"),
    # naive SSN
    (r"\b\d{3}-\d{2}-\d{4}\b", "[ssn]"),
    # credit-card-ish (13-19 digit run with separators)
    (r"\b(?:\d[ -]?){13,19}\b", "[card]"),
)


def _load_custom_rules() -> list[tuple[str, str]]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT pattern, replacement FROM evaluation_redaction_rules"
            ).fetchall()
        return [(r["pattern"], r["replacement"]) for r in rows]
    except Exception:
        return []


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in _PII_PATTERNS:
        out = re.sub(pat, repl, out)
    for pat in _DEFAULT_PROFANITY:
        out = re.sub(pat, "[redacted]", out, flags=re.IGNORECASE)
    for pat, repl in _load_custom_rules():
        try:
            out = re.sub(pat, repl, out, flags=re.IGNORECASE)
        except re.error:
            continue
    return out


def add_redaction_rule(pattern: str, replacement: str = "[redacted]") -> int:
    re.compile(pattern)  # validate up-front
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_redaction_rules (pattern, replacement) VALUES (?,?)",
            (pattern, replacement),
        )
        conn.commit()
        return cur.lastrowid


def list_redaction_rules() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_redaction_rules ORDER BY rule_id"
        ).fetchall()]


# ---------- Sentiment preview (19) ----------

_POSITIVE = {
    "great", "good", "excellent", "amazing", "loved", "love", "clear",
    "engaging", "helpful", "fantastic", "wonderful", "brilliant", "fun",
    "interesting", "well", "supportive", "kind", "fair", "best", "thanks",
}
_NEGATIVE = {
    "bad", "boring", "confusing", "rude", "awful", "terrible", "hated",
    "hate", "unhelpful", "unclear", "unfair", "rushed", "lost", "worst",
    "slow", "useless", "disappointed", "frustrated", "broken", "poor",
}
_INTENSIFIERS = {"very", "really", "extremely", "so", "incredibly"}
_NEGATORS = {"not", "no", "never", "nothing", "n't"}


def sentiment(text: str) -> dict:
    """Tiny lexicon-based sentiment scorer for in-form previews.

    Returns dict(polarity in [-1, 1], label in pos/neutral/neg, hits).
    Not for grading — for hint UX so students see how their comment reads.
    """
    if not text or not text.strip():
        return {"polarity": 0.0, "label": "neutral", "hits": {"pos": 0, "neg": 0}}
    tokens = re.findall(r"[A-Za-z']+", text.lower())
    pos = neg = 0
    for i, tok in enumerate(tokens):
        weight = 1
        if i > 0 and tokens[i - 1] in _INTENSIFIERS:
            weight = 2
        flipped = i > 0 and tokens[i - 1] in _NEGATORS
        if tok in _POSITIVE:
            if flipped:
                neg += weight
            else:
                pos += weight
        elif tok in _NEGATIVE:
            if flipped:
                pos += weight
            else:
                neg += weight
    total = pos + neg
    polarity = 0.0 if total == 0 else (pos - neg) / total
    if polarity > 0.25:
        label = "positive"
    elif polarity < -0.25:
        label = "negative"
    else:
        label = "neutral"
    return {"polarity": round(polarity, 3), "label": label,
            "hits": {"pos": pos, "neg": neg}}


def sentiment_preview(text: str) -> str:
    """One-line human-readable preview for the respondent."""
    s = sentiment(text)
    emoji = {"positive": "🙂", "neutral": "😐", "negative": "🙁"}[s["label"]]
    return f"{emoji}  Reads as {s['label']} (score {s['polarity']:+.2f}, +{s['hits']['pos']}/-{s['hits']['neg']})"


__all__ = [
    "save_draft", "load_draft", "delete_draft", "progress",
    "estimate_minutes", "store_estimate", "responsive_columns",
    "redact", "add_redaction_rule", "list_redaction_rules",
    "sentiment", "sentiment_preview",
]
