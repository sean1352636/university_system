"""Dropdowns for the Academic Integrity window: the scoped lists from
``application/integrity/choices`` as form choices (``Field(kind="pick")``)
and as inline toolbar dropdowns (:class:`Picker`)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.integrity import choices
from education_system.systems.university.infrastructure.ui.record_screens import Field, call


def pairs(parent, fn, who, *args, **kwargs) -> list[tuple]:
    """``fn(conn, who, …)`` as ``[(value, label)]``; empty when refused."""
    return call(parent, fn, who, *args, quiet=True, **kwargs) or []


# ── form fields ─────────────────────────────────────────────────────────


def module_field(parent, who, key="module_code", label="Module", required=False, hint=""):
    return Field(key, label, "pick", lambda: pairs(parent, choices.modules, who),
                 required=required, filter=True, hint=hint)


def student_field(parent, who, key="student_id", label="Student", required=False,
                  module_key=None):
    """Students ``who`` may pick; narrowed to the module in ``module_key``
    when that field is set."""
    if module_key:
        return Field(key, label, "pick", required=required, filter=True, depends_on=module_key,
                     choices_for=lambda module: pairs(parent, choices.students, who,
                                                      module or None))
    return Field(key, label, "pick", lambda: pairs(parent, choices.students, who),
                 required=required, filter=True)


def assignment_field(parent, who, key="assignment_id", label="Assignment", required=False,
                     module_key="module_code"):
    """Assignments on the module chosen in ``module_key`` (every allowed
    module while it is blank)."""
    return Field(key, label, "pick", required=required, filter=True, depends_on=module_key,
                 choices_for=lambda module: pairs(parent, choices.assignments, who,
                                                  module or None))


def submission_field(parent, who, key="submission_id", label="Submission", required=True):
    return Field(key, label, "pick", lambda: pairs(parent, choices.submissions, who),
                 required=required, filter=True)


# ── inline toolbar dropdowns ────────────────────────────────────────────


class Picker(ttk.Combobox):
    """An inline dropdown showing labels and giving back values. Empty
    (the first entry) means "any". ``source`` is a no-argument callable
    returning ``[(value, label)]``; ``filter`` makes it type-to-narrow."""

    def __init__(self, master, source, *, width=24, filter=False, blank="", **kw):
        self._source = source
        self._blank = blank
        self._pairs: list[tuple] = []
        self.var = tk.StringVar()
        super().__init__(master, textvariable=self.var, width=width,
                         state="normal" if filter else "readonly", **kw)
        if filter:
            self.bind("<KeyRelease>", self._narrow)
        self.reload()

    def reload(self, source=None):
        if source is not None:
            self._source = source
        self._pairs = list(self._source() or [])
        self.configure(values=[self._blank] + [label for _v, label in self._pairs])
        if self.var.get() and self.var.get() not in self["values"]:
            self.var.set("")

    def _narrow(self, _event=None):
        typed = self.var.get().strip().lower()
        labels = [label for _v, label in self._pairs]
        self.configure(values=[label for label in labels if typed in label.lower()]
                       if typed else [self._blank] + labels)

    def value(self):
        text = self.var.get().strip()
        if not text or text == self._blank:
            return ""
        for value, label in self._pairs:
            if text == label or text.lower() == str(value).lower():
                return value
        return text

    def set_value(self, value):
        label = next((lbl for v, lbl in self._pairs if str(v) == str(value)), "")
        self.var.set(label)
