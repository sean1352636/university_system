"""Incoming from Primary screen (Year 6 -> Year 7 through the platform).

Queue: every transfer from primary addressed to this school, with status,
start date, whether the handover is ready and acknowledged, and the pupil
it is matched to (filters: status, search, include finished). Buttons:
Handover…, Acknowledge, Reject…, Match…, Create pupil…, Complete…, Open
pupil, Export CSV…, Refresh. Checklist (for the selected pupil): the
platform's items and this school's, with Tick / Untick, SEN to SENCO…,
Safeguarding file received (safeguarding leads), Import KS2 and Unmatch….
Step log: the platform's transfer events and this school's steps.

What a person sees of the handover is decided by the platform for their
role; the safeguarding flag is shown to safeguarding leads only. Rules are
in :mod:`modules.progression.domain.incoming_primary`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.progression.domain import incoming_primary as IP
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = W.ERRORS
STATUSES = ("", "Expected", "Handover ready", "Admitted", "Completed", "Rejected", "Cancelled")


class IncomingPrimaryPage:
    TABS = ("Queue", "Checklist", "Step log")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = IP.is_editor(principal)
        self.lead = IP.is_safeguarding_lead(principal)
        self.rows: dict[str, IP.Incoming] = {}
        activity_log.record("incoming.open")
        ttk.Label(parent, text="Incoming from Primary", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self._build_queue(self.tabs["Queue"])
        self._built.add("Queue")
        start = state.get("tab") if state.get("tab") in self.TABS else "Queue"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self.refresh()
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Checklist": self._build_checklist, "Step log": self._build_log}[name](
                self.tabs[name])
        if name == "Checklist":
            self.refresh_checklist()
        elif name == "Step log":
            self.refresh_log()

    def _selected(self, title: str = "", quiet: bool = False) -> IP.Incoming | None:
        tid = self.state.get("transition_id")
        sel = self.tree.selection()
        if sel:
            tid = sel[0]
        item = self.rows.get(tid or "")
        if item is None and not quiet:
            self._info(title or "Incoming", "Select a pupil in the queue first.")
        return item

    def _done(self, title: str, text: str | None = None) -> None:
        self.refresh()
        if "Checklist" in self._built:
            self.refresh_checklist()
        if text:
            self._info(title, text)

    # ── Queue ────────────────────────────────────────────────────────

    def _build_queue(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value=self.state.get("status", ""))
        cb = ttk.Combobox(bar, textvariable=self.status_var, values=STATUSES, state="readonly",
                          width=15)
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar(value=self.state.get("search", ""))
        e = ttk.Entry(bar, textvariable=self.search_var, width=18)
        e.pack(side="left", padx=(4, 8))
        e.bind("<Return>", lambda _e: self.refresh())
        self.closed_var = tk.BooleanVar(value=bool(self.state.get("closed")))
        ttk.Checkbutton(bar, text="Include finished", variable=self.closed_var,
                        command=self.refresh).pack(side="left")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        for text, cmd, lead in (("Handover…", self.show_handover, False),
                                ("Acknowledge", self.acknowledge, True),
                                ("Reject…", self.reject, True), ("Match…", self.match, True),
                                ("Create pupil…", self.create, True),
                                ("Complete…", self.complete, True),
                                ("Open pupil", self._open, False),
                                ("Export CSV…", self.export, False),
                                ("Refresh", self.refresh, False)):
            self._button(bar2, text, cmd, lead)
        self.tree = W.tree(tab, [("name", "Pupil", 200), ("dob", "Born", 90),
                                 ("upn", "UPN", 120), ("status", "Status", 110),
                                 ("starts", "Starts", 90), ("handover", "Handover", 110),
                                 ("matched", "Matched to", 200), ("note", "Note", 220)],
                           height=18, stretch={"note"}, tags=W.STANDARD_TAGS)
        self.tree.bind("<<TreeviewSelect>>", self._picked)
        self.tree.bind("<Double-1>", lambda _e: self.show_handover())

    def _picked(self, _e=None) -> None:
        sel = self.tree.selection()
        if sel:
            self.state["transition_id"] = sel[0]

    def refresh(self) -> None:
        self.state.update(status=self.status_var.get(), search=self.search_var.get().strip(),
                          closed=self.closed_var.get())
        try:
            rows = IP.queue(actor=self.principal, include_closed=self.closed_var.get(),
                            status=self.status_var.get() or None,
                            search=self.search_var.get().strip() or None)
            counts = IP.counts(actor=self.principal)
        except _ERRORS as e:
            self._err("Incoming from Primary", e)
            return
        except Exception as e:  # noqa: BLE001 - the platform queue unreachable
            self.summary_var.set(f"The platform transfer queue can't be read: {e}")
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        pupils = {}
        for i in rows:
            self.rows[i.transition_id] = i
            if i.pupil_id and i.pupil_id not in pupils:
                pupils[i.pupil_id] = P.get_pupil(i.pupil_id)
            p = pupils.get(i.pupil_id) if i.pupil_id else None
            handover = ("acknowledged" if i.acknowledged_at else "ready") if i.handover_ready \
                else "not yet"
            tag = "muted" if not i.is_open else "good" if p else \
                "warn" if i.handover_ready else ""
            self.tree.insert("", "end", iid=i.transition_id, tags=(tag,) if tag else (),
                             values=(i.name + i.tag,
                                     i.date_of_birth or "", i.upn or "", i.status_label,
                                     i.effective_date or "", handover,
                                     f"{p.display_name} ({p.admission_no})" if p else
                                     (f"application #{i.application_id}" if i.application_id
                                      else ""), i.reason or ""))
        tid = self.state.get("transition_id")
        if tid in self.rows:
            self.tree.selection_set(tid)
            self.tree.see(tid)
        self.summary_var.set("    ".join(f"{k}: {v}" for k, v in counts.items()) or
                             "No transfers from primary yet.")

    def show_handover(self) -> None:
        item = self._selected("Handover")
        if item is None:
            return
        try:
            h = IP.handover(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Handover", e)
            return
        W.text_window(self.parent, f"Handover — {item.name}", IP.handover_text(h),
                      size="720x560")

    def acknowledge(self) -> None:
        item = self._selected("Acknowledge")
        if item is None:
            return
        try:
            IP.acknowledge(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Acknowledge", e)
            return
        self._done("Acknowledge", f"Primary has been told the handover for {item.name} "
                                  "arrived.")

    def reject(self) -> None:
        item = self._selected("Reject")
        if item is None:
            return

        def save(v):
            IP.reject(item.transition_id, actor=self.principal, reason=v["reason"])
            self._done("Reject")
        W.form_dialog(self.parent, f"Reject transfer — {item.name}",
                      [("reason", "Reason (sent to primary)", "", "text")], save,
                      note="Rejecting ends the transfer; primary is told the reason.")

    def match(self) -> None:
        item = self._selected("Match")
        if item is None:
            return
        try:
            cands = IP.match_candidates(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Match", e)
            return
        win, frm = W.dialog(self.parent, f"Match — {item.name} ({item.date_of_birth})",
                            size="760x400")
        ttk.Label(frm, text="Records here that may be this pupil. Choose one, or type a pupil "
                            "id / admission number below.", foreground="#555").pack(anchor="w")
        t = W.tree(frm, [("kind", "Kind", 90), ("label", "Record", 380),
                         ("reason", "Why", 200)], height=10, stretch={"label"})
        for n, c in enumerate(cands):
            t.insert("", "end", iid=str(n), values=(c["kind"], c["label"], c["reason"]))
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Or pupil (id / admission no.):").pack(side="left")
        ref = tk.StringVar()
        ttk.Entry(row, textvariable=ref, width=16).pack(side="left", padx=4)

        def go() -> None:
            sel = t.selection()
            try:
                if sel:
                    c = cands[int(sel[0])]
                    out = (IP.match_pupil if c["kind"] == "pupil" else IP.match_application)(
                        item.transition_id, c["id"], actor=self.principal)
                elif ref.get().strip():
                    p = P.find_by_reference(ref.get().strip())
                    if p is None:
                        raise IP.NotFound(f"No pupil {ref.get().strip()}")
                    out = IP.match_pupil(item.transition_id, p.pupil_id, actor=self.principal)
                else:
                    messagebox.showinfo("Match", "Choose a record first.", parent=win)
                    return
            except _ERRORS as e:
                messagebox.showerror("Match", W.problems(e), parent=win)
                return
            win.destroy()
            self._done("Match", "Matched." + ("\n\n" + "\n".join(f"• {n}" for n in out.notes)
                                              if out.notes else ""))
        bar = ttk.Frame(frm)
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Match selected", command=go).pack(side="right")

    def create(self) -> None:
        item = self._selected("Create pupil")
        if item is None:
            return
        try:
            d = IP.new_pupil_defaults(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Create pupil", e)
            return
        allow = {"dup": False}

        def save(v):
            try:
                out = IP.create_pupil(item.transition_id, v, actor=self.principal,
                                      allow_duplicate=allow["dup"])
            except P.DuplicatePupil as e:
                if messagebox.askyesno("Possible duplicate", f"{e}\n\nMatch to that pupil "
                                       "instead? (No = create a second record anyway)",
                                       parent=self._top()):
                    out = IP.match_pupil(item.transition_id, e.existing.pupil_id,
                                         actor=self.principal)
                else:
                    allow["dup"] = True
                    raise IP.ValidationError(["Press Save again to create a second record"]) \
                        from None
            self._done("Create pupil", f"{out.pupil.display_name if out.pupil else ''} "
                                       "created.\n\n" + "\n".join(f"• {n}" for n in out.notes))
        W.form_dialog(self.parent, f"Create pupil — {item.name}", [
            ("legal_first_name", "Legal first name", d["legal_first_name"], None),
            ("middle_names", "Middle names", d["middle_names"], None),
            ("legal_last_name", "Legal last name", d["legal_last_name"], None),
            ("preferred_name", "Preferred name", d["preferred_name"], None),
            ("date_of_birth", "Date of birth", d["date_of_birth"], None),
            ("gender", "Gender", d["gender"], list(P.GENDERS)),
            ("upn", "UPN", d["upn"], None),
            ("year_group", "Year group", d["year_group"], [str(y) for y in P.YEAR_GROUPS]),
            ("form_group", "Form group", d["form_group"], None),
            ("admission_date", "Admission date", d["admission_date"], None),
            ("address_line1", "Address line 1", d.get("address_line1", ""), None),
            ("address_line2", "Address line 2", d.get("address_line2", ""), None),
            ("town", "Town", d.get("town", ""), None),
            ("postcode", "Postcode", d.get("postcode", ""), None),
            ("sen_status", "SEN (N / K / E)", d["sen_status"], list(P.SEN_STATUSES)),
            ("fsm_eligible", "Free school meals", d.get("fsm_eligible", False), "check"),
            ("eal", "English as an additional language", d.get("eal", False), "check")],
            save,
            note="From the primary handover (check gender if primary didn't send it). The "
                 "parents / carers in the handover are added as contacts.")

    def complete(self) -> None:
        item = self._selected("Complete")
        if item is None:
            return

        def save(v):
            IP.complete(item.transition_id, actor=self.principal,
                        start_date=v["start_date"] or None)
            self._done("Complete")
        W.form_dialog(self.parent, f"Complete transfer — {item.name}",
                      [("start_date", "First day here (blank = as planned)",
                        item.effective_date or "", None)], save,
                      note="Do this once the pupil has started. Primary closes their record.")

    def _open(self) -> None:
        item = self._selected("Open pupil")
        if item is None:
            return
        if item.pupil_id is None:
            self._info("Open pupil", "This incoming pupil isn't matched to a record yet.")
        elif self.open_pupil:
            self.open_pupil(item.pupil_id)

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile="incoming_primary.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = IP.export_csv(path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} pupil(s) to\n{path}")

    # ── Checklist ────────────────────────────────────────────────────

    def _build_checklist(self, tab) -> None:
        self.ck_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.ck_var, font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(4, 4))
        self._button(bar, "Tick", lambda: self.tick(True), True)
        self._button(bar, "Untick", lambda: self.tick(False), True)
        self._button(bar, "SEN to SENCO…", self.sen, True)
        b = ttk.Button(bar, text="Safeguarding file received", command=self.safeguarding)
        if not self.lead:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        self._button(bar, "Import KS2", self.ks2, True)
        self._button(bar, "Unmatch…", self.unmatch, True)
        self.ck_tree = W.tree(tab, [("done", "Done", 50), ("label", "Item", 360),
                                    ("owner", "Who", 110), ("by", "By", 110),
                                    ("at", "When", 150), ("src", "Kept by", 80)], height=12,
                              stretch={"label"}, tags=W.STANDARD_TAGS)

    def refresh_checklist(self) -> None:
        t = self.ck_tree
        t.delete(*t.get_children())
        item = self._selected(quiet=True)
        if item is None:
            self.ck_var.set("Select a pupil in the queue.")
            return
        self.ck_var.set(f"{item.name} — {item.status_label}")
        try:
            rows = IP.checklist(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Checklist", e)
            return
        for r in rows:
            t.insert("", "end", iid=r["key"], tags=("good",) if r["done"] else (), values=(
                "✓" if r["done"] else "", r["label"], r.get("owner") or "",
                r.get("done_by") or "", r.get("done_at") or "", r["source"]))

    def _ck_key(self, title: str) -> tuple[IP.Incoming, str] | None:
        item = self._selected(title)
        sel = self.ck_tree.selection() if item else ()
        if item is None:
            return None
        if not sel:
            self._info(title, "Select a checklist item first.")
            return None
        return item, sel[0]

    def tick(self, done: bool) -> None:
        got = self._ck_key("Tick" if done else "Untick")
        if got is None:
            return
        item, key = got
        if key == "sen_to_senco" and done:
            return self.sen()
        try:
            IP.tick(item.transition_id, key, actor=self.principal, done=done)
        except _ERRORS as e:
            self._err("Checklist", e)
            return
        self._done("Checklist")

    def sen(self) -> None:
        item = self._selected("SEN to SENCO")
        if item is None:
            return

        def save(v):
            IP.pass_sen_to_senco(item.transition_id, to=v["to"], actor=self.principal)
            self._done("SEN to SENCO")
        W.form_dialog(self.parent, f"SEN information to the SENCO — {item.name}",
                      [("to", "Passed to (SENCO's name)", "", None)], save)

    def safeguarding(self) -> None:
        item = self._selected("Safeguarding file")
        if item is None:
            return
        try:
            IP.record_safeguarding_file(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Safeguarding file", e)
            return
        self._done("Safeguarding file")

    def ks2(self) -> None:
        item = self._selected("Import KS2")
        if item is None:
            return
        try:
            k = IP.import_ks2(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Import KS2", e)
            return
        self._done("Import KS2", f"KS2 reading {k.reading_scaled or '-'}, maths "
                                 f"{k.maths_scaled or '-'} saved as prior attainment.")

    def unmatch(self) -> None:
        item = self._selected("Unmatch")
        if item is None:
            return

        def save(v: dict[str, Any]):
            IP.unmatch(item.transition_id, actor=self.principal, reason=v["reason"])
            self._done("Unmatch")
        W.form_dialog(self.parent, f"Unmatch — {item.name}",
                      [("reason", "Why was the match wrong?", "", None)], save)

    # ── Step log ─────────────────────────────────────────────────────

    def _build_log(self, tab) -> None:
        self.log_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.log_var, font=("", 11, "bold")).pack(anchor="w")
        ttk.Button(tab, text="Refresh", command=self.refresh_log).pack(anchor="w", pady=4)
        self.log_tree = W.tree(tab, [("at", "When (UTC)", 150), ("who", "Who", 120),
                                     ("step", "Step", 140), ("src", "Kept by", 80),
                                     ("note", "Note", 400)], height=16, stretch={"note"})

    def refresh_log(self) -> None:
        t = self.log_tree
        t.delete(*t.get_children())
        item = self._selected(quiet=True)
        if item is None:
            self.log_var.set("Select a pupil in the queue.")
            return
        self.log_var.set(item.name)
        try:
            rows = IP.step_log(item.transition_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Step log", e)
            return
        for r in rows:
            t.insert("", "end", values=(r["at"], r["who"], r["step"], r["source"], r["note"]))


def draw_incoming_primary(parent: ttk.Frame, *, principal: Principal, state: dict,
                          open_pupil: Callable[[int], None] | None = None
                          ) -> IncomingPrimaryPage:
    return IncomingPrimaryPage(parent, principal=principal, state=state, open_pupil=open_pupil)
