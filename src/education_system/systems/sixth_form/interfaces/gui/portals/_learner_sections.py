"""Student portal sections added after the first twelve tabs.

My Plan, Exams, Projects & Placements, Library, Surveys, Wellbeing &
Help and Study Planner. Mixed into
:class:`.student_portal_gui.StudentPortalGUI`, which supplies ``sid``
(always ``principal.student_id``), ``principal``, ``root``, ``refresh``
and ``status_var``. Every read and action goes through
:mod:`...parent_portal.learner_self_service` with ``self.sid`` — no id
is ever read from the screen except row ids of the learner's own
records, which the domain re-checks against ``self.sid``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    learner_self_service as ls,
)

logger = logging.getLogger(__name__)

_MUTED = "#7f8c8d"


def _table(parent, columns, *, height: int = 12) -> ttk.Treeview:
    from education_system.systems.sixth_form.interfaces.gui.portals.student_portal_gui import (
        _table as table,
    )
    return table(parent, columns, height=height)


def _dash(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


def _set_text(widget: tk.Text, body: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", body)
    widget.configure(state="disabled")


def _form(win: tk.Toplevel, title: str) -> ttk.Frame:
    win.title(title)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    return frm


class LearnerSectionsMixin:
    """The learner-only tabs. Needs sid, principal, root, refresh."""

    sid: str
    principal: Any
    root: tk.Tk

    # ── My Plan ──────────────────────────────────────────────────────

    def _myplan(self, f: ttk.Frame) -> None:
        data = ls.my_plan(self.sid)
        box = ttk.LabelFrame(f, text="My targets", padding=6)
        box.pack(fill="x", pady=(0, 8))
        ttk.Label(box, text="MEG is the minimum expected grade from your GCSE "
                            "baseline; your target is the grade your teachers set.",
                  foreground=_MUTED).pack(anchor="w")
        tree = _table(box, (("subject", "Subject", 220), ("meg", "MEG", 70),
                            ("target", "Target", 80), ("asp", "Aspirational", 100),
                            ("current", "Working at", 100), ("status", "On track?", 120),
                            ("review", "Next review", 100)),
                      height=min(max(len(data["targets"]), 2), 6))
        for t in data["targets"]:
            tree.insert("", "end", values=(t["subject"], _dash(t["meg"]), _dash(t["target"]),
                                           _dash(t["aspirational"]), _dash(t["current"]),
                                           _dash(t["status"]), _dash(t["next_review"])))
        if data["actions"]:
            acts = _table(box, (("subject", "Subject", 160), ("action", "Action step", 380),
                                ("due", "Due", 100), ("status", "Status", 110)),
                          height=min(len(data["actions"]), 4))
            acts.tag_configure("overdue", foreground="#c0392b")
            for a in data["actions"]:
                acts.insert("", "end", tags=("overdue",) if a["overdue"] else (),
                            values=(_dash(a["subject"]), a["description"],
                                    _dash(a["due"]), a["status"]))

        box = ttk.LabelFrame(f, text="My individual learning plan", padding=6)
        box.pack(fill="both", expand=True)
        plans = data["plans"]
        if not plans:
            ttk.Label(box, text="You have no learning plan shared with you yet.").pack(
                anchor="w")
            return
        panes = ttk.Panedwindow(box, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=3)
        ptree = _table(left, (("title", "Plan", 200), ("status", "Status", 80)), height=6)
        for i, p in enumerate(plans):
            ptree.insert("", "end", iid=str(i), values=(p["title"], p["status"]))
        info = tk.Text(right, height=5, wrap="word", state="disabled", padx=6, pady=4)
        info.pack(fill="x")
        gtree = _table(right, (("goal", "Goal", 300), ("cat", "Area", 110),
                               ("by", "By", 100), ("status", "Status", 110)), height=4)
        rtree = _table(right, (("date", "Review", 100), ("by", "Reviewer", 140),
                               ("progress", "Progress", 110), ("mine", "My comment", 90)),
                       height=4)
        detail = tk.Text(right, height=5, wrap="word", state="disabled", padx=6, pady=4)
        detail.pack(fill="x", pady=(4, 0))
        ttk.Label(right, text="My comment on this review (only you can change it):").pack(
            anchor="w", pady=(4, 0))
        mine = tk.Text(right, height=3, wrap="word")
        mine.pack(fill="x")
        state: dict[str, Any] = {"plan": None, "review": None}

        def show_plan(_e=None) -> None:
            sel = ptree.selection()
            if not sel:
                return
            p = plans[int(sel[0])]
            state["plan"], state["review"] = p, None
            _set_text(info, "\n".join(
                f"{label}: {p[key]}" for label, key in (
                    ("Type", "type"), ("Lead", "lead"), ("Next review", "next_review"),
                    ("Strengths", "strengths"), ("Strategies", "strategies"),
                    ("Support", "support"), ("Success looks like", "success_criteria"))
                if p.get(key)))
            gtree.delete(*gtree.get_children())
            for g in p["goals"]:
                gtree.insert("", "end", values=(g["title"], g["category"],
                                                _dash(g["target_date"]), g["status"]))
            rtree.delete(*rtree.get_children())
            for i, r in enumerate(p["reviews"]):
                rtree.insert("", "end", iid=str(i), values=(
                    r["date"], _dash(r["reviewer"]), _dash(r["progress"]),
                    "Yes" if r["student_comment"] else "—"))
            _set_text(detail, "")
            mine.delete("1.0", "end")

        def show_review(_e=None) -> None:
            sel = rtree.selection()
            if not sel or state["plan"] is None:
                return
            r = state["plan"]["reviews"][int(sel[0])]
            state["review"] = r
            _set_text(detail, f"Comments: {_dash(r['comments'])}\n"
                              f"Next steps: {_dash(r['next_steps'])}\n"
                              f"Next review: {_dash(r['next_review'])}")
            mine.delete("1.0", "end")
            mine.insert("1.0", r["student_comment"] or "")

        def save_comment() -> None:
            r = state["review"]
            if r is None:
                messagebox.showinfo("My Plan", "Choose a review first.", parent=self.root)
                return
            try:
                ls.set_review_comment(self.sid, r["review_id"],
                                      mine.get("1.0", "end").strip() or None)
            except Exception as e:      # ValidationError
                messagebox.showerror("My Plan", str(e), parent=self.root)
                return
            messagebox.showinfo("My Plan", "Your comment has been saved.", parent=self.root)
            self.refresh()

        ttk.Button(right, text="Save my comment", command=save_comment).pack(
            anchor="e", pady=(4, 0))
        ptree.bind("<<TreeviewSelect>>", show_plan)
        rtree.bind("<<TreeviewSelect>>", show_review)
        ptree.selection_set("0")
        show_plan()

    # ── Exams ────────────────────────────────────────────────────────

    def _exams(self, f: ttk.Frame) -> None:
        data = ls.exams(self.sid)
        ttk.Label(f, text=f"Candidate number: {_dash(data['candidate_no'])}    "
                          f"Access arrangements: {data['arrangements'] or 'none recorded'}",
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
        box = ttk.LabelFrame(f, text="My exam entries and timetable", padding=6)
        box.pack(fill="both", expand=True)
        if not data["entries"]:
            ttk.Label(box, text="You have not been entered for any exams yet.").pack(
                anchor="w")
        else:
            tree = _table(box, (("date", "Date", 95), ("sess", "Session", 60),
                                ("time", "Time", 95), ("subject", "Subject", 150),
                                ("paper", "Paper", 200), ("code", "Code", 80),
                                ("board", "Board", 70), ("room", "Room", 80),
                                ("seat", "Seat", 50), ("status", "Entry", 80),
                                ("clash", "Clash", 260)), height=10)
            tree.tag_configure("clash", foreground="#c0392b")
            for e in data["entries"]:
                time = (f"{e['start']}–{e['end']}" if e["start"] else "—")
                if e["finish"] and e["finish"] != e["end"]:
                    time += f" (to {e['finish']})"
                tree.insert("", "end", tags=("clash",) if e["clash"] else (), values=(
                    _dash(e["date"]), _dash(e["session"]), time, e["subject"],
                    _dash(e["paper"]), e["paper_code"], e["board"], _dash(e["room"]),
                    _dash(e["seat"]), e["entry_status"], _dash(e["clash"])))
        if data["contingency"]:
            ttk.Label(box, text="Keep free (contingency): " + "; ".join(
                f"{c['date']} {c['session']} ({c['series']})" for c in data["contingency"]),
                foreground="#7a5800", wraplength=1100).pack(anchor="w", pady=(4, 0))
        box = ttk.LabelFrame(f, text="Released results", padding=6)
        box.pack(fill="both", expand=True, pady=(8, 0))
        ttk.Label(box, text="Results appear here only once they have been released "
                            "to you on results day.", foreground=_MUTED).pack(anchor="w")
        rtree = _table(box, (("series", "Series", 110), ("subject", "Subject", 200),
                             ("what", "Paper / qualification", 260), ("grade", "Grade", 70),
                             ("marks", "Marks / UMS", 100)), height=6)
        for q in data["qualification_results"]:
            rtree.insert("", "end", values=(q["series"], q["subject"],
                                            f"Qualification ({_dash(q['type'])})",
                                            q["grade"], _dash(q["ums"])))
        for r in data["results"]:
            rtree.insert("", "end", values=(f"{r['season']} {r['year']}", r["subject"],
                                            _dash(r["paper"]), r["grade"],
                                            _dash(r["marks"] if r["marks"] is not None
                                                  else r["ums"])))

    # ── Projects & placements ────────────────────────────────────────

    def _projects(self, f: ttk.Frame) -> None:
        data = ls.projects(self.sid)
        panes = ttk.Panedwindow(f, orient="vertical")
        panes.pack(fill="both", expand=True)
        epq_box = ttk.LabelFrame(panes, text="Extended Project (EPQ)", padding=6)
        we_box = ttk.LabelFrame(panes, text="Work experience", padding=6)
        car_box = ttk.LabelFrame(panes, text="Careers guidance", padding=6)
        panes.add(epq_box, weight=3)
        panes.add(we_box, weight=1)
        panes.add(car_box, weight=1)

        epq = data["epq"]
        if epq is None:
            ttk.Label(epq_box, text="You are not doing an EPQ.").pack(anchor="w")
        else:
            ttk.Label(epq_box, text=f"{epq['title']} · {epq['artefact']} · stage "
                                    f"{epq['stage']} · supervisor {_dash(epq['supervisor'])}",
                      font=("", 10, "bold")).pack(anchor="w")
            if epq["question"]:
                ttk.Label(epq_box, text=f"Question: {epq['question']}",
                          wraplength=1100).pack(anchor="w")
            ttk.Label(epq_box, text=f"Production log: {epq['hours']}"
                      + (" · authenticated by your supervisor" if epq["authenticated"]
                         else ""), foreground=_MUTED).pack(anchor="w")
            bar = ttk.Frame(epq_box)
            bar.pack(fill="x", pady=(4, 4))
            if epq["log_open"]:
                ttk.Button(bar, text="Add a log entry…",
                           command=self._epq_log_dialog).pack(side="left")
            row = ttk.Frame(epq_box)
            row.pack(fill="both", expand=True)
            left, right = ttk.Frame(row), ttk.Frame(row)
            left.pack(side="left", fill="both", expand=True)
            right.pack(side="left", fill="both", expand=True, padx=(8, 0))
            ms = _table(left, (("m", "Milestone", 180), ("due", "Due", 90),
                               ("done", "Done", 90), ("status", "Status", 90)), height=4)
            for m in epq["milestones"]:
                ms.insert("", "end", values=(m["milestone"], _dash(m["due"]),
                                             _dash(m["done"]), m["status"]))
            log = _table(right, (("date", "Date", 90), ("h", "Hours", 60),
                                 ("act", "Activity", 260), ("ref", "Reflection", 220)),
                         height=4)
            for e in epq["log"]:
                log.insert("", "end", values=(e["date"], f"{e['hours']:g}", e["activity"],
                                              _dash(e["reflection"])))

        if not data["placements"]:
            ttk.Label(we_box, text="No work experience placements recorded.").pack(
                anchor="w")
        else:
            we = _table(we_box, (("emp", "Employer", 200), ("role", "Role", 150),
                                 ("dates", "Dates", 180), ("status", "Status", 100),
                                 ("hours", "Hours", 120), ("sup", "Supervisor", 140),
                                 ("consent", "Parent consent", 110)), height=3)
            for p in data["placements"]:
                req = f" / {p['hours_required']:g}" if p["hours_required"] else ""
                we.insert("", "end", values=(
                    p["employer"], _dash(p["role"]), f"{p['start']} → {p['end']}",
                    p["status"], f"{p['hours_done']:g}{req}", _dash(p["supervisor"]),
                    "Yes" if p["consent"] else "Needed"))

        a = data["aspiration"]
        if a:
            ttk.Label(car_box, text=f"My plans: {a['pathway']}"
                      + "".join(f" · {lbl} {a[k]}" for lbl, k in (
                          ("career", "career"), ("sector", "sector"),
                          ("employer", "employer"), ("course", "course")) if a[k]),
                      font=("", 10, "bold")).pack(anchor="w")
        if not data["careers"]:
            ttk.Label(car_box, text="No careers guidance meetings recorded yet.").pack(
                anchor="w")
        else:
            ct = _table(car_box, (("date", "Date", 90), ("who", "Adviser", 140),
                                  ("type", "Type", 140), ("topics", "Topics", 240),
                                  ("plan", "Action plan", 280), ("fu", "Follow-up", 90)),
                        height=3)
            for s in data["careers"]:
                ct.insert("", "end", values=(s["date"], _dash(s["adviser"]), s["type"],
                                             _dash(s["topics"]), _dash(s["action_plan"]),
                                             _dash(s["follow_up"])))

    def _epq_log_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.transient(self.root)
        frm = _form(win, "EPQ production log")
        vars_ = {k: tk.StringVar(value=v) for k, v in (
            ("date", _dt.date.today().isoformat()), ("hours", ""), ("activity", ""))}
        for r, (label, key) in enumerate((("Date (YYYY-MM-DD)", "date"),
                                          ("Hours", "hours"), ("What you did", "activity"))):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(frm, textvariable=vars_[key], width=44).grid(row=r, column=1,
                                                                   sticky="ew", pady=3)
        ttk.Label(frm, text="Reflection (optional)").grid(row=3, column=0, sticky="nw")
        ref = tk.Text(frm, width=44, height=4)
        ref.grid(row=3, column=1, sticky="ew", pady=3)

        def save() -> None:
            try:
                ls.add_epq_log(self.sid, entry_date=vars_["date"].get().strip(),
                               hours=vars_["hours"].get().strip(),
                               activity=vars_["activity"].get().strip(),
                               reflection=ref.get("1.0", "end").strip() or None)
            except Exception as e:      # ValidationError
                messagebox.showerror("EPQ production log", str(e), parent=win)
                return
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Add entry", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ── Library ──────────────────────────────────────────────────────

    def _library(self, f: ttk.Frame) -> None:
        data = ls.library(self.sid)
        top = ttk.Frame(f)
        top.pack(fill="x")
        loans = ttk.LabelFrame(top, text="On loan to me", padding=6)
        loans.pack(side="left", fill="both", expand=True)
        holds = ttk.LabelFrame(top, text="My reservations", padding=6)
        holds.pack(side="left", fill="both", expand=True, padx=(8, 0))
        lt = _table(loans, (("title", "Title", 280), ("due", "Due back", 100),
                            ("ren", "Renewals", 70)), height=6)
        lt.tag_configure("overdue", foreground="#c0392b")
        for x in data["loans"]:
            lt.insert("", "end", tags=("overdue",) if x["overdue"] else (),
                      values=(x["title"], x["due_on"] + (" (overdue)" if x["overdue"]
                                                         else ""), x["renewals"]))
        if not data["loans"]:
            ttk.Label(loans, text="Nothing on loan.").pack(anchor="w")
        ht = _table(holds, (("title", "Title", 240), ("status", "Status", 80),
                            ("pos", "Queue", 60), ("by", "Collect by", 100)), height=6)
        for x in data["reservations"]:
            ht.insert("", "end", values=(x["title"], x["status"],
                                         _dash(x["queue_position"]), _dash(x["collect_by"])))
        if data["balance"]:
            ttk.Label(f, text=f"Library charges outstanding: £{data['balance']:,.2f} — "
                              "see the library desk.", foreground="#c0392b").pack(
                anchor="w", pady=(6, 0))
        box = ttk.LabelFrame(f, text="Reading lists for my subjects", padding=6)
        box.pack(fill="both", expand=True, pady=(8, 0))
        if not data["reading_lists"]:
            ttk.Label(box, text="No reading lists for your subjects yet.").pack(anchor="w")
            return
        frame = ttk.Frame(box)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=("req", "note"), show="tree headings")
        tree.heading("#0", text="List / title")
        tree.heading("req", text="Required?")
        tree.heading("note", text="Note")
        tree.column("#0", width=420)
        tree.column("req", width=100)
        tree.column("note", width=360)
        bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        for rl in data["reading_lists"]:
            node = tree.insert("", "end", open=True,
                               text=f"{rl['title']} ({_dash(rl['subject'])})")
            for i in rl["items"]:
                tree.insert(node, "end", text=i["title"],
                            values=(i["requirement"], _dash(i["note"])))

    # ── Surveys ──────────────────────────────────────────────────────

    def _surveys(self, f: ttk.Frame) -> None:
        rows = ls.surveys(self.sid)
        if not rows:
            ttk.Label(f, text="There are no surveys open for you at the moment.").pack(
                anchor="w")
            return
        ttk.Label(f, text="Anonymous surveys never record your name with your "
                          "answers. You can complete each survey once.",
                  foreground=_MUTED).pack(anchor="w", pady=(0, 4))
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 4))
        tree = _table(f, (("name", "Survey", 360), ("closes", "Closes", 100),
                          ("anon", "Anonymous", 90), ("state", "Status", 110)))
        for i, s in enumerate(rows):
            tree.insert("", "end", iid=str(i), values=(
                s["name"], _dash(s["close_on"]), "Yes" if s["anonymous"] else "No — named",
                "Completed" if s["completed"] else "To do"))

        def take() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Surveys", "Choose a survey first.", parent=self.root)
                return
            s = rows[int(sel[0])]
            if s["completed"]:
                messagebox.showinfo("Surveys", "You have already completed this survey.",
                                    parent=self.root)
                return
            self._survey_dialog(s)

        ttk.Button(bar, text="Take selected survey…", command=take).pack(side="left")

    def _survey_dialog(self, s: dict[str, Any]) -> None:
        win = tk.Toplevel(self.root)
        win.transient(self.root)
        frm = _form(win, s["name"])
        if s["description"]:
            ttk.Label(frm, text=s["description"], wraplength=560).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(frm, text=("Anonymous — your name is not stored with your answers."
                             if s["anonymous"] else
                             "Named survey — your name is recorded with your answers."),
                  foreground=_MUTED).grid(row=1, column=0, columnspan=2, sticky="w")
        getters: dict[int, Any] = {}
        for idx, q in enumerate(s["questions"]):
            r = idx + 2
            ttk.Label(frm, text=q["prompt"] + (" *" if q["required"] else ""),
                      wraplength=320).grid(row=r, column=0, sticky="nw", pady=3)
            kind = q["type"]
            if kind == "Multi Choice":
                lb = tk.Listbox(frm, selectmode="multiple", height=min(len(q["choices"]), 5),
                                exportselection=False)
                for c in q["choices"]:
                    lb.insert("end", c)
                lb.grid(row=r, column=1, sticky="ew", pady=3)
                getters[idx] = (lambda lb=lb: [lb.get(i) for i in lb.curselection()])
                continue
            var = tk.StringVar()
            if kind in ("Likert", "Yes/No", "Single Choice"):
                values = {"Likert": ["1", "2", "3", "4", "5"],
                          "Yes/No": ["Yes", "No"]}.get(kind, q["choices"])
                ttk.Combobox(frm, textvariable=var, values=values, state="readonly",
                             width=40).grid(row=r, column=1, sticky="ew", pady=3)
            else:
                ttk.Entry(frm, textvariable=var, width=43).grid(row=r, column=1,
                                                                sticky="ew", pady=3)
            getters[idx] = var.get

        def submit() -> None:
            answers = {}
            for idx, get in getters.items():
                v = get()
                if v not in ("", [], None):
                    answers[idx] = v
            try:
                ls.submit_survey(self.sid, s["survey_id"], answers,
                                 name=getattr(self, "me", {}).get("full_name"))
            except Exception as e:      # ValidationError
                messagebox.showerror(s["name"], str(e), parent=win)
                return
            messagebox.showinfo(s["name"], "Thank you — your response has been recorded.",
                                parent=win)
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=len(s["questions"]) + 2, column=0, columnspan=2, sticky="e",
                  pady=(8, 0))
        ttk.Button(btns, text="Submit", command=submit).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ── Wellbeing & help ─────────────────────────────────────────────

    def _wellbeing(self, f: ttk.Frame) -> None:
        box = ttk.LabelFrame(f, text="Need help now?", padding=8)
        box.pack(fill="x", pady=(0, 8))
        for line in ls.urgent_help():
            ttk.Label(box, text="• " + line, wraplength=1100).pack(anchor="w")
        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Ask for support…", command=self._support_dialog).pack(
            side="left")
        ttk.Button(bar, text="Report a concern…", command=self._concern_dialog).pack(
            side="left", padx=(6, 0))

        box = ttk.LabelFrame(f, text="My requests for support", padding=6)
        box.pack(fill="both", expand=True)
        reqs = ls.my_support_requests(self.sid)
        if not reqs:
            ttk.Label(box, text="You have not asked for support through the portal.").pack(
                anchor="w")
        tree = _table(box, (("date", "Asked", 100), ("type", "Kind of help", 180),
                            ("issue", "What you said", 420), ("status", "Status", 110),
                            ("who", "With", 140)), height=5)
        for r in reqs:
            tree.insert("", "end", values=(r["date"], r["type"], _dash(r["issue"])[:120],
                                           r["status"], _dash(r["assigned_to"])))
        receipts = ls.my_concern_receipts(self.principal)
        if receipts:
            ttk.Label(f, text="Concerns you have reported (passed to the DSL): " + ", ".join(
                f"#{r['reference']} ({(r['filed'] or '')[:10]})" for r in receipts),
                foreground=_MUTED, wraplength=1100).pack(anchor="w", pady=(6, 0))
        res = ls.saved_help_resources(self.sid)
        if res:
            box = ttk.LabelFrame(f, text="Help resources I have saved", padding=6)
            box.pack(fill="x", pady=(8, 0))
            rt = _table(box, (("title", "Resource", 240), ("cat", "Type", 100),
                              ("how", "Link / contact", 360)), height=min(len(res), 4))
            for r in res:
                rt.insert("", "end", values=(r["title"], r["category"],
                                             _dash(r["url"] or r["contact"])))

    def _support_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.transient(self.root)
        frm = _form(win, "Ask for support")
        types = list(ls.support_types())
        kind = tk.StringVar(value=types[0])
        urgent = tk.BooleanVar(value=False)
        ttk.Label(frm, text="What kind of help").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(frm, textvariable=kind, values=types, state="readonly",
                     width=40).grid(row=0, column=1, sticky="ew")
        ttk.Label(frm, text="Tell us a little more").grid(row=1, column=0, sticky="nw")
        text = tk.Text(frm, width=44, height=6, wrap="word")
        text.grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(frm, text="It's urgent", variable=urgent).grid(row=2, column=1,
                                                                       sticky="w")
        ttk.Label(frm, text="If you are worried about your safety or someone else's, "
                            "use 'Report a concern' instead.", foreground=_MUTED,
                  wraplength=440).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

        def send() -> None:
            try:
                rid = ls.request_support(self.sid, support_type=kind.get(),
                                         issue=text.get("1.0", "end").strip(),
                                         referrer=self.principal.username,
                                         urgent=urgent.get())
            except Exception as e:      # ValidationError
                messagebox.showerror("Ask for support", str(e), parent=win)
                return
            messagebox.showinfo("Ask for support", f"Request #{rid} sent to the student "
                                "support team.", parent=win)
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Send", command=send).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    def _concern_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.transient(self.root)
        frm = _form(win, "Report a concern")
        ttk.Label(frm, text="This goes straight to the college's Designated Safeguarding "
                            "Lead. If anyone is in immediate danger, call 999 now.",
                  wraplength=460, foreground="#c0392b").grid(row=0, column=0, columnspan=2,
                                                             sticky="w", pady=(0, 6))
        topics, subjects = list(ls.concern_topics()), list(ls.concern_subjects())
        topic, about = tk.StringVar(value=topics[-1]), tk.StringVar(value=subjects[0])
        unsafe = tk.BooleanVar(value=False)
        ttk.Label(frm, text="What is it about").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(frm, textvariable=topic, values=topics, state="readonly",
                     width=42).grid(row=1, column=1, sticky="ew")
        ttk.Label(frm, text="Who is it about").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(frm, textvariable=about, values=subjects, state="readonly",
                     width=42).grid(row=2, column=1, sticky="ew")
        ttk.Label(frm, text="What has happened").grid(row=3, column=0, sticky="nw")
        text = tk.Text(frm, width=46, height=7, wrap="word")
        text.grid(row=3, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(frm, text="I don't feel safe right now", variable=unsafe).grid(
            row=4, column=1, sticky="w")

        def send() -> None:
            try:
                msg = ls.report_concern(self.principal, text.get("1.0", "end").strip(),
                                        topic=topic.get(), about=about.get(),
                                        unsafe_now=unsafe.get())
            except Exception as e:      # ValidationError
                messagebox.showerror("Report a concern", str(e), parent=win)
                return
            messagebox.showinfo("Report a concern", msg, parent=win)
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Send to the DSL", command=send).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ── Study planner ────────────────────────────────────────────────

    def _study(self, f: ttk.Frame) -> None:
        data = ls.study_plan(self.sid)
        s = data["summary"]
        ttk.Label(f, text=f"{s['total']} sessions · {s['completed']} done · {s['open']} "
                          f"to do · {s['overdue']} overdue · {s['actual_minutes']} of "
                          f"{s['planned_minutes']} planned minutes studied",
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
        if not data["tasks"]:
            ttk.Label(f, text="You have no study sessions planned yet. Ask your tutor "
                              "to help you set up a revision plan.").pack(anchor="w")
            return
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 4))
        tree = _table(f, (("date", "Date", 95), ("time", "Start", 60),
                          ("subject", "Subject", 160), ("title", "Session", 300),
                          ("type", "Type", 110), ("mins", "Mins", 80),
                          ("prio", "Priority", 80), ("status", "Status", 100)))
        tree.tag_configure("overdue", foreground="#c0392b")
        tasks = {str(t["task_id"]): t for t in data["tasks"]}
        for t in data["tasks"]:
            mins = (f"{t['actual']}/{t['planned']}" if t["actual"]
                    else _dash(t["planned"]))
            tree.insert("", "end", iid=str(t["task_id"]),
                        tags=("overdue",) if t["overdue"] else (),
                        values=(_dash(t["date"]), t["start"], _dash(t["subject"]),
                                t["title"], t["type"], mins, t["priority"],
                                "Overdue" if t["overdue"] else t["status"]))

        def selected() -> dict[str, Any] | None:
            sel = tree.selection()
            t = tasks.get(sel[0]) if sel else None
            if t is None or not t["open"]:
                messagebox.showinfo("Study Planner", "Choose a session that is still to do.",
                                    parent=self.root)
                return None
            return t

        def start() -> None:
            t = selected()
            if t is None:
                return
            try:
                ls.start_study_session(self.sid, t["task_id"])
            except Exception as e:
                messagebox.showerror("Study Planner", str(e), parent=self.root)
                return
            self.refresh()

        def done() -> None:
            t = selected()
            if t is not None:
                self._study_done_dialog(t)

        ttk.Button(bar, text="Start selected", command=start).pack(side="left")
        ttk.Button(bar, text="Mark selected done…", command=done).pack(side="left",
                                                                      padx=(6, 0))

    def _study_done_dialog(self, t: dict[str, Any]) -> None:
        win = tk.Toplevel(self.root)
        win.transient(self.root)
        frm = _form(win, "Session done")
        ttk.Label(frm, text=t["title"], font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w")
        mins = tk.StringVar(value=str(t["planned"] or ""))
        ttk.Label(frm, text="Minutes spent (optional)").grid(row=1, column=0, sticky="w",
                                                             pady=3)
        ttk.Entry(frm, textvariable=mins, width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="How did it go? (optional)").grid(row=2, column=0, sticky="nw")
        ref = tk.Text(frm, width=40, height=4, wrap="word")
        ref.grid(row=2, column=1, sticky="ew", pady=3)

        def save() -> None:
            raw = mins.get().strip()
            if raw and not raw.isdigit():
                messagebox.showerror("Session done", "Minutes must be a whole number.",
                                     parent=win)
                return
            try:
                ls.finish_study_session(self.sid, t["task_id"],
                                        actual_minutes=int(raw) if raw else None,
                                        reflection=ref.get("1.0", "end").strip() or None)
            except Exception as e:
                messagebox.showerror("Session done", str(e), parent=win)
                return
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Mark done", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)
