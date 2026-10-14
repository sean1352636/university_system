"""Dropdowns for the identifiers and dates the academic GUIs ask for.

Course Management and the Assignment system asked people to type opaque
identifiers — a student number, a module code, an instructor's row id —
and dates as free text in whatever format the label happened to
document. Typing them means knowing them, and a typo produced "not
found" rather than a correction; a mistyped date produced a silently
wrong record, since the formats varied between ``YYYY-MM-DD``,
``YYYY-MM-DD HH:MM`` and "date".

This module supplies the lists behind a dropdown for each of those, and
re-exports the platform ``DatePicker`` (three dropdowns, always emitting
``YYYY-MM-DD``) so a date cannot be entered in the wrong shape.

Choices load once when the widget is built. Screens that stay open
across data changes should call ``picker.reload()``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.date_picker import (  # noqa: F401
    DatePicker, birth_years, recent_years,
)

logger = logging.getLogger(__name__)

__all__ = [
    "IdPicker", "attach_picker", "attach_combo",
    "DateField", "attach_date", "attach_datetime", "DatePicker", "birth_years", "recent_years",
    "time_values", "academic_year_values", "semester_values", "term_values",
    "student_choices", "course_choices", "module_choices",
    "instructor_choices", "assignment_choices",
]


# --------------------------------------------------------------------------
# Value lists that need no database
# --------------------------------------------------------------------------

def time_values(step_minutes: int = 15, start_hour: int = 7,
                end_hour: int = 22) -> list[str]:
    """``HH:MM`` strings across the teaching day."""
    out = []
    minute = start_hour * 60
    while minute <= end_hour * 60:
        out.append(f"{minute // 60:02d}:{minute % 60:02d}")
        minute += step_minutes
    return out


def academic_year_values(ahead: int = 2, back: int = 5) -> list[str]:
    """``2025-26`` style labels, current year first."""
    this = _dt.date.today().year
    # A UK academic year starts in September, so before then the "current"
    # academic year is the one that began last calendar year.
    base = this if _dt.date.today().month >= 9 else this - 1
    return [f"{y}-{str(y + 1)[-2:]}"
            for y in range(base + ahead, base - back, -1)]


def semester_values() -> list[str]:
    return ["1", "2", "3"]


def term_values(ahead: int = 2, back: int = 2) -> list[str]:
    """``Fall 2026`` style term labels across nearby years."""
    this = _dt.date.today().year
    return [f"{term} {y}"
            for y in range(this - back, this + ahead + 1)
            for term in ("Spring", "Summer", "Fall", "Winter")]


# --------------------------------------------------------------------------
# Database-backed choice lists
# --------------------------------------------------------------------------

def _fetch(sql, params=()):
    try:
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        conn = get_connection()
    except Exception:
        logger.debug("DB unavailable for picker", exc_info=True)
        return []
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        logger.debug("Picker query failed: %s", sql, exc_info=True)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def student_choices():
    rows = _fetch(
        "SELECT student_id, COALESCE(first_name,''), COALESCE(last_name,''), "
        "       COALESCE(course, COALESCE(program,'')) "
        "FROM students WHERE COALESCE(is_active, 1) = 1 "
        "ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE")
    out = []
    for sid, first, last, course in rows:
        name = " ".join(p for p in (first, last) if p) or "(no name)"
        label = f"{sid} — {name}"
        if course:
            label += f" ({course})"
        out.append((str(sid), label))
    return out


def course_choices():
    rows = _fetch(
        "SELECT id, COALESCE(NULLIF(course_code,''), COALESCE(code,'')), "
        "       COALESCE(NULLIF(course_name,''), COALESCE(name,'')) "
        "FROM courses ORDER BY 2 COLLATE NOCASE")
    out = []
    for cid, code, name in rows:
        label = code or str(cid)
        if name:
            label += f" — {name}"
        out.append((str(cid), label))
    return out


def module_choices(active_only: bool = True):
    sql = ("SELECT module_code, COALESCE(module_name,'') FROM modules "
           "WHERE TRIM(COALESCE(module_code,'')) != ''")
    if active_only:
        sql += " AND COALESCE(is_active, 1) = 1"
    sql += " ORDER BY module_code COLLATE NOCASE"
    return [(str(code), f"{code} — {name}" if name else str(code))
            for code, name in _fetch(sql)]


def instructor_choices():
    rows = _fetch(
        "SELECT id, COALESCE(first_name,''), COALESCE(last_name,''), "
        "       COALESCE(department,'') FROM instructors "
        "WHERE COALESCE(is_active, 1) = 1 "
        "ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE")
    out = []
    for iid, first, last, dept in rows:
        name = " ".join(p for p in (first, last) if p) or f"Instructor {iid}"
        label = f"{iid} — {name}"
        if dept:
            label += f" ({dept})"
        out.append((str(iid), label))
    return out


def assignment_choices(module_code: str | None = None):
    sql = ("SELECT id, COALESCE(title,''), COALESCE(module_code,''), "
           "       COALESCE(due_date,'') FROM assignments")
    params = ()
    if module_code:
        sql += " WHERE module_code = ?"
        params = (module_code,)
    sql += " ORDER BY due_date DESC, id DESC"
    out = []
    for aid, title, mod, due in _fetch(sql, params):
        label = f"{aid} — {title or '(untitled)'}"
        if mod:
            label += f" [{mod}]"
        if due:
            label += f" due {str(due)[:10]}"
        out.append((str(aid), label))
    return out


# --------------------------------------------------------------------------
# The widget
# --------------------------------------------------------------------------

class IdPicker:
    """An editable, type-to-filter combobox over ``(value, label)`` pairs.

    ``get()`` returns the selected underlying ID. Typing a raw ID that
    isn't in the list still returns it verbatim, so someone who knows the
    code — or a row the query missed — is never locked out.
    """

    def __init__(self, parent, choices, width=42, empty_label=None,
                 on_select=None, loader=None, id_var=None):
        """*id_var* is an existing ``StringVar`` that previously backed a
        typed-in Entry. The picker keeps it holding the resolved ID, so
        code already calling ``var.get()`` keeps working untouched — that
        is what makes converting an existing field a local change rather
        than a rewrite of everything downstream of it.
        """
        self._loader = loader
        self._on_select = on_select
        self._empty_label = empty_label
        self._id_var = id_var
        self.var = tk.StringVar()
        self.combo = ttk.Combobox(parent, textvariable=self.var, width=width)
        self.combo.bind("<KeyRelease>", self._filter)
        self.combo.bind("<<ComboboxSelected>>", self._selected)
        self._apply(list(choices))
        # Mirror in both directions: seed from whatever the var already
        # held (dialogs pre-fill it), then track every edit.
        if id_var is not None:
            if id_var.get():
                self.set(id_var.get())
            self.var.trace_add("write", self._sync_id_var)
            self._sync_id_var()

    def _sync_id_var(self, *_args):
        if self._id_var is not None:
            self._id_var.set(self.get())

    def _apply(self, choices):
        self.choices = choices
        self._by_label = {label: value for value, label in choices}
        self._by_value = {value: label for value, label in choices}
        self.combo["values"] = [label for _v, label in choices]
        if not choices and self._empty_label:
            self.var.set(self._empty_label)
            self.combo.configure(state="disabled")
        else:
            self.combo.configure(state="normal")

    def reload(self, choices=None):
        """Refresh the list — for screens open while data changes."""
        if choices is None and callable(self._loader):
            choices = self._loader()
        if choices is not None:
            current = self.get()
            self._apply(list(choices))
            if current:
                self.set(current)

    # -- Tk passthroughs so callers lay it out like any widget --
    def grid(self, **kw):
        self.combo.grid(**kw)
        return self

    def pack(self, **kw):
        self.combo.pack(**kw)
        return self

    def _filter(self, event):
        # Navigation keys must not re-filter, or opening the dropdown with
        # the arrow keys immediately narrows it to whatever was typed.
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab",
                            "Left", "Right"):
            return
        typed = self.var.get().strip().lower()
        allv = [label for _v, label in self.choices]
        self.combo["values"] = (
            [l for l in allv if typed in l.lower()] or allv) if typed else allv

    def _selected(self, _event=None):
        if callable(self._on_select):
            try:
                self._on_select(self.get())
            except Exception:
                logger.exception("Picker on_select callback failed")

    def get(self):
        text = self.var.get().strip()
        if text == (self._empty_label or object()):
            return ""
        if text in self._by_label:
            return self._by_label[text]
        if text in self._by_value:
            return text
        return text.split(" — ")[0].strip() if " — " in text else text

    def set(self, value):
        if value is None:
            return
        self.var.set(self._by_value.get(str(value), str(value)))

    # -- Entry-compatible methods --------------------------------------
    # Some call sites populate the old widget with delete()/insert()
    # (e.g. filling a form from a selected table row). Supporting them
    # keeps the picker a drop-in replacement rather than forcing every
    # caller to change at the same time.
    def delete(self, first=0, last=None):
        self.var.set("")

    def insert(self, index, value):
        self.set(value)

    def configure(self, **kw):
        return self.combo.configure(**kw)

    config = configure

    def bind(self, *a, **kw):
        return self.combo.bind(*a, **kw)

    def focus_set(self):
        return self.combo.focus_set()


_LOADERS = {
    "student": (student_choices, "No students found"),
    "course": (course_choices, "No courses found"),
    "module": (module_choices, "No modules found"),
    "instructor": (instructor_choices, "No instructors found"),
    "assignment": (assignment_choices, "No assignments found"),
}


def attach_picker(parent, kind, **kw):
    """Factory: ``kind`` is student / course / module / instructor / assignment."""
    try:
        loader, empty = _LOADERS[kind]
    except KeyError:
        raise ValueError(f"Unknown picker kind: {kind!r}") from None
    return IdPicker(parent, loader(), empty_label=empty, loader=loader, **kw)


def attach_combo(parent, values, textvariable=None, width=18, readonly=True):
    """A plain readonly combobox for a fixed value list (times, years...).

    Returned as a ttk.Combobox so callers lay it out exactly where the
    Entry it replaces used to sit.
    """
    combo = ttk.Combobox(parent, values=list(values), width=width,
                         state="readonly" if readonly else "normal")
    if textvariable is not None:
        combo.configure(textvariable=textvariable)
    return combo


class DateField(ttk.Frame):
    """``DatePicker`` that mirrors into an existing ``StringVar``.

    Same trick as ``IdPicker(id_var=...)``: the surrounding code keeps
    reading ``var.get()`` and keeps getting a string, but the string can
    no longer be a malformed date. With *with_time* the value is
    ``YYYY-MM-DD HH:MM``, for the fields that store a due datetime.
    """

    def __init__(self, parent, id_var=None, value=None, with_time=False,
                 default_time="23:59", years=None):
        super().__init__(parent)
        self._id_var = id_var
        self._with_time = with_time

        seed = (value if value is not None
                else (id_var.get() if id_var is not None else "")) or ""
        date_part, _, time_part = str(seed).partition(" ")

        self.picker = DatePicker(self, years=years)
        self.picker.pack(side="left")
        if date_part:
            self.picker.set(date_part)

        self.time_var = tk.StringVar(value=(time_part or default_time)
                                     if with_time else "")
        if with_time:
            self.time_combo = ttk.Combobox(
                self, textvariable=self.time_var, width=7, state="readonly",
                values=time_values(step_minutes=15, start_hour=0, end_hour=23))
            self.time_combo.pack(side="left", padx=(6, 0))
            self.time_combo.bind("<<ComboboxSelected>>", self._sync)

        for combo in (self.picker.cb_day, self.picker.cb_month, self.picker.cb_year):
            combo.bind("<<ComboboxSelected>>", self._sync, add="+")
        # Today / Clear are buttons, not combos, so poll the value too.
        self.bind("<Enter>", self._sync, add="+")
        self._sync()

    def _sync(self, _event=None):
        if self._id_var is not None:
            self._id_var.set(self.get())

    def get(self):
        date = self.picker.get()
        if not date:
            return ""
        if self._with_time and self.time_var.get():
            return f"{date} {self.time_var.get()}"
        return date

    def set(self, value):
        date_part, _, time_part = str(value or "").partition(" ")
        self.picker.set(date_part)
        if self._with_time and time_part:
            self.time_var.set(time_part)
        self._sync()


def attach_date(parent, id_var=None, **kw):
    """Date-only field (``YYYY-MM-DD``)."""
    return DateField(parent, id_var=id_var, **kw)


def attach_datetime(parent, id_var=None, **kw):
    """Date + time field (``YYYY-MM-DD HH:MM``)."""
    return DateField(parent, id_var=id_var, with_time=True, **kw)
