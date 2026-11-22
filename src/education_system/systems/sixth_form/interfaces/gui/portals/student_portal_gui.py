"""Student self-service window for the Sixth Form System.

The launcher sends anyone signed in with the ``student`` role here
instead of the staff window. Everything shown is the signed-in learner's
own record: every read goes through
:mod:`...parent_portal.learner_view` with ``principal.student_id`` and
nothing else — there is no student picker and no id is ever taken from
the screen.

Withheld until released: embargoed exam results, unreleased coursework
marks, predicted grades that have not gone out on a published report,
and report cards not yet published.

Actions: report an absence / self-certify (attendance office's
``attendance_absence_reports``), change password and MFA (the shared
platform dialogs), and Logout.

The learner-only tabs after Sign-outs (My Plan, Exams, Projects &
Placements, Library, Surveys, Wellbeing & Help, Study Planner) live in
:mod:`._learner_sections` and read through
:mod:`...parent_portal.learner_self_service`, again with
``principal.student_id`` only.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    learner_view as lv,
)
from education_system.systems.sixth_form.interfaces.gui.portals._learner_sections import (
    LearnerSectionsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.portals._learner_extras import (
    LearnerExtrasMixin,
)

logger = logging.getLogger(__name__)

_MUTED = "#7f8c8d"


def _table(parent, columns: tuple[tuple[str, str, int], ...], *,
           height: int = 12) -> ttk.Treeview:
    """A Treeview with headings and a vertical scrollbar, packed to fill."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height)
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


