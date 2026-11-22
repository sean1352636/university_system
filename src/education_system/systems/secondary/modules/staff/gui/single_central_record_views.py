"""Single Central Record screen.

New tabs first: Record (everyone, with the state of each check they need -
missing, expired and overdue checks highlighted), To do (what needs doing,
worst first), Reminders (Update Service checks and expiries falling due) and
People. Then the old DBS Checks window's tabs, in its order - Active,
Expired, Expiring Soon, Update Overdue, Unsigned, Risk Pending, All and
Summary - with its toolbar (Staff, Level, Status on All, Cert; Apply, New),
columns (Id, Staff, Level, DBS No, Issued, Expires, Cert Type, Update,
Signed, Status, Flags) and actions (Edit, Issue certificate, Mark cert seen,
Subscribe US, Record update, Complete risk, Sign off, Mark Lapsed, Start
renewal, Change status, Delete, Refresh). Rules:
:mod:`modules.staff.domain.single_central_record`.
"""

from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.staff.domain import single_central_record as SCR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = W.ERRORS
_DBS_SCOPES = {"Active": {"active_only": True}, "Expired": {"expired": True},
               "Expiring Soon": {"expiring_soon": True},
               "Update Overdue": {"update_check_overdue": True},
               "Unsigned": {"unsigned": True},
               "Risk Pending": {"risk_assessment_pending": True}, "All": {}}
_SHORT = {"Identity": "ID", "Qualifications": "Quals", "DBS": "DBS", "Barred list": "Barred",
          "Prohibition from teaching": "Prohib.", "Section 128": "s128",
          "Overseas": "Overseas", "Right to work": "RTW", "References": "Refs",
          "Medical fitness": "Medical", "Disqualification by association": "DbA",
          "Agency confirmation": "Agency"}
_MARK = {"ok": "✓", "missing": "MISSING", "pending": "pending", "expiring": "expiring",
         "expired": "EXPIRED", "overdue": "OVERDUE", "problem": "PROBLEM"}
_TAGS = {**W.STANDARD_TAGS, "missing": {"background": "#fde2e2"},
         "expired": {"background": "#ffd1d1", "foreground": "#8c0d0d"},
         "soon": {"background": "#fff0d6", "foreground": "#7a5800"}}


def _person_fields(p: SCR.Person | None) -> list:
    g = (lambda k, d="": getattr(p, k) if p is not None and getattr(p, k) is not None else d)
    return [("full_name", "Name (blank = from login / roster)", g("full_name"), None),
            ("username", "Staff login (if any)", g("username"), None),
            ("category", "Category", g("category", "Staff"), SCR.CATEGORIES),
            ("role_title", "Post / role", g("role_title"), None),
            ("agency_name", "Agency (supply)", g("agency_name"), None),
            ("supply_id", "Supply roster id (supply)", g("supply_id"), None),
            ("start_date", "Start date", g("start_date"), None),
            ("end_date", "Leaving date", g("end_date"), None),
            ("teaching_role", "Teaching post", p.teaching_role if p else False, "check"),
            ("leadership_role", "Management post (section 128)",
             p.leadership_role if p else False, "check"),
            ("regulated_activity", "Regulated activity", p.regulated_activity if p else True,
             "check"),
            ("lived_overseas", "Lived / worked overseas", p.lived_overseas if p else False,
             "check"),
            ("childcare_relevant", "Childcare disqualification relevant",
             p.childcare_relevant if p else False, "check"),
            ("notes", "Notes", g("notes"), "text")]


