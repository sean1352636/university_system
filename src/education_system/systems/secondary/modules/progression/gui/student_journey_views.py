"""Student Journey screen: a pupil's linked learner record.

Left: find a pupil (name, admission number or UPN; leavers included).
Right, for the chosen pupil:

* **Journey** - the journey id and a strip of the seven systems showing
  which hold a record (and which is current); a pupil not linked yet lists
  the journeys that might be theirs, with Link… and Register (data manager).
* **Learner 360** - the platform's whole-record view, section by section,
  tiered by the viewer's role (sections not shown to you are listed), with
  Save….
* **Transfers** - moves in and out with status and decision; Events… shows
  a move's step log.
* **Duplicates** - possible duplicate journeys (data manager only): Link
  (merge)… and Not the same person….
* **History** - this school's journey changes.

Open pupil opens the pupil's profile. Learner 360 builds in the background
(``tk_threads``). Rules are in :mod:`modules.progression.domain.student_journey`.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui import tk_threads
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.progression.domain import student_journey as SJ
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = W.ERRORS


def _brief(value: Any, limit: int = 140) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit - 3] + "..."


class StudentJourneyPage:
    TABS = ("Journey", "Learner 360", "Transfers", "Duplicates", "History")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.manager = SJ.is_data_manager(principal)
        self.pupil: P.Pupil | None = None
        self.journey: SJ.Journey | None = None
        self.view: dict[str, Any] | None = None
        activity_log.record("journey.open")
        ttk.Label(parent, text="Student Journey", font=("", 16, "bold")).pack(anchor="w")
        self.head_var = tk.StringVar(value="Choose a pupil on the left.")
        ttk.Label(parent, textvariable=self.head_var, foreground="#555").pack(anchor="w",
                                                                             pady=(0, 6))
        panes = ttk.PanedWindow(parent, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes, padding=(0, 0, 6, 0))
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=4)
        self._build_finder(left)
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(0, 4))
        b = ttk.Button(bar, text="Open pupil", command=self._open)
        if open_pupil is None:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=2)
        self.book = ttk.Notebook(right)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Journey"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self.find()
        pid = state.get("pupil_id")
        if pid:
            self.choose(int(pid))
        else:
            self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, manager_only: bool = False) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if manager_only and not self.manager:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _open(self) -> None:
        if self.pupil is None:
            self._info("Open pupil", "Choose a pupil first.")
        elif self.open_pupil:
            self.open_pupil(self.pupil.pupil_id)

    # ── finding a pupil ──────────────────────────────────────────────

    def _build_finder(self, left: ttk.Frame) -> None:
        row = ttk.Frame(left)
        row.pack(fill="x", pady=(0, 4))
        self.search_var = tk.StringVar(value=self.state.get("search", ""))
        e = ttk.Entry(row, textvariable=self.search_var, width=22)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda _e: self.find())
        ttk.Button(row, text="Find", command=self.find).pack(side="left", padx=(4, 0))
        self.leavers = tk.BooleanVar(value=bool(self.state.get("leavers")))
        ttk.Checkbutton(left, text="Include leavers", variable=self.leavers,
                        command=self.find).pack(anchor="w")
        self.find_tree = W.tree(left, [("name", "Pupil", 170), ("yr", "Yr", 35),
                                       ("adm", "Adm no", 90)], height=22, stretch={"name"},
                                tags=W.STANDARD_TAGS)
        self.find_tree.bind("<<TreeviewSelect>>", self._picked)

    def find(self) -> None:
        self.state.update(search=self.search_var.get().strip(), leavers=self.leavers.get())
        rows = P.list_pupils(search=self.search_var.get().strip() or None,
                             roll_status=None if self.leavers.get() else "on_roll")
        t = self.find_tree
        t.delete(*t.get_children())
        for p in rows[:500]:
            t.insert("", "end", iid=str(p.pupil_id), tags=("muted",) if p.roll_status != "on_roll"
                     else (), values=(f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                                      p.year_group, p.admission_no))

    def _picked(self, _e=None) -> None:
        sel = self.find_tree.selection()
        if sel and (self.pupil is None or int(sel[0]) != self.pupil.pupil_id):
            self.choose(int(sel[0]))

    def choose(self, pupil_id: int) -> None:
        p = P.get_pupil(pupil_id)
        if p is None:
            return
        self.pupil, self.view = p, None
        self.state["pupil_id"] = p.pupil_id
        self.refresh()

    def refresh(self) -> None:
        if self.pupil is None:
            return
        try:
            self.journey = SJ.journey(self.pupil.pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Student Journey", e)
            return
        j = self.journey
        self.head_var.set(f"{self.pupil.display_name} ({self.pupil.admission_no}), Year "
                          f"{self.pupil.year_group}, {self.pupil.roll_status_label} — journey "
                          f"{j.journey_id or 'not linked'}"
                          + (f" — records in: {', '.join(j.held_in)}" if j.linked else ""))
        self.view = None
        for name in list(self._built):
            self._refresh_tab(name)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Journey": self._build_journey, "Learner 360": self._build_360,
             "Transfers": self._build_transfers, "Duplicates": self._build_dups,
             "History": self._build_history}[name](self.tabs[name])
            self._refresh_tab(name)
        elif name == "Learner 360" and self.view is None:
            self._refresh_tab(name)

    def _refresh_tab(self, name: str) -> None:
        {"Journey": self.refresh_journey, "Learner 360": self.refresh_360,
         "Transfers": self.refresh_transfers, "Duplicates": self.refresh_dups,
         "History": self.refresh_history}[name]()

    # ── Journey ──────────────────────────────────────────────────────

    def _build_journey(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._button(bar, "Link to selected journey…", self.link, manager_only=True)
        self._button(bar, "Register in the registry", self.register, manager_only=True)
        self._button(bar, "Copy journey id", self.copy_id)
        self.strip = ttk.Frame(tab)
        self.strip.pack(fill="x", pady=(0, 8))
        ttk.Label(tab, text="Systems", font=("", 10, "bold")).pack(anchor="w")
        self.sys_tree = W.tree(tab, [("system", "System", 170), ("held", "Record", 80),
                                     ("ids", "Local id(s)", 200), ("status", "Status", 200)],
                               height=8, stretch={"status"}, tags=W.STANDARD_TAGS)
        ttk.Label(tab, text="Journeys that might be this pupil's (not linked yet)",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))
        self.cand_tree = W.tree(tab, [("jid", "Journey", 280), ("name", "Name", 180),
                                      ("dob", "Born", 90), ("why", "Why", 200)], height=5,
                                stretch={"why"})

    def refresh_journey(self) -> None:
        for child in self.strip.winfo_children():
            child.destroy()
        for t in (self.sys_tree, self.cand_tree):
            t.delete(*t.get_children())
        j = self.journey
        if j is None:
            return
        for s in j.systems or [SJ.SystemRecord(x, SJ.SYSTEM_LABELS.get(x, x), (), False)
                               for x in SJ.PHASES]:
            colour = "#cfe8d4" if s.current else "#e7f0fb" if s.held else "#eeeeee"
            tk.Label(self.strip, text=s.label + ("\n(current)" if s.current else
                                                 "\nrecord" if s.held else "\n—"),
                     bg=colour, padx=8, pady=4, relief="groove").pack(side="left", padx=2)
            self.sys_tree.insert("", "end", tags=("good",) if s.current else
                                 () if s.held else ("muted",),
                                 values=(s.label, "Yes" if s.held else "No",
                                         ", ".join(s.student_ids),
                                         ", ".join(x for x in s.statuses if x)))
        for c in j.candidates:
            self.cand_tree.insert("", "end", iid=c["journey_id"], values=(
                c["journey_id"], f"{c.get('legal_first_name')} {c.get('legal_last_name')}",
                c.get("date_of_birth") or "", c["_reason"]))

    def link(self) -> None:
        sel = self.cand_tree.selection() if "Journey" in self._built else ()
        if self.pupil is None or not sel:
            self._info("Link", "Choose a pupil, then select one of the possible journeys.")
            return
        if not messagebox.askyesno("Link", f"Link {self.pupil.display_name} to journey "
                                           f"{sel[0]}?", parent=self._top()):
            return
        try:
            SJ.link(self.pupil.pupil_id, sel[0], actor=self.principal)
        except _ERRORS as e:
            self._err("Link", e)
            return
        self.refresh()

    def register(self) -> None:
        if self.pupil is None:
            return
        try:
            jid = SJ.register(self.pupil.pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Register", e)
            return
        self._info("Register", f"{self.pupil.display_name} is on journey {jid}.")
        self.refresh()

    def copy_id(self) -> None:
        if self.journey and self.journey.journey_id:
            self._top().clipboard_clear()
            self._top().clipboard_append(self.journey.journey_id)

    # ── Learner 360 ──────────────────────────────────────────────────

    def _build_360(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Rebuild", lambda: self.refresh_360(force=True))
        self._button(bar, "Save…", self.save_360)
        self.v360_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.v360_var, foreground="#555").pack(side="left", padx=8)
        self.v360_tree = ttk.Treeview(tab, columns=("value",), show="tree headings", height=20)
        self.v360_tree.heading("#0", text="Section")
        self.v360_tree.heading("value", text="")
        self.v360_tree.column("#0", width=260)
        self.v360_tree.column("value", width=640)
        self.v360_tree.pack(fill="both", expand=True)

    def refresh_360(self, force: bool = False) -> None:
        if "Learner 360" not in self._built or self.pupil is None:
            return
        if self.view is not None and not force:
            return self._show_360()
        pid = self.pupil.pupil_id
        self.v360_var.set("Building…")
        widget = self.parent

        def work() -> None:
            try:
                view = SJ.learner_view(pid, actor=self.principal)
                tk_threads.ui(widget, self._got_360, pid, view, None)
            except Exception as e:  # noqa: BLE001 - shown below
                tk_threads.ui(widget, self._got_360, pid, None, e)
        tk_threads.start_thread(widget, work, name="secondary-learner-360")

    def _got_360(self, pid: int, view: dict | None, err: Exception | None) -> None:
        try:
            if not self.parent.winfo_exists() or self.pupil is None or \
                    self.pupil.pupil_id != pid:
                return
        except tk.TclError:
            return
        if err is not None:
            self.v360_var.set("")
            self._err("Learner 360", err)
            return
        self.view = view
        self._show_360()

    def _show_360(self) -> None:
        t, v = self.v360_tree, self.view or {}
        t.delete(*t.get_children())
        if not v.get("found"):
            self.v360_var.set("Not linked to a journey yet - see the Journey tab.")
            return
        tier = (v.get("viewer") or {}).get("tier")
        hidden = v.get("restricted_sections") or []
        self.v360_var.set(f"Shown for your role ({tier})" + (
            f" — not shown to you: {', '.join(hidden)}" if hidden else ""))
        for key, title in SJ.section_titles():
            data = v.get(key)
            if data is None:
                t.insert("", "end", text=title, values=("(not shown for your role)",))
                continue
            node = t.insert("", "end", text=title, open=key in ("overview", "transfers"),
                            values=(f"{len(data)} item(s)" if isinstance(data, list) else "",))
            self._fill(node, data)

    def _fill(self, node: str, data: Any) -> None:
        t = self.v360_tree
        if isinstance(data, dict):
            for k, val in data.items():
                if isinstance(val, (dict, list)) and val:
                    child = t.insert(node, "end", text=str(k), values=("",))
                    self._fill(child, val)
                else:
                    t.insert(node, "end", text=str(k), values=(_brief(val),))
        elif isinstance(data, list):
            for i, item in enumerate(data[:200]):
                if isinstance(item, dict):
                    label = item.get("label") or item.get("title") or item.get("kind") or \
                        item.get("system") or f"#{i + 1}"
                    summary = item.get("detail") or item.get("date") or item.get("status") or ""
                    child = t.insert(node, "end", text=str(label), values=(_brief(summary),))
                    self._fill(child, item)
                else:
                    t.insert(node, "end", text=f"#{i + 1}", values=(_brief(item),))

    def save_360(self) -> None:
        if not (self.view and self.view.get("found")):
            self._info("Save", "Nothing to save yet.")
            return
        W.text_window(self.parent, "Learner 360", SJ.learner_text(self.view),
                      save_name=f"learner_360_{self.pupil.admission_no if self.pupil else ''}"
                                ".txt")

    # ── Transfers ────────────────────────────────────────────────────

    def _build_transfers(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Events…", self.transfer_events)
        self.tr_tree = W.tree(tab, [("dir", "In/out", 60), ("move", "Move", 300),
                                    ("status", "Status", 120), ("decision", "Decision", 90),
                                    ("date", "Effective", 90), ("started", "Started", 140),
                                    ("reason", "Reason", 200)], height=14, stretch={"reason"},
                              tags=W.STANDARD_TAGS)
        self.tr_tree.bind("<Double-1>", lambda _e: self.transfer_events())

    def refresh_transfers(self) -> None:
        t = self.tr_tree
        t.delete(*t.get_children())
        if self.pupil is None:
            return
        try:
            rows = SJ.transfers(self.pupil.pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Transfers", e)
            return
        for r in rows:
            tag = "muted" if r.status == "cancelled" else "good" if r.status == "completed" \
                else ""
            t.insert("", "end", iid=r.transition_id, tags=(tag,) if tag else (), values=(
                r.direction, r.label, r.status, r.decision or "", r.effective_date or "",
                r.initiated_at or "", r.reason or ""))

    def transfer_events(self) -> None:
        sel = self.tr_tree.selection()
        if not sel:
            self._info("Events", "Select a transfer first.")
            return
        try:
            events = SJ.transfer_events(sel[0], actor=self.principal)
        except _ERRORS as e:
            self._err("Events", e)
            return
        text = "\n".join(f"{e.get('at')}  {e.get('step'):<18} {e.get('actor') or '':<14} "
                         f"{e.get('note') or ''}" for e in events) or "(no events)"
        W.text_window(self.parent, f"Transfer {sel[0]}", text)

    # ── Duplicates ───────────────────────────────────────────────────

    def _build_dups(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Link (merge)…", self.merge, manager_only=True)
        self._button(bar, "Not the same person…", self.not_same, manager_only=True)
        self._button(bar, "Refresh", self.refresh_dups, manager_only=True)
        self.whole = tk.BooleanVar(value=False)
        cb = ttk.Checkbutton(bar, text="Whole registry", variable=self.whole,
                             command=self.refresh_dups)
        if not self.manager:
            cb.state(["disabled"])
        cb.pack(side="left", padx=8)
        if not self.manager:
            ttk.Label(tab, text="Only the data manager can review duplicate records.",
                      foreground="#a44").pack(anchor="w")
        self.dup_tree = W.tree(tab, [("score", "Score", 55), ("keep", "Keep", 230),
                                     ("fold", "Fold in", 230), ("why", "Why", 320)], height=14,
                               stretch={"why"})
        self.dup_rows: dict[str, dict[str, Any]] = {}

    def refresh_dups(self) -> None:
        t = self.dup_tree
        t.delete(*t.get_children())
        self.dup_rows = {}
        if not self.manager:
            return
        try:
            rows = SJ.duplicates(None if self.whole.get() or self.pupil is None
                                 else self.pupil.pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Duplicates", e)
            return

        def who(d: dict) -> str:
            return f"{d.get('legal_first_name')} {d.get('legal_last_name')} " \
                   f"{d.get('date_of_birth') or ''}"
        for n, r in enumerate(rows):
            self.dup_rows[str(n)] = r
            t.insert("", "end", iid=str(n), values=(
                r["score"], f"{who(r['journey'])}", f"{who(r['duplicate'])}",
                "; ".join(r["reasons"])))

    def _dup(self, title: str) -> dict[str, Any] | None:
        sel = self.dup_tree.selection()
        if not sel:
            self._info(title, "Select a pair first.")
            return None
        return self.dup_rows[sel[0]]

    def merge(self) -> None:
        r = self._dup("Link (merge)")
        if r is None:
            return

        def save(v):
            SJ.merge(r["journey_id"], r["duplicate_id"], actor=self.principal,
                     reason=v["reason"], force=bool(v["force"]))
            self.refresh()
            self.refresh_dups()
        W.form_dialog(self.parent, "Link (merge) two journeys", [
            ("reason", "Why are these the same person?", "", "text"),
            ("force", "Merge even though their UPN / NHS numbers differ", False, "check")],
            save, note=f"Journey {r['duplicate_id']} folds into {r['journey_id']}; every "
                       "system's records follow it. The platform keeps a copy to reverse it.")

    def not_same(self) -> None:
        r = self._dup("Not the same person")
        if r is None:
            return

        def save(v):
            SJ.not_duplicate(r["journey_id"], r["duplicate_id"], actor=self.principal,
                             reason=v["reason"])
            self.refresh_dups()
        W.form_dialog(self.parent, "Not the same person",
                      [("reason", "Reason (e.g. twins)", "", None)], save)

    # ── History ──────────────────────────────────────────────────────

    def _build_history(self, tab) -> None:
        self.hist_tree = W.tree(tab, [("at", "When (UTC)", 150), ("actor", "Who", 100),
                                      ("action", "Action", 110), ("jid", "Journey", 280),
                                      ("detail", "Detail", 260)], height=16,
                                stretch={"detail"})

    def refresh_history(self) -> None:
        t = self.hist_tree
        t.delete(*t.get_children())
        if self.pupil is None:
            return
        for h in SJ.history(self.pupil.pupil_id):
            t.insert("", "end", values=(h["at"], h["actor"], h["action"], h["journey_id"] or "",
                                        ", ".join(f"{k}={v}" for k, v in h["detail"].items())))


def draw_student_journey(parent: ttk.Frame, *, principal: Principal, state: dict,
                         open_pupil: Callable[[int], None] | None = None
                         ) -> StudentJourneyPage:
    return StudentJourneyPage(parent, principal=principal, state=state, open_pupil=open_pupil)
