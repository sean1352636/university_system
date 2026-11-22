"""Shared Tk editor for structured UCAS offer conditions.

Used by the university's offer decision dialog and the sixth form's offer
editor, both of which store conditions in the platform's shape
(``platform/cross_system/offer_conditions``). ``read_only=True`` shows the
rows without the edit buttons — the sixth form's view of an offer the
platform's own university issued.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.platform.cross_system import offer_conditions as oc
from education_system.platform.cross_system import qualification_grades as qg

logger = logging.getLogger(__name__)

__all__ = ["ConditionsEditor"]


# ─────────────────────────────────────────────────────────────────
# Conditions editor
# ─────────────────────────────────────────────────────────────────

class ConditionsEditor(ttk.LabelFrame):
    """Edit an offer's structured conditions as a list of rows."""

    _COLS = (("kind", "Kind", 150), ("qualification_type", "Qualification", 150),
             ("subject", "Subject", 150), ("min_grade", "Grade", 80),
             ("min_points", "Points", 60), ("count", "Count", 50),
             ("text", "Text", 200))

    def __init__(self, master, *, conditions: list[dict] | None = None,
                 text_source=None, read_only: bool = False,
                 title: str = "Structured conditions (checked on results day)"
                 ) -> None:
        super().__init__(master, text=title, padding=6)
        self._rows: list[dict[str, Any]] = [dict(c) for c in conditions or []]
        self._text_source = text_source
        self.tree = ttk.Treeview(self, columns=[c[0] for c in self._COLS],
                                 show="headings", height=4)
        for key, label, width in self._COLS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(4, 0))
        self.tree.pack(fill="both", expand=True)
        if not read_only:
            for label, cmd in (("Add", self._add), ("Edit", self._edit),
                               ("Remove", self._remove),
                               ("Read from grade requirement", self._from_text)):
                ttk.Button(bar, text=label, command=cmd).pack(side="left",
                                                              padx=(0, 6))
        self.hint = ttk.Label(bar, text="", foreground="#666")
        self.hint.pack(side="left", padx=(8, 0))
        self._render()

    def get(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows]

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self._rows):
            self.tree.insert("", "end", iid=str(i), values=[
                oc.KIND_LABELS.get(r.get("kind"), r.get("kind")) if k == "kind"
                else ("" if r.get(k) is None else r.get(k))
                for k, _l, _w in self._COLS])
        self.hint.configure(text=(" · ".join(oc.describe(r) for r in self._rows)
                                  or "None — the grade requirement text is read instead."))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        row = _ConditionDialog(self, None).result
        if row:
            self._rows.append(row)
            self._render()

    def _edit(self) -> None:
        i = self._selected()
        if i is None:
            return
        row = _ConditionDialog(self, self._rows[i]).result
        if row:
            self._rows[i] = row
            self._render()

    def _remove(self) -> None:
        i = self._selected()
        if i is not None:
            del self._rows[i]
            self._render()

    def _from_text(self) -> None:
        text = self._text_source() if callable(self._text_source) else ""
        if not (text or "").strip():
            messagebox.showinfo("Conditions", "Type the grade requirement first.",
                                parent=self)
            return
        rows = oc.conditions_from_text(text)
        if rows and rows[0]["kind"] == "other_text" and len(rows) == 1:
            if not messagebox.askyesno(
                    "Conditions",
                    "That text could not be read in full, so it would be kept "
                    "as one condition checked by hand. Use it anyway?", parent=self):
                return
        self._rows = rows
        self._render()


class _ConditionDialog(tk.Toplevel):
    def __init__(self, master, row: dict | None) -> None:
        super().__init__(master)
        self.title("Offer condition")
        self.transient(master.winfo_toplevel())
        self.result: dict | None = None
        row = row or {"kind": "grade_profile"}
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        self.vars: dict[str, tk.StringVar] = {}
        labels = {v: k for k, v in oc.KIND_LABELS.items()}
        self._kind_by_label = labels
        fields = (("kind", "Kind", list(labels)),
                  ("qualification_type", "Qualification type",
                   ["", *qg.QUALIFICATION_TYPES]),
                  ("subject", "Subject(s)", None),
                  ("min_grade", "Minimum grade / profile", None),
                  ("min_points", "Minimum UCAS points", None),
                  ("count", "Count", None),
                  ("text", "Text (other)", None))
        for r, (key, label, values) in enumerate(fields):
            ttk.Label(frm, text=label + ":").grid(row=r, column=0, sticky="w", pady=3)
            init = row.get(key)
            if key == "kind":
                init = oc.KIND_LABELS.get(row.get("kind"), "")
            var = tk.StringVar(value="" if init is None else str(init))
            self.vars[key] = var
            if values is not None:
                w = ttk.Combobox(frm, textvariable=var, values=values,
                                 state="readonly", width=34)
            else:
                w = ttk.Entry(frm, textvariable=var, width=36)
            w.grid(row=r, column=1, sticky="ew", pady=3, padx=(8, 0))
        ttk.Label(frm, foreground="#666", wraplength=380, justify="left", text=(
            "Profile: ABB, D*DD, BB + DM, Distinction.  Subject: alternatives "
            "with '/' or 'or', Count = how many of them.  Points: Count = best N "
            "results.  GCSE: subjects with 'and', grade 9-1.")).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", pady=(6, 0))
        bar = ttk.Frame(frm)
        bar.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="OK", command=self._ok).pack(side="right", padx=(0, 6))
        self.grab_set()
        self.wait_window(self)

    def _ok(self) -> None:
        data = {k: v.get().strip() for k, v in self.vars.items()}
        data["kind"] = self._kind_by_label.get(data["kind"], data["kind"])
        try:
            self.result = oc.validate_condition(data)
        except ValueError as e:
            messagebox.showwarning("Offer condition", str(e), parent=self)
            return
        self.destroy()