def _check_fields(c: SCR.Check | None, check_type: str = "") -> list:
    g = (lambda k, d="": getattr(c, k) if c is not None and getattr(c, k) is not None else d)
    return [("check_type", "Check*", g("check_type", check_type or SCR.DBS), SCR.CHECK_TYPES),
            ("status", "Status", g("status"), ("edit", [*SCR.STATUSES, *SCR.DBS_STATUSES])),
            ("checked_on", "Checked on (blank = today when clear)", g("checked_on"), None),
            ("checked_by", "Checked by (blank = you)", g("checked_by"), None),
            ("reference", "Document / reference", g("reference"), None),
            ("issued_on", "Issued on", g("issued_on"), None),
            ("expires_on", "Expires on", g("expires_on"), None),
            ("dbs_level", "DBS level", g("dbs_level"), ["", *SCR.LEVELS]),
            ("dbs_number", "DBS certificate no.", g("dbs_number"), None),
            ("applied_on", "Applied on", g("applied_on"), None),
            ("certificate_type", "Certificate", g("certificate_type"),
             ["", *SCR.CERTIFICATE_TYPES]),
            ("certificate_seen_on", "Certificate seen on", g("certificate_seen_on"), None),
            ("update_service_subscribed", "Update Service",
             c.update_service_subscribed if c else False, "check"),
            ("update_service_id", "Update Service id", g("update_service_id"), None),
            ("last_update_check_on", "Last update check", g("last_update_check_on"), None),
            ("next_update_check_due", "Next update check", g("next_update_check_due"), None),
            ("portability_check", "Portability check", c.portability_check if c else False,
             "check"),
            ("risk_assessment_required", "Risk assessment required",
             c.risk_assessment_required if c else False, "check"),
            ("risk_assessment_completed_on", "Risk assessment on",
             g("risk_assessment_completed_on"), None),
            ("risk_assessment_outcome", "Risk assessment outcome",
             g("risk_assessment_outcome"), None),
            ("signed_off_by", "Signed off by", g("signed_off_by"), None),
            ("signed_off_on", "Signed off on", g("signed_off_on"), None),
            ("notes", "Notes", g("notes"), "text")]


def _blank_to_none(v: dict[str, Any]) -> dict[str, Any]:
    return {k: (None if x == "" else x) for k, x in v.items()}


