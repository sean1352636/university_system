"""Shared constants and small helpers for the Sixth Form Admissions GUI.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import subprocess
import sys
import tkinter as tk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
)



# Days an open applicant may sit in one stage before the row is flagged.
STALE_WARN_DAYS = 14
STALE_CRIT_DAYS = 30

logger = logging.getLogger("education_system.systems.sixth_form.interfaces.gui.admissions.admissions_views")

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def _today() -> str:
    return _dt.date.today().isoformat()


def _subject_options() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


def _parse_date(value: str | None) -> _dt.date | None:
    """Best-effort parse of an ISO date (optionally with a time suffix)."""
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _compute_age(dob: str | None) -> int | None:
    d = _parse_date(dob)
    if d is None:
        return None
    today = _dt.date.today()
    years = today.year - d.year - (
        (today.month, today.day) < (d.month, d.day))
    return years if 0 <= years < 130 else None


def _days_in_stage(applicant: Applicant) -> int | None:
    """Whole days since the applicant last changed (updated_at)."""
    d = _parse_date(applicant.updated_at)
    if d is None:
        return None
    return max(0, (_dt.date.today() - d).days)


def _prompt(parent: tk.Misc, title: str, text: str,
            initial: str = "") -> str | None:
    """Single-line text prompt; returns None on cancel."""
    return simpledialog.askstring(
        title, text, initialvalue=initial,
        parent=parent.winfo_toplevel())


def _open_path(path: str) -> None:
    """Open a file with the OS default handler."""
    try:
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", path], check=False)
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
        messagebox.showerror("Open file", f"Could not open file:\n{e}")


def _gcse_concerns(predicted: str | None, conditions: str | None) -> str | None:
    """Heuristic flag (delegates to the shared domain implementation)."""
    return reports.gcse_concern(predicted, conditions)
