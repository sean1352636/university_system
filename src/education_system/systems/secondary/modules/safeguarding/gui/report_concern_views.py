"""Report a Safeguarding Concern - open to every member of staff.

Kept from the old screen: the "Raise concern" entry for staff who can't open
the safeguarding records (pupil, category, incident date / time, location,
description). New:

* **Report a concern** - the form KCSIE asks for: what you saw or heard, the
  child's own words, when and where, a body-map note of any injury, what you
  did straight away, who else was involved, and "is the child in immediate
  danger?" (urgent: the safeguarding team is e-mailed at once, or you are
  told who to phone).
* **My reports** - the concerns you reported with their status only (never
  the DSL's notes), and Add information… to add to one.
* **Who to contact** - the DSL and deputies with their phone numbers.

Rules: :func:`modules.safeguarding.domain.safeguarding.report_concern`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
TITLE = "Report a Safeguarding Concern"
_ERRORS = W.ERRORS
_DANGER = ("If a child is in immediate danger, call 999 and then speak to the DSL in person "
           "straight away. Don't investigate, don't promise to keep a secret, and don't ask "
           "leading questions - write down what was said in the child's own words.")


def team_text() -> str:
    team = SG.team()
    if not team:
        return "No safeguarding lead is set up yet - tell the headteacher."
    return "\n".join(f"{m['name']} ({m['team_role']})"
                     + (f"   phone {m['phone']}" if m["phone"] else "")
                     + (f"   {m['email']}" if m["email"] else "") for m in team)


class ReportConcernPage:
    TABS = ("Report a concern", "My reports", "Who to contact")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        activity_log.record("safeguarding.report_view")
        ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text=_DANGER, foreground="#a00", wraplength=820,
                  justify="left").pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else self.TABS[0]
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build = {"Report a concern": (self._build_form, lambda: None),
                 "My reports": (self._build_mine, self.refresh_mine),
                 "Who to contact": (self._build_team, self.refresh_team)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        try:
            build[1]()
        except _ERRORS as e:
            messagebox.showerror(TITLE, W.problems(e), parent=self._top())

    # ── The form ─────────────────────────────────────────────────────

    def _build_form(self, tab) -> None:
        from education_system.systems.secondary.modules.safeguarding.gui.safeguarding_views import (
            pupil_choices,
        )
        canvas = tk.Canvas(tab, highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        frm = ttk.Frame(canvas)
        frm.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frm, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.vars: dict[str, Any] = {}
        self.texts: dict[str, tk.Text] = {}
        row = 0

        def label(text: str) -> None:
            ttk.Label(frm, text=text).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=3)

        for key, text, kind in (
                ("pupil_id", "Pupil *", ("combo", pupil_choices())),
                ("category", "What kind of concern (if you know)",
                 ("ro", ["", *SG.CONCERN_CATEGORIES])),
                ("incident_date", "Date it happened (YYYY-MM-DD, blank = today)", None),
                ("incident_time", "Time (HH:MM)", None),
                ("location", "Where", None),
                ("description", "What you saw or heard *", 5),
                ("child_words", "What the child said - their own words", 4),
                ("body_map", "Any injury - where on the body, size, colour", 2),
                ("immediate_action", "What you did straight away", 3),
                ("people_involved", "Anyone else involved or who saw it", 2)):
            label(text)
            if isinstance(kind, int):
                t = tk.Text(frm, width=70, height=kind, wrap="word")
                t.grid(row=row, column=1, sticky="w", pady=3)
                self.texts[key] = t
            else:
                v = tk.StringVar()
                if kind and kind[0] == "combo":
                    w = ttk.Combobox(frm, textvariable=v, values=kind[1], width=50)
                elif kind:
                    w = ttk.Combobox(frm, textvariable=v, values=kind[1], state="readonly",
                                     width=36)
                else:
                    w = ttk.Entry(frm, textvariable=v, width=30)
                w.grid(row=row, column=1, sticky="w", pady=3)
                self.vars[key] = v
            row += 1
        self.danger = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="The child is in immediate danger / this is urgent "
                                  "(the safeguarding team is alerted now)",
                        variable=self.danger).grid(row=row, column=1, sticky="w", pady=6)
        row += 1
        bar = ttk.Frame(frm)
        bar.grid(row=row, column=1, sticky="w", pady=(6, 0))
        self.submit_btn = ttk.Button(bar, text="Submit to the DSL", command=self.submit)
        self.submit_btn.pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=6)
        if not self.principal.is_staff:
            self.submit_btn.state(["disabled"])

    def _values(self) -> dict[str, Any]:
        out = {k: v.get() for k, v in self.vars.items()}
        out.update({k: t.get("1.0", "end").strip() for k, t in self.texts.items()})
        out["immediate_danger"] = self.danger.get()
        return out

    def clear(self) -> None:
        for v in self.vars.values():
            v.set("")
        for t in self.texts.values():
            t.delete("1.0", "end")
        self.danger.set(False)

    def submit(self) -> None:
        data = self._values()
        if data["immediate_danger"] and not messagebox.askyesno(
                TITLE, "You've said the child is in immediate danger. If so, call 999 now.\n\n"
                       "Submit as URGENT and alert the safeguarding team?",
                parent=self._top()):
            return
        try:
            rep, alert = SG.report_concern(data, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror(TITLE, W.problems(e, "Not sent yet:"), parent=self._top())
            return
        self.clear()
        if "My reports" in self._built:
            self.refresh_mine()
        if not rep.urgent:
            messagebox.showinfo(TITLE, f"Thank you. Concern #{rep.concern_id} has gone to the "
                                       "DSL.", parent=self._top())
            return
        self._alerted(rep, alert)

    def _alerted(self, rep: SG.MyReport, alert: dict) -> None:
        if alert.get("message_id"):
            from education_system.systems.secondary.modules.communication.gui import email_views

            def done(_report, error) -> None:
                try:
                    messagebox.showinfo(TITLE, f"Urgent concern #{rep.concern_id} sent. "
                                        f"{alert['emails']} member(s) of the safeguarding team "
                                        "e-mailed" + (f" (delivery problem: {error} - phone "
                                                      "them)" if error else "")
                                        + ".\n\nNow find the DSL in person.\n\n" + team_text(),
                                        parent=self._top())
                except tk.TclError:
                    pass
            email_views.deliver_in_background(self.parent, alert["message_id"], self.principal,
                                              done)
            return
        phones = "\n".join(f"{m['name']} ({m['team_role']})"
                           + (f": {m['phone']}" if m["phone"] else ": no phone recorded")
                           for m in alert.get("phone", [])) or "Ask the school office."
        messagebox.showwarning(TITLE, f"Urgent concern #{rep.concern_id} is recorded, but no "
                                      "one on the safeguarding team has an e-mail address.\n\n"
                                      f"PHONE THE DSL NOW:\n{phones}", parent=self._top())

        def save(v):
            SG.record_phoned(rep.concern_id, actor=self.principal, who=v["who"])
        W.form_dialog(self.parent, "Who did you speak to?",
                      [("who", "Name of the DSL / deputy you spoke to", "", None)], save,
                      note="Record it once you have passed the concern on by phone.")

    # ── My reports ───────────────────────────────────────────────────

    def _build_mine(self, tab) -> None:
        ttk.Label(tab, text="The concerns you reported. The DSL's notes and decisions are "
                            "confidential - you see the status only.",
                  foreground="#555").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        for text, cmd in (("Add information…", self.add_info), ("Refresh", self.refresh_mine)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.mine = W.tree(tab, [("id", "No.", 50), ("date", "Reported", 90),
                                 ("pupil", "Pupil", 240), ("category", "Kind", 200),
                                 ("urgent", "Urgent", 60), ("status", "Status", 220)],
                           stretch={"pupil"}, tags=W.STANDARD_TAGS, height=14)
        self.mine.bind("<Double-1>", lambda _e: self.add_info())

    def refresh_mine(self) -> None:
        self.mine.delete(*self.mine.get_children())
        for r in SG.my_reports(actor=self.principal):
            self.mine.insert("", "end", iid=str(r.concern_id),
                             tags=("muted",) if r.status == "Closed" else (),
                             values=(r.concern_id, r.raised_date,
                                     f"{r.pupil_name} ({r.admission_no})", r.category,
                                     "Yes" if r.urgent else "", r.status))

    def add_info(self) -> None:
        sel = self.mine.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select one of your reports first.", parent=self._top())
            return

        def save(v):
            SG.add_information(int(sel[0]), v["text"], actor=self.principal)
            messagebox.showinfo(TITLE, "Added - the DSL can see it.", parent=self._top())
        W.form_dialog(self.parent, f"Add to concern #{sel[0]}",
                      [("text", "What you have since seen or heard", "", "text")], save,
                      note="A report can't be changed once it's in - add to it instead.")

    # ── Who to contact ───────────────────────────────────────────────

    def _build_team(self, tab) -> None:
        ttk.Label(tab, text="Designated safeguarding lead and deputies",
                  font=("", 11, "bold")).pack(anchor="w")
        self.team_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.team_var, justify="left",
                  font=("TkFixedFont", 10)).pack(anchor="w", pady=6)
        ttk.Label(tab, text=_DANGER, wraplength=800, justify="left").pack(anchor="w")

    def refresh_team(self) -> None:
        self.team_var.set(team_text())


def draw_report_concern(parent: ttk.Frame, *, principal: Principal, state: dict,
                        open_pupil: Callable[[int], None] | None = None) -> ReportConcernPage:
    return ReportConcernPage(parent, principal=principal, state=state, open_pupil=open_pupil)