class SingleCentralRecordPage:
    TABS = ("Record", "To do", "Reminders", "People", *_DBS_SCOPES, "Summary")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = SCR.is_editor(principal)
        activity_log.record("scr.view", principal=principal)
        ttk.Label(parent, text="Single Central Record", font=("", 16, "bold")).pack(anchor="w")
        if not self.editor:
            ttk.Label(parent, text=principal.denied_message("Single Central Record"),
                      foreground="#777", justify="left").pack(anchor="w", pady=8)
            self.book = None
            return
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self.dbs: dict[str, dict[str, Any]] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else "Record"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = True) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _run(self, title: str, fn, done: str | None = None) -> Any:
        try:
            out = fn()
        except _ERRORS as e:
            self._err(title, e)
            return None
        self._refresh_all()
        if done:
            self._info(title, done.format(out=out))
        return out

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Record": self._build_record, "To do": self._build_todo,
             "Reminders": self._build_reminders, "People": self._build_people,
             "Summary": self._build_summary}.get(name, lambda t: self._build_dbs(name, t))(
                self.tabs[name])
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        {"Record": self.refresh_record, "To do": self.refresh_todo,
         "Reminders": self.refresh_reminders, "People": self.refresh_people,
         "Summary": self.refresh_summary}.get(name, lambda: self.refresh_dbs(name))()
        try:
            s = SCR.summary(actor=self.principal)
            st = s["states"]
            self.summary_var.set(
                f"People: {s['people']}    Complete: {s['complete']}    Missing: "
                f"{st.get('missing', 0)}    Expired: {st.get('expired', 0)}    Overdue: "
                f"{st.get('overdue', 0)}    Problems: {st.get('problem', 0)}")
        except _ERRORS:
            self.summary_var.set("")

    def _refresh_all(self) -> None:
        for name in self._built:
            self._refresh(name)

    # ── Record ───────────────────────────────────────────────────────

    def _build_record(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.cat = tk.StringVar(value=self.state.get("category", ""))
        self.search = tk.StringVar(value=self.state.get("search", ""))
        self.only_problems = tk.BooleanVar(value=bool(self.state.get("problems_only")))
        self.leavers = tk.BooleanVar(value=bool(self.state.get("leavers")))
        ttk.Label(bar, text="Category:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.cat, values=["", *SCR.CATEGORIES],
                          state="readonly", width=11)
        cb.pack(side="left", padx=(2, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_record())
        ttk.Label(bar, text="Search:").pack(side="left")
        e = ttk.Entry(bar, textvariable=self.search, width=16)
        e.pack(side="left", padx=(2, 8))
        e.bind("<Return>", lambda _e: self.refresh_record())
        for text, var in (("Outstanding only", self.only_problems),
                          ("Include leavers", self.leavers)):
            ttk.Checkbutton(bar, text=text, variable=var, command=self.refresh_record).pack(
                side="left", padx=4)
        ttk.Button(bar, text="Apply", command=self.refresh_record).pack(side="left", padx=4)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        for text, cmd, ed in (("Add person…", self.add_person, True),
                              ("Edit person…", self.edit_person, True),
                              ("Checks…", self.checks_window, False),
                              ("Add check…", self.add_check_for_selected, True),
                              ("Record leaving…", self.leaving, True),
                              ("Delete person", self.delete_person, True),
                              ("Add staff logins", self.add_logins, True),
                              ("Sync supply roster", self.sync_supply, True),
                              ("Print…", self.print_record, False),
                              ("Export CSV…", self.export, False),
                              ("History", self.person_history, False)):
            self._button(bar2, text, cmd, ed)
        cols = [("name", "Name", 180), ("cat", "Category", 80), ("post", "Post", 120),
                ("start", "Started", 85)]
        cols += [(f"c{i}", _SHORT[t], 70) for i, t in enumerate(SCR.CHECK_TYPES)]
        self.rec_tree = W.tree(tab, cols, height=18, stretch={"name"}, tags=_TAGS,
                               xscroll=True, minwidth=40)
        self.rec_tree.bind("<Double-1>", lambda _e: self.checks_window())
        self.rec_rows: dict[str, SCR.Person] = {}

    def refresh_record(self) -> None:
        self.state.update(category=self.cat.get(), search=self.search.get(),
                          problems_only=self.only_problems.get(), leavers=self.leavers.get())
        try:
            rows = SCR.record(actor=self.principal, category=self.cat.get() or None,
                              search=self.search.get().strip() or None,
                              problems_only=self.only_problems.get(),
                              current_only=not self.leavers.get())
        except _ERRORS as e:
            self._err("Single Central Record", e)
            return
        self.rec_tree.delete(*self.rec_tree.get_children())
        self.rec_rows = {}
        for p, st in rows:
            self.rec_rows[str(p.person_id)] = p
            states = {v["state"] for v in st.values()}
            tag = ("muted",) if not p.is_current else ("expired",) if states & {
                "expired", "problem"} else ("missing",) if "missing" in states and \
                p.has_started else ("soon",) if states - {"ok"} else ("good",)
            self.rec_tree.insert("", "end", iid=str(p.person_id), tags=tag, values=(
                p.full_name, p.category, p.role_title or "", p.start_date or "",
                *[_MARK[st[t]["state"]] if t in st else "—" for t in SCR.CHECK_TYPES]))

    def _person(self, title: str) -> SCR.Person | None:
        tree, rows = (self.rec_tree, self.rec_rows) if self.state.get("tab") == "Record" \
            else (self.ppl_tree, self.ppl_rows)
        sel = tree.selection()
        if not sel:
            self._info(title, "Select a person first.")
            return None
        return rows[sel[0]]

    def add_person(self) -> None:
        def save(v):
            SCR.create_person(_blank_to_none(v), actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, "Add to the single central record", _person_fields(None),
                      save, note="Staff: give their login. Supply: give the supply roster id "
                                 "(Cover > Supply staff) to link them.")

    def edit_person(self) -> None:
        p = self._person("Edit person")
        if p is None:
            return

        def save(v):
            SCR.update_person(p.person_id, _blank_to_none(v), actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Edit - {p.full_name}", _person_fields(p), save)

    def leaving(self) -> None:
        p = self._person("Record leaving")
        if p is None:
            return

        def save(v):
            SCR.record_leaving(p.person_id, end_date=v["day"] or None, actor=self.principal)
            self._refresh_all()
        W.form_dialog(self.parent, f"Leaving - {p.full_name}",
                      [("day", "Leaving date", _dt.date.today().isoformat(), None)], save,
                      note="Their record and checks are kept.")

    def delete_person(self) -> None:
        p = self._person("Delete person")
        if p and messagebox.askyesno("Delete person", f"Delete {p.full_name} (added in "
                                     "error)?", parent=self._top()):
            self._run("Delete person", lambda: SCR.delete_person(p.person_id,
                                                                 actor=self.principal))

    def add_logins(self) -> None:
        self._run("Add staff logins", lambda: SCR.add_from_logins(actor=self.principal),
                  "Added {out} member(s) of staff.")

    def sync_supply(self) -> None:
        self._run("Sync supply roster", lambda: SCR.sync_supply(actor=self.principal),
                  "Added {out} supply person(s) from the cover roster.")

    def print_record(self) -> None:
        try:
            text = SCR.scr_text(actor=self.principal, category=self.cat.get() or None,
                                current_only=not self.leavers.get())
        except _ERRORS as e:
            self._err("Print", e)
            return
        W.text_window(self.parent, "Single Central Record", text, size="980x620",
                      save_name="single_central_record.txt")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="single_central_record.csv")
        if path:
            self._run("Export", lambda: SCR.export_csv(
                path, actor=self.principal, category=self.cat.get() or None,
                current_only=not self.leavers.get()), "Exported {out} person(s).")

    def person_history(self) -> None:
        p = self._person("History")
        if p:
            W.text_window(self.parent, "History", "\n".join(
                f"{h['at']}  {h['actor']:<14} {h['action']:<14} "
                + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
                for h in SCR.history(p.person_id)) or "No changes recorded.")

    def add_check_for_selected(self) -> None:
        p = self._person("Add check")
        if p:
            self._check_form(p, None)

    def _check_form(self, p: SCR.Person, c: SCR.Check | None, after=None,
                    check_type: str = "") -> None:
        def save(v):
            v = _blank_to_none(v)
            if c is None:
                SCR.add_check(p.person_id, v, actor=self.principal)
            else:
                SCR.update_check(c.check_id, v, actor=self.principal)
            self._refresh_all()
            if after:
                after()
        need = ", ".join(SCR.required_checks(p))
        W.form_dialog(self.parent, f"{'Edit check' if c else 'Add check'} - {p.full_name}",
                      _check_fields(c, check_type), save,
                      note=f"Needed for this person: {need}. DBS fields are for DBS checks "
                           "only. A renewal is a new check; the latest counts.")

    def checks_window(self) -> None:
        p = self._person("Checks")
        if p is None:
            return
        win, frm = W.dialog(self.parent, f"Checks - {p.full_name} ({p.category})",
                            size="980x460")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        tree = W.tree(frm, [("id", "Id", 50), ("type", "Check", 170), ("status", "Status", 150),
                            ("on", "Checked on", 90), ("by", "By", 100),
                            ("ref", "Reference / DBS no.", 150), ("exp", "Expires", 90),
                            ("state", "State", 80)], height=12, stretch={"type"}, tags=_TAGS)
        rows: dict[str, SCR.Check] = {}

        def refresh() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            st = SCR.person_status(p)
            for t, v in st.items():
                if v["check"] is None:
                    tree.insert("", "end", iid=f"need:{t}", tags=("missing",),
                                values=("", t, "not recorded", "", "", "", "", "MISSING"))
            for c in SCR.checks_for_person(p.person_id, actor=self.principal):
                rows[str(c.check_id)] = c
                current = st.get(c.check_type, {}).get("check")
                tag = "expired" if c.state in ("expired", "problem") else "soon" \
                    if c.state in ("overdue", "expiring", "pending") else "good"
                if current is not None and current.check_id != c.check_id:
                    tag = "muted"
                tree.insert("", "end", iid=str(c.check_id), tags=(tag,), values=(
                    c.check_id, c.check_type, c.status, c.checked_on or "",
                    c.checked_by or "", c.dbs_number or c.reference or "", c.expires_on or "",
                    c.state))

        def selected_check() -> SCR.Check | None:
            sel = tree.selection()
            return rows.get(sel[0]) if sel else None

        def add() -> None:
            sel = tree.selection()
            t = sel[0].split(":", 1)[1] if sel and sel[0].startswith("need:") else ""
            self._check_form(p, None, refresh, t)

        def edit() -> None:
            c = selected_check()
            if c:
                self._check_form(p, c, refresh)

        def remove() -> None:
            c = selected_check()
            if c and messagebox.askyesno("Delete check", f"Delete check #{c.check_id} "
                                         f"({c.check_type})?", parent=win):
                try:
                    SCR.delete_check(c.check_id, actor=self.principal)
                except _ERRORS as e:
                    messagebox.showerror("Delete check", W.problems(e), parent=win)
                    return
                refresh()
                self._refresh_all()
        for text, cmd, ed in (("Add check…", add, True), ("Edit…", edit, True),
                              ("Delete", remove, True), ("Refresh", refresh, False)):
            self._button(bar, text, cmd, ed)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        tree.bind("<Double-1>", lambda _e: edit() if selected_check() else add())
        refresh()

    # ── To do / Reminders / People ───────────────────────────────────

    def _build_todo(self, tab) -> None:
        ttk.Label(tab, text="Checks missing, expired, overdue or with a problem - people who "
                            "have started first.", foreground="#555").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(4, 4))
        self._button(bar, "Add check…", self._todo_add)
        self.todo_tree = W.tree(tab, [("person", "Person", 200), ("cat", "Category", 90),
                                      ("check", "Check", 200), ("state", "State", 90),
                                      ("detail", "Detail", 360)], height=18,
                                stretch={"detail"}, tags=_TAGS)
        self.todo_rows: dict[str, dict] = {}

    def refresh_todo(self) -> None:
        try:
            rows = SCR.problems(actor=self.principal)
        except _ERRORS as e:
            self._err("To do", e)
            return
        self.todo_tree.delete(*self.todo_tree.get_children())
        self.todo_rows = {}
        for i, x in enumerate(rows):
            iid = str(i)
            self.todo_rows[iid] = x
            tag = "expired" if x["state"] in ("expired", "problem") else "missing" \
                if x["state"] == "missing" else "soon"
            self.todo_tree.insert("", "end", iid=iid, tags=(tag,), values=(
                x["person"].full_name, x["person"].category, x["check"],
                _MARK[x["state"]], x["detail"]))

    def _todo_add(self) -> None:
        sel = self.todo_tree.selection()
        if not sel:
            self._info("Add check", "Select a line first.")
            return
        x = self.todo_rows[sel[0]]
        self._check_form(x["person"], None, check_type=x["check"])

    def _build_reminders(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.rem_days = tk.StringVar(value=str(self.state.get("rem_days", 60)))
        ttk.Label(bar, text="Due within (days):").pack(side="left")
        ttk.Entry(bar, textvariable=self.rem_days, width=5).pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply", command=self.refresh_reminders).pack(side="left")
        self.rem_tree = W.tree(tab, [("due", "Due", 90), ("person", "Person", 200),
                                     ("what", "What", 260), ("status", "Status", 160)],
                               height=18, stretch={"what"}, tags=_TAGS)

    def refresh_reminders(self) -> None:
        days = int(self.rem_days.get()) if self.rem_days.get().strip().isdigit() else 60
        self.state["rem_days"] = days
        try:
            rows = SCR.reminders(actor=self.principal, within_days=days)
        except _ERRORS as e:
            self._err("Reminders", e)
            return
        self.rem_tree.delete(*self.rem_tree.get_children())
        today = _dt.date.today().isoformat()
        for x in rows:
            self.rem_tree.insert("", "end", tags=("expired",) if x["due"] < today else ("soon",),
                                 values=(x["due"], x["person"].full_name, x["what"],
                                         x["check"].status))

    def _build_people(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd, ed in (("Add person…", self.add_person, True),
                              ("Edit person…", self.edit_person, True),
                              ("Checks…", self.checks_window, False),
                              ("Record leaving…", self.leaving, True)):
            self._button(bar, text, cmd, ed)
        self.ppl_note = tk.StringVar()
        ttk.Label(tab, textvariable=self.ppl_note, foreground="#a60").pack(anchor="w")
        self.ppl_tree = W.tree(tab, [("name", "Name", 200), ("login", "Login", 100),
                                     ("cat", "Category", 90), ("post", "Post", 140),
                                     ("agency", "Agency", 120), ("start", "Started", 90),
                                     ("left", "Left", 90), ("needs", "Checks needed", 360)],
                               height=18, stretch={"needs"}, tags=_TAGS)
        self.ppl_tree.bind("<Double-1>", lambda _e: self.checks_window())
        self.ppl_rows: dict[str, SCR.Person] = {}

    def refresh_people(self) -> None:
        try:
            people = SCR.list_people(actor=self.principal, current_only=False)
            missing = SCR.missing_people(actor=self.principal)
        except _ERRORS as e:
            self._err("People", e)
            return
        self.ppl_note.set(
            (f"Not on the record: {len(missing['logins'])} staff login(s), "
             f"{len(missing['supply'])} supply person(s) - use Add staff logins / Sync supply "
             "roster on the Record tab.") if missing["logins"] or missing["supply"] else "")
        self.ppl_tree.delete(*self.ppl_tree.get_children())
        self.ppl_rows = {}
        for p in people:
            self.ppl_rows[str(p.person_id)] = p
            self.ppl_tree.insert("", "end", iid=str(p.person_id),
                                 tags=("muted",) if not p.is_current else (), values=(
                                     p.full_name, p.username or "", p.category,
                                     p.role_title or "", p.agency_name or "",
                                     p.start_date or "", p.end_date or "",
                                     ", ".join(SCR.required_checks(p))))

    # ── The old DBS register tabs ────────────────────────────────────

    def _build_dbs(self, name: str, tab) -> None:
        ctx: dict[str, Any] = {"rows": {}}
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        saved = self.state.setdefault("dbs_filters", {}).get(name, {})
        for k in ("staff", "level", "status", "cert"):
            ctx[k] = tk.StringVar(value=saved.get(k, ""))
        ttk.Label(bar, text="Staff:").pack(side="left")
        ttk.Entry(bar, textvariable=ctx["staff"], width=12).pack(side="left", padx=(2, 8))
        combos = [("Level:", ctx["level"], SCR.LEVELS, 26)]
        if name == "All":
            combos.append(("Status:", ctx["status"], SCR.DBS_STATUSES, 22))
        combos.append(("Cert:", ctx["cert"], SCR.CERTIFICATE_TYPES, 18))
        for label, var, values, width in combos:
            ttk.Label(bar, text=label).pack(side="left")
            cb = ttk.Combobox(bar, textvariable=var, values=["", *values], state="readonly",
                              width=width)
            cb.pack(side="left", padx=(2, 8))
            cb.bind("<<ComboboxSelected>>", lambda _e, n=name: self.refresh_dbs(n))
        ttk.Button(bar, text="Apply", command=lambda: self.refresh_dbs(name)).pack(
            side="left", padx=4)
        self._button(bar, "New", self.new_dbs)
        tree = W.tree(tab, [("id", "Id", 50), ("staff", "Staff", 160), ("level", "Level", 190),
                            ("no", "DBS No", 110), ("issued", "Issued", 90),
                            ("expires", "Expires", 90), ("cert", "Cert Type", 130),
                            ("update", "Update", 60), ("signed", "Signed", 100),
                            ("status", "Status", 160), ("flags", "Flags", 120)],
                      height=16, stretch={"staff"}, tags=_TAGS)
        tree.bind("<Double-1>", lambda _e: self.edit_dbs())
        ctx["tree"] = tree
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(4, 0))
        for text, cmd in (("Edit", self.edit_dbs), ("Issue certificate", self.issue_cert),
                          ("Mark cert seen", self.cert_seen), ("Subscribe US", self.subscribe),
                          ("Record update", self.update_check),
                          ("Complete risk", self.risk), ("Sign off", self.sign_off),
                          ("Mark Lapsed", self.lapsed), ("Start renewal", self.renewal),
                          ("Change status", self.dbs_status), ("Delete", self.delete_dbs)):
            self._button(acts, text, cmd)
        self._button(acts, "Refresh", lambda: self.refresh_dbs(name), editor_only=False)
        ctx["count"] = ttk.Label(acts, text="")
        ctx["count"].pack(side="right")
        self.dbs[name] = ctx

    def refresh_dbs(self, name: str) -> None:
        ctx = self.dbs[name]
        vals = {k: ctx[k].get().strip() for k in ("staff", "level", "status", "cert")}
        self.state.setdefault("dbs_filters", {})[name] = vals
        try:
            rows = SCR.list_checks(actor=self.principal, check_type=SCR.DBS,
                                   search=vals["staff"] or None, level=vals["level"] or None,
                                   status=vals["status"] or None,
                                   certificate_type=vals["cert"] or None, **_DBS_SCOPES[name])
        except _ERRORS as e:
            self._err("DBS checks", e)
            return
        tree = ctx["tree"]
        tree.delete(*tree.get_children())
        ctx["rows"] = {}
        for c in rows:
            ctx["rows"][str(c.check_id)] = c
            flags = [f for f, on in (("EXP", c.is_expired), ("SOON", c.expiring_soon),
                                     ("US-DUE", c.update_check_overdue),
                                     ("RISK", c.risk_pending), ("UNSIGNED", c.unsigned)) if on]
            tag = "expired" if c.is_expired or c.state == "problem" else "soon" if (
                c.expiring_soon or c.update_check_overdue) else ""
            tree.insert("", "end", iid=str(c.check_id), tags=(tag,) if tag else (), values=(
                c.check_id, c.person_name, c.dbs_level or "", c.dbs_number or "",
                c.issued_on or "", c.expires_on or "", c.certificate_type or "",
                "yes" if c.update_service_subscribed else "", c.signed_off_by or "",
                c.status, ",".join(flags)))
        ctx["count"].config(text=f"{len(rows)} check(s)")

    def _dbs_selected(self, title: str) -> SCR.Check | None:
        ctx = self.dbs.get(self.state.get("tab") or "")
        sel = ctx["tree"].selection() if ctx else ()
        if not sel:
            self._info(title, "Select a check first.")
            return None
        return ctx["rows"][sel[0]]

    def new_dbs(self) -> None:
        try:
            people = SCR.list_people(actor=self.principal)
        except _ERRORS as e:
            self._err("New", e)
            return
        labels = {f"{p.full_name} ({p.category}) #{p.person_id}": p for p in people}

        def save(v):
            p = labels.get(v.pop("who"))
            if p is None:
                raise SCR.ValidationError(["Choose who the check is for (add them on the "
                                           "Record tab first)"])
            SCR.add_check(p.person_id, {**_blank_to_none(v), "check_type": SCR.DBS},
                          actor=self.principal)
            self._refresh_all()
        fields = [("who", "Staff*", "", list(labels))] + [
            f for f in _check_fields(None, SCR.DBS) if f[0] != "check_type"]
        W.form_dialog(self.parent, "New DBS check", fields, save)

    def edit_dbs(self) -> None:
        c = self._dbs_selected("Edit")
        if c:
            self._check_form(SCR.get_person(c.person_id), c)

    def _ask(self, title: str, c: SCR.Check, fields: list, call) -> None:
        def save(v):
            call(v)
            self._refresh_all()
        W.form_dialog(self.parent, f"{title} - #{c.check_id} {c.person_name}", fields, save)

    def issue_cert(self) -> None:
        c = self._dbs_selected("Issue certificate")
        if c:
            self._ask("Issue certificate", c, [
                ("no", "DBS number*", c.dbs_number or "", None),
                ("issued", "Issued on", _dt.date.today().isoformat(), None),
                ("expires", "Expires on (school policy)", c.expires_on or "", None)],
                lambda v: SCR.issue_certificate(c.check_id, dbs_number=v["no"],
                                                issued_on=v["issued"] or None,
                                                expires_on=v["expires"] or None,
                                                actor=self.principal))

    def cert_seen(self) -> None:
        c = self._dbs_selected("Mark cert seen")
        if c:
            self._ask("Mark cert seen", c, [("on", "Seen on", _dt.date.today().isoformat(),
                                             None)],
                      lambda v: SCR.see_certificate(c.check_id, seen_on=v["on"] or None,
                                                    actor=self.principal))

    def subscribe(self) -> None:
        c = self._dbs_selected("Subscribe US")
        if c:
            self._ask("Update Service", c, [
                ("id", "Update Service id", c.update_service_id or "", None),
                ("next", "Next check due (blank = 12 months)", "", None)],
                lambda v: SCR.subscribe_update_service(c.check_id, update_id=v["id"] or None,
                                                       next_check_due=v["next"] or None,
                                                       actor=self.principal))

    def update_check(self) -> None:
        c = self._dbs_selected("Record update")
        if c:
            self._ask("Update Service check", c, [
                ("on", "Checked on", _dt.date.today().isoformat(), None),
                ("next", "Next check due (blank = 12 months)", "", None)],
                lambda v: SCR.record_update_check(c.check_id, checked_on=v["on"] or None,
                                                  next_check_due=v["next"] or None,
                                                  actor=self.principal))

    def risk(self) -> None:
        c = self._dbs_selected("Complete risk")
        if c:
            self._ask("Risk assessment", c, [
                ("outcome", "Outcome*", c.risk_assessment_outcome or "", "text"),
                ("on", "Completed on", _dt.date.today().isoformat(), None)],
                lambda v: SCR.complete_risk_assessment(c.check_id, outcome=v["outcome"],
                                                       completed_on=v["on"] or None,
                                                       actor=self.principal))

    def sign_off(self) -> None:
        c = self._dbs_selected("Sign off")
        if c:
            self._ask("Sign off", c, [
                ("by", "Signed off by*", self.principal.username, None),
                ("on", "Signed off on", _dt.date.today().isoformat(), None)],
                lambda v: SCR.sign_off(c.check_id, signed_off_by=v["by"],
                                       signed_off_on=v["on"] or None, actor=self.principal))

    def lapsed(self) -> None:
        c = self._dbs_selected("Mark Lapsed")
        if c and messagebox.askyesno("Mark Lapsed", f"Mark check #{c.check_id} lapsed?",
                                     parent=self._top()):
            self._run("Mark Lapsed", lambda: SCR.mark_lapsed(c.check_id, actor=self.principal))

    def renewal(self) -> None:
        c = self._dbs_selected("Start renewal")
        if c:
            self._run("Start renewal", lambda: SCR.start_renewal(c.check_id,
                                                                 actor=self.principal))

    def dbs_status(self) -> None:
        c = self._dbs_selected("Change status")
        if c:
            self._ask("Change status", c, [("status", "Status", c.status, SCR.DBS_STATUSES)],
                      lambda v: SCR.set_status(c.check_id, v["status"], actor=self.principal))

    def delete_dbs(self) -> None:
        c = self._dbs_selected("Delete")
        if c and messagebox.askyesno("Delete", f"Delete DBS check #{c.check_id} for "
                                     f"{c.person_name}?", parent=self._top()):
            self._run("Delete", lambda: SCR.delete_check(c.check_id, actor=self.principal))

    # ── Summary (old DBS summary + the record) ───────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh_summary).pack(side="left")
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10))
        self.sum_text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        try:
            s = SCR.summary(actor=self.principal)
        except _ERRORS as e:
            self._err("Summary", e)
            return
        lines = ["Single Central Record", "=" * 60, "",
                 f"People on the record : {s['people']}",
                 f"All checks complete  : {s['complete']}", ""]
        lines += [f"  {k:<10}: {n}" for k, n in sorted(s["states"].items())]
        lines += ["", "By category:"] + [f"  {k:<12}: {n}" for k, n in
                                         sorted(s["by_category"].items())]
        lines += ["", "DBS Checks Summary", "-" * 60]
        for label, key in (("Total", "dbs_total"), ("Active", "dbs_active"),
                           ("Pending", "dbs_pending"), ("Renewing", "dbs_renewing"),
                           ("Expired", "dbs_expired"), ("Expiring soon", "dbs_expiring_soon"),
                           ("Update check overdue", "update_check_overdue"),
                           ("Update Service", "update_service_subscribed"),
                           ("Risk assessment pending", "risk_assessment_pending"),
                           ("Unsigned", "unsigned")):
            lines.append(f"{label:<24}: {s[key]}")
        for head, key in (("By level", "by_level"), ("By status", "by_status"),
                          ("By certificate type", "by_certificate_type")):
            lines += ["", f"{head}:"] + [f"  {k or '-':<34}: {n}" for k, n in s[key].items()]
        self.sum_text.config(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", "\n".join(lines))
        self.sum_text.config(state="disabled")


def draw_single_central_record(parent: ttk.Frame, *, principal: Principal, state: dict
                               ) -> SingleCentralRecordPage:
    return SingleCentralRecordPage(parent, principal=principal, state=state)
