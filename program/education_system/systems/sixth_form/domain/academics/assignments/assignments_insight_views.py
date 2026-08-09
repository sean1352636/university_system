"""Tkinter views for coursework analysis and administration.

Adds an **Insight** tab to the Assignments window, itself a notebook:

* Student — one learner's timeline, targets, trend and weighted grade.
* Cohort — distribution, criterion weak spots, subject/teacher compare.
* Concerns — non-submission and underperformance, ranked for referral.
* Operations — clashes, digests and cover.
* Exports — marks in and out, coversheets and the sample pack.

Sibling to :mod:`assignments_planning_views`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
    assignments_admin as admin,
    assignments_analytics as analytics,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)


def _names() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name
                 for s in student_data.list_students()}
    except Exception:
        logger.debug("Student names unavailable", exc_info=True)
        return {}


def _teachers() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.staff import (
            staff as staff_data,
        )
        return sorted({s.full_name for s in staff_data.list_staff()
                        if s.is_active})
    except Exception:
        return []


def _fmt(value: float | None, dash: str = "—") -> str:
    return f"{value:g}" if value is not None else dash


def _tree(parent: tk.Misc, spec: list[tuple[str, str, int]],
           height: int = 12) -> ttk.Treeview:
    cols = [key for key, _, _ in spec]
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                          height=height)
    for key, heading, width in spec:
        tree.heading(key, text=heading)
        tree.column(key, width=width,
                     anchor="e" if width <= 70 else "w")
    return tree


# ══ Insight tab ═══════════════════════════════════════════════════

class InsightTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Insight")
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.nb = ttk.Notebook(self.frame)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.student = StudentPane(self.nb, self)
        self.cohort = CohortPane(self.nb, self)
        self.concerns = ConcernsPane(self.nb, self)
        self.operations = OperationsPane(self.nb, self)
        self.exports = ExportsPane(self.nb, self)

    def refresh(self) -> None:
        for pane in (self.student, self.cohort, self.concerns,
                      self.operations, self.exports):
            try:
                pane.refresh()
            except Exception:
                logger.exception("Insight pane refresh failed")


# ══ Student ═══════════════════════════════════════════════════════

class StudentPane:
    def __init__(self, nb: ttk.Notebook, owner: InsightTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Student")
        self._ids: list[str] = []
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.student_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.student_cb.pack(side="left", padx=(2, 8))
        self.student_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self._load())
        ttk.Button(bar, text="Export record...",
                    command=self._export).pack(side="left", padx=4)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", pady=(0, 4))

        panes = ttk.Panedwindow(self.frame, orient="vertical")
        panes.pack(fill="both", expand=True)
        top = ttk.Frame(panes)
        panes.add(top, weight=3)
        bottom = ttk.Frame(panes)
        panes.add(bottom, weight=2)

        self.tree = _tree(top, [
            ("due", "Due", 95), ("subject", "Subject", 130),
            ("title", "Title", 230), ("state", "State", 100),
            ("marks", "Mark", 90), ("percent", "%", 55),
            ("grade", "Grade", 55),
        ], height=11)
        self.tree.tag_configure("missing", background="#ffd0d0")
        self.tree.tag_configure("marked", background="#d8f4d8")
        self.tree.pack(fill="both", expand=True)

        self.subjects = _tree(bottom, [
            ("subject", "Subject", 140), ("target", "Target", 60),
            ("predicted", "Predicted", 75), ("actual", "Actual", 60),
            ("gap", "Gap", 45), ("weighted", "Weighted", 75),
            ("wgrade", "Grade", 55), ("trend", "Trend", 190),
        ], height=7)
        self.subjects.tag_configure("under", background="#ffd0d0")
        self.subjects.tag_configure("declining", background="#ffe0b0")
        self.subjects.pack(fill="both", expand=True)

    def refresh(self) -> None:
        names = _names()
        self._ids = sorted(names)
        self.student_cb.configure(
            values=[f"{sid} — {names[sid]}" for sid in self._ids])
        if self._ids and not self.student_cb.get():
            self.student_cb.current(0)
        self._load()

    def _current(self) -> str | None:
        idx = self.student_cb.current()
        if 0 <= idx < len(self._ids):
            return self._ids[idx]
        return None

    def _load(self) -> None:
        for tree in (self.tree, self.subjects):
            for i in tree.get_children():
                tree.delete(i)
        sid = self._current()
        if sid is None:
            self.summary_var.set("")
            return
        history = analytics.student_history(sid)
        for entry in history.entries:
            tags = []
            if entry.is_missing:
                tags.append("missing")
            elif entry.percent is not None:
                tags.append("marked")
            mark = ("—" if entry.submission.marks is None
                    else f"{entry.submission.marks:g}"
                         f"/{_fmt(entry.assignment.max_marks)}")
            self.tree.insert("", "end", values=(
                entry.due_date or "—", entry.assignment.subject_name,
                entry.assignment.title, entry.state, mark,
                _fmt(entry.percent), entry.submission.grade or "—",
            ), tags=tuple(tags))

        for subject in history.subjects:
            comparison = analytics.target_comparison(sid, subject)
            weighted = analytics.weighted_grade(sid, subject)
            trend = analytics.student_trend(sid, subject_name=subject)
            tags = []
            if comparison.is_underperforming:
                tags.append("under")
            elif trend.is_declining:
                tags.append("declining")
            self.subjects.insert("", "end", values=(
                subject, comparison.target_grade or "—",
                comparison.predicted_grade or "—",
                comparison.actual_grade or "—",
                comparison.grades_below_target
                if comparison.grades_below_target else "—",
                _fmt(weighted.percent), weighted.grade or "—",
                trend.message[:44],
            ), tags=tuple(tags))
        self.summary_var.set(history.message)

    def _export(self) -> None:
        sid = self._current()
        if sid is None:
            return
        path = filedialog.asksaveasfilename(
            title="Export record", defaultextension=".csv",
            initialfile=f"coursework_{sid}.csv",
            parent=self.frame.winfo_toplevel())
        if not path:
            return
        admin.export_history(sid, path=path)
        messagebox.showinfo("Export", f"Written to {path}")


# ══ Cohort ════════════════════════════════════════════════════════

class CohortPane:
    def __init__(self, nb: ttk.Notebook, owner: InsightTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Cohort")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_e = ttk.Entry(bar, width=16)
        self.subject_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=10)
        self.year_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="View:").pack(side="left")
        self.mode_cb = ttk.Combobox(
            bar, values=("Subjects", "Teachers", "Criteria"),
            state="readonly", width=12)
        self.mode_cb.current(0)
        self.mode_cb.pack(side="left", padx=(2, 8))
        self.mode_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self.refresh())
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", pady=(0, 4))

        self.tree = _tree(self.frame, [
            ("name", "Name", 240), ("count", "Marked", 65),
            ("mean", "Mean", 65), ("median", "Median", 65),
            ("low", "Low", 55), ("high", "High", 55),
            ("detail", "Grades", 300),
        ], height=14)
        self.tree.tag_configure("weak", background="#ffd0d0")
        self.tree.pack(fill="both", expand=True)

        self.note_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.note_var,
                   foreground="#555", anchor="w",
                   wraplength=900).pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        subject = self.subject_e.get().strip() or None
        year = self.year_e.get().strip() or None
        mode = self.mode_cb.get()
        self.note_var.set("")

        if mode == "Criteria":
            self._criteria(subject)
        else:
            rows = (analytics.compare_subjects(year_group=year)
                    if mode == "Subjects"
                    else analytics.compare_teachers(
                        subject_name=subject))
            for name, dist in rows.items():
                grades = "  ".join(f"{g} {n}" for g, n
                                    in dist.by_grade.items())
                self.tree.insert("", "end", values=(
                    name, dist.count, _fmt(dist.mean),
                    _fmt(dist.median), _fmt(dist.lowest),
                    _fmt(dist.highest), grades))
            if mode == "Teachers":
                self.note_var.set(
                    "A difference between two teachers has many "
                    "innocent explanations — different sets, different "
                    "pieces. This is a question to ask, not an answer.")

        summary = analytics.cohort_summary(subject_name=subject,
                                            year_group=year)
        self.summary_var.set(
            f"{summary['assignments']} assignment(s)  ·  "
            f"{summary['marked']}/{summary['submissions']} marked  ·  "
            f"{summary['missing']} missing  ·  "
            f"{summary['distribution'].message}")

    def _criteria(self, subject: str | None) -> None:
        self.tree.heading("name", text="Criterion")
        self.tree.heading("count", text="Scored")
        self.tree.heading("mean", text="Average")
        self.tree.heading("median", text="Max")
        self.tree.heading("low", text="Facility")
        rows = []
        for a in data.list_assignments(subject_name=subject):
            for weak in analytics.criterion_weaknesses(a.assignment_id):
                rows.append((a, weak))
        rows.sort(key=lambda pair: (pair[1].facility is None,
                                     pair[1].facility or 0))
        for a, weak in rows:
            self.tree.insert("", "end", values=(
                f"{weak.label}  ({a.title[:20]})", weak.scored,
                _fmt(weak.average), f"{weak.max_marks:g}",
                "—" if weak.facility is None else f"{weak.facility:g}%",
                "", ""),
                tags=("weak",) if (weak.facility is not None
                                    and weak.facility < 50) else ())
        self.note_var.set(
            "Weakest first. A cohort scoring well overall but "
            "collapsing on one objective has a teaching gap the total "
            "mark hides.")


# ══ Concerns ══════════════════════════════════════════════════════

class ConcernsPane:
    def __init__(self, nb: ttk.Notebook, owner: InsightTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Concerns")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="View:").pack(side="left")
        self.mode_cb = ttk.Combobox(
            bar, values=("Non-submission", "Below target",
                          "Declining"),
            state="readonly", width=16)
        self.mode_cb.current(0)
        self.mode_cb.pack(side="left", padx=(2, 8))
        self.mode_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self.refresh())
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_e = ttk.Entry(bar, width=16)
        self.subject_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.tree = _tree(self.frame, [
            ("student", "Student", 80), ("name", "Name", 170),
            ("a", "", 90), ("b", "", 90), ("c", "", 80),
            ("level", "Level", 100), ("detail", "Detail", 330),
        ], height=15)
        self.tree.tag_configure("referral", background="#ffd0d0")
        self.tree.tag_configure("concern", background="#ffe0b0")
        self.tree.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w", wraplength=900).pack(fill="x",
                                                      pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        subject = self.subject_e.get().strip() or None
        mode = self.mode_cb.get()

        if mode == "Non-submission":
            for key, text in (("a", "Missing"), ("b", "Of"),
                               ("c", "Rate")):
                self.tree.heading(key, text=text)
            rows = analytics.non_submitters(subject_name=subject)
            for row in rows:
                self.tree.insert("", "end", values=(
                    row.student_id, row.student_name, row.missing,
                    row.total, f"{row.rate:g}%", row.level,
                    ", ".join(row.subjects)),
                    tags=("referral",) if row.needs_referral
                    else ("concern",) if row.level == "Concern" else ())
            referrals = sum(1 for r in rows if r.needs_referral)
            self.summary_var.set(
                f"{len(rows)} flagged, {referrals} at referral level. "
                f"A referral should rest on a pattern — the rate "
                f"matters as much as the raw number.")

        elif mode == "Below target":
            for key, text in (("a", "Target"), ("b", "Actual"),
                               ("c", "Gap")):
                self.tree.heading(key, text=text)
            rows = analytics.underperformers(subject_name=subject)
            for row in rows:
                self.tree.insert("", "end", values=(
                    row.student_id, "", row.target_grade or "—",
                    row.actual_grade or "—",
                    row.grades_below_target or 0,
                    "Serious" if row.is_serious else "Below",
                    row.message),
                    tags=("referral",) if row.is_serious
                    else ("concern",))
            self.summary_var.set(
                f"{len(rows)} student-subject(s) below target. One "
                f"grade below is noise; two is a pattern.")

        else:
            for key, text in (("a", "Change"), ("b", "Pieces"),
                               ("c", "")):
                self.tree.heading(key, text=text)
            rows = analytics.declining_students(subject_name=subject)
            for trend in rows:
                self.tree.insert("", "end", values=(
                    trend.student_id, "", f"{trend.change:+g}",
                    trend.sample, "", "Declining",
                    ", ".join(f"{p:g}%" for p in trend.percents)),
                    tags=("concern",))
            self.summary_var.set(
                f"{len(rows)} student(s) trending downwards over their "
                f"last {analytics.TREND_WINDOW} marked pieces.")


# ══ Operations ════════════════════════════════════════════════════

class OperationsPane:
    def __init__(self, nb: ttk.Notebook, owner: InsightTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Operations")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="View:").pack(side="left")
        self.mode_cb = ttk.Combobox(
            bar, values=("Clashes", "Cover"), state="readonly",
            width=12)
        self.mode_cb.current(0)
        self.mode_cb.pack(side="left", padx=(2, 8))
        self.mode_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self.refresh())
        ttk.Button(bar, text="Teacher digest...",
                    command=self._digest).pack(side="left", padx=4)
        ttk.Button(bar, text="Send all digests",
                    command=self._send_all).pack(side="left", padx=4)
        ttk.Button(bar, text="Assign cover...",
                    command=self._cover).pack(side="left", padx=(16, 4))

        self.tree = _tree(self.frame, [
            ("a", "", 110), ("b", "", 150), ("c", "", 150),
            ("d", "", 110), ("e", "", 110), ("detail", "Detail", 320),
        ], height=15)
        self.tree.tag_configure("severe", background="#ffd0d0")
        self.tree.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w", wraplength=900).pack(fill="x",
                                                      pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        if self.mode_cb.get() == "Clashes":
            for key, text in (("a", "Week"), ("b", "Year group"),
                               ("c", "Subjects"), ("d", "Deadlines"),
                               ("e", "Est. hours")):
                self.tree.heading(key, text=text)
            rows = admin.clashes()
            for clash in rows:
                titles = ", ".join(a.title for a in clash.assignments)
                self.tree.insert("", "end", values=(
                    clash.week_start, clash.year_group or "—",
                    ", ".join(clash.subjects), clash.count,
                    f"{clash.estimated_hours:g}" or "—", titles),
                    tags=("severe",) if clash.is_severe else ())
            self.summary_var.set(
                f"{len(rows)} week(s) carrying more than one deadline. "
                f"Sometimes unavoidable — but a head of year should see "
                f"it before the students do.")
        else:
            for key, text in (("a", "#"), ("b", "Owner"),
                               ("c", "Cover marker"), ("d", "From"),
                               ("e", "Until")):
                self.tree.heading(key, text=text)
            rows = admin.list_covered()
            for a in rows:
                self.tree.insert("", "end", values=(
                    a.assignment_id, a.teacher or "—",
                    a.cover_marker or "—", a.cover_from or "—",
                    a.cover_until or "open",
                    f"{a.title} — {a.cover_reason or 'no reason given'}"))
            expired = admin.expired_cover()
            self.summary_var.set(
                f"{len(rows)} assignment(s) currently covered. The "
                f"substantive teacher is never overwritten."
                + (f"  {len(expired)} expired arrangement(s) still on "
                   f"record." if expired else ""))

    def _digest(self) -> None:
        DigestDialog(self.frame.winfo_toplevel())

    def _send_all(self) -> None:
        if not messagebox.askyesno(
                "Digests",
                "Send a digest to every teacher with something "
                "outstanding?\n\nTeachers with nothing to do are "
                "skipped."):
            return
        sent = admin.send_all_digests()
        messagebox.showinfo(
            "Digests",
            f"{len(sent)} digest(s) sent.\n\n"
            + "\n".join(f"{who}: {d.message}"
                        for who, d in list(sent.items())[:10]))

    def _cover(self) -> None:
        CoverDialog(self.frame.winfo_toplevel(),
                     on_save=self.owner.refresh)


class DigestDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Teacher digest")
        self.win.geometry("720x560")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Teacher:").pack(side="left")
        self.teacher_cb = ttk.Combobox(
            bar, values=("",) + tuple(_teachers()), width=28)
        self.teacher_cb.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Period:").pack(side="left")
        self.period_cb = ttk.Combobox(bar, values=admin.DIGEST_PERIODS,
                                        state="readonly", width=10)
        self.period_cb.set(admin.DEFAULT_DIGEST_PERIOD)
        self.period_cb.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Build",
                    command=self._build).pack(side="left")
        ttk.Button(bar, text="Send",
                    command=self._send).pack(side="left", padx=4)

        self.text = tk.Text(outer, wrap="none",
                              font=("TkFixedFont", 9))
        self.text.pack(fill="both", expand=True)
        ttk.Button(outer, text="Close",
                    command=self.win.destroy).pack(anchor="e",
                                                     pady=(8, 0))

    def _build(self) -> None:
        who = self.teacher_cb.get().strip()
        if not who:
            messagebox.showinfo("Digest", "Pick a teacher.")
            return
        try:
            digest = admin.build_digest(who,
                                         period=self.period_cb.get())
        except Exception as e:
            messagebox.showerror("Digest", str(e))
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", digest.as_text())

    def _send(self) -> None:
        who = self.teacher_cb.get().strip()
        if not who:
            messagebox.showinfo("Digest", "Pick a teacher.")
            return
        digest = admin.send_digest(who, period=self.period_cb.get(),
                                    skip_if_empty=False)
        messagebox.showinfo(
            "Digest",
            f"Sent to {who}." if digest else "Nothing to send.")


class CoverDialog:
    def __init__(self, parent: tk.Misc, *,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Assign cover marking")
        self.win.geometry("600x360")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(
            form,
            text="The substantive teacher stays on the assignment.\n"
                 "Editing the teacher field instead would lose who\n"
                 "owns the work.",
            foreground="#555").grid(row=0, column=0, columnspan=2,
                                      sticky="w", pady=(0, 8))

        ttk.Label(form, text="Teacher who is out:").grid(
            row=1, column=0, sticky="e", pady=4)
        self.out_cb = ttk.Combobox(form,
                                     values=("",) + tuple(_teachers()),
                                     width=28)
        self.out_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Cover marker:").grid(row=2, column=0,
                                                      sticky="e",
                                                      pady=4)
        self.cover_cb = ttk.Combobox(form,
                                       values=("",) + tuple(_teachers()),
                                       width=28)
        self.cover_cb.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Until:").grid(row=3, column=0,
                                               sticky="e", pady=4)
        self.until_e = ttk.Entry(form, width=14)
        self.until_e.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reason:").grid(row=4, column=0,
                                                sticky="e", pady=4)
        self.reason_e = ttk.Entry(form, width=40)
        self.reason_e.insert(0, "Staff absence")
        self.reason_e.grid(row=4, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Cover whole load",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            rows = admin.cover_for_teacher(
                self.out_cb.get().strip(),
                cover_marker=self.cover_cb.get().strip(),
                cover_until=self.until_e.get().strip() or None,
                reason=self.reason_e.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Cover failed", str(e))
            return
        messagebox.showinfo(
            "Cover",
            f"{len(rows)} assignment(s) now marked by "
            f"{self.cover_cb.get().strip()}.")
        self.win.destroy()
        self.on_save()


# ══ Exports ═══════════════════════════════════════════════════════

class ExportsPane:
    def __init__(self, nb: ttk.Notebook, owner: InsightTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Exports")
        self._assignments: list = []
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Assignment:").pack(side="left")
        self.assign_cb = ttk.Combobox(bar, state="readonly", width=52)
        self.assign_cb.pack(side="left", padx=(2, 8))
        self.assign_cb.bind("<<ComboboxSelected>>",
                             lambda _e: self._preview())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", pady=(0, 6))
        ttk.Button(actions, text="Export marks...",
                    command=self._export).pack(side="left")
        ttk.Button(actions, text="Blank mark sheet...",
                    command=self._template).pack(side="left", padx=4)
        ttk.Button(actions, text="Import marks...",
                    command=self._import).pack(side="left", padx=4)
        ttk.Button(actions, text="Coversheets...",
                    command=self._coversheets).pack(side="left",
                                                      padx=(16, 4))
        ttk.Button(actions, text="Sample pack",
                    command=self._sample_pack).pack(side="left", padx=4)

        self.text = tk.Text(self.frame, wrap="none",
                              font=("TkFixedFont", 9))
        self.text.pack(fill="both", expand=True)
        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        self._assignments = data.list_assignments()
        self.assign_cb.configure(values=[
            f"#{a.assignment_id}  {a.title} ({a.subject_name})"
            for a in self._assignments])
        if self._assignments and not self.assign_cb.get():
            self.assign_cb.current(0)
        self._preview()

    def _current(self):
        idx = self.assign_cb.current()
        if 0 <= idx < len(self._assignments):
            return self._assignments[idx]
        return None

    def _preview(self) -> None:
        a = self._current()
        self.text.delete("1.0", "end")
        if a is None:
            self.summary_var.set("")
            return
        text = admin.export_marks(a.assignment_id)
        self.text.insert("1.0", text)
        rows = max(0, len(text.strip().splitlines()) - 1)
        self.summary_var.set(
            f"{rows} row(s). Raw mark, penalty and final mark are "
            f"separate columns — an export showing only the final "
            f"figure cannot be reconciled later.")

    def _export(self) -> None:
        a = self._current()
        if a is None:
            return
        path = filedialog.asksaveasfilename(
            title="Export marks", defaultextension=".csv",
            initialfile=f"marks_{a.assignment_id}.csv",
            parent=self.frame.winfo_toplevel())
        if not path:
            return
        admin.export_marks(a.assignment_id, path=path)
        messagebox.showinfo("Export", f"Written to {path}")

    def _template(self) -> None:
        a = self._current()
        if a is None:
            return
        path = filedialog.asksaveasfilename(
            title="Blank mark sheet", defaultextension=".csv",
            initialfile=f"marksheet_{a.assignment_id}.csv",
            parent=self.frame.winfo_toplevel())
        if not path:
            return
        admin.export_template(a.assignment_id, path=path)
        messagebox.showinfo("Mark sheet", f"Written to {path}")

    def _import(self) -> None:
        a = self._current()
        if a is None:
            return
        path = filedialog.askopenfilename(
            title="Import marks",
            parent=self.frame.winfo_toplevel())
        if not path:
            return
        try:
            preview = admin.import_marks(path, a.assignment_id,
                                          dry_run=True)
        except Exception as e:
            messagebox.showerror("Import", str(e))
            return
        if preview.errors:
            detail = "\n".join(f"line {r.line}: {r.message}"
                               for r in preview.errors[:10])
            if not messagebox.askyesno(
                    "Import",
                    f"{preview.message}\n\n{detail}\n\n"
                    "Import the valid rows anyway?"):
                return
        elif not messagebox.askyesno(
                "Import", f"{preview.message}\n\nApply?"):
            return
        result = admin.import_marks(path, a.assignment_id,
                                     marked_by=a.teacher,
                                     allow_partial=True)
        messagebox.showinfo("Import", result.message)
        self.owner.refresh()

    def _coversheets(self) -> None:
        a = self._current()
        if a is None:
            return
        directory = filedialog.askdirectory(
            title="Where to write coversheets",
            parent=self.frame.winfo_toplevel())
        if not directory:
            return
        written = admin.write_coversheets(a.assignment_id,
                                           directory=directory)
        messagebox.showinfo(
            "Coversheets",
            f"{len(written)} coversheet(s) written to {directory}.")

    def _sample_pack(self) -> None:
        a = self._current()
        if a is None:
            return
        try:
            text = admin.build_sample_pack(a.assignment_id)
        except Exception as e:
            messagebox.showerror("Sample pack", str(e))
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.summary_var.set(
            "Standardisation sample pack — every sampled script's "
            "coversheet in one document, ready for the moderator.")
