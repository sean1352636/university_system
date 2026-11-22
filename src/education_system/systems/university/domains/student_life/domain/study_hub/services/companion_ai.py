"""The study companion's AI: concept explanations and flashcard writing.

Two paths, chosen per call:

* **Claude** (``claude-opus-5-5``) when the ``anthropic`` SDK is installed and
  credentials resolve (``ANTHROPIC_API_KEY``, ``ANTHROPIC_AUTH_TOKEN`` or an
  ``ant auth login`` profile). Flashcards come back as schema-checked JSON
  (``output_config.format``). Server-side refusal fallback is on
  (``fallbacks: "default"``); a request that is still refused, or any API
  error, drops to the second path rather than failing the student.
* **Course materials** otherwise: explanations are assembled from what the
  university's records say about the module (specification, learning
  outcomes, description) and the student's own cards, and flashcards are
  extracted from definition-shaped sentences in the student's notes. Nothing
  is invented, and the text says which path produced it.

The old explainer returned the same fill-in-the-blanks template for every
concept ("First key point… Think of it like…").

``STUDY_COMPANION_AI=off`` disables the Claude path; ``STUDY_COMPANION_MODEL``
overrides the model. The system prompt keeps explanations on the concept and
away from writing assessed work (see ``_SYSTEM``).
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
LEVELS = ("Beginner", "Intermediate", "Advanced")
MAX_NOTES_CHARS = 60_000
MAX_CARDS = 40

_SYSTEM = (
    "You are the study companion in a university's student system. You help one "
    "student understand concepts from their own modules and revise them.\n"
    "- Explain the concept itself: what it is, why it matters, how it works, a "
    "worked example, and the mistakes students commonly make.\n"
    "- Pitch it at the level asked for (Beginner: no prior knowledge, plain words; "
    "Intermediate: assumes the basics, adds mechanism and application; Advanced: "
    "formal detail, edge cases, links to related ideas).\n"
    "- Where course material is supplied, stay consistent with it and use its "
    "terms. Say so if the course material and the concept do not seem to match.\n"
    "- Academic integrity: do not write answers to assessment, coursework or exam "
    "questions, essays or reports for submission. If the request is an assessment "
    "task, explain the underlying concepts and how to approach it instead, and say "
    "why.\n"
    "- If the student seems distressed or at risk, say kindly that support is "
    "available and point them to the university's wellbeing service.\n"
    "- Use short headed sections and bullet points in plain text with light "
    "Markdown. Aim for 250-600 words."
)

_CARD_SYSTEM = (
    "You write revision flashcards for a university student from their own notes. "
    "Each card tests one idea. Questions are specific and answerable from the notes; "
    "answers are short (one to three sentences) and correct according to the notes. "
    "Do not add facts the notes do not support. Skip anything that is not study "
    "content (names, admin notices)."
)

_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cards"],
    "additionalProperties": False,
}


# ── Claude ──────────────────────────────────────────────────────────────


def ai_enabled() -> bool:
    return os.environ.get("STUDY_COMPANION_AI", "on").strip().lower() not in (
        "off", "0", "false", "no")


def _model() -> str:
    return os.environ.get("STUDY_COMPANION_MODEL", "").strip() or MODEL


def _client():
    if not ai_enabled():
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        logger.debug("Anthropic client unavailable", exc_info=True)
        return None


def _call(system, user, *, schema=None, max_tokens=16000):
    """One Claude request; the response text, or ``None`` on any failure,
    refusal or truncation (the caller then uses its course-materials path)."""
    client = _client()
    if client is None:
        return None
    params = {
        "model": _model(),
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": "medium"},
    }
    if schema is not None:
        params["output_config"]["format"] = {"type": "json_schema", "schema": schema}
    import anthropic
    try:
        try:
            response = client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
        except (TypeError, anthropic.BadRequestError):
            # An SDK that does not know the fallback parameter, or a platform
            # that rejects it: the same request without it.
            response = client.messages.create(**params)
    except Exception as exc:  # anthropic.APIError, connection, auth, ...
        logger.warning("Study companion AI request failed: %s", exc)
        return None
    if getattr(response, "stop_reason", None) in ("refusal", "max_tokens"):
        logger.info("Study companion AI stopped: %s", response.stop_reason)
        return None
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    return text.strip() or None


# ── explanations ────────────────────────────────────────────────────────


def _material_block(material) -> str:
    if not material or not material.get("module_code"):
        return ""
    lines = [f"Module: {material['module_code']} {material.get('module_name') or ''}".strip()]
    if material.get("aims"):
        lines.append(f"Aims: {material['aims']}")
    if material.get("description"):
        lines.append(f"Description: {material['description']}")
    if material.get("topics"):
        lines.append("Topics / learning outcomes:\n" + "\n".join(f"- {t}" for t in material["topics"]))
    return "\n".join(lines)


def explain(concept, level="Beginner", material=None, own_cards=()) -> dict:
    """``{explanation, source, model}`` for ``concept`` at ``level``.

    ``material`` is :func:`study_context.course_material` for the module (or
    ``None``); ``own_cards`` are the student's flashcards that mention it.
    """
    concept = (concept or "").strip()
    if not concept:
        raise ValueError("Enter a concept to explain")
    if len(concept) > 300:
        raise ValueError("Keep the concept to 300 characters — use flashcards-from-notes "
                         "for longer text")
    level = level if level in LEVELS else "Beginner"
    block = _material_block(material)
    prompt = (f"Explain this concept at {level} level: {concept}"
              + (f"\n\nCourse material for context:\n{block}" if block else ""))
    text = _call(_SYSTEM, prompt)
    if text:
        return {"explanation": text, "source": "claude", "model": _model()}
    return {"explanation": _grounded_explanation(concept, level, material, own_cards),
            "source": "course_materials", "model": None}


_APPROACH = {
    "Beginner": [
        "Write a one-sentence definition of {c} in your own words, then check it "
        "against your lecture notes.",
        "Find one concrete example of {c} in this module's material and say why it "
        "is an example.",
        "Note one thing {c} is often confused with and how they differ.",
    ],
    "Intermediate": [
        "Explain step by step how {c} works, as if teaching a classmate.",
        "Apply {c} to a problem or case from a past paper or seminar sheet.",
        "List the conditions under which {c} holds, and one where it does not.",
    ],
    "Advanced": [
        "Set out the formal statement or model behind {c} and the assumptions it needs.",
        "Work through an edge case or limitation of {c} and what the literature says about it.",
        "Connect {c} to two other topics in the module and explain the link.",
    ],
}


def _grounded_explanation(concept, level, material, own_cards) -> str:
    out = [f"{concept} — {level} study notes from your course materials", ""]
    found = False
    if material and material.get("module_code"):
        name = f"{material['module_code']} {material.get('module_name') or ''}".strip()
        if material.get("mentions"):
            found = True
            out.append(f"Where it appears in {name}:")
            out += [f"• {m}" for m in material["mentions"]]
            out.append("")
        elif material.get("topics"):
            out.append(f"{name} covers these topics — find where {concept} fits:")
            out += [f"• {t}" for t in material["topics"][:8]]
            out.append("")
        if material.get("aims"):
            out += [f"Module aims: {material['aims']}", ""]
        if material.get("reading_list"):
            out += [f"Reading list: {material['reading_list']}", ""]
    cards = list(own_cards or [])
    if cards:
        found = True
        out.append("From your own flashcards:")
        out += [f"• Q: {c['question']}\n  A: {c['answer']}" for c in cards[:6]]
        out.append("")
    if not found:
        out += [f"Your module records do not mention {concept} yet. Your lecture notes, "
                "the module reading list and your module team are the places to start.", ""]
    out.append("How to study it at this level:")
    out += [f"{i}. {step.format(c=concept)}" for i, step in enumerate(_APPROACH[level], 1)]
    out += ["", "(AI explanations are not available here, so this page is drawn from the "
                "university's module records and your own cards.)"]
    return "\n".join(out)


# ── flashcards ──────────────────────────────────────────────────────────


def _clean_cards(cards, limit) -> list[dict]:
    seen, out = set(), []
    for card in cards:
        q = re.sub(r"\s+", " ", str(card.get("question") or "")).strip()
        a = re.sub(r"\s+", " ", str(card.get("answer") or "")).strip()
        if len(q) < 3 or len(a) < 1 or q.lower() in seen:
            continue
        seen.add(q.lower())
        out.append({"question": q[:500], "answer": a[:1000]})
        if len(out) >= limit:
            break
    return out


def cards_from_text(text, count=10, topic=None) -> dict:
    """``{cards: [{question, answer}], source}`` written from ``text``."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Paste some notes to make flashcards from")
    if len(text) > MAX_NOTES_CHARS:
        raise ValueError(f"The notes are {len(text):,} characters; the limit is "
                         f"{MAX_NOTES_CHARS:,}. Split them and make cards from each part.")
    count = max(1, min(int(count or 10), MAX_CARDS))
    prompt = (f"Write up to {count} flashcards"
              + (f" on {topic}" if topic else "")
              + f" from these notes:\n\n<notes>\n{text}\n</notes>")
    raw = _call(_CARD_SYSTEM, prompt, schema=_CARD_SCHEMA)
    if raw:
        try:
            cards = _clean_cards(json.loads(raw).get("cards", []), count)
            if cards:
                return {"cards": cards, "source": "claude"}
        except (ValueError, AttributeError):
            logger.warning("Study companion AI returned unparseable cards")
    return {"cards": _clean_cards(extract_definitions(text), count), "source": "extracted"}


