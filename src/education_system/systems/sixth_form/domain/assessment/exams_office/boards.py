"""Awarding bodies and the board-level constants the exams office uses.

Kept free of imports so :mod:`exam_entries` can use it without a cycle.
"""

from __future__ import annotations

# The five UK awarding bodies a sixth form enters with, plus the two
# legacy values older rows may carry (Cambridge International and a
# catch-all) so existing entries still validate.
EXAM_BOARDS: tuple[str, ...] = (
    "Pearson (Edexcel)",
    "AQA",
    "OCR",
    "WJEC/Eduqas",
    "CCEA",
    "CIE",
    "Other",
)

# Spellings found in older rows and in board result files.
BOARD_ALIASES: dict[str, str] = {
    "edexcel": "Pearson (Edexcel)",
    "pearson": "Pearson (Edexcel)",
    "pearson edexcel": "Pearson (Edexcel)",
    "pearson (edexcel)": "Pearson (Edexcel)",
    "aqa": "AQA",
    "ocr": "OCR",
    "wjec": "WJEC/Eduqas",
    "eduqas": "WJEC/Eduqas",
    "wjec/eduqas": "WJEC/Eduqas",
    "wjec eduqas": "WJEC/Eduqas",
    "ccea": "CCEA",
    "cie": "CIE",
    "cambridge": "CIE",
    "other": "Other",
}


def normalise_board(value: str | None) -> str | None:
    """Canonical board name for *value*, or None when it is not a board."""
    s = (value or "").strip()
    if not s:
        return None
    if s in EXAM_BOARDS:
        return s
    return BOARD_ALIASES.get(s.lower())


def stored_names(board: str) -> list[str]:
    """Every spelling a row for *board* may be stored under (for filters)."""
    canonical = normalise_board(board) or board
    names = {canonical}
    names.update(k for k, v in BOARD_ALIASES.items() if v == canonical)
    # Aliases are lower-case; the legacy stored spelling is title-case.
    if canonical == "Pearson (Edexcel)":
        names.update({"Edexcel", "Pearson"})
    if canonical == "WJEC/Eduqas":
        names.update({"WJEC", "Eduqas"})
    return sorted(names)


# ── Exam sessions ───────────────────────────────────────────────────

SESSIONS: tuple[str, ...] = ("AM", "PM")

# JCQ's standard session start times. A centre may start up to 30
# minutes later; change these if the college's published times differ.
SESSION_START: dict[str, str] = {"AM": "09:00", "PM": "13:30"}


# ── Post-results services ───────────────────────────────────────────

# JCQ sets common post-results deadlines across all its member boards
# (AQA, CCEA, OCR, Pearson, WJEC/Eduqas). They are published each year
# in JCQ's "Post-Results Services" booklet as calendar dates; expressed
# here as days after results day, which is how they fall in practice:
# priority services close about a week after results, the rest about
# five weeks after (summer) or four weeks (November / January series).
# Check the booklet each year and change these if JCQ moves them.
_JCQ_SUMMER_DAYS: dict[str, int] = {
    "Clerical check": 35,
    "Review of marking": 35,
    "Priority review of marking": 7,
    "Access to scripts (priority copy)": 7,
    "Access to scripts (copy)": 35,
    "Review of moderation": 35,
}
_JCQ_WINTER_DAYS: dict[str, int] = {
    "Clerical check": 28,
    "Review of marking": 28,
    "Priority review of marking": 28,
    "Access to scripts (priority copy)": 28,
    "Access to scripts (copy)": 28,
    "Review of moderation": 28,
}

POST_RESULTS_DEADLINE_DAYS: dict[str, dict[str, dict[str, int]]] = {
    board: {"Summer": dict(_JCQ_SUMMER_DAYS),
            "November": dict(_JCQ_WINTER_DAYS),
            "January": dict(_JCQ_WINTER_DAYS)}
    for board in ("Pearson (Edexcel)", "AQA", "OCR", "WJEC/Eduqas", "CCEA")
}
# Non-JCQ boards set their own; use the JCQ pattern until told otherwise.
for _board in ("CIE", "Other"):
    POST_RESULTS_DEADLINE_DAYS[_board] = {
        "Summer": dict(_JCQ_SUMMER_DAYS),
        "November": dict(_JCQ_WINTER_DAYS),
        "January": dict(_JCQ_WINTER_DAYS)}

POST_RESULTS_SERVICES: tuple[str, ...] = tuple(_JCQ_SUMMER_DAYS)


def post_results_deadline_days(board: str, season: str, service: str) -> int:
    """Days after results day the board's deadline for *service* falls."""
    table = POST_RESULTS_DEADLINE_DAYS.get(normalise_board(board) or "Other",
                                           POST_RESULTS_DEADLINE_DAYS["Other"])
    by_series = table.get(season) or table["Summer"]
    return by_series.get(service, 35)
