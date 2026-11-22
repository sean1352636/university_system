"""Shared pieces for the AI Content Detector's views.

* :func:`scope` — who is signed in, whether they are an integrity officer
  and the modules they may see (cached on the window).
* :func:`modules`, :func:`students`, :func:`assignments` — picker data that
  carries real ids (module code, student number, assignment id); labels are
  only for showing. :class:`IdPicker` is a read-only combobox that gives the
  id back.
* :func:`level_colour` — colour by strength against the one review
  threshold (integrity setting ``ai_review_threshold``).
* :func:`show_reading` — a reading's notice, level, indicators table,
  informational extras and the text with its passages highlighted by kind.
* :func:`call` — run a backend call, showing refusals and errors plainly.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

logger = logging.getLogger(__name__)

TITLE = "AI Content Detector"
NOTICE = ("These are indicators, not evidence: no tool can tell reliably whether a person or a "
          "model wrote a text. Review it with the student; the student's account matters more "
          "than any reading.")
PASSAGE_COLOURS = {"artefact": "#f4b6b6", "stock": "#fde68a", "opener": "#bfdbfe"}
PASSAGE_NAMES = {"artefact": "leftover chat text", "stock": "stock phrasing",
                 "opener": "formulaic opening"}


def _connect():
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(row_factory=False)


def scope(gui, refresh=False) -> dict:
    """``{"who", "officer", "modules"}`` for the signed-in person; modules
    ``None`` means every module."""
    cached = gui.__dict__.get("_scope_cache")
    if cached is not None and not refresh:
        return cached
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    conn = _connect()
    try:
        user = gui.__dict__.get("user") or getattr(gui.detector, "current_user", None)
        who = integrity_access.from_user(conn, user) if user else None
        officer = bool(who and integrity_access.is_officer(conn, who))
        found = integrity_access.taught_modules(conn, who) if who and who.is_staff else []
    finally:
        conn.close()
    gui.__dict__["_scope_cache"] = cached = {"who": who, "officer": officer, "modules": found}
    return cached


def is_officer(gui) -> bool:
    return scope(gui)["officer"]


def officer_only(gui, *widgets) -> None:
    """Disable ``widgets`` for anyone who is not an integrity officer."""
    if not is_officer(gui):
        for widget in widgets:
            try:
                widget.configure(state="disabled")
            except tk.TclError:
                pass


def threshold() -> float:
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    conn = _connect()
    try:
        return integrity_access.number(conn, "ai_review_threshold")
    finally:
        conn.close()


def level_colour(gui, strength, limit=None) -> str:
    if strength is None:
        return gui.colors["text_secondary"]
    limit = threshold() if limit is None else limit
    if strength >= max(limit, 0.85):
        return gui.colors["danger"]
    if strength >= limit:
        return gui.colors["warning"]
    return gui.colors["success"]


# ── pickers with real ids ───────────────────────────────────────────────


def modules(gui) -> list[tuple]:
    """``[(module_code, "CODE - Name")]`` the person may read work on."""
    allowed = scope(gui)["modules"]
    conn = _connect()
    try:
        rows = conn.execute("SELECT module_code, module_name FROM modules WHERE module_code IS "
                            "NOT NULL ORDER BY module_code").fetchall()
    finally:
        conn.close()
    return [(code, f"{code} - {name or ''}".rstrip(" -")) for code, name in rows
            if allowed is None or code in allowed]


def students(module_code=None) -> list[tuple]:
    """``[(student_id, "Name (student_id)")]`` — on the module when given."""
    conn = _connect()
    try:
        if module_code and conn.execute("SELECT 1 FROM sqlite_master WHERE name = "
                                        "'student_modules'").fetchone():
            rows = conn.execute(
                "SELECT DISTINCT s.student_id, s.first_name, s.last_name FROM students s JOIN "
                "student_modules sm ON sm.student_id = s.student_id WHERE sm.module_code = ? "
                "ORDER BY s.last_name, s.first_name", (module_code,)).fetchall()
            if rows:
                return [(r[0], f"{(r[1] or '')} {(r[2] or '')} ({r[0]})".strip()) for r in rows]
        rows = conn.execute("SELECT student_id, first_name, last_name FROM students ORDER BY "
                            "last_name, first_name").fetchall()
    finally:
        conn.close()
    return [(r[0], f"{(r[1] or '')} {(r[2] or '')} ({r[0]})".strip()) for r in rows]


def assignments(module_code) -> list[tuple]:
    """``[(assignment id, "Title (due date)")]`` on the module."""
    if not module_code:
        return []
    conn = _connect()
    try:
        rows = conn.execute("SELECT id, title, due_date FROM assignments WHERE module_code = ? "
                            "ORDER BY due_date DESC", (module_code,)).fetchall()
    finally:
        conn.close()
    return [(r[0], f"{r[1] or f'Assignment {r[0]}'}"
             + (f" (due {str(r[2]).split()[0]})" if r[2] else "")) for r in rows]


class IdPicker(ttk.Combobox):
    """A read-only combobox over ``[(id, label)]``; :meth:`value` is the id."""

    def __init__(self, parent, choices=(), allow_blank=False, blank_label="(any)", **kw):
        kw.setdefault("state", "readonly")
        super().__init__(parent, **kw)
        self._blank = blank_label if allow_blank else None
        self.set_choices(choices)

    def set_choices(self, choices) -> None:
        self._pairs = list(choices)
        labels = [label for _id, label in self._pairs]
        if self._blank is not None:
            labels = [self._blank] + labels
        self["values"] = labels
        self.set("")

    def value(self):
        label = self.get()
        for item_id, item_label in self._pairs:
            if item_label == label:
                return item_id
        return None

    def select(self, item_id) -> None:
        for pair_id, label in self._pairs:
            if pair_id == item_id:
                self.set(label)
                return


# ── showing a reading ───────────────────────────────────────────────────


def _reading_of(result) -> dict:
    found = result.get("detailed_results") if isinstance(result, dict) else None
    if isinstance(found, str):
        import json
        try:
            found = json.loads(found)
        except ValueError:
            found = None
    return found if isinstance(found, dict) else (result or {})


def summary(result) -> str:
    """One line: level, strength, review and how much text it rests on."""
    reading = _reading_of(result)
    strength = result.get("strength", reading.get("strength"))
    words = result.get("words_checked") or reading.get("words_checked") or 0
    level = result.get("level") or reading.get("level") or "—"
    if strength is None:
        return f"{level} (based on {words} words)"
    review = "waits for review" if result.get("needs_review") else "below the review level"
    return f"{level} — strength {float(strength):.2f}, {review}, based on {words} words"


def show_reading(gui, parent, result, text=None) -> None:
    """The notice, summary, indicators, informational extras and (with
    ``text``) the text with passages highlighted, inside ``parent``."""
    reading = _reading_of(result)
    tk.Label(parent, text=NOTICE, fg=gui.colors["danger"], wraplength=640, justify="left",
             font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
    strength = result.get("strength", reading.get("strength"))
    head = ttk.Frame(parent)
    head.pack(fill="x", padx=8, pady=4)
    tk.Label(head, text="●", font=("Arial", 18), fg=level_colour(gui, strength)).pack(side="left")
    ttk.Label(head, text=summary(result), font=("Segoe UI", 11, "bold")).pack(side="left", padx=6)
    note = reading.get("note")
    if note:
        ttk.Label(parent, text=note, wraplength=640).pack(anchor="w", padx=8)

    indicators = result.get("indicators") or reading.get("indicators") or []
    extras = result.get("informational") or reading.get("detector", {}).get("informational", [])
    for title, rows in (("Indicators", indicators),
                        ("Informational (does not change the strength)", extras)):
        if not rows:
            continue
        box = ttk.LabelFrame(parent, text=title, padding=4)
        box.pack(fill="x", padx=8, pady=4)
        tree = ttk.Treeview(box, columns=("label", "shown", "meaning"), show="headings",
                            height=min(6, len(rows)))
        for col, label, width in (("label", "Indicator", 200), ("shown", "Value", 130),
                                  ("meaning", "What it means", 460)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        for row in rows:
            tree.insert("", "end", values=(row.get("label"), row.get("shown"),
                                           row.get("meaning")))
        tree.pack(fill="x")

    passages = result.get("passages") or reading.get("passages") or []
    if text and passages:
        box = ttk.LabelFrame(parent, text="Text, with the passages behind the indicators",
                             padding=4)
        box.pack(fill="both", expand=True, padx=8, pady=4)
        key = ttk.Frame(box)
        key.pack(side="bottom", fill="x")
        for kind, colour in PASSAGE_COLOURS.items():
            tk.Label(key, text=f" {PASSAGE_NAMES[kind]} ", bg=colour).pack(side="left", padx=3)
        widget = scrolledtext.ScrolledText(box, wrap="word", height=10)
        widget.pack(fill="both", expand=True)
        widget.insert("1.0", text)
        for kind, colour in PASSAGE_COLOURS.items():
            widget.tag_configure(kind, background=colour)
        for p in passages:
            if p.get("start") is not None and p.get("end") is not None:
                widget.tag_add(p.get("kind", "stock"), f"1.0+{int(p['start'])}c",
                               f"1.0+{int(p['end'])}c")
        widget.configure(state="disabled")


def call(gui, fn, *args, quiet=False, **kwargs):
    """``fn(*args, **kwargs)``; refusals and errors shown, ``None`` back."""
    try:
        return fn(*args, **kwargs)
    except (PermissionError, ValueError) as exc:
        if not quiet:
            messagebox.showerror(TITLE, str(exc), parent=gui.root)
    except Exception as exc:
        logger.exception("AI detector action failed: %s", getattr(fn, "__name__", fn))
        if not quiet:
            messagebox.showerror(TITLE, f"That did not work: {exc}", parent=gui.root)
    return None


def result_failed(gui, result) -> bool:
    """Show a backend ``{"success": False, "error": …}`` and say so."""
    if isinstance(result, dict) and result.get("success") is False:
        messagebox.showerror(TITLE, result.get("error") or result.get("message")
                             or "That did not work.", parent=gui.root)
        return True
    return False


def format_value(value, indent=0) -> str:
    """A backend dict/list as readable text (for report windows)."""
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if key in ("success",):
                continue
            label = str(key).replace("_", " ").capitalize()
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{label}:")
                lines.append(format_value(item, indent + 1))
            else:
                lines.append(f"{pad}{label}: {item if item not in (None, '') else '—'}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}(none)"
        return "\n".join(format_value(item, indent) if isinstance(item, (dict, list))
                         else f"{pad}- {item}" for item in value)
    return f"{pad}{value}"


def text_window(gui, title, body, width=820, height=560):
    """A read-only text window."""
    win = tk.Toplevel(gui.root)
    win.title(title)
    win.geometry(f"{min(width, win.winfo_screenwidth() - 60)}x"
                 f"{min(height, win.winfo_screenheight() - 100)}")
    win.transient(gui.root)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    widget = scrolledtext.ScrolledText(win, wrap="word")
    widget.pack(fill="both", expand=True, padx=8, pady=8)
    widget.insert("1.0", body if isinstance(body, str) else format_value(body))
    widget.configure(state="disabled")
    return win