_TERM = r"([A-Z]?[\w'’()\-/ ]{1,60}?)"
_PATTERNS = (
    re.compile(r"^\s*" + _TERM + r"\s*(?::|—|–| - )\s*(.{3,})$"),
    re.compile(r"^\s*" + _TERM + r"\s+(?:is defined as|is called|refers to|means|"
               r"describes)\s+(.{3,})$", re.I),
    re.compile(r"^\s*(?:an?|the)?\s*" + _TERM + r"\s+(?:is|are)\s+((?:an?|the|one|"
               r"when|where|how|a set|the process)\b.{3,})$", re.I),
)


def extract_definitions(text) -> list[dict]:
    """Definition-shaped lines and sentences as question/answer pairs:
    ``Term: definition``, ``Term means …``, ``A term is a …``."""
    cards = []
    lines = []
    for line in str(text).splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if not line:
            continue
        lines += [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line) if s.strip()]
    for sentence in lines:
        for pattern in _PATTERNS:
            m = pattern.match(sentence)
            if not m:
                continue
            term, rest = m.group(1).strip(" .,"), m.group(2).strip()
            if not term or len(term.split()) > 8 or term.lower() in _NOT_TERMS:
                continue
            question = term if term.endswith("?") else f"What is {term}?"
            cards.append({"question": question, "answer": rest[:1].upper() + rest[1:]})
            break
    return cards


