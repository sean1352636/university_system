"""Tkinter views for Primary School Settings."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable
from education_system.primarysch_system.modules.shared import settings as data
from education_system.shared import branding
from education_system.primarysch_system.modules.shared.settings import (
    SettingError,
    SettingSpec,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1100x800"
WIN_MINSIZE = (900, 700)


def open_settings_window(parent=None, *, auth=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Settings — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    SettingsForm(win, auth)


def _format_value(spec: SettingSpec, v: Any) -> str:
    if spec.type == "bool":
        return "Yes" if v else "No"
    if v == "" or v is None:
        return "(unset)"
    return str(v)


class SettingsForm:
    def __init__(self, root: tk.Misc, auth: Any) -> None:
        self.root = root
        self.auth = auth
        self._widgets: dict[str, tk.Variable] = {}
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar,
                   text="Local settings save instantly. "
                        "Global (auth-policy) settings need an admin "
                        "session.",
                   foreground="#444").pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self._refresh).pack(side="right")
        ttk.Button(bar, text="Export snapshot…",
                    command=self._export).pack(side="right",
                                                  padx=(0, 4))
        ttk.Button(bar, text="Reset all local",
                    command=self._reset_all).pack(side="right",
                                                     padx=(0, 4))

        # Category tabs
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=8)
        self._populate_tabs()

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.status_var,
                   anchor="w",
                   foreground="#357").pack(fill="x", padx=10,
                                              pady=(0, 8))

    def _populate_tabs(self) -> None:
        for cat in data.categories():
            specs = [s for s in data.list_settings()
                      if s.category == cat]
            if not specs:
                continue
            tab = ttk.Frame(self.nb)
            self.nb.add(tab, text=cat)
            self._build_tab(tab, specs)

    def _build_tab(self, tab: ttk.Frame,
                      specs: list[SettingSpec]) -> None:
        canvas = tk.Canvas(tab, borderwidth=0,
                              highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical",
                                  command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for spec in specs:
            self._build_row(inner, spec)

    def _build_row(self, parent: tk.Misc, spec: SettingSpec) -> None:
        is_global = spec.scope == "global"
        disabled = is_global and self.auth is None
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=6)

        # Header: label + scope tag.
        head = ttk.Frame(row)
        head.pack(fill="x")
        title = spec.label + ("   [global]" if is_global else "")
        ttk.Label(head, text=title,
                   font=("", 10, "bold")).pack(side="left")
        ttk.Label(head,
                   text=f"({spec.key})",
                   foreground="#888",
                   font=("", 9)).pack(side="left", padx=8)

        ttk.Label(row, text=spec.description,
                   foreground="#444",
                   wraplength=820,
                   justify="left").pack(anchor="w")

        # Value control
        bar = ttk.Frame(row)
        bar.pack(fill="x", pady=(4, 0))

        try:
            current = data.get(spec.key, auth=self.auth) \
                if not disabled else spec.default
        except SettingError:
            current = spec.default

        if spec.type == "bool":
            var = tk.BooleanVar(value=bool(current))
            cb = ttk.Checkbutton(
                bar, text="Enabled", variable=var,
                command=lambda: self._on_change(spec, var.get()))
            if disabled:
                cb.state(["disabled"])
            cb.pack(side="left")
            self._widgets[spec.key] = var
        elif spec.type == "choice":
            var = tk.StringVar(value=str(current))
            cb = ttk.Combobox(bar, values=list(spec.choices or ()),
                                 state=("disabled" if disabled
                                         else "readonly"),
                                 textvariable=var, width=26)
            cb.pack(side="left")
            cb.bind("<<ComboboxSelected>>",
                       lambda _e, s=spec, v=var:
                           self._on_change(s, v.get()))
            self._widgets[spec.key] = var
        else:
            # int / float / str
            var = tk.StringVar(value=str(current))
            ent = ttk.Entry(bar, textvariable=var, width=28,
                               state="disabled" if disabled
                                     else "normal")
            ent.pack(side="left")
            ttk.Button(bar, text="Save",
                        command=lambda s=spec, v=var:
                            self._on_change(s, v.get()),
                        state="disabled" if disabled
                              else "normal").pack(side="left", padx=4)
            self._widgets[spec.key] = var

        ttk.Label(bar,
                   text=f"  Default: {_format_value(spec, spec.default)}",
                   foreground="#666").pack(side="left", padx=8)

        ttk.Button(bar, text="Reset",
                    command=lambda s=spec: self._reset_one(s),
                    state="disabled" if disabled
                          else "normal").pack(side="right")

        if disabled:
            ttk.Label(row,
                       text="(sign in as admin to change "
                            "global settings)",
                       foreground="#a44").pack(anchor="w",
                                                  pady=(2, 0))

    def _on_change(self, spec: SettingSpec, raw: Any) -> None:
        try:
            v = data.set(spec.key, raw, auth=self.auth)
        except SettingError as e:
            messagebox.showerror(spec.label, str(e))
            self._refresh_one(spec)
            return
        except Exception as e:
            logger.exception("save setting failed")
            messagebox.showerror(spec.label, str(e))
            self._refresh_one(spec)
            return
        self.status_var.set(
            f"Saved {spec.label} = {_format_value(spec, v)}")
        # Re-sync the widget to the coerced value.
        self._refresh_one(spec, v)

    def _refresh_one(self, spec: SettingSpec,
                       new_value: Any = None) -> None:
        var = self._widgets.get(spec.key)
        if var is None:
            return
        try:
            v = (new_value if new_value is not None
                  else data.get(spec.key, auth=self.auth))
        except SettingError:
            v = spec.default
        if spec.type == "bool":
            var.set(bool(v))
        else:
            var.set("" if v in (None, "") else str(v))

    def _reset_one(self, spec: SettingSpec) -> None:
        try:
            v = data.reset_to_default(spec.key, auth=self.auth)
        except SettingError as e:
            messagebox.showerror(spec.label, str(e))
            return
        self.status_var.set(
            f"Reset {spec.label} → "
            f"{_format_value(spec, v)}")
        self._refresh_one(spec, v)

    def _reset_all(self) -> None:
        if not messagebox.askyesno(
                "Reset all local settings",
                "This wipes every locally-overridden value, "
                "restoring local defaults. Global (auth-policy) "
                "settings are not affected.\n\nContinue?"):
            return
        n = data.reset_all_local()
        for spec in data.list_settings(scope="local"):
            self._refresh_one(spec)
        self.status_var.set(f"Reset {n} local override(s).")

    def _refresh(self) -> None:
        for spec in data.list_settings():
            self._refresh_one(spec)
        self.status_var.set("Refreshed.")

    def _export(self) -> None:
        snapshot = data.export_all(auth=self.auth)
        path = filedialog.asksaveasfilename(
            initialfile="settings.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        import json
        from pathlib import Path
        try:
            Path(path).write_text(
                json.dumps(snapshot, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Export", str(e))
            return
        self.status_var.set(
            f"Exported {len(snapshot)} setting(s) → {path}")
        messagebox.showinfo(
            "Export",
            f"Wrote {len(snapshot)} setting(s) to:\n{path}")
