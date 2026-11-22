"""The admissions workflow tabs added after Analytics.

Entry requirements, results day, open events, references, online
verification and Year 11 transition, one module each; then the cycle,
capacity, interview-slot, insight and record-keeping pages (``pages_*``).
A page that fails to build is logged and shown as an error page in its
place, so the window still opens and the gap explains itself.
"""

from __future__ import annotations

import importlib
import logging
from tkinter import ttk
from typing import Any

logger = logging.getLogger(__name__)

_PKG = "education_system.systems.sixth_form.interfaces.gui.admissions"

#: (module, class, sidebar label) in the order they are added.
WORKFLOW_TABS: tuple[tuple[str, str, str], ...] = (
    ("entry_requirements_views", "EntryRequirementsTab", "Entry Requirements"),
    ("results_day_views", "ResultsDayTab", "Results Day"),
    ("open_events_views", "OpenEventsTab", "Open Events"),
    ("references_views", "ReferencesTab", "References"),
    ("online_application_views", "OnlineVerificationTab",
     "Online Verification"),
    ("year11_transition_views", "Year11TransitionTab", "Year 11 Transition"),
)

#: The pages added after them (labels match admissions_window._SECTIONS).
NEW_PAGES: tuple[tuple[str, str, str], ...] = (
    ("pages_interviews", "SlotsPage", "Interview Slots"),
    ("pages_interviews", "RoomsPage", "Interview Rooms"),
    ("pages_cycles", "CyclesPage", "Cycles"),
    ("pages_capacity", "PlacesPage", "Places & Capacity"),
    ("pages_capacity", "CriteriaPage", "Oversubscription"),
    ("pages_capacity", "FeedersPage", "Feeder Schools"),
    ("pages_insights", "InsightsPage", "Insights"),
    ("pages_intake", "IntakeLogPage", "Intake Log"),
    ("pages_archive", "ArchivePage", "Archive"),
    ("pages_erasure", "ErasurePage", "Erasure Requests"),
    ("pages_retention", "RetentionPage", "Retention"),
    ("pages_dsl", "DslQueuePage", "DSL Queue"),
)


def _build(nb: Any, module: str, cls_name: str, label: str) -> Any:
    before = set(nb.tabs())
    try:
        cls = getattr(importlib.import_module(f"{_PKG}.{module}"), cls_name)
        return cls(nb)
    except Exception as e:  # noqa: BLE001 — one page must not stop the window
        logger.exception("Admissions page %s failed to build", label)
        from education_system.systems.sixth_form.interfaces.gui.admissions import (
            pages_common,
        )
        added = [t for t in nb.tabs() if t not in before]
        if added:
            # The page got as far as adding itself: show the error inside it.
            frame = nb.nametowidget(added[0])
            for child in frame.winfo_children():
                child.destroy()
            ttk.Label(frame, text=f"{label} could not be opened: "
                      f"{type(e).__name__}: {e}", foreground="#b03a2e",
                      wraplength=900, justify="left").pack(anchor="w",
                                                           pady=8)
            return None
        pages_common.error_page(nb, label, e)
        return None


def add_workflow_tabs(nb: ttk.Notebook) -> None:
    for module, cls_name, label in WORKFLOW_TABS + NEW_PAGES:
        _build(nb, module, cls_name, label)
