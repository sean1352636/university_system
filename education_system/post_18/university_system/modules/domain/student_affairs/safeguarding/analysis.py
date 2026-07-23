import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)


class RiskCategory:
    SELF_HARM = "Self-harm / Suicide"
    MENTAL_HEALTH = "Mental Health"
    BULLYING = "Bullying / Harassment"
    EXPLOITATION = "Exploitation / Abuse"
    SUBSTANCE = "Substance Misuse"
    ACADEMIC = "Academic Distress"
    DISCRIMINATION = "Discrimination / Hate"
    EXTREMISM = "Radicalisation Concern"


RISK_PATTERNS = {
    RiskCategory.SELF_HARM: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bkill\s+myself\b",
            r"\bend\s+(it|my\s+life)\b",
            r"\bsuicid\w*\b",
            r"\bself[\s-]?harm\b",
            r"\bcut\s+myself\b",
            r"\bdon't\s+want\s+to\s+(live|be\s+here)\b",
            r"\bwant\s+to\s+die\b",
            r"\bno\s+reason\s+to\s+live\b",
            r"\boverdos\w*\b",
        ],
    },
    RiskCategory.MENTAL_HEALTH: {
        "severity": "HIGH",
        "patterns": [
            r"\bdepress\w*\b",
            r"\banxiety\b",
            r"\bpanic\s+attack\b",
            r"\bcan't\s+cope\b",
            r"\bhopeless\b",
            r"\bworthless\b",
            r"\bbreakdown\b",
            r"\bmental\s+health\b",
            r"\bisolat\w+\b",
            r"\bcrying\s+(all|every)\b",
        ],
    },
    RiskCategory.BULLYING: {
        "severity": "HIGH",
        "patterns": [
            r"\bbull(y|ied|ying)\b",
            r"\bharass\w*\b",
            r"\bthreaten\w*\b",
            r"\bstalk\w*\b",
            r"\bintimidat\w*\b",
            r"\bhate\s+me\b",
            r"\bmaking\s+fun\s+of\s+me\b",
            r"\bpicking\s+on\s+me\b",
        ],
    },
    RiskCategory.EXPLOITATION: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bassault\w*\b",
            r"\brape\w*\b",
            r"\bgroom\w*\b",
            r"\bcoerc\w*\b",
            r"\bforc\w+\s+(me|to)\b",
            r"\binappropriate\s+touch\w*\b",
            r"\bsexual\s+abuse\b",
            r"\bdomestic\s+(abuse|violence)\b",
        ],
    },
    RiskCategory.SUBSTANCE: {
        "severity": "MEDIUM",
        "patterns": [
            r"\bdrunk\s+every\b",
            r"\baddict\w*\b",
            r"\boverdose\b",
            r"\bdrug\s+problem\b",
            r"\balcohol\s+problem\b",
            r"\bcan't\s+stop\s+drinking\b",
        ],
    },
    RiskCategory.ACADEMIC: {
        "severity": "LOW",
        "patterns": [
            r"\bfail\w+\s+(everything|all)\b",
            r"\bdrop\s+out\b",
            r"\bquit\s+uni\w*\b",
            r"\bcan't\s+keep\s+up\b",
            r"\boverwhelmed\b",
            r"\btoo\s+much\s+pressure\b",
            r"\bburn\s?out\b",
        ],
    },
    RiskCategory.DISCRIMINATION: {
        "severity": "HIGH",
        "patterns": [
            r"\bracis\w*\b",
            r"\bsexis\w*\b",
            r"\bhomophob\w*\b",
            r"\btransphob\w*\b",
            r"\bdiscriminat\w*\b",
            r"\bhate\s+crime\b",
            r"\bslur\w*\b",
        ],
    },
    RiskCategory.EXTREMISM: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bradicali[sz]\w*\b",
            r"\bextremis\w*\b",
            r"\bterroris\w*\b",
            r"\bjoin\s+a\s+cause\b",
        ],
    },
}
SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SEVERITY_COLOUR = {
    "LOW": "#f5c518",
    "MEDIUM": "#f38b00",
    "HIGH": "#d9480f",
    "CRITICAL": "#b00020",
    "NONE": "#2e7d32",
}


def analyse_text(text: str):
    """Return a dict of {category: [matched_snippets]} and overall severity."""
    text_lower = text.lower()
    matches = {}

    for category, cfg in RISK_PATTERNS.items():
        hits = []
        for pattern in cfg["patterns"]:
            for m in re.finditer(pattern, text_lower):
                # Capture a little surrounding context for the reviewer
                start = max(0, m.start() - 25)
                end = min(len(text_lower), m.end() + 25)
                hits.append("…" + text_lower[start:end].strip() + "…")
        if hits:
            matches[category] = {
                "severity": cfg["severity"],
                "snippets": hits,
            }

    # Overall severity = highest across all categories
    if not matches:
        overall = "NONE"
    else:
        overall = max(
            (m["severity"] for m in matches.values()),
            key=lambda s: SEVERITY_ORDER[s],
        )

    return matches, overall


