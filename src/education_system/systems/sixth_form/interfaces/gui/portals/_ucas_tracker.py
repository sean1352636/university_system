"""The read-only "move to university" tracker and offer-detail panel,
shared by the student portal's UCAS tab and the parent portal's child
view. Data comes from ``learner_view.ucas`` (``tracker`` and the per-choice
offer fields); nothing here reads a database.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

#: state -> (symbol, colour)
_STATE_STYLE: dict[str, tuple[str, str]] = {
    "done": ("✔", "#0d6b2a"),
    "current": ("▶", "#1a3f8c"),
    "pending": ("○", "#777777"),
    "held": ("⏸", "#7a5800"),
    "n/a": ("–", "#999999"),
}

_STATE_TEXT = {"done": "Done", "current": "Next", "pending": "Not yet",
               "held": "Held (results embargo)", "n/a": "Not applicable"}


def render_tracker(parent: tk.Misc, steps: list[dict[str, Any]] | None, *,
                   title: str = "Your move to university") -> None:
    """A labelled strip of steps, one row each: symbol, step, date, detail."""
    if not steps:
        return
    box = ttk.LabelFrame(parent, text=title, padding=6)
    box.pack(fill="x", pady=(0, 8))
    for i, s in enumerate(steps):
        symbol, colour = _STATE_STYLE.get(s["state"], ("?", "#333"))
        ttk.Label(box, text=symbol, foreground=colour, width=2).grid(
            row=i, column=0, sticky="w")
        ttk.Label(box, text=s["label"], foreground=colour,
                  font=("", 10, "bold") if s["state"] == "current" else ("", 10)).grid(
            row=i, column=1, sticky="w", padx=(2, 12))
        ttk.Label(box, text=_STATE_TEXT.get(s["state"], s["state"]),
                  foreground=colour).grid(row=i, column=2, sticky="w", padx=(0, 12))
        ttk.Label(box, text=s.get("date") or "", foreground="#555").grid(
            row=i, column=3, sticky="w", padx=(0, 12))
        ttk.Label(box, text=s.get("detail") or "", foreground="#555",
                  wraplength=520, justify="left").grid(row=i, column=4, sticky="w")


def offer_detail_text(choice: dict[str, Any]) -> str:
    """The terms of one choice as plain lines, for a detail panel."""
    lines = [f"{choice['university']} — {choice['course']}"
             + (f" ({choice['course_code']})" if choice.get("course_code") else ""),
             f"Decision: {choice['decision']}"
             + (f"  (on {choice['decision_date']})" if choice.get("decision_date") else "")]
    if choice.get("offer"):
        lines.append(f"Offer: {choice['offer']}")
    if choice.get("conditions"):
        lines.append("Conditions:")
        lines += [f"  • {c}" for c in choice["conditions"]]
    if choice.get("reply_by"):
        lines.append(f"Reply by: {choice['reply_by']}")
    if choice.get("final"):
        lines.append(f"Your reply: {choice['final']}")
    if choice.get("placed"):
        lines.append("Place confirmed — enrolled.")
    return "\n".join(lines)


__all__ = ["offer_detail_text", "render_tracker"]
