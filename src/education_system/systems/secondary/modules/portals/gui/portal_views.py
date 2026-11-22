"""The pupil and parent portals.

A pupil signs in and sees their own record; a parent signs in and picks one of
their children at the top. Sections (sidebar): Home, Timetable, Homework,
Attendance, Grades, Reports, Exams, Library, Clubs, Options, Sixth Form, Calendar,
My details, Behaviour, Messages (announcements, letters, parents' evenings),
Money (trips, dinner money) and - for pupils - Wellbeing.
A pupil can hand in homework; a pupil or parent can make Year 9 options
choices while a round is open. Everything is read through
:mod:`modules.portals.domain.portal`, which checks the link on every call.

:class:`PortalFrame` is the portal itself (also opened from the staff portal
for a teacher who is a parent here); :class:`PortalWindow` is the window a
pupil or parent gets at sign-in.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.secondary import SYSTEM_NAME
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.portals.gui.portal_linked import PortalLinkedMixin
from education_system.systems.secondary.modules.progression.domain import sixth_form_choices as SC
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = (PT.ValidationError, PT.PermissionDenied, PT.NotFound)
_TAGS = {"warn": "#fff6d6", "bad": "#fde2e2", "good": "#e7f6ea", "muted": "#f4f4f4"}


_problems = W.problems


def _date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%a %d %b")
    except ValueError:
        return str(iso)


def _tree(parent, columns, height: int = 8) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"title", "detail", "name"}, tags=_TAGS,
                  minwidth=0)


def _box(parent, title: str) -> ttk.LabelFrame:
    box = ttk.LabelFrame(parent, text=title, padding=8)
    box.pack(fill="x", pady=(0, 10))
    return box


def _empty(parent, text: str) -> None:
    ttk.Label(parent, text=text, foreground="#777").pack(anchor="w")


class PortalFrame(PortalLinkedMixin):
    """Sidebar + content for one pupil (a parent can switch child)."""

    def __init__(self, parent: tk.Misc, *, principal: Principal,
                 on_status: Callable[[str], None] | None = None) -> None:
        self.parent, self.principal = parent, principal
        self.on_status = on_status or (lambda _s: None)
        self.is_pupil = principal.is_student
        self.children = PT.pupils(principal)
        self.section = "Home"
        self.pupil_id: int | None = self.children[0].pupil_id if self.children else None

        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 6))
        self.title_var = tk.StringVar()
        ttk.Label(top, textvariable=self.title_var, font=("", 15, "bold")).pack(side="left")
        if not self.is_pupil and len(self.children) > 1:
            ttk.Label(top, text="Child:").pack(side="left", padx=(16, 4))
            self.child_var = tk.StringVar()
            labels = {self._label(p): p.pupil_id for p in self.children}
            cb = ttk.Combobox(top, textvariable=self.child_var, values=list(labels),
                              state="readonly", width=34)
            cb.pack(side="left")
            self.child_var.set(next(iter(labels)))
            cb.bind("<<ComboboxSelected>>",
                    lambda _e: self._pick_child(labels[self.child_var.get()]))
        body = ttk.Frame(parent)
        body.pack(fill="both", expand=True)
        nav = ttk.Frame(body, padding=(0, 0, 10, 0))
        nav.pack(side="left", fill="y")
        self.nav_buttons: dict[str, ttk.Button] = {}
        for s in PT.sections_for(principal):
            b = ttk.Button(nav, text=s, width=16, command=lambda s=s: self.show(s))
            b.pack(fill="x", pady=1)
            self.nav_buttons[s] = b
        holder = ttk.Frame(body)
        holder.pack(side="left", fill="both", expand=True)
        canvas = tk.Canvas(holder, highlightthickness=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(canvas, padding=(4, 0))
        win = canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>",
                          lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        self.canvas = canvas
        self.show("Home")

    @staticmethod
    def _label(p) -> str:
        return f"{p.display_name} (Year {p.year_group}{' ' + p.form_group if p.form_group else ''})"

    def _top(self):
        return self.parent.winfo_toplevel()

    def _pick_child(self, pupil_id: int) -> None:
        self.pupil_id = pupil_id
        self.show(self.section)

    def show(self, section: str) -> None:
        self.section = section
        for w in self.content.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)
        for s, b in self.nav_buttons.items():
            b.state(["pressed"] if s == section else ["!pressed"])
        if self.pupil_id is None:
            self.title_var.set("Portal")
            _empty(self.content, (
                "Your login isn't linked to a pupil record yet." if self.is_pupil else
                "No children are linked to your login yet.")
                + "\n\nPlease contact the school office - they can link it for you.")
            return
        pupil = next(p for p in self.children if p.pupil_id == self.pupil_id)
        self.title_var.set(f"{pupil.display_name} - {section}" if not self.is_pupil
                           else section)
        try:
            getattr(self, "_draw_" + section.lower().replace(" ", "_"))(self.content)
        except _ERRORS as e:
            _empty(self.content, _problems(e))
        self.on_status(f"Opened: {section}")

    # ── Sections ─────────────────────────────────────────────────────
    def _draw_home(self, f) -> None:
        pid = self.pupil_id
        h = PT.home(self.principal, pid)
        now = datetime.now()
        greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 \
            else "Good evening"
        pupil = next(p for p in self.children if p.pupil_id == pid)
        who = (pupil.preferred_name or pupil.legal_first_name) if self.is_pupil else None
        ttk.Label(f, text=f"{greet}{', ' + who if who else ''}", font=("", 13, "bold")).pack(
            anchor="w")
        ttk.Label(f, text=h["day"].strftime("%A %d %B %Y") + (f" · {h['day_label']}"
                                                            if h["day_label"] else ""),
                  foreground="#666").pack(anchor="w", pady=(0, 8))
        alerts = []
        if h["overdue_homework"]:
            alerts.append(f"{len(h['overdue_homework'])} homework overdue")
        overdue_books = [b for b in h["books_due"] if b.days_overdue]
        if overdue_books:
            alerts.append(f"{len(overdue_books)} library book(s) overdue")
        if alerts:
            ttk.Label(f, text="⚠ " + " · ".join(alerts), foreground="#a60").pack(
                anchor="w", pady=(0, 8))
        att = h["attendance"]
        tiles = ttk.Frame(f)
        tiles.pack(fill="x", pady=(0, 10))
        for i, (label, value) in enumerate((
                ("Attendance this year", f"{att.attendance_pct}%" if att and
                 att.attendance_pct is not None else "-"),
                ("Lessons today", str(len(h["lessons"]))),
                ("Homework due this week", str(len(h["homework_due"]))),
                ("Books due back", str(len(h["books_due"]))))):
            tiles.columnconfigure(i, weight=1, uniform="t")
            t = ttk.LabelFrame(tiles, padding=8)
            t.grid(row=0, column=i, sticky="nsew", padx=3)
            ttk.Label(t, text=label, foreground="#666").pack(anchor="w")
            ttk.Label(t, text=value, font=("", 18, "bold")).pack(anchor="w")
        box = _box(f, "Today's lessons")
        if not h["lessons"]:
            _empty(box, "No lessons today.")
        else:
            self._lesson_rows(box, h["lessons"])
        box = _box(f, "Homework due this week")
        if not h["homework_due"]:
            _empty(box, "Nothing due this week.")
        for t, w in h["homework_due"]:
            row = ttk.Frame(box)
            row.pack(fill="x")
            late = t.due_date < h["day"].isoformat()
            ttk.Label(row, text=f"{_date(t.due_date):<10}  {t.subject_code}  {t.title}"
                      + ("  (overdue)" if late else ""),
                      foreground="#a00" if late else "").pack(side="left")
            if self.is_pupil:
                ttk.Button(row, text="Hand in", command=lambda t=t: self._hand_in(t)).pack(
                    side="right")
        box = _box(f, "Coming up")
        if not h["events"]:
            _empty(box, "No events in the next two weeks.")
        for e in h["events"]:
            ttk.Label(box, text=f"{_date(e.start_date):<10}  {e.title}"
                      + (f" - {e.location}" if e.location else "")
                      + (" (cancelled)" if e.status == "Cancelled" else "")).pack(anchor="w")
        self._draw_home_linked(f, h)

    def _lesson_rows(self, parent, lessons) -> None:
        from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
        times = {p.period: p for p in TT.periods()}
        for x in lessons:
            p = times.get(x.period)
            ttk.Label(parent, text=f"{(p.label if p else f'P{x.period}'):<8} "
                                   f"{(p.times if p else ''):<12} {x.subject_name} "
                                   f"({x.group_code}) · {x.teacher or ''}"
                                   + (f" · room {x.room}" if x.room else "")).pack(anchor="w")

    def _draw_timetable(self, f) -> None:
        from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
        t = PT.timetable(self.principal, self.pupil_id)
        if not t["lessons"]:
            _empty(f, "No timetable yet.")
            return
        for week in range(1, t["weeks"] + 1):
            box = _box(f, (TT.WEEK_LABELS[week] + (" (this week)" if week == t["this_week"]
                                                  else "")) if t["weeks"] == 2 else "My week")
            grid = ttk.Frame(box)
            grid.pack(anchor="w")
            ttk.Label(grid, text="").grid(row=0, column=0)
            for d, name in enumerate(TT.DAY_NAMES, start=1):
                ttk.Label(grid, text=name, font=("", 9, "bold")).grid(row=0, column=d, padx=4)
            for r, p in enumerate(t["periods"], start=1):
                ttk.Label(grid, text=f"{p.label}\n{p.times}", foreground="#555").grid(
                    row=r, column=0, sticky="w", padx=(0, 6), pady=2)
                for d in range(1, 6):
                    cell = t["grid"].get((week, d, p.period), [])
                    text = "\n".join(f"{x.subject_code}\n{x.room or ''}" for x in cell) or "-"
                    tk.Label(grid, text=text, width=12, relief="groove", bg="#fafafa" if cell
                             else "#f0f0f0", justify="center").grid(row=r, column=d, padx=2,
                                                                     pady=2, sticky="nsew")

    def _draw_homework(self, f) -> None:
        h = PT.homework(self.principal, self.pupil_id)
        s = h["summary"]
        if s:
            ttk.Label(f, text=f"This year: {s.handed_in} of {s.set} handed in, {s.late} late, "
                              f"{s.missing} missing"
                      + (f", average mark {s.average_pct}%" if s.average_pct is not None
                         else ""),
                      foreground="#555").pack(anchor="w", pady=(0, 6))
        box = _box(f, "To do")
        tree = _tree(box, [("due", "Due", 90), ("subj", "Subject", 90), ("title", "Title", 260),
                           ("mins", "Time", 60), ("status", "Status", 80)], height=6)
        today = datetime.now().date().isoformat()
        tasks = {}
        for t, w in h["due"]:
            tasks[str(t.task_id)] = t
            tree.insert("", "end", iid=str(t.task_id), tags=("bad",) if t.due_date < today
                        else (), values=(_date(t.due_date), t.subject_code, t.title,
                                         f"{t.est_minutes}m" if t.est_minutes else "",
                                         w.status))
        detail = tk.Text(box, height=6, wrap="word")
        detail.pack(fill="x", pady=(6, 0))

        def show(_e=None) -> None:
            sel = tree.selection()
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            if sel:
                t = tasks[sel[0]]
                detail.insert("1.0", f"{t.title} ({t.subject_name}, set {t.set_date} by "
                                     f"{t.set_by_name or t.teacher_username or 'the teacher'})"
                                     f"\nDue {t.due_date}\n\n{t.instructions or ''}"
                              + (f"\n\nResources: {t.resources}" if t.resources else ""))
            detail.configure(state="disabled")
        tree.bind("<<TreeviewSelect>>", show)
        if self.is_pupil:
            bar = ttk.Frame(box)
            bar.pack(fill="x", pady=(4, 0))
            ttk.Button(bar, text="Hand in selected", command=lambda: (
                self._hand_in(tasks[tree.selection()[0]]) if tree.selection() else
                messagebox.showinfo("Homework", "Select the homework first.",
                                    parent=self._top()))).pack(side="left")
        box = _box(f, "Handed in and marked")
        tree2 = _tree(box, [("due", "Due", 90), ("subj", "Subject", 90),
                            ("title", "Title", 220), ("status", "Status", 80),
                            ("mark", "Mark", 60), ("grade", "Grade", 60),
                            ("detail", "Feedback", 260)], height=8)
        for t, w in h["done"]:
            tag = {"Missing": "bad", "Late": "warn", "Graded": "good"}.get(w.status, "")
            tree2.insert("", "end", tags=(tag,) if tag else (), values=(
                _date(t.due_date), t.subject_code, t.title, w.status,
                "" if w.mark is None else f"{w.mark:g}" + (f"/{t.points}" if t.points else "%"),
                w.grade or "", (w.feedback or "").replace("\n", " ")))

    def _hand_in(self, task) -> None:
        from education_system.systems.secondary.modules.curriculum.domain import homework as HW
        note = simpledialog.askstring("Hand in", f"Hand in '{task.title}'?\n\nAdd a note for "
                                      "your teacher (optional):", parent=self._top())
        if note is None:
            return
        try:
            w = HW.hand_in(task.task_id, actor=self.principal, pupil_id=self.pupil_id,
                           note=note)
        except _ERRORS as e:
            messagebox.showerror("Hand in", _problems(e), parent=self._top())
            return
        messagebox.showinfo("Hand in", f"Handed in{' (late)' if w.status == 'Late' else ''}.",
                            parent=self._top())
        self.show(self.section)

    def _draw_attendance(self, f) -> None:
        from education_system.systems.secondary.modules.attendance.domain import attendance as AT
        a = PT.attendance(self.principal, self.pupil_id)
        s = a["summary"]
        if s is None or not s.possible:
            _empty(f, "No attendance recorded yet this year.")
            return
        pct = s.attendance_pct or 0
        ttk.Label(f, text=f"{pct}% attendance since {a['since']:%d %B %Y}",
                  font=("", 14, "bold"), foreground="#060" if pct >= 95 else
                  "#a60" if pct >= 90 else "#a00").pack(anchor="w")
        ttk.Label(f, text=f"{s.attended} of {s.possible} sessions attended · "
                          f"{s.authorised} authorised absence · {s.unauthorised} unauthorised "
                          f"· {s.late} late", foreground="#555").pack(anchor="w", pady=(0, 8))
        if pct < 90:
            ttk.Label(f, text="Below 90% counts as persistent absence. Please speak to the "
                              "form tutor if there is a reason we should know about.",
                      foreground="#a00", wraplength=700).pack(anchor="w", pady=(0, 8))
        box = _box(f, "Absences and lates (last 60 days)")
        tree = _tree(box, [("date", "Date", 100), ("session", "Session", 70),
                           ("code", "Code", 50), ("detail", "Meaning", 320)], height=10)
        shown = 0
        for m in a["recent"]:
            cat = AT.category_of(m.code)
            if cat == AT.PRESENT and m.code != "L":
                continue
            shown += 1
            tree.insert("", "end", tags=("bad",) if cat == AT.UNAUTHORISED else (
                "warn",) if m.code in ("L", "U") else (), values=(
                _date(m.date), m.session, m.code, m.label
                + (f" ({m.minutes_late} min)" if m.minutes_late else "")))
        if not shown:
            ttk.Label(box, text="No absences or lates. Well done!",
                      foreground="#060").pack(anchor="w")

    def _draw_grades(self, f) -> None:
        g = PT.grades(self.principal, self.pupil_id)
        box = _box(f, f"Subjects ({g['year']})")
        if not g["overview"]:
            _empty(box, "No marked work yet this year.")
        else:
            tree = _tree(box, [("subj", "Subject", 120), ("count", "Pieces", 70),
                               ("avg", "Average", 80), ("grade", "Latest grade", 100)], height=8)
            for r in g["overview"]:
                tree.insert("", "end", values=(r["subject_code"], r["count"],
                                               "" if r["avg_pct"] is None else f"{r['avg_pct']}%",
                                               r["latest_grade"] or ""))
        box = _box(f, "Marked work")
        tree = _tree(box, [("date", "Date", 90), ("subj", "Subject", 80),
                           ("title", "Assessment", 220), ("marks", "Marks", 80),
                           ("pct", "%", 60), ("grade", "Grade", 60),
                           ("detail", "Comment", 240)], height=12)
        for e in g["entries"]:
            tree.insert("", "end", values=(
                _date(e.assessment_date), e.subject_code, e.assessment_name,
                "" if e.marks_awarded is None else f"{e.marks_awarded:g}"
                + (f"/{e.max_marks:g}" if e.max_marks else ""),
                "" if e.mark_pct is None else e.mark_pct, e.grade or "", e.comments or ""))

    def _draw_reports(self, f) -> None:
        from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
        r = PT.reports(self.principal, self.pupil_id)
        box = _box(f, "School reports")
        if not r.get("issued"):
            _empty(box, "No school report has been issued yet.")
        else:
            rtree = _tree(box, [("name", "Report", 260), ("issued", "Issued", 110),
                                ("seen", "", 160)], height=min(6, len(r["issued"])))
            for cy, rep in r["issued"]:
                rtree.insert("", "end", iid=str(rep.report_id), values=(
                    cy.title, (rep.issued_at or "")[:10],
                    "acknowledged" if rep.acknowledged_at else ""))
            rtree.bind("<Double-1>", lambda _e: self._open_school_report(rtree))
            ttk.Button(box, text="Read report", command=lambda: self._open_school_report(
                rtree)).pack(anchor="w", pady=(4, 0))
        box = _box(f, "Latest report" + (f" - {r['point'][0].name}" if r["point"] else ""))
        if not r["point"]:
            _empty(box, "No report has been published yet.")
        else:
            pt, rows = r["point"]
            tree = _tree(box, [("subj", "Subject", 100), ("now", "Working at", 100),
                               ("pred", "Predicted", 90), ("att", "Attitude", 80),
                               ("hw", "Homework", 80), ("detail", "Comment", 300)], height=8)
            for x in rows:
                tree.insert("", "end", values=(x.subject_code, x.working_at or "",
                                               x.predicted or "", x.attitude or "",
                                               x.homework or "", x.comment or ""))
            ttk.Label(box, text="Attitude and homework: 1 = excellent ... 4 = a concern.",
                      foreground="#777").pack(anchor="w")
        box = _box(f, "Targets")
        if not r["targets"]:
            _empty(box, "No targets set yet.")
        else:
            tree = _tree(box, [("subj", "Subject", 100), ("tgt", "Target", 80),
                               ("now", "Now", 80), ("from", "From", 160),
                               ("status", "Progress", 110)], height=8)
            for x in r["targets"]:
                t = x["target"]
                tag = {"Above": "good", "Below": "warn", "Well below": "bad"}.get(x["status"])
                tree.insert("", "end", tags=(tag,) if tag else (), values=(
                    t.subject_code, t.target_grade, x["current"] or "-", x["from"] or "",
                    x["status"]))
        m = r["mocks"]
        box = _box(f, "Mock exams" + (f" - {m['series'].name}" if m else ""))
        if not m:
            _empty(box, "No mock exam results released yet.")
        else:
            tree = _tree(box, [("subj", "Subject", 120), ("tier", "Tier", 90),
                               ("marks", "Marks", 90), ("pct", "%", 60), ("grade", "Grade", 60),
                               ("tgt", "Target", 60), ("detail", "Against target", 160)],
                         height=8)
            for x in m["subjects"]:
                tree.insert("", "end", values=(
                    x["subject_name"], x["tier"], f"{MX._num(x['marks'])}/{MX._num(x['max'])}"
                    if x["marks"] is not None else "", x["pct"] if x["pct"] is not None else "",
                    x["grade"] or "-", x["target"] or "", x["note"] or x["vs_target"]))

    def _open_school_report(self, tree) -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("School report", "Select a report first.",
                                parent=tree.winfo_toplevel())
            return
        rid = int(sel[0])
        try:
            got = PT.school_report(self.principal, self.pupil_id, rid)
        except (PT.PermissionDenied, PT.NotFound) as e:
            messagebox.showerror("School report", str(e), parent=tree.winfo_toplevel())
            return
        win = make_toplevel(tree.winfo_toplevel())
        win.title(got["content"]["cycle"]["title"])
        win.geometry("760x560")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        t = tk.Text(frm, wrap="word", font=("TkFixedFont", 10))
        t.insert("1.0", got["text"])
        t.configure(state="disabled")
        t.pack(fill="both", expand=True)
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        if self.principal.is_parent:
            rep = got["report"]
            label = tk.StringVar(value=f"Acknowledged {rep.acknowledged_at[:10]}"
                                 if rep.acknowledged_at else "")

            def ack() -> None:
                try:
                    done = PT.acknowledge_report(self.principal, self.pupil_id, rid)
                except (PT.PermissionDenied, PT.NotFound) as e:
                    messagebox.showerror("School report", str(e), parent=win)
                    return
                label.set(f"Acknowledged {done.acknowledged_at[:10]}")
                b.state(["disabled"])
            b = ttk.Button(bar, text="I have read this report", command=ack)
            b.pack(side="left")
            if rep.acknowledged_at:
                b.state(["disabled"])
            ttk.Label(bar, textvariable=label, foreground="#555").pack(side="left", padx=8)

    def _draw_exams(self, f) -> None:
        d = PT.exams(self.principal, self.pupil_id)
        c = d["candidate"]
        ttk.Label(f, text="Candidate number: " + (c.candidate_number if c else "not given yet"),
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
        for sl in d.get("results", []):
            s = sl["series"]
            box = _box(f, f"Results - {s.name}")
            tree = _tree(box, [("subject", "Subject", 200), ("qual", "Qualification", 110),
                               ("board", "Board", 110), ("grade", "Grade", 80),
                               ("note", "", 200)],
                         height=min(12, len(sl["results"]) + len(sl["awaited"])))
            for r in sl["results"]:
                grade = {"Pending": "awaited", "Withheld": "withheld"}.get(r.status,
                                                                           r.final_grade)
                note = ("under review" if r.status == "Remarked" else
                        f"changed from {r.original_grade} after review"
                        if r.status == "Adjusted" and r.original_grade else "")
                tree.insert("", "end", values=(r.subject_name, r.qualification, r.exam_board,
                                               grade, note))
            for e in sl["awaited"]:
                tree.insert("", "end", values=(e.subject_name, e.qualification, e.exam_board,
                                               "awaited", ""))
        if not d["statements"]:
            _empty(f, "No exam entries have been confirmed yet.")
        for st in d["statements"]:
            s = st["series"]
            box = _box(f, f"Statement of entry - {s.name}")
            tree = _tree(box, [("subject", "Subject", 200), ("qual", "Qualification", 110),
                               ("board", "Board", 110), ("code", "Entry code", 90),
                               ("tier", "Tier", 90)], height=min(10, len(st["entries"])))
            for e in st["entries"]:
                tree.insert("", "end", values=(e.subject_name, e.qualification, e.exam_board,
                                               e.entry_code, "" if e.tier == "N/A" else e.tier))
            if st["access"]:
                ttk.Label(box, text=f"Access arrangements: {st['access']}").pack(anchor="w")
            if s.results_day:
                ttk.Label(box, text=f"Results day: {_date(s.results_day)}",
                          foreground="#555").pack(anchor="w")
        ttk.Label(f, text="Please check the subjects, tiers and name. If anything is wrong, "
                          "tell the exams officer straight away.", foreground="#777",
                  wraplength=600).pack(anchor="w", pady=(8, 0))

    def _draw_behaviour(self, f) -> None:
        b = PT.behaviour(self.principal, self.pupil_id)
        box = _box(f, "Points this year")
        nxt = b["next"]
        ttk.Label(box, text=f"{b['positive_points']} positive point(s)"
                  + (f" · house: {b['house'].name}" if b["house"] else ""),
                  font=("", 12, "bold")).pack(anchor="w")
        ttk.Label(box, text=("Rewards reached: " + ", ".join(
            m["level"] for m in reversed(b["milestones"])) if b["milestones"] else
            "No reward levels reached yet.")
            + (f" {nxt['needed']} more to {nxt['next']}." if nxt["next"] else ""),
            foreground="#555").pack(anchor="w")
        self._draw_detentions(f, b.get("detentions") or {"upcoming": [], "past": []})
        self._draw_exclusions(f, b.get("exclusions") or [])
        box = _box(f, "Shared by school")
        if not b["entries"]:
            _empty(box, "Nothing shared yet this year.")
            return
        tree = _tree(box, [("date", "Date", 90), ("type", "Type", 140),
                           ("pts", "Points", 60), ("detail", "Details", 380)], height=10)
        for e in b["entries"]:
            tree.insert("", "end", tags=("good",) if e.polarity == "positive" else (),
                        values=(_date(e.entry_date), e.incident_type, f"{e.points:+d}",
                                e.description))

    def _draw_detentions(self, f, dts: dict) -> None:
        if not dts["upcoming"] and not dts["past"]:
            return
        box = _box(f, "Detentions")
        for d in dts["upcoming"]:
            ttk.Label(box, text=f"Coming up: {_date(d.detention_date)}"
                      + (f" at {d.start_time}" if d.start_time else "")
                      + f" - {d.detention_type}, {d.duration_min} minutes"
                      + (f", {d.location}" if d.location else "") + f". Reason: {d.reason}",
                      foreground="#a60", wraplength=640, justify="left").pack(anchor="w")
        if dts["past"]:
            by = {}
            for d in dts["past"]:
                by[d.status] = by.get(d.status, 0) + 1
            ttk.Label(box, text="This year: " + ", ".join(f"{n} {s.lower()}" for s, n in
                                                         by.items()),
                      foreground="#555").pack(anchor="w")

    def _draw_exclusions(self, f, rows: list) -> None:
        if not rows:
            return
        box = _box(f, "Suspensions")
        for x in rows:
            line = f"{x['type']}: {x['period']}" + (
                f" ({x['days']} school day(s))" if x["days"] else "") + f". {x['reason']}"
            if x["return_date"]:
                line += f" Back on {_date(x['return_date'])}."
            if x["reintegration_date"]:
                line += f" Return meeting {_date(x['reintegration_date'])}."
            if x["governors_decision"]:
                line += f" Governors: {x['governors_decision'].lower()}."
            ttk.Label(box, text=line, wraplength=640, justify="left").pack(anchor="w")

    def _draw_library(self, f) -> None:
        lib = PT.library(self.principal, self.pupil_id)
        box = _box(f, "Books out")
        if not lib["out"]:
            _empty(box, "No books out.")
        else:
            tree = _tree(box, [("title", "Title", 280), ("author", "Author", 160),
                               ("out", "Borrowed", 90), ("due", "Due back", 90),
                               ("detail", "", 120)], height=6)
            for x in lib["out"]:
                tree.insert("", "end", tags=("bad",) if x.days_overdue else (), values=(
                    x.book_title, x.book_author or "", _date(x.loan_date), _date(x.due_date),
                    f"{x.days_overdue} day(s) overdue" if x.days_overdue else ""))
        box = _box(f, "Reservations")
        if not lib["holds"]:
            _empty(box, "No reservations.")
        for h in lib["holds"]:
            ttk.Label(box, text=f"{h.book_title} - {h.status}"
                      + (f", collect by {_date(h.expires_on)}" if h.expires_on else "")).pack(
                anchor="w")
        ttk.Label(f, text=f"{lib['total']} book(s) borrowed in total.", foreground="#777").pack(
            anchor="w")

    def _draw_clubs(self, f) -> None:
        rows = PT.clubs(self.principal, self.pupil_id)
        if not rows:
            _empty(f, "Not in any clubs yet. See the Enrichment notices or ask your form tutor.")
            return
        tree = _tree(f, [("name", "Club", 200), ("when", "When", 160), ("room", "Room", 80),
                         ("leader", "Leader", 140), ("status", "Status", 90),
                         ("detail", "Consent", 120)], height=10)
        for m, c in rows:
            tree.insert("", "end", tags=("warn",) if m.status == "Waitlisted" else (), values=(
                m.club_name or (c.name if c else ""), c.when if c else "", (c.room or "") if c
                else "", (c.leader or "") if c else "", m.status,
                ("given " + _date(m.consent_on)) if m.consent_on else (
                    "needed" if c and c.consent_required else "")))

    def _draw_options(self, f) -> None:
        rounds = PT.options(self.principal, self.pupil_id)
        if not rounds:
            _empty(f, "There are no options choices for this year group.")
            return
        for x in rounds:
            r = x["round"]
            box = _box(f, f"{r.name} ({r.status})")
            ttk.Label(box, text=f"Choose {r.choices_required} subject(s)"
                      + (f" and {r.reserves_required} reserve(s)" if r.reserves_required else "")
                      + (f" by {_date(r.closes_on)}" if r.closes_on else ""),
                      foreground="#555").pack(anchor="w")
            if x["rules"]:
                ttk.Label(box, text="Rules: " + "; ".join(u.label for u in x["rules"]),
                    foreground="#555", wraplength=700).pack(anchor="w")
            ch = x["choices"]
            if x["allocations"]:
                ttk.Label(box, text="Your subjects: " + ", ".join(
                    f"{a.name} (block {a.block})" for a in x["allocations"]),
                    font=("", 10, "bold")).pack(anchor="w", pady=(4, 0))
            elif ch:
                picks = [c for c in ch.choices if not c.is_reserve]
                res = [c for c in ch.choices if c.is_reserve]
                ttk.Label(box, text="Choices: " + ", ".join(f"{c.rank}. {c.name}" for c in picks)
                          + ("  ·  Reserves: " + ", ".join(c.name for c in res) if res else "")
                          + f"  (sent {_date(ch.submitted_at)})").pack(anchor="w", pady=(4, 0))
            else:
                ttk.Label(box, text="No choices made yet.", foreground="#a60").pack(anchor="w")
            if x["can_choose"]:
                ttk.Button(box, text="Change choices" if ch else "Make choices",
                           command=lambda x=x: self._choose(x)).pack(anchor="w", pady=(6, 0))
            sub = ttk.Frame(box)
            sub.pack(fill="x", pady=(6, 0))
            for s in x["subjects"]:
                g = x["guidance"].get(s.subject_id)
                ttk.Label(sub, text=f"• {s.name}" + (f" - {g}" if g else ""),
                          wraplength=700, foreground="#333").pack(anchor="w")

    def _choose(self, x: dict[str, Any]) -> None:
        r = x["round"]
        names = {s.name: s.subject_id for s in x["subjects"]}
        win = make_toplevel(self._top())
        win.title(r.name)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        current = [c for c in (x["choices"].choices if x["choices"] else ())]
        vars_: list[tk.StringVar] = []
        rows = [(f"Choice {i}", i) for i in range(1, r.choices_required + 1)] + \
               [(f"Reserve {i}", r.choices_required + i) for i in range(1, r.reserves_required
                                                                         + 1)]
        for label, rank in rows:
            v = tk.StringVar(value=next((c.name for c in current if c.rank == rank), ""))
            row = ttk.Frame(frm)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=10).pack(side="left")
            ttk.Combobox(row, textvariable=v, values=list(names), state="readonly",
                         width=32).pack(side="left")
            vars_.append(v)

        def save() -> None:
            picks = [names.get(v.get()) for v in vars_]
            if None in picks:
                messagebox.showerror(r.name, "Choose a subject in every box.", parent=win)
                return
            try:
                PT.submit_options(self.principal, self.pupil_id, r.round_id,
                                  picks[:r.choices_required], picks[r.choices_required:])
            except _ERRORS as e:
                messagebox.showerror(r.name, _problems(e), parent=win)
                return
            win.destroy()
            messagebox.showinfo(r.name, "Choices sent to the school.", parent=self._top())
            self.show("Options")

        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Send choices", command=save).pack(side="right")

    def _draw_sixth_form(self, f) -> None:
        st = PT.sixth_form(self.principal, self.pupil_id)
        me = "your" if self.is_pupil else "their"
        if st["locked"] and not st["choices"]:
            _empty(f, st["locked"])
            return
        box = _box(f, "A-level choices")
        if st["options"] is None:
            ttk.Label(box, text="The sixth form's course list isn't available just now.",
                      foreground="#a60").pack(anchor="w")
        if not st["choices"]:
            ttk.Label(box, text=f"Choose three A-levels to study at the sixth form. Each "
                                "course's entry requirements are shown below.",
                      wraplength=700, justify="left").pack(anchor="w")
        else:
            if not st["results_known"]:
                msg, colour = (f"Results awaited - each course shows what {me} results need "
                               "to be.", "#555")
            elif st["all_met"]:
                msg, colour = (f"{me.capitalize()} results meet the entry requirements for "
                               "all three courses - "
                               + ("you" if self.is_pupil else "they")
                               + " can study the courses chosen.", "#1a7f37")
            else:
                bad = [c["course"] for c in st["chosen"] if c["outcome"] != "Met"]
                msg, colour = (f"{me.capitalize()} results don't meet the entry requirements "
                               f"for {', '.join(bad)}.", "#b42318")
            ttk.Label(box, text=msg, foreground=colour, wraplength=700, justify="left",
                      font=("", 10, "bold")).pack(anchor="w", pady=(0, 4))
            tree = _tree(box, [("course", "Course", 170), ("need", "Entry requirements", 330),
                               ("outcome", "Results", 100), ("detail", "Detail", 220),
                               ("block", "Block", 90)],
                         height=3)
            for c in st["chosen"]:
                self._course_row(tree, c, st["results_known"])
            clashes = (st.get("blocks") or {}).get("clashes") or []
            if clashes:
                ttk.Label(box, text=" ".join(clashes) + ". Choose one course from each "
                          "block.",
                          foreground="#b42318", wraplength=700, justify="left"
                          ).pack(anchor="w", pady=(4, 0))
        if st["locked"]:
            ttk.Label(box, text=st["locked"], foreground="#555").pack(anchor="w", pady=(4, 0))
        if st["can_choose"] and st["options"] is not None:
            ttk.Button(box, text="Change choices" if st["choices"] else "Choose A-levels",
                       command=lambda: self._choose_sixth_form(st)).pack(anchor="w",
                                                                          pady=(6, 0))
        if st["results_known"] and st["all_met"] is False:
            alt = _box(f, "Courses " + ("you" if self.is_pupil else "they")
                       + " can choose from")
            if st["can_choose_from"]:
                ttk.Label(alt, text=", ".join(st["can_choose_from"]), wraplength=700,
                          justify="left").pack(anchor="w")
            else:
                ttk.Label(alt, text="None of the other courses' requirements are met - "
                                    "please talk to the sixth form.", foreground="#b42318"
                          ).pack(anchor="w")
            if st["near_miss"]:
                ttk.Label(alt, text="One grade short (ask the sixth form): "
                          + ", ".join(st["near_miss"]), foreground="#555", wraplength=700,
                          justify="left").pack(anchor="w", pady=(4, 0))
        lines = SC.block_lines(st.get("blocks"))
        if lines:
            ob = _box(f, f"Option blocks ({st['blocks']['academic_year']})")
            ttk.Label(ob, text="Courses in the same block are taught at the same time, so "
                               "choose one course from each block. A full course has no "
                               "places left.", wraplength=700, justify="left"
                      ).pack(anchor="w", pady=(0, 4))
            for line in lines:
                ttk.Label(ob, text=line).pack(anchor="w")
        if st["options"]:
            every = _box(f, "Every course and what it needs")
            tree = _tree(every, [("course", "Course", 170), ("need", "Entry requirements", 330),
                                 ("outcome", "Results", 100), ("detail", "Detail", 220),
                                 ("block", "Block", 90)],
                         height=min(14, len(st["options"])))
            for c in st["options"]:
                self._course_row(tree, c, st["results_known"])

    @staticmethod
    def _course_row(tree, c: dict[str, Any], known: bool) -> None:
        need = "; ".join(c.get("requirements") or []) or "No entry requirements"
        if not known and c.get("requirements"):
            outcome, tag, detail = "Awaited", "muted", ""
        else:
            outcome = c["outcome"] if c.get("requirements") else "Met"
            tag = {"Met": "good", "Near miss": "warn", "Not met": "bad"}.get(outcome, "muted")
            detail = "; ".join(x["detail"] for x in c.get("checks") or []
                               if x["outcome"] != "Met")
        block = "/".join(c.get("blocks") or []) or "-"
        if c.get("full"):
            block += " (full)"
        tree.insert("", "end", tags=(tag,), values=(c["course"], need, outcome, detail,
                                                    block))

    def _choose_sixth_form(self, st: dict[str, Any]) -> None:
        mine = {c.lower() for c in st["choices"]}
        if st["results_known"]:  # only courses the results meet (and with places)
            names = st["eligible"]
        else:  # a full course only if it's already chosen
            names = [o["course"] for o in st["options"]
                     if not o.get("full") or o["course"].lower() in mine]
        win = make_toplevel(self._top())
        win.title("A-level choices")
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=("Your results are in: you can choose from the courses whose "
                             "entry requirements they meet." if st["results_known"] else
                             "Choose three different A-levels."), wraplength=380,
                  justify="left").pack(anchor="w", pady=(0, 6))
        lines = SC.block_lines(st.get("blocks"))
        if lines:
            ttk.Label(frm, text="One course from each block:\n" + "\n".join(lines),
                      foreground="#555", wraplength=380, justify="left"
                      ).pack(anchor="w", pady=(0, 6))
        vars_ = []
        for i in range(3):
            v = tk.StringVar(value=st["choices"][i] if i < len(st["choices"]) else "")
            row = ttk.Frame(frm)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"A-level {i + 1}", width=10).pack(side="left")
            ttk.Combobox(row, textvariable=v, values=names, state="readonly",
                         width=32).pack(side="left")
            vars_.append(v)

        def save() -> None:
            try:
                out = PT.choose_sixth_form(self.principal, self.pupil_id,
                                           [v.get() for v in vars_])
            except _ERRORS as e:
                messagebox.showerror("A-level choices", _problems(e), parent=win)
                return
            win.destroy()
            messagebox.showinfo("A-level choices", "Choices saved."
                                + (" The sixth form has been told." if out["sixth_form"]
                                   == "updated" else ""), parent=self._top())
            self.show("Sixth Form")

        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Save choices", command=save).pack(side="right")

    def _draw_calendar(self, f) -> None:
        terms = PT.term_dates(self.principal, self.pupil_id)
        box = _box(f, "Term dates and holidays")
        if not terms:
            _empty(box, "Term dates haven't been published yet.")
        for name, start, end in terms:
            ttk.Label(box, text=f"{name:<28} {_date(start)} - {_date(end)}").pack(anchor="w")
        box = _box(f, "Events (next 60 days)")
        rows = PT.calendar(self.principal, self.pupil_id)
        if not rows:
            _empty(box, "No events coming up.")
            return
        tree = _tree(box, [("date", "Date", 110), ("time", "Time", 100),
                           ("title", "Event", 260), ("where", "Where", 140),
                           ("detail", "", 120)], height=10)
        for e in rows:
            tree.insert("", "end", tags=("muted",) if e.status == "Cancelled" else (), values=(
                _date(e.start_date) + ("" if e.end_date == e.start_date else
                                       f" - {_date(e.end_date)}"),
                "All day" if e.all_day else f"{e.start_time or ''}-{e.end_time or ''}",
                e.title, e.location or "", e.status if e.status != "Scheduled" else
                (f"£{e.cost:.2f}" if e.cost else "")))

    def _draw_my_details(self, f) -> None:
        d = PT.details(self.principal, self.pupil_id)
        p = d["pupil"]
        form = d["form"]
        rows = [("Name", p.full_name + (f" (known as {p.preferred_name})" if p.preferred_name
                                        else "")),
                ("Admission number", p.admission_no), ("Year", str(p.year_group)),
                ("Form", form.get("form_group") or "not set yet"),
                ("Form tutor", (form.get("form_tutor") or "")
                 + (f" ({form['form_tutor_email']})" if form.get("form_tutor_email") else "")),
                ("Form room", form.get("form_room") or ""),
                ("Date of birth", p.date_of_birth),
                ("School e-mail", d.get("school_email") or ""),
                ("Address", ", ".join(x for x in (p.address_line1, p.address_line2, p.town,
                                                  p.postcode) if x))]
        grid = ttk.Frame(f)
        grid.pack(anchor="w")
        for i, (k, v) in enumerate(rows):
            ttk.Label(grid, text=k + ":", foreground="#555").grid(row=i, column=0, sticky="w",
                                                                 padx=(0, 12), pady=2)
            ttk.Label(grid, text=v or "-").grid(row=i, column=1, sticky="w", pady=2)
        if "contacts" in d:
            box = _box(f, "Contacts the school holds")
            tree = _tree(box, [("name", "Name", 180), ("rel", "Relationship", 110),
                               ("pri", "Priority", 60), ("email", "E-mail", 200),
                               ("phone", "Phone", 120)], height=5)
            for c in d["contacts"]:
                tree.insert("", "end", values=(c.full_name, c.relationship, c.priority,
                                               c.email or "", c.phone or ""))
        ttk.Label(f, text="If anything here is wrong, please tell the school office.",
                  foreground="#777").pack(anchor="w", pady=(8, 0))


def open_portal_window(owner: tk.Misc, *, principal: Principal) -> None:
    """The parent portal as a window (for staff who are also parents here)."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Parent portal — {SYSTEM_NAME}")
    window_sizing.fit(win, "1100x760", (900, 600))
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    PortalFrame(frm, principal=principal)