_NLP_VOCAB = {
    RiskCategory.SELF_HARM: {
        "die",
        "death",
        "kill",
        "killing",
        "suicide",
        "suicidal",
        "harm",
        "hurt",
        "hurting",
        "pain",
        "blade",
        "overdose",
        "tablets",
        "end",
        "alive",
        "live",
        "living",
    },
    RiskCategory.MENTAL_HEALTH: {
        "depressed",
        "depression",
        "anxious",
        "anxiety",
        "panic",
        "stress",
        "lonely",
        "alone",
        "cry",
        "crying",
        "sad",
        "tired",
        "exhausted",
        "hopeless",
        "worthless",
        "empty",
    },
    RiskCategory.BULLYING: {
        "bully",
        "bullies",
        "bullying",
        "harass",
        "harassment",
        "threaten",
        "threats",
        "stalk",
        "stalking",
        "mean",
        "horrible",
        "mocking",
    },
    RiskCategory.EXPLOITATION: {
        "force",
        "forced",
        "forcing",
        "touch",
        "touched",
        "rape",
        "raped",
        "abuse",
        "abused",
        "assault",
        "groomed",
        "coerce",
        "coerced",
    },
    RiskCategory.SUBSTANCE: {
        "drunk",
        "drinking",
        "alcohol",
        "drugs",
        "pills",
        "weed",
        "cocaine",
        "addict",
        "addiction",
    },
    RiskCategory.ACADEMIC: {
        "fail",
        "failing",
        "exam",
        "exams",
        "deadline",
        "behind",
        "drop",
        "overwhelmed",
        "burnout",
        "pressure",
    },
    RiskCategory.DISCRIMINATION: {
        "racist",
        "sexist",
        "homophobic",
        "transphobic",
        "slur",
        "slurs",
        "discriminated",
        "hate",
    },
    RiskCategory.EXTREMISM: {
        "radical",
        "radicalised",
        "extremist",
        "extremism",
        "terrorist",
        "terrorism",
        "cause",
    },
}
_NLP_THRESHOLD = 0.10  # min normalized score to flag a category


def _crude_stem(word):
    for suf in ("ings", "ing", "ied", "ies", "ed", "es", "s"):
        if word.endswith(suf) and len(word) > len(suf) + 2:
            return word[: -len(suf)]
    return word


def nlp_classify(text):
    """Return ({category: score}, overall_confidence). Complements the regex
    classifier — both are stored so reviewers can see *why* a case was flagged."""
    if not text:
        return {}, 0.0
    tokens = [_crude_stem(t.lower()) for t in re.findall(r"[A-Za-z']+", text)]
    if not tokens:
        return {}, 0.0
    bag = {}
    for t in tokens:
        bag[t] = bag.get(t, 0) + 1
    total = len(tokens)
    scores = {}
    for cat, vocab in _NLP_VOCAB.items():
        stemmed = {_crude_stem(w) for w in vocab}
        hits = sum(bag.get(w, 0) for w in stemmed)
        score = hits / total
        if score >= _NLP_THRESHOLD:
            scores[cat] = round(score, 3)
    overall = max(scores.values()) if scores else 0.0
    return scores, overall


SELF_HARM_ESCALATION = (
    "Immediate-risk pathway triggered.\n\n"
    "ACTION CHECKLIST (DSL):\n"
    "  1. Attempt direct contact with the student now.\n"
    "  2. If unable to reach them and concern is acute, request a welfare\n"
    "     check via campus security and/or emergency services.\n"
    "  3. Notify the Designated Safeguarding Lead and log all actions.\n\n"
    "HOTLINES TO SHARE WITH STUDENT:\n"
    "  • Samaritans (UK)        116 123 — free, 24/7\n"
    "  • Shout (UK text)        Text SHOUT to 85258\n"
    "  • CALM (UK, men)         0800 58 58 58\n"
    "  • Papyrus HOPELINEUK     0800 068 4141 (under 35)\n"
    "  • Emergency services     999 / 112"
)


def is_self_harm_case(matches, nlp_scores):
    if (matches or {}).get(RiskCategory.SELF_HARM):
        return True
    if (nlp_scores or {}).get(RiskCategory.SELF_HARM, 0) >= 0.15:
        return True
    return False


__all__ = [
    "RiskCategory",
    "RISK_PATTERNS",
    "SEVERITY_ORDER",
    "SEVERITY_COLOUR",
    "analyse_text",
    "_NLP_VOCAB",
    "_NLP_THRESHOLD",
    "_crude_stem",
    "nlp_classify",
    "SELF_HARM_ESCALATION",
    "is_self_harm_case",
]