def _dash(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


def _money(v: Any) -> str:
    return "—" if v is None else f"£{float(v):,.2f}"


class StudentPortalGUI(LearnerSectionsMixin, LearnerExtrasMixin):
    """One signed-in learner's own record."""

    def __init__(self, auth, principal) -> None:
        self.auth = auth
        self.principal = principal
        self.sid: str = principal.student_id
        self.root = tk.Tk()
        self.root.title(f"{SYSTEM_NAME} — Student Portal")
        window_sizing.fit(self.root, "1400x900", (1200, 800))
        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass
        try:
            self.me = lv.student_identity(self.sid)
        except Exception:
            logger.exception("Student identity unavailable for %s", self.sid)
            self.me = {"student_id": self.sid, "full_name": principal.username,
                       "email": None, "status": "", "tutor_group": None}

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._build_header()
        self._build_status_bar()
        self._build_body()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            from education_system.systems.sixth_form.interfaces.gui.idle_timeout import (
                IdleTimeoutWatcher,
            )
            self._idle_watcher = IdleTimeoutWatcher(self.root,
                                                    on_timeout=self._idle_logout)
            self._idle_watcher.start()
        except Exception:
            logger.exception("Could not start idle-timeout watcher")
            self._idle_watcher = None

    # ── Chrome ───────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        left = ttk.Frame(header)
        left.grid(row=0, column=0, sticky="w")
        ttk.Button(left, text="⟳ Refresh", command=self.refresh).pack(side="left")
        ttk.Button(left, text="Report Absence…",
                   command=self._absence_dialog).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="Change Password",
                   command=self._change_password).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="MFA", command=self._mfa).pack(side="left", padx=(6, 0))
        ttk.Button(left, text="Pay…", command=self._pay).pack(side="left", padx=(6, 0))
        title = ttk.Frame(header)
        title.grid(row=0, column=1)
        ttk.Label(title, text="Student Portal", font=("", 15, "bold")).pack()
        tg = self.me.get("tutor_group") or {}
        ttk.Label(title, text=f"{self.me['full_name']} · {self.sid}"
                  + (f" · Tutor group {tg.get('name')}" if tg else ""),
                  foreground=_MUTED).pack()
        ttk.Button(header, text="Logout", command=self._logout).grid(
            row=0, column=2, sticky="e")

    def _build_status_bar(self) -> None:
        ttk.Separator(self.root, orient="horizontal").grid(row=2, column=0, sticky="ew")
        bar = ttk.Frame(self.root, padding=(12, 4))
        bar.grid(row=3, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(bar, text=f"Signed in as {self.principal.username}",
                  foreground=_MUTED).grid(row=0, column=1, sticky="e")

    def _build_body(self) -> None:
        body = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.nb = ttk.Notebook(body)
        self.nb.grid(row=0, column=0, sticky="nsew", pady=(8, 8))
        self._sections: list[tuple[ttk.Frame, Callable[[ttk.Frame], None], str]] = []
        for label, builder in (
                ("Overview", self._overview), ("Timetable", self._timetable),
                ("Attendance", self._attendance), ("Subjects & Grades", self._grades),
                ("Results", self._results), ("Work Due", self._work),
                ("Reports", self._reports), ("UCAS", self._ucas),
                ("Bursary", self._bursary), ("Trips", self._trips),
                ("Messages", self._messages), ("Sign-outs", self._signouts),
                # Learner-only sections (_learner_sections.LearnerSectionsMixin).
                ("My Plan", self._myplan), ("Exams", self._exams),
                ("Projects & Placements", self._projects), ("Library", self._library),
                ("Surveys", self._surveys), ("Wellbeing & Help", self._wellbeing),
                ("Study Planner", self._study),
                # _learner_extras.LearnerExtrasMixin.
                ("Class Resources", self._resources), ("My Devices", self._devices)):
            frame = ttk.Frame(self.nb, padding=10)
            self.nb.add(frame, text=label)
            self._sections.append((frame, builder, label))
        self._built: set[int] = set()
        self.nb.bind("<<NotebookTabChanged>>", lambda _e: self._ensure_built())
        self._ensure_built()

    def _ensure_built(self, force: bool = False) -> None:
        idx = self.nb.index(self.nb.select())
        if idx in self._built and not force:
            return
        frame, builder, label = self._sections[idx]
        for w in frame.winfo_children():
            w.destroy()
        try:
            builder(frame)
            self.status_var.set(f"{label} loaded")
        except Exception:
            logger.exception("Student portal section %s failed for %s", label, self.sid)
            ttk.Label(frame, text=f"Your {label.lower()} could not be loaded just now. "
                                  "Please try again, or contact the college office.",
                      wraplength=640).pack(anchor="w")
            self.status_var.set(f"{label} unavailable")
        self._built.add(idx)

    def refresh(self) -> None:
        self._built.clear()
        self._ensure_built(force=True)

    # ── Sections ─────────────────────────────────────────────────────

    def _overview(self, f: ttk.Frame) -> None:
        tiles = ttk.Frame(f)
        tiles.pack(fill="x", pady=(0, 12))
        try:
            att = lv.attendance(self.sid)
            self._tile(tiles, "Attendance", _dash(att["overall_percentage"]) + (
                "%" if att["overall_percentage"] is not None else ""),
                f"last {att['days']} days: {_dash(att['percentage'])}%")
        except Exception:
            logger.debug("Overview attendance failed", exc_info=True)
        try:
            work = lv.coursework(self.sid)
            due = [w for w in work if not w["submitted"]]
            self._tile(tiles, "Work outstanding", str(len(due)),
                       f"{sum(1 for w in due if w['overdue'])} overdue")
        except Exception:
            logger.debug("Overview work failed", exc_info=True)
        try:
            cards = lv.report_cards(self.sid)
            self._tile(tiles, "Reports", str(len(cards)),
                       cards[0]["period"] if cards else "none published yet")
        except Exception:
            logger.debug("Overview reports failed", exc_info=True)

        today = _dt.date.today().isoweekday()
        box = ttk.LabelFrame(f, text="Today's lessons", padding=8)
        box.pack(fill="x", pady=(0, 12))
        lessons = [s for s in lv.timetable(self.sid) if s["day"] == today]
        if not lessons:
            ttk.Label(box, text="No lessons timetabled today.").pack(anchor="w")
        for s in lessons:
            ttk.Label(box, text=f"P{s['period']}  {s['start_time']}–{s['end_time']}  "
                                f"{s['subject']}  ({_dash(s['room'])}, "
                                f"{_dash(s['teacher'])})").pack(anchor="w")

        box = ttk.LabelFrame(f, text="Announcements", padding=8)
        box.pack(fill="both", expand=True)
        anns = lv.announcements("students")
        if not anns:
            ttk.Label(box, text="No current announcements.").pack(anchor="w")
        for a in anns[:8]:
            ttk.Label(box, text=f"{'📌 ' if a['pinned'] else ''}{a['title']}  "
                                f"[{a['priority']}]", font=("", 10, "bold")
                      ).pack(anchor="w", pady=(4, 0))
            if a["summary"] or a["body"]:
                ttk.Label(box, text=(a["summary"] or a["body"] or "")[:400],
                          wraplength=1000, foreground="#333").pack(anchor="w")

    @staticmethod
    def _tile(parent, title: str, value: str, sub: str = "") -> None:
        tile = ttk.LabelFrame(parent, text=title, padding=10)
        tile.pack(side="left", padx=(0, 10))
        ttk.Label(tile, text=value, font=("", 18, "bold")).pack(anchor="w")
        if sub:
            ttk.Label(tile, text=sub, foreground=_MUTED).pack(anchor="w")

    def _timetable(self, f: ttk.Frame) -> None:
        from education_system.systems.sixth_form.domain.academics.timetable import (
            timetable as _tt,
        )
        slots = lv.timetable(self.sid)
        if not slots:
            ttk.Label(f, text="You have no timetabled lessons yet.").pack(anchor="w")
            return
        grid = ttk.Frame(f)
        grid.pack(fill="both", expand=True)
        ttk.Label(grid, text="").grid(row=0, column=0)
        for c, d in enumerate(_tt.DAYS, 1):
            ttk.Label(grid, text=d, font=("", 10, "bold")).grid(row=0, column=c, padx=4)
            grid.columnconfigure(c, weight=1)
        by_cell = {(s["day"], s["period"]): s for s in slots}
        for r, p in enumerate(_tt.PERIODS, 1):
            start, end = _tt.DEFAULT_PERIOD_TIMES.get(p, ("", ""))
            ttk.Label(grid, text=f"P{p}\n{start}–{end}").grid(row=r, column=0, padx=4,
                                                            sticky="n")
            for c, d in enumerate(_tt.DAY_NUMBERS, 1):
                s = by_cell.get((d, p))
                cell = ttk.LabelFrame(grid, padding=4)
                cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
                if s:
                    ttk.Label(cell, text=s["subject"], font=("", 10, "bold")).pack(anchor="w")
                    ttk.Label(cell, text=f"{_dash(s['room'])} · {_dash(s['teacher'])}",
                              foreground=_MUTED).pack(anchor="w")
                else:
                    ttk.Label(cell, text="Study", foreground="#bbb").pack(anchor="w")

    def _attendance(self, f: ttk.Frame) -> None:
        att = lv.attendance(self.sid)
        c = att["counts"]
        ttk.Label(f, text=f"This year: {_dash(att['overall_percentage'])}%    "
                          f"Last {att['days']} days: {_dash(att['percentage'])}%    "
                          f"Present {c['Present']} · Late {c['Late']} · "
                          f"Absent {c['Absent']} · Authorised {c['Authorised']}",
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Report an absence / self-certify…",
                   command=self._absence_dialog).pack(side="left")
        try:
            from education_system.systems.sixth_form.domain.academics.attendance import (
                attendance_absence_reports as _abs,
            )
            ttk.Label(bar, text=_abs.self_cert_status(self.sid).label,
                      foreground=_MUTED).pack(side="left", padx=10)
        except Exception:
            logger.debug("Self-cert status unavailable", exc_info=True)
        panes = ttk.Panedwindow(f, orient="vertical")
        panes.pack(fill="both", expand=True)
        top, bottom = ttk.LabelFrame(panes, text="Marks", padding=6), \
            ttk.LabelFrame(panes, text="My absence reports", padding=6)
        panes.add(top, weight=3)
        panes.add(bottom, weight=1)
        tree = _table(top, (("date", "Date", 100), ("session", "Session", 80),
                            ("subject", "Subject", 220), ("status", "Mark", 110),
                            ("code", "Code", 70), ("late", "Mins late", 80)))
        for m in att["marks"]:
            tree.insert("", "end", values=(m["date"], _dash(m["session"]), m["subject"],
                                           m["status"], _dash(m["code"]),
                                           _dash(m["minutes_late"] or None)))
        reps = _table(bottom, (("dates", "Dates", 200), ("reason", "Reason", 300),
                               ("state", "Status", 120), ("by", "Reported by", 120)),
                      height=4)
        try:
            from education_system.systems.sixth_form.domain.academics.attendance import (
                attendance_absence_reports as _abs,
            )
            for r in _abs.portal_history(self.principal):
                reps.insert("", "end", values=(r.span, _dash(r.reason_text),
                                               r.state + (" (self-cert)" if r.self_certified
                                                          else ""), r.reported_by))
        except Exception:
            logger.debug("Absence history unavailable", exc_info=True)

    def _grades(self, f: ttk.Frame) -> None:
        box = ttk.LabelFrame(f, text="My learning aims", padding=6)
        box.pack(fill="x", pady=(0, 8))
        aims = lv.learning_aims(self.sid)
        tree = _table(box, (("subject", "Subject", 220), ("qual", "Qualification", 140),
                            ("board", "Awarding body", 120), ("year", "Year", 90),
                            ("start", "Start", 100), ("end", "Planned end", 100),
                            ("status", "Status", 100)), height=min(max(len(aims), 3), 8))
        for a in aims:
            tree.insert("", "end", values=(a["subject"], a["qualification_type"],
                                           _dash(a["awarding_body"]),
                                           _dash(a["academic_year"]), a["start_date"],
                                           _dash(a["planned_end_date"]), a["status"]))
        box = ttk.LabelFrame(f, text="Grades", padding=6)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Predicted grades appear here once they have been shared "
                            "with you on a published report.",
                  foreground=_MUTED).pack(anchor="w", pady=(0, 4))
        tree = _table(box, (("subject", "Subject", 220), ("current", "Working at", 110),
                            ("target", "Target (MTG)", 110),
                            ("asp", "Aspirational", 110), ("pred", "Predicted", 110),
                            ("status", "Progress", 120)))
        for g in lv.grades(self.sid):
            tree.insert("", "end", values=(g["subject"], _dash(g["current"]),
                                           _dash(g["target"]), _dash(g["aspirational"]),
                                           _dash(g["predicted"]), _dash(g["status"])))

    def _results(self, f: ttk.Frame) -> None:
        rows = lv.released_results(self.sid)
        if not rows:
            ttk.Label(f, text="No exam results have been released to you yet.").pack(
                anchor="w")
            return
        tree = _table(f, (("season", "Series", 120), ("subject", "Subject", 200),
                          ("paper", "Paper", 220), ("board", "Board", 90),
                          ("grade", "Grade", 80), ("marks", "Marks", 80),
                          ("ums", "UMS", 70), ("released", "Released", 110)))
        for r in rows:
            tree.insert("", "end", values=(f"{r['season']} {r['year']}", r["subject"],
                                           _dash(r["paper"]), r["board"], r["grade"],
                                           _dash(r["marks"]), _dash(r["ums"]),
                                           _dash(r["released_at"])))

    def _work(self, f: ttk.Frame) -> None:
        rows = lv.coursework(self.sid)
        if not rows:
            ttk.Label(f, text="Nothing has been set for you.").pack(anchor="w")
            return
        panes = ttk.Panedwindow(f, orient="vertical")
        panes.pack(fill="both", expand=True)
        top, bottom = ttk.Frame(panes), ttk.LabelFrame(panes, text="Feedback", padding=6)
        panes.add(top, weight=3)
        panes.add(bottom, weight=1)
        tree = _table(top, (("due", "Due", 100), ("kind", "Type", 90),
                            ("subject", "Subject", 180), ("title", "Title", 320),
                            ("status", "Status", 110), ("mark", "Mark", 90)))
        tree.tag_configure("overdue", foreground="#c0392b")
        for i, r in enumerate(rows):
            tree.insert("", "end", iid=str(i), tags=("overdue",) if r["overdue"] else (),
                        values=(_dash(r["due_date"]), r["kind"], _dash(r["subject"]),
                                r["title"], ("Overdue" if r["overdue"] else r["status"]),
                                _dash(r["mark"])))
        text = tk.Text(bottom, height=5, wrap="word", state="disabled")
        text.pack(fill="both", expand=True)

        def show(_e=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            fb = rows[int(sel[0])].get("feedback") or "No feedback released yet."
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", fb)
            text.configure(state="disabled")
        tree.bind("<<TreeviewSelect>>", show)

    def _reports(self, f: ttk.Frame) -> None:
        cards = lv.report_cards(self.sid)
        if not cards:
            ttk.Label(f, text="No reports have been published to you yet.").pack(anchor="w")
            return
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        panes = ttk.Panedwindow(f, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=3)
        tree = _table(left, (("period", "Period", 160), ("published", "Published", 140)))
        for c in cards:
            tree.insert("", "end", iid=str(c["card_id"]),
                        values=(c["period"], _dash(c["published_at"])))
        text = tk.Text(right, wrap="word", state="disabled", padx=10, pady=10)
        text.pack(fill="both", expand=True)

        def show(_e=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            try:
                body = lv.report_card_text(self.sid, int(sel[0]))
            except Exception as e:
                body = str(e)
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", body)
            text.configure(state="disabled")

        def save(fmt: str) -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Reports", "Choose a report first.", parent=self.root)
                return
            from education_system.systems.sixth_form.domain.assessment.report_cards import (
                report_cards as _rc,
            )
            try:
                card = _rc.published_card(self.sid, int(sel[0]))
                path = _rc.render(card.card_id, fmt=fmt)
            except _rc.ValidationError as e:
                messagebox.showerror("Reports", str(e), parent=self.root)
                return
            messagebox.showinfo("Reports", f"Saved to:\n{path}", parent=self.root)

        ttk.Button(bar, text="Save as HTML", command=lambda: save("html")).pack(side="left")
        ttk.Button(bar, text="Save as PDF", command=lambda: save("pdf")).pack(
            side="left", padx=6)
        tree.bind("<<TreeviewSelect>>", show)
        tree.selection_set(str(cards[0]["card_id"]))
        show()

    def _ucas(self, f: ttk.Frame) -> None:
        u = lv.ucas(self.sid)
        if u is None:
            ttk.Label(f, text="You have no UCAS application on record.").pack(anchor="w")
            return
        ttk.Label(f, text=f"Cycle {u['cycle_year']} · Status: {u['status']}"
                          f" · UCAS ID {_dash(u['ucas_id'])}"
                          f" · Submitted {_dash(u['submitted_at'])}",
                  font=("", 11, "bold")).pack(anchor="w")
        d = u.get("deadline")
        if d:
            ttk.Label(f, text=f"Deadline {d['deadline']} ({d['reason']}) · college "
                              f"internal deadline {d['internal_date']} "
                              f"({d['days_to_internal']} days) · {d['state']}",
                      foreground="#c0392b" if d["days_to_internal"] < 14 else "#333"
                      ).pack(anchor="w", pady=(2, 8))
        if u.get("results_embargoed"):
            ttk.Label(f, text="Your results have not been released yet, so results-day "
                              "outcomes on your Firm and Insurance choices are held "
                              "back until they are.", foreground="#7a5800").pack(
                anchor="w", pady=(0, 6))
        box = ttk.LabelFrame(f, text="Choices", padding=6)
        box.pack(fill="x", pady=(0, 8))
        tree = _table(box, (("n", "#", 40), ("uni", "University", 200),
                            ("course", "Course", 230), ("decision", "Decision", 130),
                            ("offer", "Offer", 200), ("final", "Your reply", 100),
                            ("reply_by", "Reply by", 90), ("decided", "Decided", 90)),
                      height=5)
        for i, c in enumerate(u["choices"]):
            tree.insert("", "end", iid=str(i), values=(
                c["order"], c["university"], c["course"], c["decision"],
                _dash(c["offer"]), _dash(c["final"]), _dash(c.get("reply_by")),
                _dash(c.get("decision_date"))))
        # Offer terms and conditions of the selected choice.
        from education_system.systems.sixth_form.interfaces.gui.portals import (
            _ucas_tracker,
        )
        detail = ttk.Label(box, text="Select a choice to see its offer terms and "
                                     "conditions.", foreground="#555",
                           justify="left", wraplength=900)
        detail.pack(anchor="w", pady=(6, 0))

        def _show_terms(_e=None) -> None:
            sel = tree.selection()
            if sel:
                detail.configure(text=_ucas_tracker.offer_detail_text(
                    u["choices"][int(sel[0])]), foreground="#222")
        tree.bind("<<TreeviewSelect>>", _show_terms)
        _ucas_tracker.render_tracker(f, u.get("tracker"))
        p = u.get("pipeline")
        if p:
            box = ttk.LabelFrame(f, text=f"Application steps — {p['percent']}% complete",
                                 padding=6)
            box.pack(fill="both", expand=True)
            tree = _table(box, (("step", "Step", 300), ("status", "Status", 140),
                                ("due", "Due", 110)))
            for s in p["stages"]:
                tree.insert("", "end", values=(s["label"], s["status"],
                                               _dash(s["due_date"])))

    def _bursary(self, f: ttk.Frame) -> None:
        apps = lv.bursaries(self.sid)
        if not apps:
            ttk.Label(f, text="You have no bursary applications. Ask the finance "
                              "office, or a parent can start one from the parent "
                              "portal.").pack(anchor="w")
            return
        tree = _table(f, (("type", "Bursary", 200), ("year", "Year", 90),
                          ("applied", "Applied", 100), ("status", "Status", 130),
                          ("awarded", "Awarded", 100), ("paid", "Paid", 100),
                          ("left", "Still to pay", 100)), height=6)
        for a in apps:
            tree.insert("", "end", iid=str(a["application_id"]), values=(
                a["type"], _dash(a["academic_year"]), a["applied"], a["status"],
                _money(a["awarded"]), _money(a["paid"]), _money(a["remaining"])))
        box = ttk.LabelFrame(f, text="Payments and schedule", padding=6)
        box.pack(fill="both", expand=True, pady=(8, 0))
        pay = _table(box, (("when", "Date", 110), ("what", "Item", 160),
                           ("amount", "Amount", 100), ("state", "Status", 140)))

        def show(_e=None) -> None:
            pay.delete(*pay.get_children())
            sel = tree.selection()
            if not sel:
                return
            a = next(x for x in apps if x["application_id"] == int(sel[0]))
            for p in a["payments"]:
                pay.insert("", "end", values=(p["date"], f"Payment ({p['method']})",
                                              _money(p["amount"]), p["status"]))
            for s in a["schedule"]:
                pay.insert("", "end", values=(s["due_date"], f"Instalment {s['period']}",
                                              _money(s["amount"]), s["state"]))
        tree.bind("<<TreeviewSelect>>", show)

    def _trips(self, f: ttk.Frame) -> None:
        rows = lv.trips(self.sid)
        if not rows:
            ttk.Label(f, text="You are not booked on any trips.").pack(anchor="w")
            return
        ttk.Label(f, text="Consent is given by a parent or guardian from the parent "
                          "portal (or on paper to the trip leader).",
                  foreground=_MUTED).pack(anchor="w", pady=(0, 4))
        tree = _table(f, (("trip", "Trip", 220), ("dest", "Destination", 160),
                          ("dates", "Dates", 170), ("status", "Booking", 100),
                          ("consent", "Consent", 90), ("cost", "Cost", 90),
                          ("paid", "Paid", 90), ("balance", "Balance", 90),
                          ("pay", "Payment", 110)))
        for t in rows:
            tree.insert("", "end", values=(
                t["trip"], _dash(t["destination"]),
                t["start_date"] + (f" → {t['end_date']}" if t["end_date"] else ""),
                t["booking_status"], "Given" if t["consent"] else "Needed",
                _money(t["cost"]), _money(t["paid"]), _money(t["balance"]),
                t["payment_state"]))

    def _messages(self, f: ttk.Frame) -> None:
        address = self.me.get("email")
        inbox = lv.messages_to(address)
        panes = ttk.Panedwindow(f, orient="vertical")
        panes.pack(fill="both", expand=True)
        top, bottom = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(top, weight=1)
        panes.add(bottom, weight=2)
        ttk.Label(top, text=f"Messages sent to {_dash(address)}",
                  foreground=_MUTED).pack(anchor="w")
        tree = _table(top, (("sent", "Sent", 150), ("from", "From", 200),
                            ("subject", "Subject", 480), ("cat", "Category", 120)),
                      height=8)
        for m in inbox:
            tree.insert("", "end", iid=str(m["message_id"]), values=(
                (m["sent_at"] or "")[:16], m["from_name"] or m["from_address"] or "—",
                m["subject"], m["category"]))
        text = tk.Text(bottom, wrap="word", state="disabled", padx=10, pady=10)
        text.pack(fill="both", expand=True)
        if not inbox:
            ttk.Label(top, text="No messages yet.").pack(anchor="w")

        def show(_e=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            try:
                m = lv.message_for(address, int(sel[0]))
                body = (f"{m['subject']}\nFrom: {m['from_name'] or m['from_address']}\n"
                        f"Sent: {_dash(m['sent_at'])}\n{'-' * 60}\n\n{m['body']}")
            except LookupError as e:
                body = str(e)
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", body)
            text.configure(state="disabled")
        tree.bind("<<TreeviewSelect>>", show)

    def _signouts(self, f: ttk.Frame) -> None:
        self._signout_requests(f)
        rows = lv.signouts(self.sid)
        ttk.Label(f, text="Signing out of site is done at reception or the kiosk; "
                          "this is your record.", foreground=_MUTED).pack(anchor="w")
        if not rows:
            ttk.Label(f, text="No sign-outs recorded.").pack(anchor="w")
            return
        tree = _table(f, (("date", "Date", 100), ("out", "Out", 70),
                          ("back", "Back", 70), ("exp", "Expected back", 110),
                          ("reason", "Reason", 160), ("state", "Status", 110),
                          ("perm", "Parent permission", 130)))
        for s in rows:
            tree.insert("", "end", values=(s["date"], s["out"], _dash(s["back"]),
                                           _dash(s["expected_back"]), s["reason"],
                                           s["state"],
                                           "Yes" if s["parent_permission"] else "—"))

    def _signout_requests(self, f: ttk.Frame) -> None:
        box = ttk.LabelFrame(f, text="Requests to leave site", padding=8)
        box.pack(fill="x", pady=(0, 10))
        ttk.Label(box, text="Ask ahead (an appointment, early leave); a member of "
                            "staff approves it, then sign out at reception as usual.",
                  foreground=_MUTED).pack(anchor="w")
        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(4, 4))
        reqs = lv.signout_requests(self.sid)
        holder = ttk.Frame(box)
        holder.pack(fill="x")
        tree = _table(holder, (("date", "Date", 100), ("leave", "Leaving", 70),
                               ("back", "Back by", 70), ("reason", "Reason", 200),
                               ("state", "Status", 90), ("note", "Staff note", 260)),
                      height=4)
        for r in reqs:
            why = r["reason"] + (f" ({r['detail']})" if r["detail"] else "")
            tree.insert("", "end", iid=str(r["request_id"]),
                        values=(r["date"], r["leave_time"], _dash(r["expected_back"]),
                                why, r["state"], _dash(r["decision_note"])))
        open_ids = {str(r["request_id"]) for r in reqs if r["open"]}

        def cancel() -> None:
            sel = tree.selection()
            if not sel or sel[0] not in open_ids:
                messagebox.showinfo("Sign-out requests",
                                    "Select a request that is still open.",
                                    parent=self.root)
                return
            try:
                lv.cancel_signout_request(self.sid, int(sel[0]),
                                          by=self.principal.username)
            except Exception as e:
                messagebox.showerror("Sign-out requests", str(e), parent=self.root)
                return
            self.refresh()

        ttk.Button(bar, text="Request to leave site…",
                   command=self._signout_request_dialog).pack(side="left")
        ttk.Button(bar, text="Cancel selected", command=cancel).pack(
            side="left", padx=(6, 0))

    def _signout_request_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Request to leave site")
        win.transient(self.root)
        frm = ttk.Frame(win, padding=14)
        frm.pack(fill="both", expand=True)
        reasons = list(lv.signout_reasons())
        vars_ = {k: tk.StringVar(value=v) for k, v in (
            ("reason", reasons[1] if len(reasons) > 1 else reasons[0]),
            ("date", _dt.date.today().isoformat()), ("leave", ""),
            ("back", ""), ("detail", ""))}
        aware = tk.BooleanVar(value=False)
        ttk.Label(frm, text="Reason").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(frm, textvariable=vars_["reason"], values=reasons,
                     state="readonly", width=37).grid(row=0, column=1, sticky="ew")
        for r, (label, key) in enumerate((("Date (YYYY-MM-DD)", "date"),
                                          ("Leaving at (HH:MM)", "leave"),
                                          ("Back by (HH:MM, optional)", "back"),
                                          ("Detail (who / why)", "detail")), 1):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(frm, textvariable=vars_[key], width=40).grid(
                row=r, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(frm, text="A parent/carer knows about this",
                        variable=aware).grid(row=5, column=1, sticky="w")

        def send() -> None:
            try:
                out = lv.request_signout(
                    self.sid, reason=vars_["reason"].get(),
                    date=vars_["date"].get().strip(),
                    leave_time=vars_["leave"].get().strip(),
                    detail=vars_["detail"].get().strip() or None,
                    expected_back=vars_["back"].get().strip() or None,
                    parent_aware=aware.get(),
                    requested_by=self.principal.username)
            except Exception as e:      # ValidationError
                messagebox.showerror("Request to leave site", str(e), parent=win)
                return
            messagebox.showinfo("Request to leave site",
                                f"Request #{out['request_id']} sent — a member of "
                                "staff will approve or decline it.", parent=win)
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Send request", command=send).pack(side="left")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ── Actions ──────────────────────────────────────────────────────

    def _absence_dialog(self) -> None:
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_absence_reports as _abs,
        )
        win = tk.Toplevel(self.root)
        win.title("Report an absence")
        win.transient(self.root)
        frm = ttk.Frame(win, padding=14)
        frm.pack(fill="both", expand=True)
        today = _dt.date.today().isoformat()
        vars_ = {k: tk.StringVar(value=v) for k, v in
                 (("from", today), ("to", today), ("reason", ""))}
        for r, (label, key) in enumerate((("First day (YYYY-MM-DD)", "from"),
                                          ("Last day (YYYY-MM-DD)", "to"),
                                          ("Reason", "reason"))):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(frm, textvariable=vars_[key], width=40).grid(row=r, column=1,
                                                                   sticky="ew", pady=3)
        ttk.Label(frm, text="Message (optional)").grid(row=3, column=0, sticky="nw")
        msg = tk.Text(frm, width=40, height=4)
        msg.grid(row=3, column=1, sticky="ew", pady=3)
        try:
            status = _abs.self_cert_status(self.sid).label
        except Exception:
            status = ""
        ttk.Label(frm, text="Self-certify if you are ill (coded straight away, limited "
                            f"days per term). {status}", wraplength=420,
                  foreground=_MUTED).grid(row=4, column=0, columnspan=2, sticky="w",
                                          pady=(6, 6))

        def go(self_cert: bool) -> None:
            kwargs = {"date_to": vars_["to"].get().strip() or None,
                      "reason_text": vars_["reason"].get().strip() or None,
                      "message": msg.get("1.0", "end").strip() or None}
            try:
                if self_cert:
                    rep = _abs.self_certify_for(self.principal, vars_["from"].get().strip(),
                                                **kwargs)
                else:
                    rep = _abs.report_absence_for(self.principal, None,
                                                  vars_["from"].get().strip(), **kwargs)
            except Exception as e:      # ValidationError / AccessDenied
                messagebox.showerror("Report an absence", str(e), parent=win)
                return
            messagebox.showinfo("Report an absence",
                                f"Received — {rep.span} ({rep.state}).", parent=win)
            win.destroy()
            self.refresh()

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Self-certify (ill)", command=lambda: go(True)).pack(
            side="left")
        ttk.Button(btns, text="Send to attendance office",
                   command=lambda: go(False)).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left")

    def _change_password(self) -> None:
        from education_system.platform.delivery.gui.change_password_gui import (
            open_change_password_dialog,
        )
        open_change_password_dialog(self.root, auth=self.auth)

    def _mfa(self) -> None:
        from education_system.platform.delivery.gui import mfa_setup_gui
        mfa_setup_gui.open_mfa(self.root, auth=self.auth)

    def _logout(self) -> None:
        if not messagebox.askyesno("Logout", "Log out of the Student Portal?",
                                   parent=self.root):
            return
        from education_system import switch
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout on the shared session failed", exc_info=True)
        switch.request_logout("gui")
        self.root.destroy()

    def _idle_logout(self) -> None:
        logger.info("Idle logout for student=%s", self.sid)
        from education_system import switch
        self._stop_idle_watcher()
        try:
            messagebox.showinfo("Signed out", "You've been signed out due to "
                                "inactivity. Please sign in again to continue.",
                                parent=self.root)
        except tk.TclError:
            pass
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout on the shared session failed", exc_info=True)
        switch.request_logout("gui")
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _stop_idle_watcher(self) -> None:
        watcher = getattr(self, "_idle_watcher", None)
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                logger.debug("Could not stop the idle watcher", exc_info=True)
            self._idle_watcher = None

    def _on_close(self) -> None:
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            pass
        self.root.destroy()


def run(shared_auth, principal) -> int:
    """Open the student portal for an already-authenticated learner."""
    if not getattr(principal, "student_id", None):
        raise ValueError("The student portal needs a principal with a student_id")
    gui = StudentPortalGUI(shared_auth, principal)
    gui.root.mainloop()
    return 0
