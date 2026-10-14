"""A modal form that asks for a handful of typed fields and returns a dict.

The governance, PGR and assessment-board windows each need a dozen small
"create/advance/approve" dialogs. Building a Toplevel per dialog by hand
repeats the same grid/validate/return dance; this helper takes a list of
field specs and returns the typed values (or ``None`` on cancel)::

    values = ask_form(parent, "Create committee", [
        Field("name", "Committee name"),
        Field("committee_type", "Type", default="validation"),
        Field("quorum", "Quorum", kind="int", default="3"),
    ])

Field kinds: ``str`` (default), ``int``, ``float``, ``text`` (multi-line),
``list`` (comma-separated -> ``list[str]``), ``json`` (object -> ``dict``),
``bool`` (checkbox) and ``choice`` (``options=[...]`` combobox). An ``int``,
``float``, ``json`` or ``list`` left blank returns ``None``/``[]`` when the
field is ``optional``; otherwise the dialog refuses to close.
"""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox


@dataclass
class Field:
    key: str
    label: str
    kind: str = "str"
    default: str = ""
    optional: bool = False
    options: list[str] = field(default_factory=list)


def _coerce(spec: Field, raw: Any) -> Any:
    if spec.kind == "bool":
        return bool(raw)
    text = str(raw).strip()
    if not text:
        if spec.optional:
            return [] if spec.kind == "list" else None
        raise ValueError(f"{spec.label} is required")
    if spec.kind == "int":
        return int(text)
    if spec.kind == "float":
        return float(text)
    if spec.kind == "list":
        return [item.strip() for item in text.split(",") if item.strip()]
    if spec.kind == "json":
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError(f"{spec.label} must be a JSON object")
        return value
    return text


class _FormDialog:
    def __init__(self, parent, title: str, fields: list[Field]) -> None:
        self.result: dict[str, Any] | None = None
        self._fields = fields
        self._widgets: dict[str, Any] = {}
        self.top = make_toplevel(parent)
        self.top.title(title)
        self.top.resizable(False, False)
        body = ttk.Frame(self.top, padding=12)
        body.pack(fill="both", expand=True)
        for row, spec in enumerate(fields):
            ttk.Label(body, text=spec.label + ":").grid(row=row, column=0, sticky="ne",
                                                        padx=4, pady=3)
            self._widgets[spec.key] = self._make_widget(body, spec, row)
        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(buttons, text="OK", command=self._ok).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.top.destroy).pack(side="left")
        self.top.bind("<Escape>", lambda _e: self.top.destroy())
        self.top.grab_set()
        first = next(iter(self._widgets.values()), None)
        if first is not None:
            first.focus_set()

    def _make_widget(self, body, spec: Field, row: int):
        if spec.kind == "text":
            widget = tk.Text(body, width=48, height=4, wrap="word")
            widget.insert("1.0", spec.default)
        elif spec.kind == "bool":
            var = tk.BooleanVar(value=spec.default.lower() in ("1", "true", "y", "yes"))
            widget = ttk.Checkbutton(body, variable=var)
            widget.var = var
        elif spec.kind == "choice":
            var = tk.StringVar(value=spec.default or (spec.options[0] if spec.options else ""))
            widget = ttk.Combobox(body, textvariable=var, values=spec.options,
                                  state="readonly", width=40)
            widget.var = var
        else:
            var = tk.StringVar(value=spec.default)
            widget = ttk.Entry(body, textvariable=var, width=44)
            widget.var = var
        widget.grid(row=row, column=1, sticky="w", padx=4, pady=3)
        return widget

    def _raw(self, spec: Field) -> Any:
        widget = self._widgets[spec.key]
        if spec.kind == "text":
            return widget.get("1.0", "end")
        return widget.var.get()

    def _ok(self) -> None:
        values: dict[str, Any] = {}
        try:
            for spec in self._fields:
                values[spec.key] = _coerce(spec, self._raw(spec))
        except (ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Invalid input", str(exc), parent=self.top)
            return
        self.result = values
        self.top.destroy()


def ask_form(parent, title: str, fields: list[Field]) -> dict[str, Any] | None:
    """Show the form modally; return the typed values or ``None`` if cancelled."""
    dialog = _FormDialog(parent, title, fields)
    parent.wait_window(dialog.top)
    return dialog.result


__all__ = ["Field", "ask_form"]