_NOT_TERMS = frozenset({
    "it", "this", "that", "there", "these", "those", "note", "notes", "example", "e.g", "i.e",
    "tip", "warning", "see", "todo", "date", "time", "week", "lecture", "reading", "nb",
    "question", "answer", "summary",
})


def card_from_mistake(question, answer, given=None) -> dict:
    """A new ``{question, answer, source}`` card aimed at what went wrong
    when the student answered ``question`` with ``given`` instead of
    ``answer``."""
    question, answer = (question or "").strip(), (answer or "").strip()
    if not question or not answer:
        raise ValueError("The card has no question or answer")
    if given:
        prompt = (f"A student revising got this flashcard wrong.\nQuestion: {question}\n"
                  f"Correct answer: {answer}\nThe student answered: {given}\n\n"
                  "Write ONE new flashcard that targets the confusion behind their answer "
                  "(for example, asking how the two ideas differ).")
        raw = _call(_CARD_SYSTEM, prompt, schema=_CARD_SCHEMA, max_tokens=4000)
        if raw:
            try:
                cards = _clean_cards(json.loads(raw).get("cards", []), 1)
                if cards:
                    return dict(cards[0], source="claude")
            except (ValueError, AttributeError):
                pass
        return {"question": f"{question}\n(Not: {given.strip()[:200]})", "answer": answer,
                "source": "mistake"}
    # No wrong answer recorded: practise it the other way round.
    return {"question": f"Which question does this answer?\n{answer}", "answer": question,
            "source": "mistake"}
