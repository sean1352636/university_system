"""Indicators that prose may have been produced with a generative AI tool.
Pure functions, no database.

This is **not** a detector and the result is not a probability. No tool can
tell reliably whether a person or a model wrote a text, and the false
positives fall hardest on students writing in a second language. What this
does is point a member of staff at features worth asking the student about,
each shown with the passages behind it:

* **Leftover chat text** — "As an AI language model", "I hope this helps",
  "[Insert …]", "as of my last knowledge update". The one strong signal.
* **Stock phrasing** — phrases far more common in model output than in
  student essays ("delve into", "a testament to", "plays a pivotal role"),
  per 1,000 words.
* **Even sentence lengths** — people vary sentence length a lot; model
  prose is often strikingly even (coefficient of variation).
* **Even paragraph lengths** — the same, for paragraphs.
* **Formulaic openings** — the share of sentences that open with a stock
  connective ("Moreover,", "Furthermore,", "Additionally,").

Quotations, the reference list and code are left out first (the same
masking as the similarity check), and a text shorter than ``min_words``
(default 250) gets no reading at all: there is too little to say anything.

Signals deliberately **not** used, because they mark honest students:
spelling quality, grammar-tool use, time of day or week, writing speed,
"translated" idiom, non-Latin characters, vocabulary richness.

:func:`assess` returns the indicators, a 0–1 ``strength`` (how much the
indicators together point the same way — for sorting a review queue, never
for a decision) and a ``level`` in words.
"""

from __future__ import annotations

import re
import statistics

from education_system.systems.university.application.integrity import plagiarism_text as ptext

METHOD = "indicators-v1"
MIN_WORDS = 250
MIN_SENTENCES = 12
MIN_PARAGRAPHS = 5

LEVELS = ((0.6, "several indicators"), (0.3, "some indicators"), (0.0, "few or no indicators"))

_ARTEFACTS = (
    r"as an ai(?: language)? model", r"as a large language model", r"i hope this helps",
    r"certainly[!,] here(?:'s| is)", r"here(?:'s| is) (?:a|an|the) (?:revised|rewritten) ",
    r"\[insert [^\]]{1,60}\]", r"as of my (?:last )?knowledge (?:update|cutoff)",
    r"regenerate response", r"i (?:cannot|can't) browse the internet",
    r"(?:feel free to|let me know if you(?:'d like| want| need))",
)
_STOCK = (
    "delve into", "delves into", "delving into", "a testament to", "plays a pivotal role",
    "plays a crucial role", "plays a vital role", "in today's fast-paced", "in today's digital",
    "ever-evolving", "ever-changing landscape", "navigate the complexities",
    "navigating the complexities", "the intricate interplay", "a rich tapestry", "tapestry of",
    "multifaceted", "it is important to note", "it is worth noting", "it's important to note",
    "underscores the importance", "highlights the importance", "in the realm of",
    "a nuanced understanding", "foster a sense", "serves as a reminder", "shed light on",
    "sheds light on", "paving the way", "pave the way", "at the end of the day",
    "a double-edged sword", "unlock the potential", "harness the power", "in conclusion,",
    "overall, it is clear", "embark on a journey", "stands as a", "the landscape of",
    "a myriad of", "myriad of", "seamlessly integrat", "game-changer", "cutting-edge",
)
_OPENERS = ("moreover", "furthermore", "additionally", "in addition", "overall", "ultimately",
            "consequently", "notably", "importantly", "in conclusion", "in summary")
_ARTEFACT_RX = re.compile("|".join(_ARTEFACTS), re.IGNORECASE)
_STOCK_RX = re.compile("|".join(re.escape(p) for p in _STOCK), re.IGNORECASE)


def _level(strength) -> str:
    return next(label for floor, label in LEVELS if strength >= floor)


def _variation(values) -> float | None:
    values = [v for v in values if v > 0]
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    return statistics.pstdev(values) / mean if mean else None


def _artefacts(text, kept):
    found = [m for m in _ARTEFACT_RX.finditer(text) if kept(m)]
    if not found:
        return None, 0.0, []
    return ({"key": "artefacts", "label": "Leftover chat text", "value": len(found),
             "shown": f"{len(found)} found",
             "meaning": "Text that chat tools produce and people do not write. Ask the student "
                        "about it."},
            0.6, [{"start": m.start(), "end": m.end(), "kind": "artefact"} for m in found])


