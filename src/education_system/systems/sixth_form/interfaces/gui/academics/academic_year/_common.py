"""Shared constants, colours and prefs persistence for the Sixth Form Academic Year GUI.

Split out of ``academic_year_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import logging
import json as _json
import os as _os



logger = logging.getLogger("education_system.systems.sixth_form.interfaces.gui.academics.academic_year.academic_year_views")

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

# Shared term palette — re-used by Gantt strip and (later) Calendar tab.
TERM_COLOURS: dict[str, str] = {
    "Autumn":   "#f6c453",
    "Autumn 1": "#f6c453",
    "Autumn 2": "#e3a13a",
    "Spring":   "#9ad17e",
    "Spring 1": "#9ad17e",
    "Spring 2": "#74b35e",
    "Summer":   "#7ec4f4",
    "Summer 1": "#7ec4f4",
    "Summer 2": "#5ba6dc",
}
DEFAULT_TERM_COLOUR: str = "#bdbdbd"


def _term_colour(name: str) -> str:
    return TERM_COLOURS.get(name, DEFAULT_TERM_COLOUR)


# ══ GUI polish utilities (items 39-44) ════════════════════════════
#
# Toast, Tooltip, prefs persistence, dark-mode theme, undo stack,
# help overlay. Kept inline so the module stays self-contained.


PREFS_PATH = _os.path.join(
    _os.path.expanduser("~"), ".config", "edu_system",
    "sixthform_academic_year.json")


def _load_prefs() -> dict:
    try:
        with open(PREFS_PATH, encoding="utf-8") as fh:
            d = _json.load(fh)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_prefs(prefs: dict) -> None:
    try:
        _os.makedirs(_os.path.dirname(PREFS_PATH), exist_ok=True)
        with open(PREFS_PATH, "w", encoding="utf-8") as fh:
            _json.dump(prefs, fh, indent=2)
    except OSError as e:
        logger.warning("Could not save prefs: %s", e)