class PortalWindow:
    """The window a pupil or parent gets when they sign in."""

    def __init__(self, auth, principal: Principal) -> None:
        self.auth, self.principal = auth, principal
        self.root = tk.Tk()
        who = "Pupil" if principal.is_student else "Parent"
        self.root.title(f"{SYSTEM_NAME} — {who} portal")
        self.root.report_callback_exception = self._on_error
        window_sizing.fit(self.root, "1400x900", (1200, 800))
        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        head = ttk.Frame(main)
        head.pack(fill="x", pady=(0, 8))
        ttk.Button(head, text="Logout", command=self._logout).pack(side="left")
        ttk.Button(head, text="Change Password", command=self._change_password).pack(
            side="left", padx=(6, 0))
        ttk.Label(head, text=f"{SYSTEM_NAME} · {who} portal", font=("", 14, "bold")).pack(
            side="left", padx=20)
        ttk.Button(head, text="⏻ Shutdown", command=self._shutdown).pack(side="right")
        ttk.Label(head, text=f"Signed in: {principal.username}", foreground="#555").pack(
            side="right", padx=10)
        self.status_var = tk.StringVar(value="Ready")
        body = ttk.Frame(main)
        body.pack(fill="both", expand=True)
        self.portal = PortalFrame(body, principal=principal, on_status=self.status_var.set)
        ttk.Label(main, textvariable=self.status_var, foreground="#555").pack(anchor="w",
                                                                          pady=(6, 0))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        from education_system.platform.delivery.gui.idle_timeout import install_idle_logout
        self._cancel_idle = install_idle_logout(self.root, self._idle_logout)

    def _on_error(self, exc_type, exc, tb) -> None:
        logger.error("Unhandled error in the secondary portal", exc_info=(exc_type, exc, tb))
        activity_log.record("error", outcome="error", error=exc_type.__name__)
        try:
            messagebox.showerror(SYSTEM_NAME, f"Something went wrong:\n{exc}", parent=self.root)
        except tk.TclError:
            pass

    def _change_password(self) -> None:
        from education_system.platform.delivery.gui.change_password_gui import (
            open_change_password_dialog,
        )
        open_change_password_dialog(self.root, auth=self.auth)

    def _sign_out(self) -> None:
        try:
            self._cancel_idle()
        except Exception:  # noqa: BLE001
            logger.debug("Idle watcher cancel raised", exc_info=True)
        try:
            self.auth.logout()
        except Exception:  # noqa: BLE001
            logger.exception("Logout failed")

    def _logout(self) -> None:
        from education_system import switch as _switch
        activity_log.end_session("logout")
        self._sign_out()
        _switch.request_logout("gui")
        self.root.destroy()

    def _idle_logout(self) -> None:
        from education_system import switch as _switch
        from education_system.platform.delivery.gui import idle_timeout as _idle
        activity_log.end_session("idle_timeout")
        self._sign_out()
        _switch.request_logout("gui")
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        _idle.notify_signed_out(self.root, "Signed out", "You've been signed out due to "
                                "inactivity. Please sign in again to continue.")

    def _shutdown(self) -> None:
        if not messagebox.askyesno("Shutdown", f"Close the {SYSTEM_NAME}?", parent=self.root):
            return
        activity_log.end_session("shutdown")
        self._sign_out()
        self.root.destroy()
        sys.exit(0)

    def _on_close(self) -> None:
        activity_log.end_session("window_closed")
        self._sign_out()
        self.root.destroy()


def run_portal(auth, principal: Principal) -> int:
    app = PortalWindow(auth, principal)
    app.root.mainloop()
    return 0
