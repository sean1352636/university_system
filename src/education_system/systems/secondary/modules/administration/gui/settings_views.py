"""Settings screen.

Kept from the old Settings window: a tab per category; each setting shows
its label, key and description, a control (tick box, drop-down, or entry
with Save), its default and a Reset button; the top bar has Refresh,
Export snapshot… and Reset all local, and a status line says what was
saved. New: the School tab (name, URN, LA and DfE numbers, address,
contact details, headteacher, logo with Browse…) with Save all, the E-mail
and Academic year conventions tabs, Other areas (session times, library,
cover, homework, lessons per week, timetable cycle - changed through their
own modules), Sign-in policy (editable again: shared settings apply to all
seven systems, with a warning), term dates (read from Academic
Year & Calendar), History and Import snapshot…. Rules are in
:mod:`modules.administration.domain.settings`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.administration.domain import settings as ST
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = W.ERRORS


def _scrolling(tab: ttk.Frame) -> ttk.Frame:
    canvas = tk.Canvas(tab, borderwidth=0, highlightthickness=0)
    bar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return inner


class SettingsPage:
    OTHER, POLICY, HISTORY = "Other areas", "Sign-in policy", "History"

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = ST.is_editor(principal)
        self.TABS = (*ST.categories(), self.OTHER, self.POLICY, self.HISTORY)
        activity_log.record("settings.open")
        ttk.Label(parent, text="Settings", font=("", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(2, 4))
        ttk.Label(bar, text="School settings save straight away. Most of the sign-in policy is "
                            "shared by every system.",
                  foreground="#444").pack(side="left")
        for text, cmd in (("Refresh", self.refresh_all), ("Export snapshot…", self.export),
                          ("Import snapshot…", self.import_), ("Reset all local",
                                                               self.reset_all)):
            b = ttk.Button(bar, text=text, command=cmd)
            if not self.editor and text != "Refresh":
                b.state(["disabled"])
            b.pack(side="right", padx=(4, 0))
        self.warn_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.warn_var, foreground="#a44", wraplength=900,
                  justify="left").pack(anchor="w")
        if not self.editor:
            ttk.Label(parent, text="Your account can't see or change the school settings.",
                      foreground="#a44").pack(anchor="w", pady=8)
            return
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=6) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self.status_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.status_var, foreground="#357").pack(
            fill="x", pady=(4, 0))
        self.vars: dict[str, tk.Variable] = {}
        self.marks: dict[str, tk.StringVar] = {}
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else self.TABS[0]
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()
        self._warnings()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _warnings(self) -> None:
        try:
            w = ST.warnings()
        except Exception:  # noqa: BLE001
            w = []
        self.warn_var.set("\n".join(f"! {x}" for x in w))

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            tab = self.tabs[name]
            if name == self.OTHER:
                self._build_other(tab)
            elif name == self.POLICY:
                self._build_policy(tab)
            elif name == self.HISTORY:
                self._build_history(tab)
            else:
                self._build_category(tab, name)
        if name == self.HISTORY:
            self.refresh_history()
        elif name == self.OTHER:
            self.refresh_other()

    # ── a category (the old tab layout) ──────────────────────────────

    def _build_category(self, tab: ttk.Frame, category: str) -> None:
        if category == ST.SCHOOL:
            top = ttk.Frame(tab)
            top.pack(fill="x", pady=(0, 4))
            ttk.Button(top, text="Save all", command=lambda: self.save_all(category)).pack(
                side="left")
            ttk.Label(top, text="  Change several fields, then Save all (checked together, "
                                "e.g. the DfE number starts with the LA number).",
                      foreground="#555").pack(side="left")
        if category == ST.CONVENTIONS:
            self._term_dates(tab)
        inner = _scrolling(tab)
        try:
            rows = ST.list_settings(actor=self.principal, category=category)
        except _ERRORS as e:
            self._err("Settings", e)
            return
        for s in rows:
            self._row(inner, s)

    def _term_dates(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Term dates (set in Academic Year & Calendar)",
                             padding=6)
        box.pack(fill="x", pady=(0, 6))
        td = ST.term_dates()
        if td["year"]:
            y = td["year"]
            text = f"{y['name']}: {y['start']} to {y['end']} ({y['status']})\n" + "\n".join(
                f"   {t['name']}: {t['start']} to {t['end']}" for t in td["terms"])
        else:
            text = "No current school year is set up yet."
        ttk.Label(box, text=text + "\n\nOpen System → Academic Year & Calendar to change "
                                   "them.", justify="left").pack(anchor="w")

    def _row(self, parent: tk.Misc, s: ST.Setting) -> None:
        spec = s.spec
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=6)
        head = ttk.Frame(row)
        head.pack(fill="x")
        ttk.Label(head, text=spec.label, font=("", 10, "bold")).pack(side="left")
        ttk.Label(head, text=f"({spec.key})", foreground="#888", font=("", 9)).pack(
            side="left", padx=8)
        mark = tk.StringVar(value="" if s.is_default else
                            f"changed by {s.updated_by} {s.updated_at or ''}")
        ttk.Label(head, textvariable=mark, foreground="#777", font=("", 9)).pack(side="left")
        self.marks[spec.key] = mark
        if spec.description:
            ttk.Label(row, text=spec.description, foreground="#444", wraplength=820,
                      justify="left").pack(anchor="w")
        bar = ttk.Frame(row)
        bar.pack(fill="x", pady=(4, 0))
        if spec.type == "bool":
            var: tk.Variable = tk.BooleanVar(value=bool(s.value))
            ttk.Checkbutton(bar, text="Enabled", variable=var,
                            command=lambda: self.save(spec, var.get())).pack(side="left")
        elif spec.type == "choice":
            var = tk.StringVar(value=str(s.value))
            cb = ttk.Combobox(bar, values=list(spec.choices or ()), state="readonly",
                              textvariable=var, width=26)
            cb.pack(side="left")
            cb.bind("<<ComboboxSelected>>", lambda _e: self.save(spec, var.get()))
        else:
            var = tk.StringVar(value="" if s.value in (None, "") else str(s.value))
            ent = ttk.Entry(bar, textvariable=var, width=48 if spec.max_len > 60 else 28)
            ent.pack(side="left")
            ent.bind("<Return>", lambda _e: self.save(spec, var.get()))
            ttk.Button(bar, text="Save", command=lambda: self.save(spec, var.get())).pack(
                side="left", padx=4)
            if spec.type == "path":
                ttk.Button(bar, text="Browse…", command=lambda: self.browse(spec, var)).pack(
                    side="left")
        self.vars[spec.key] = var
        ttk.Label(bar, text=f"  Default: {ST.format_value(spec, spec.default)}",
                  foreground="#666").pack(side="left", padx=8)
        ttk.Button(bar, text="Reset", command=lambda: self.reset_one(spec)).pack(side="right")

    def _set_var(self, spec: ST.SettingSpec, value: Any) -> None:
        var = self.vars.get(spec.key)
        if var is None:
            return
        if spec.type == "bool":
            var.set(bool(value))
        else:
            var.set("" if value in (None, "") else str(value))

    def _refresh_one(self, key: str) -> None:
        try:
            s = ST.get(key, actor=self.principal)
        except _ERRORS:
            return
        self._set_var(s.spec, s.value)
        if key in self.marks:
            self.marks[key].set("" if s.is_default else
                                f"changed by {s.updated_by} {s.updated_at or ''}")

    def save(self, spec: ST.SettingSpec, raw: Any) -> None:
        try:
            v = ST.set_setting(spec.key, raw, actor=self.principal)
        except _ERRORS as e:
            self._err(spec.label, e)
            self._refresh_one(spec.key)
            return
        self.status_var.set(f"Saved {spec.label} = {ST.format_value(spec, v)}")
        self._refresh_one(spec.key)
        self._warnings()

    def save_all(self, category: str) -> None:
        changes = {}
        for spec in ST.list_specs(category=category):
            var = self.vars.get(spec.key)
            if var is not None:
                changes[spec.key] = var.get()
        try:
            changed = ST.set_many(changes, actor=self.principal)
        except _ERRORS as e:
            self._err("Save all", e)
            return
        for k in changes:
            self._refresh_one(k)
        self.status_var.set(f"Saved {len(changed)} change(s)." if changed else "No changes.")
        self._warnings()

    def browse(self, spec: ST.SettingSpec, var: tk.Variable) -> None:
        if spec.key == "logo_path":
            path = filedialog.askopenfilename(
                parent=self._top(), title="Logo", filetypes=[
                    ("Images", "*.png *.gif *.jpg *.jpeg"), ("All files", "*.*")])
        else:
            path = filedialog.askdirectory(parent=self._top(), title=spec.label)
        if path:
            var.set(path)
            self.save(spec, path)

    def reset_one(self, spec: ST.SettingSpec) -> None:
        try:
            v = ST.reset(spec.key, actor=self.principal)
        except _ERRORS as e:
            self._err(spec.label, e)
            return
        self.status_var.set(f"Reset {spec.label} → {ST.format_value(spec, v)}")
        self._refresh_one(spec.key)
        self._warnings()

    def reset_all(self) -> None:
        if not messagebox.askyesno(
                "Reset all local settings",
                "This wipes every changed school setting, restoring the defaults (including "
                "the school's name and details). Other areas' settings and the sign-in policy "
                "are not affected.\n\nContinue?", parent=self._top()):
            return
        try:
            n = ST.reset_all(actor=self.principal)
        except _ERRORS as e:
            self._err("Reset all", e)
            return
        self.refresh_all()
        self.status_var.set(f"Reset {n} setting(s).")

    def refresh_all(self) -> None:
        if not self.editor:
            return
        for spec in ST.REGISTRY:
            if spec.key in self.vars:
                self._refresh_one(spec.key)
        if self.OTHER in self._built:
            self.refresh_other()
        if self.POLICY in self._built:
            self.refresh_policy()
        if self.HISTORY in self._built:
            self.refresh_history()
        self._warnings()
        self.status_var.set("Refreshed.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), initialfile="settings.json",
                                            defaultextension=".json",
                                            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            n = ST.export_json(path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export", e)
            return
        self.status_var.set(f"Exported {n} setting(s) → {path}")
        messagebox.showinfo("Export", f"Wrote {n} setting(s) to:\n{path}", parent=self._top())

    def import_(self) -> None:
        path = filedialog.askopenfilename(parent=self._top(), title="Import settings",
                                          filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path or not messagebox.askyesno(
                "Import", "Replace the school settings with the values in this file?",
                parent=self._top()):
            return
        try:
            changed = ST.import_json(path, actor=self.principal)
        except _ERRORS as e:
            self._err("Import", e)
            return
        self.refresh_all()
        self.status_var.set(f"Imported: {len(changed)} change(s).")

    # ── Other areas ──────────────────────────────────────────────────

    def _build_other(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="These settings belong to other screens; they are changed here "
                            "through those screens' own rules (and audit).",
                  foreground="#555").pack(anchor="w", pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Change…", command=self.change_other).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh_other).pack(side="left", padx=4)
        self.other_tree = W.tree(tab, [("area", "Area", 120), ("label", "Setting", 300),
                                       ("value", "Value", 120), ("hint", "Allowed", 140)],
                                 height=16, stretch={"label"})
        self.other_tree.bind("<Double-1>", lambda _e: self.change_other())

    def refresh_other(self) -> None:
        vals = ST.linked_values()
        t = self.other_tree
        t.delete(*t.get_children())
        for x in ST.LINKED:
            v = vals.get(x.key)
            t.insert("", "end", iid=x.key, values=(x.area, x.label,
                                                   "(unavailable)" if v is None else v, x.hint))

    def change_other(self) -> None:
        sel = self.other_tree.selection()
        if not sel:
            messagebox.showinfo("Change", "Select a setting first.", parent=self._top())
            return
        x = next(i for i in ST.LINKED if i.key == sel[0])

        def save(v):
            ST.set_linked(x.key, v["value"], actor=self.principal)
            self.refresh_other()
            self.status_var.set(f"Saved {x.area}: {x.label}")
        W.form_dialog(self.parent, f"{x.area}: {x.label}",
                      [("value", f"{x.label} ({x.hint})", ST.linked_values().get(x.key), None)],
                      save)

    # ── Sign-in policy ───────────────────────────────────────────────

    def _build_policy(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="Stored with the shared logins. [all systems] settings change "
                            "sign-in for all seven systems; [this school] only here. "
                            "Double-click or Edit to change one.",
                  foreground="#555", wraplength=900, justify="left").pack(anchor="w",
                                                                         pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Edit…", command=self.edit_policy).pack(side="left")
        ttk.Button(bar, text="Reset to default", command=self.reset_policy).pack(
            side="left", padx=4)
        self.policy_tree = W.tree(tab, [("label", "Setting", 340), ("value", "Value", 100),
                                        ("default", "Default", 100),
                                        ("desc", "What it does", 420)],
                                  height=8, stretch={"desc"})
        self.policy_tree.bind("<Double-1>", lambda _e: self.edit_policy())
        self.refresh_policy()

    def refresh_policy(self) -> None:
        t = self.policy_tree
        t.delete(*t.get_children())
        pol = ST.auth_policy()
        for s in ST.AUTH_POLICY:
            where = "[this school]" if s.scope == "system" else "[all systems]"
            t.insert("", "end", iid=s.key, values=(f"{s.label}   {where}",
                                                   ST.format_value(s, pol[s.key]),
                                                   ST.format_value(s, s.default),
                                                   s.description))

    def _policy_spec(self):
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showinfo("Sign-in policy", "Select a setting first.",
                                parent=self.parent.winfo_toplevel())
            return None
        return next(s for s in ST.AUTH_POLICY if s.key == sel[0])

    def _confirm_shared(self, spec) -> bool:
        return spec.scope == "system" or messagebox.askyesno(
            "Sign-in policy", f"'{spec.label}' applies to every system on this platform "
            "(university, sixth form, primary ...), not just this school. Change it?",
            parent=self.parent.winfo_toplevel())

    def edit_policy(self) -> None:
        spec = self._policy_spec()
        if spec is None:
            return
        cur = ST.auth_policy()[spec.key]
        hint = f" ({int(spec.min)}-{int(spec.max)})" if spec.min is not None else ""
        kind = "check" if spec.type == "bool" else None

        def save(v: dict[str, Any]) -> None:
            if not self._confirm_shared(spec):
                return
            new = ST.set_auth_policy(spec.key, v["value"], actor=self.principal)
            self.status_var.set(f"Saved sign-in policy: {spec.label} = "
                                f"{ST.format_value(spec, new)}")
            self.refresh_policy()
            if self.HISTORY in self._built:
                self.refresh_history()
        W.form_dialog(self.parent, spec.label, [("value", spec.label + hint, cur, kind)],
                      save, spec.description)

    def reset_policy(self) -> None:
        spec = self._policy_spec()
        if spec is None or not self._confirm_shared(spec):
            return
        try:
            new = ST.reset_auth_policy(spec.key, actor=self.principal)
        except W.ERRORS as e:
            messagebox.showerror("Sign-in policy", W.problems(e),
                                 parent=self.parent.winfo_toplevel())
            return
        self.status_var.set(f"Reset sign-in policy: {spec.label} = "
                            f"{ST.format_value(spec, new)}")
        self.refresh_policy()
        if self.HISTORY in self._built:
            self.refresh_history()

    # ── History ──────────────────────────────────────────────────────

    def _build_history(self, tab: ttk.Frame) -> None:
        ttk.Button(tab, text="Refresh", command=self.refresh_history).pack(anchor="w",
                                                                           pady=(0, 4))
        self.hist_tree = W.tree(tab, [("at", "When (UTC)", 150), ("actor", "Who", 100),
                                      ("action", "Action", 70), ("key", "Setting", 220),
                                      ("old", "Was", 200), ("new", "Now", 200)],
                                height=18, stretch={"old", "new"})

    def refresh_history(self) -> None:
        t = self.hist_tree
        t.delete(*t.get_children())
        for h in ST.history():
            t.insert("", "end", values=(h["at"], h["actor"], h["action"], h["key"] or "",
                                        "" if h["old"] is None else h["old"],
                                        "" if h["new"] is None else h["new"]))


def draw_settings(parent: ttk.Frame, *, principal: Principal, state: dict) -> SettingsPage:
    return SettingsPage(parent, principal=principal, state=state)