def _stock(text, kept, words):
    found = [m for m in _STOCK_RX.finditer(text) if kept(m)]
    per_k = len(found) * 1000 / words
    return ({"key": "stock_phrases", "label": "Stock phrasing", "value": round(per_k, 2),
             "shown": f"{per_k:.1f} per 1,000 words",
             "meaning": "Student essays usually have fewer than 2 per 1,000 words; above 6 is "
                        "unusual."},
            min(0.35, max(0.0, (per_k - 2) / 4 * 0.35)),
            [{"start": m.start(), "end": m.end(), "kind": "stock"} for m in found])


def _sentence_variation(lengths):
    cv = _variation(lengths) if len(lengths) >= MIN_SENTENCES else None
    if cv is None:
        return None, 0.0, []
    return ({"key": "sentence_variation", "label": "Sentence length variation",
             "value": round(cv, 3), "shown": f"{cv:.2f}",
             "meaning": "People's writing is usually above 0.45; below 0.30 is strikingly "
                        "even."},
            min(0.2, max(0.0, (0.45 - cv) / 0.15 * 0.2)), [])


def _paragraph_variation(text):
    paragraphs = [p for p in re.split(r"\n[ \t]*\n", text) if len(p.split()) >= 15]
    cv = _variation([len(p.split()) for p in paragraphs]) \
        if len(paragraphs) >= MIN_PARAGRAPHS else None
    if cv is None:
        return None, 0.0, []
    return ({"key": "paragraph_variation", "label": "Paragraph length variation",
             "value": round(cv, 3), "shown": f"{cv:.2f}",
             "meaning": "Below 0.20 means the paragraphs are almost the same length."},
            min(0.1, max(0.0, (0.3 - cv) / 0.1 * 0.1)), [])


def _openers(text, prepared):
    if not prepared.sentences:
        return None, 0.0, []
    found = []
    for first, _last in prepared.sentences:
        start = prepared.spans[first][0]
        if any(text[start:start + 20].lower().startswith(o) for o in _OPENERS):
            found.append((start, prepared.spans[first][1]))
    share = len(found) / len(prepared.sentences)
    return ({"key": "openers", "label": "Formulaic sentence openings", "value": round(share, 3),
             "shown": f"{share:.0%} of sentences",
             "meaning": "Above 25% of sentences opening with Moreover / Furthermore / "
                        "Additionally is unusual (it is also common in second-language writing, "
                        "so weigh it lightly)."},
            min(0.15, max(0.0, (share - 0.15) / 0.15 * 0.15)),
            [{"start": a, "end": b, "kind": "opener"} for a, b in found])


def assess(text, file_type="txt", min_words=MIN_WORDS) -> dict:
    """The indicators for ``text``. ``level`` is ``"not enough text"`` (and
    ``strength`` ``None``) below ``min_words`` checked words, or for code."""
    text = str(text or "")
    prepared = ptext.prepare(text, file_type)
    words = len(prepared.tokens)
    base = {"method": METHOD, "words_checked": words, "words_excluded": prepared.excluded_words,
            "indicators": [], "passages": []}
    if prepared.code:
        return {**base, "strength": None, "level": "not assessed (code)"}
    if words < min_words:
        return {**base, "strength": None, "level": "not enough text",
                "note": f"Fewer than {min_words} words of the student's own prose; no reading."}
    masked = ptext._masked(ptext.fold(text)[0], False)

    def kept(match) -> bool:
        return not ptext._inside(match.start(), masked)

    lengths = [last - first + 1 for first, last in prepared.sentences]
    indicators, passages, strength = [], [], 0.0
    for indicator, weight, found in (_artefacts(text, kept), _stock(text, kept, words),
                                     _sentence_variation(lengths), _paragraph_variation(text),
                                     _openers(text, prepared)):
        if indicator is not None:
            indicators.append(indicator)
            strength += weight
            passages += found
    strength = round(min(1.0, strength), 3)
    passages.sort(key=lambda p: p["start"])
    return {**base, "strength": strength, "level": _level(strength), "indicators": indicators,
            "passages": passages}
