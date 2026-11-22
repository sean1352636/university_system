"""The dropdowns on the instructor forms (add and edit share them)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.curriculum.domain.course_management.instructor_service import (
    MAX_PREFERRED_DAYS,
    PREFERRED_TIME_WINDOWS,
    TEACHING_DAYS,
    department_specialisms,
    parse_preferred_days,
    time_label,
    time_value,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

_K = "gui.academics.course_management_gui.instructors.instructor_fields"


class DepartmentFields:
    """Department and specialisation; picking a department narrows the second list.

    An older record's free-typed value stays in its list, so opening and saving
    the form does not lose it.
    """

    def __init__(self, frame, department_var, specialization_var, *, row=0, editable=True):
        self.catalogue = department_specialisms()
        self.department_var = department_var
        self.specialization_var = specialization_var
        self._kept_specialism = specialization_var.get().strip()
        state = "readonly" if editable else "disabled"

        departments = sorted(self.catalogue, key=str.casefold)
        kept = department_var.get().strip()
        if kept and kept not in departments:
            departments.append(kept)

        ttk.Label(frame, text=_t(f"{_K}.department", default="Department:")).grid(
            row=row, column=0, sticky=tk.W)
        self.department = ttk.Combobox(frame, textvariable=department_var, values=departments,
                                       state=state, width=33)
        self.department.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(frame, text=_t(f"{_K}.specialisation", default="Specialisation:")).grid(
            row=row + 1, column=0, sticky=tk.W)
        self.specialization = ttk.Combobox(frame, textvariable=specialization_var,
                                           state=state, width=33)
        self.specialization.grid(row=row + 1, column=1, sticky=tk.W, padx=5, pady=2)

        self.department.bind("<<ComboboxSelected>>", self._department_changed)
        self._fill_specialisms()

    def _fill_specialisms(self):
        department = self.department_var.get().strip()
        if department in self.catalogue:
            subjects = list(self.catalogue[department])
        else:
            subjects = sorted({s for group in self.catalogue.values() for s in group},
                              key=str.casefold)
        if self._kept_specialism and self._kept_specialism not in subjects:
            subjects.append(self._kept_specialism)
        self.specialization["values"] = subjects

    def _department_changed(self, _event=None):
        self._kept_specialism = ""
        self._fill_specialisms()
        if self.specialization_var.get() not in self.specialization["values"]:
            self.specialization_var.set("")


class PreferredDaysField:
    """Up to four dropdowns; a day chosen in one disappears from the others."""

    def __init__(self, frame, *, row=0, column=1, value="", editable=True):
        self.vars = [tk.StringVar() for _ in range(MAX_PREFERRED_DAYS)]
        holder = ttk.Frame(frame)
        holder.grid(row=row, column=column, sticky=tk.W, padx=5, pady=2)
        self.combos = []
        for i, var in enumerate(self.vars):
            combo = ttk.Combobox(holder, textvariable=var, width=11,
                                 state="readonly" if editable else "disabled")
            combo.grid(row=0, column=i, padx=(0, 4))
            combo.bind("<<ComboboxSelected>>", self._refresh)
            self.combos.append(combo)
        for var, day in zip(self.vars, parse_preferred_days(value)):
            var.set(day)
        self._refresh()

    def _refresh(self, _event=None):
        chosen = [v.get() for v in self.vars]
        for i, combo in enumerate(self.combos):
            taken = {d for j, d in enumerate(chosen) if j != i and d}
            combo["values"] = [""] + [d for d in TEACHING_DAYS if d not in taken]

    def get(self) -> str:
        return ",".join(v.get() for v in self.vars if v.get())


class PreferredTimesField:
    """One dropdown of working windows, stored in the HH:MM-HH:MM form."""

    def __init__(self, frame, *, row=0, column=1, value="", editable=True):
        self.var = tk.StringVar(value=time_label(value))
        labels = [""] + [label for label, _stored in PREFERRED_TIME_WINDOWS]
        if self.var.get() not in labels:
            labels.append(self.var.get())
        ttk.Combobox(frame, textvariable=self.var, values=labels, width=20,
                     state="readonly" if editable else "disabled").grid(
            row=row, column=column, sticky=tk.W, padx=5, pady=2)

    def get(self) -> str:
        return time_value(self.var.get())
