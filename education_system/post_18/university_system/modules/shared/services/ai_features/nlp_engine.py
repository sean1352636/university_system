"""Real NLP backends for the AI-features GUI.

Two capabilities replace the previous placeholders in ``ai_features_gui``:

* :func:`analyze_sentiment_text` — sentiment scoring via NLTK's VADER model
  (a real lexicon-based analyzer), with a keyword fallback if the VADER lexicon
  is unavailable.
* :func:`generate_chatbot_reply` — a deterministic, database-grounded assistant
  response. When the Anthropic SDK and credentials are available it calls
  Claude (``claude-opus-4-8``); otherwise it answers from real university data
  (fee types, scholarships, payment methods) with an intent-aware fallback.

Neither path returns random canned text.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

# --- Sentiment ------------------------------------------------------------

# Keyword lists kept as a fallback when the VADER lexicon isn't downloaded.
_POSITIVE_WORDS = [
    "good", "great", "excellent", "amazing", "wonderful", "fantastic", "love",
    "helpful", "clear", "outstanding", "positive", "happy", "satisfied",
]
_NEGATIVE_WORDS = [
    "bad", "terrible", "awful", "hate", "horrible", "poor", "worst",
    "confusing", "useless", "negative", "unhappy", "disappointed", "broken",
]

_vader = None
_vader_tried = False


def _get_vader():
    """Lazily construct a VADER analyzer, downloading the lexicon if needed."""
    global _vader, _vader_tried
    if _vader is not None or _vader_tried:
        return _vader
    _vader_tried = True
    try:
        import nltk
        from nltk.sentiment import SentimentIntensityAnalyzer

        # Resolve VADER from (and download it into) the bundled repo data dir,
        # matching the plagiarism module, so nothing lands in ~/nltk_data.
        from education_system.post_18.university_system.core.paths import NLTK_DATA_DIR

        custom_nltk_path = str(NLTK_DATA_DIR)
        if custom_nltk_path not in nltk.data.path:
            nltk.data.path.insert(0, custom_nltk_path)

        try:
            _vader = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download("vader_lexicon", download_dir=custom_nltk_path, quiet=True)
            _vader = SentimentIntensityAnalyzer()
    except Exception:
        _vader = None
    return _vader


def analyze_sentiment_text(text: str) -> Tuple[str, float]:
    """Return ``(category, score)`` where category is positive/negative/neutral
    and score is a 0.0-1.0 confidence-style value.

    Uses VADER's compound score when available; otherwise falls back to a
    keyword count. The 0.0-1.0 range matches the ``ai_sentiment_analysis``
    schema (``sentiment_score`` column).
    """
    text = text or ""
    analyzer = _get_vader()
    if analyzer is not None:
        compound = analyzer.polarity_scores(text)["compound"]  # -1.0 .. 1.0
        # Map compound (-1..1) onto 0..1 for storage.
        score = (compound + 1.0) / 2.0
        if compound >= 0.05:
            sentiment = "positive"
        elif compound <= -0.05:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        return sentiment, max(0.0, min(1.0, score))

    # Fallback: keyword counting.
    lower = text.lower()
    pos = sum(w in lower for w in _POSITIVE_WORDS)
    neg = sum(w in lower for w in _NEGATIVE_WORDS)
    if pos > neg:
        return "positive", max(0.0, min(1.0, 0.6 + pos * 0.1))
    if neg > pos:
        return "negative", max(0.0, min(1.0, 0.4 - neg * 0.1))
    return "neutral", 0.5


# --- Chatbot --------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are the assistant for a university management system. Answer student "
    "and staff questions about fees, scholarships, payments, enrolment and "
    "general university services concisely and helpfully. If a question needs "
    "personal account data you don't have, tell the user which office or "
    "system to check. Keep answers under 120 words."
)


def _claude_reply(message: str, context: str = "") -> Optional[str]:
    """Call Claude if the Anthropic SDK and credentials are available.

    Returns the reply text, or ``None`` if the SDK is missing, no credentials
    are configured, or the call fails — callers then fall back to the
    database-grounded responder.
    """
    try:
        import anthropic
    except ImportError:
        return None

    # Only attempt a network call if some credential is configured; a bare
    # client would otherwise raise. (ANTHROPIC_API_KEY or an auth token.)
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None

    try:
        client = anthropic.Anthropic()
        user_content = message if not context else f"Context:\n{context}\n\nQuestion: {message}"
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return next((b.text for b in response.content if b.type == "text"), None)
    except Exception:
        return None


def _grounded_reply(message: str) -> str:
    """Deterministic, database-grounded fallback response.

    Detects the query intent and answers from real reference data where
    possible, otherwise returns a clear description of what the assistant can
    help with. Never returns random text.
    """
    msg = (message or "").lower().strip()

    def _rows(sql, params=()):
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                return conn.execute(sql, params).fetchall()
        except Exception:
            return []

    if not msg:
        return "How can I help? You can ask me about fees, scholarships, or payment methods."

    if any(w in msg for w in ("hello", "hi ", "hey", "good morning", "good afternoon")) or msg in ("hi", "hey"):
        return ("Hello! I can help with questions about tuition and fees, "
                "scholarships, and how to make payments. What would you like to know?")

    if any(w in msg for w in ("fee", "tuition", "cost", "how much", "charge")):
        rows = _rows("SELECT fee_name, amount FROM fee_types WHERE is_active = 1 ORDER BY amount DESC")
        if rows:
            lines = [f"• {r['fee_name']}: £{(r['amount'] or 0):,.2f}" for r in rows[:8]]
            return "Here are the current fee types:\n" + "\n".join(lines)
        return ("Fee information is managed in the Finance system. For your personal "
                "balance, please check your student finance account or contact the "
                "finance office.")

    if "scholarship" in msg or "bursary" in msg or "financial aid" in msg:
        rows = _rows("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM scholarships WHERE is_active = 1")
        if rows and rows[0][0]:
            n, total = rows[0]
            return (f"There are currently {n} active scholarship(s) with a total pool of "
                    f"£{(total or 0):,.2f}. You can apply through the scholarships section "
                    f"of the student portal.")
        return ("Scholarship and bursary applications are handled through the student "
                "portal. Check the scholarships section for currently open awards.")

    if any(w in msg for w in ("pay", "payment", "how do i pay", "card", "installment", "instalment")):
        rows = _rows(
            "SELECT DISTINCT payment_method FROM payments "
            "WHERE payment_method IS NOT NULL AND TRIM(payment_method) <> '' LIMIT 8")
        methods = ", ".join(r[0] for r in rows) if rows else "card, bank transfer"
        return (f"Payments can be made through the Finance system. Accepted methods "
                f"include: {methods}. Payment plans may also be available for larger "
                f"balances — ask the finance office about installment options.")

    if any(w in msg for w in ("thank", "thanks", "cheers")):
        return "You're welcome! Let me know if there's anything else I can help with."

    return ("I can help with questions about tuition and fees, scholarships and "
            "bursaries, and payment methods. Could you rephrase your question, or "
            "pick one of those topics?")


def generate_chatbot_reply(message: str, context: str = "") -> str:
    """Produce an assistant reply for ``message``.

    Prefers a Claude response when the Anthropic SDK and credentials are
    configured; otherwise returns a deterministic, database-grounded answer.
    """
    reply = _claude_reply(message, context)
    if reply:
        return reply
    return _grounded_reply(message)
