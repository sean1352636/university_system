"""Reports to Parents screen.

There was no old screen (only the menu entry). Tabs:

* **Cycles** - each report cycle (built on an assessment point): New, Edit,
  Status, Delete, History; what it includes, when comments are due and the
  issue date.
* **Comments** - pick a cycle and form; write the form-tutor or
  head-of-year comment for each pupil, with the comment bank and a live
  preview of the whole report.
* **Check & issue** - every pupil's report with what's missing: Mark ready,
  Withhold, Reset, Issue, Withdraw, Preview, Export HTML / CSV.
* **Progress** - by form: comments written, ready, issued, viewed.
* **Comment bank** - shared starting points ({first_name}, {name}).

The rules are in :mod:`modules.assessment.domain.reports_to_parents`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.modules.assessment.domain import reports_to_parents as RP
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = (RP.ValidationError, RP.PermissionDenied, RP.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 14, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "name", "text", "missing"}, tags=W.STANDARD_TAGS)


def _text_window(owner, title: str, text: str) -> None:
    W.text_window(owner, title, text, size="760x560")


_form = W.form_dialog


class ReportsToParentsPage:
    TABS = ("Cycles", "Comments", "Check & issue", "Progress", "Comment bank")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = RP.is_editor(principal)
        activity_log.record("reports.view")
        ttk.Label(parent, text="Reports to Parents", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self.cycle_var = tk.StringVar()
        self._cycles: dict[str, RP.Cycle] = {}
        self._load_cycles()
        self.book.select(self.TABS.index(state.get("tab", "Cycles")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

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
        build = {"Cycles": (self._build_cycles, self.refresh_cycles),
                 "Comments": (self._build_comments, self.refresh_comments),
                 "Check & issue": (self._build_check, self.refresh_check),
                 "Progress": (self._build_progress, self.refresh_progress),
                 "Comment bank": (self._build_bank, self.refresh_bank)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    # ── Cycle picker shared by the working tabs ──────────────────────

    def _load_cycles(self) -> None:
        self._cycles = {f"{c.title} ({c.status})": c for c in RP.list_cycles()}
        keep = self.state.get("cycle_id")
        label = next((k for k, c in self._cycles.items() if c.cycle_id == keep),
                     next(iter(self._cycles), ""))
        self.cycle_var.set(label)
        for cb in getattr(self, "_pickers", []):
            cb.configure(values=list(self._cycles))

    def _picker(self, bar, on_change) -> None:
        ttk.Label(bar, text="Cycle:").pack(side="left", padx=(0, 4))
        cb = ttk.Combobox(bar, textvariable=self.cycle_var, values=list(self._cycles),
                          state="readonly", width=34)
        cb.pack(side="left", padx=(0, 6))
        cb.bind("<<ComboboxSelected>>", lambda _e: on_change())
        self.__dict__.setdefault("_pickers", []).append(cb)

    def _cycle(self, title: str = "Reports") -> RP.Cycle | None:
        c = self._cycles.get(self.cycle_var.get())
        if c is None:
            self._info(title, "Set up a report cycle first (Cycles tab).")
            return None
        c = RP.get_cycle(c.cycle_id)
        self.state["cycle_id"] = c.cycle_id
        return c

    # ── Cycles ───────────────────────────────────────────────────────

    def _build_cycles(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._button(bar, "New", self.new_cycle, True)
        self._button(bar, "Edit", self.edit_cycle, True)
        self._button(bar, "Status", self.cycle_status, True)
        self._button(bar, "Delete", self.delete_cycle, True)
        self._button(bar, "History", self.cycle_history)
        self._button(bar, "Refresh", self.refresh_cycles)
        self.c_tree = _tree(tab, [
            ("id", "ID", 45), ("name", "Name", 180), ("ay", "Academic yr", 85),
            ("type", "Type", 80), ("years", "Years", 70), ("point", "Assessment point", 170),
            ("due", "Comments due", 95), ("issue", "Issue date", 90),
            ("status", "Status", 80), ("issued", "Issued", 60)])
        self.c_tree.bind("<Double-1>", lambda _e: self.edit_cycle())

    def refresh_cycles(self) -> None:
        self._load_cycles()
        self.c_tree.delete(*self.c_tree.get_children())
        for c in self._cycles.values():
            self.c_tree.insert("", "end", iid=str(c.cycle_id),
                               tags=("muted",) if c.status == "Closed" else (), values=(
                                   c.cycle_id, c.name, c.academic_year, c.report_type,
                                   c.years_label, f"{c.point_name} ({c.point_status})",
                                   c.comments_due or "", c.issue_date or "", c.status,
                                   RP.issued_count(c.cycle_id)))
        self.summary_var.set(f"{len(self._cycles)} report cycle(s)")

    def _sel_cycle(self, title: str) -> RP.Cycle | None:
        sel = self.c_tree.selection()
        if not sel:
            self._info(title, "Select a cycle first.")
            return None
        return RP.get_cycle(int(sel[0]))

    def _points(self) -> dict[str, int]:
        from education_system.systems.secondary.modules.assessment.domain import (
            assessment_points as AP,
        )
        return {f"{p.name} {p.academic_year} (Y{p.years_label}, {p.status})": p.point_id
                for p in AP.list_points()}

    def _cycle_fields(self, c: RP.Cycle | None) -> tuple[list, dict[str, int]]:
        pts = self._points()
        cur = next((k for k, v in pts.items() if c and v == c.point_id), next(iter(pts), ""))
        g = (lambda k, d=None: getattr(c, k) if c else d)
        f = [("name", "Name", g("name", "Autumn report"), None),
             ("report_type", "Type", g("report_type", "Full"), RP.REPORT_TYPES),
             ("point", "Assessment point", cur, list(pts)),
             ("year_groups", "Year groups (blank = the point's)", g("year_groups", ""), None)]
        f += [(k, label, g(k, k != "include_hoy"), "check") for k, label in RP.INCLUDES.items()]
        f += [("comments_due", "Comments due (YYYY-MM-DD)", g("comments_due", ""), None),
              ("issue_date", "Issue date (YYYY-MM-DD)", g("issue_date", ""), None),
              ("intro", "Introduction for families", g("intro", ""), "text"),
              ("notes", "Staff notes", g("notes", ""), "text")]
        return f, pts

    def new_cycle(self) -> None:
        fields, pts = self._cycle_fields(None)
        if not pts:
            self._info("New cycle", "Set up an assessment point first - the report is built "
                                    "from its grades.")
            return

        def save(v):
            v["point_id"] = pts.get(v.pop("point"))
            c = RP.create_cycle(v, actor=self.principal)
            self.state["cycle_id"] = c.cycle_id
            self.refresh_cycles()
        _form(self.parent, "New report cycle", fields, save,
              note="Grades, attitude, homework and subject comments come from the assessment "
                   "point. Move the cycle to Writing when tutors should write comments.")

    def edit_cycle(self) -> None:
        c = self._sel_cycle("Edit cycle")
        if c is None:
            return
        fields, pts = self._cycle_fields(c)

        def save(v):
            v["point_id"] = pts.get(v.pop("point"))
            RP.update_cycle(c.cycle_id, v, actor=self.principal)
            self.refresh_cycles()
        _form(self.parent, f"Edit {c.title}", fields, save)

    def cycle_status(self) -> None:
        c = self._sel_cycle("Status")
        if c is None:
            return
        moves = [b for a, b in sorted(RP._CYCLE_MOVES) if a == c.status]

        def save(v):
            RP.set_cycle_status(c.cycle_id, v["status"], actor=self.principal)
            self.refresh_cycles()
        _form(self.parent, f"Status - {c.title}", [("status", "New status",
                                                     moves[0] if moves else "", moves)], save,
              note=f"Currently {c.status}. Draft → Writing (comments) → Checking (mark ready "
                   "and issue) → Closed.")

    def delete_cycle(self) -> None:
        c = self._sel_cycle("Delete")
        if c is None or not messagebox.askyesno(
                "Delete", f"Delete {c.title} and its comments?", parent=self._top()):
            return
        try:
            RP.delete_cycle(c.cycle_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
        self.refresh_cycles()

    def cycle_history(self) -> None:
        c = self._sel_cycle("History")
        if c is None:
            return
        _text_window(self.parent, f"History - {c.title}", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<14} "
            + (f"pupil {h['pupil_id']} " if h["pupil_id"] else "")
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in RP.history(c.cycle_id)) or "No changes recorded.")

    # ── Comments ─────────────────────────────────────────────────────

    def _build_comments(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._picker(bar, self.refresh_comments)
        self.k_kind = tk.StringVar(value=self.state.get("kind", "Form tutor"))
        self.k_form = tk.StringVar(value=self.state.get("form", ""))
        self.k_mine = tk.BooleanVar(value=self.state.get("mine", not self.editor))
        ttk.Label(bar, text="Comment:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.k_kind, values=list(RP.COMMENT_KINDS.values()),
                     state="readonly", width=13).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Form:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.k_form, width=7).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Mine only", variable=self.k_mine).pack(side="left")
        self._button(bar, "Apply", self.refresh_comments)
        body = ttk.Panedwindow(tab, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(left, weight=1)
        body.add(right, weight=2)
        self.k_tree = _tree(left, [("pupil", "Pupil", 200), ("form", "Form", 55),
                                   ("done", "Written", 60)], height=18)
        self.k_tree.bind("<<TreeviewSelect>>", lambda _e: self._load_comment())
        self.k_who = tk.StringVar()
        ttk.Label(right, textvariable=self.k_who, font=("", 11, "bold")).pack(anchor="w")
        self.k_text = tk.Text(right, height=9, wrap="word")
        self.k_text.pack(fill="x", pady=(4, 2))
        self.k_count = tk.StringVar()
        self.k_text.bind("<KeyRelease>", lambda _e: self.k_count.set(
            f"{len(self.k_text.get('1.0', 'end').strip())}/{RP.MAX_COMMENT} characters"))
        ttk.Label(right, textvariable=self.k_count, foreground="#777").pack(anchor="w")
        bb = ttk.Frame(right)
        bb.pack(fill="x", pady=4)
        self._button(bb, "Save comment", self.save_comment)
        self._button(bb, "Save & next", lambda: self.save_comment(next_=True))
        self._button(bb, "From bank…", self.from_bank)
        self._button(bb, "Preview report", self.preview_selected)
        if self.open_pupil:
            self._button(bb, "Open pupil", lambda: self._k_pid() and self.open_pupil(
                self._k_pid()))
        ttk.Label(right, text="Grades and subject comments come from the assessment point. "
                  "{first_name} and {name} are filled in for you.", foreground="#777",
                  wraplength=460, justify="left").pack(anchor="w", pady=(6, 0))
        self.k_rows: dict[str, Any] = {}

    def _kind(self) -> str:
        return next(k for k, v in RP.COMMENT_KINDS.items() if v == self.k_kind.get())

    def refresh_comments(self) -> None:
        if not hasattr(self, "k_tree"):
            return
        self.state.update(kind=self.k_kind.get(), form=self.k_form.get(),
                          mine=self.k_mine.get())
        self.k_tree.delete(*self.k_tree.get_children())
        c = self._cycles.get(self.cycle_var.get())
        if c is None:
            self.summary_var.set("No report cycles yet")
            return
        kind = self._kind()
        pupils = RP.my_pupils(c.cycle_id, self.principal, kind) if self.k_mine.get() else \
            RP.pupils_in(c.cycle_id)
        form = self.k_form.get().strip().upper()
        if form:
            pupils = [p for p in pupils if (p.form_group or "").upper() == form]
        cm = RP.comments(c.cycle_id)
        self.k_rows = {}
        done = 0
        for p in pupils:
            have = (p.pupil_id, kind) in cm
            done += have
            self.k_rows[str(p.pupil_id)] = p
            self.k_tree.insert("", "end", iid=str(p.pupil_id), tags=("good",) if have else (),
                               values=(f"{p.admission_no} {p.display_name}",
                                       p.form_group or "", "yes" if have else ""))
        self.summary_var.set(f"{c.title} · {c.status} · {done}/{len(pupils)} "
                             f"{self.k_kind.get().lower()} comment(s) written"
                             + (f" · due {c.comments_due}" if c.comments_due else ""))

    def _k_pid(self) -> int | None:
        sel = self.k_tree.selection()
        return int(sel[0]) if sel else None

    def _load_comment(self) -> None:
        pid = self._k_pid()
        c = self._cycles.get(self.cycle_var.get())
        if pid is None or c is None:
            return
        p = self.k_rows[str(pid)]
        got = RP.comments(c.cycle_id, pid).get((pid, self._kind()))
        self.k_who.set(f"{p.display_name} - {self.k_kind.get().lower()} comment"
                       + (f" (by {got['written_by']})" if got else ""))
        self.k_text.delete("1.0", "end")
        self.k_text.insert("1.0", got["comment"] if got else "")
        self.k_count.set(f"{len(got['comment']) if got else 0}/{RP.MAX_COMMENT} characters")

    def save_comment(self, next_: bool = False) -> None:
        pid = self._k_pid()
        c = self._cycle("Comment")
        if pid is None or c is None:
            return
        try:
            RP.set_comment(c.cycle_id, pid, self._kind(), self.k_text.get("1.0", "end"),
                           actor=self.principal)
        except _ERRORS as e:
            self._err("Comment", e)
            return
        self.refresh_comments()
        kids = self.k_tree.get_children()
        if str(pid) in kids:
            i = kids.index(str(pid))
            target = kids[i + 1] if next_ and i + 1 < len(kids) else kids[i]
            self.k_tree.selection_set(target)
            self.k_tree.see(target)

    def from_bank(self) -> None:
        pid = self._k_pid()
        if pid is None:
            self._info("Comment bank", "Select a pupil first.")
            return
        p = self.k_rows[str(pid)]
        items = RP.bank(self._kind())
        if not items:
            self._info("Comment bank", "The comment bank is empty - add some on the Comment "
                                       "bank tab.")
            return
        win = make_toplevel(self._top())
        win.title("Comment bank")
        win.geometry("640x380")
        frm = ttk.Frame(win, padding=8)
        frm.pack(fill="both", expand=True)
        tree = _tree(frm, [("cat", "Category", 110), ("text", "Comment", 480)], height=12)
        for b in items:
            tree.insert("", "end", iid=str(b.bank_id), values=(b.category, b.text))

        def use() -> None:
            sel = tree.selection()
            if not sel:
                return
            text = next(b.text for b in items if b.bank_id == int(sel[0]))
            self.k_text.insert("end", ("" if not self.k_text.get("1.0", "end").strip()
                                       else " ") + RP.fill_placeholders(text, p))
            win.destroy()
        tree.bind("<Double-1>", lambda _e: use())
        ttk.Button(frm, text="Insert", command=use).pack(anchor="e", pady=(6, 0))

    def preview_selected(self) -> None:
        pid = self._k_pid()
        c = self._cycle("Preview")
        if pid is None or c is None:
            return
        _text_window(self.parent, "Report preview", RP.render_text(RP.view(c.cycle_id, pid)))

    # ── Check & issue ────────────────────────────────────────────────

    def _build_check(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._picker(bar, self.refresh_check)
        self.x_year = tk.StringVar(value=self.state.get("x_year", ""))
        self.x_status = tk.StringVar(value=self.state.get("x_status", ""))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.x_year, values=["", *YEARS], state="readonly",
                     width=5).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.x_status, values=["", *RP.REPORT_STATUSES],
                     state="readonly", width=10).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_check)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        self._button(bar2, "Preview", self.preview_check)
        self._button(bar2, "Mark ready", self.mark_ready, True)
        self._button(bar2, "Withhold…", self.withhold, True)
        self._button(bar2, "Reset", self.reset, True)
        self._button(bar2, "Issue ready reports…", self.issue, True)
        self._button(bar2, "Withdraw…", self.withdraw, True)
        self._button(bar2, "Export HTML…", self.export_html)
        self._button(bar2, "Export CSV…", self.export_csv)
        if self.open_pupil:
            self._button(bar2, "Open pupil", lambda: self._x_pids() and self.open_pupil(
                self._x_pids()[0]))
        self.x_tree = _tree(tab, [("pupil", "Pupil", 200), ("year", "Yr", 35),
                                  ("form", "Form", 55), ("status", "Status", 75),
                                  ("ver", "Ver", 40), ("issued", "Issued", 95),
                                  ("viewed", "Viewed", 95), ("missing", "Missing", 320)],
                            height=16, select="extended")
        self.x_tree.bind("<Double-1>", lambda _e: self.preview_check())
        self.x_rows: dict[str, Any] = {}

    def refresh_check(self) -> None:
        if not hasattr(self, "x_tree"):
            return
        self.state.update(x_year=self.x_year.get(), x_status=self.x_status.get())
        self.x_tree.delete(*self.x_tree.get_children())
        c = self._cycles.get(self.cycle_var.get())
        if c is None:
            self.summary_var.set("No report cycles yet")
            return
        rows = RP.list_reports(c.cycle_id, year_group=int(self.x_year.get())
                               if self.x_year.get() else None,
                               status=self.x_status.get() or None)
        self.x_rows = {}
        for p, r in rows:
            st = r.status if r else "Draft"
            missing = "" if st in ("Issued", "Withheld") else "; ".join(
                RP.problems(c.cycle_id, p.pupil_id))
            if st == "Withheld":
                missing = f"withheld: {r.withheld_reason}"
            self.x_rows[str(p.pupil_id)] = (p, r)
            tag = {"Issued": "good", "Withheld": "muted"}.get(st) or ("bad" if missing else "")
            self.x_tree.insert("", "end", iid=str(p.pupil_id), tags=(tag,) if tag else (),
                               values=(f"{p.admission_no} {p.display_name}", p.year_group,
                                       p.form_group or "", st, r.version if r else 0,
                                       (r.issued_at or "")[:10] if r else "",
                                       ((r.first_viewed_at or "")[:10] + (" ✓" if
                                                                          r.acknowledged_at
                                                                          else ""))
                                       if r else "", missing))
        s = RP.summary(c.cycle_id)
        self.summary_var.set(f"{c.title} · {c.status} · {s.get('pupils', 0)} pupil(s): "
                             + ", ".join(f"{s.get(k, 0)} {k.lower()}"
                                         for k in RP.REPORT_STATUSES)
                             + f" · {s.get('viewed', 0)} viewed by families")

    def _x_pids(self) -> list[int]:
        return [int(i) for i in self.x_tree.selection()]

    def _need(self, title: str) -> tuple[RP.Cycle, list[int]] | None:
        c = self._cycle(title)
        pids = self._x_pids()
        if c is None:
            return None
        if not pids:
            self._info(title, "Select one or more pupils first.")
            return None
        return c, pids

    def preview_check(self) -> None:
        got = self._need("Preview")
        if got:
            c, pids = got
            _text_window(self.parent, "Report preview",
                         RP.render_text(RP.view(c.cycle_id, pids[0])))

    def mark_ready(self) -> None:
        got = self._need("Mark ready")
        if not got:
            return
        c, pids = got
        try:
            res = RP.mark_ready(c.cycle_id, pids, actor=self.principal)
        except _ERRORS as e:
            self._err("Mark ready", e)
            return
        msg = f"{res['ready']} report(s) marked ready."
        if res["skipped"]:
            msg += "\n\nNot ready:\n" + "\n".join(f"• {k}: {'; '.join(v)}"
                                                  for k, v in list(res["skipped"].items())[:25])
            if messagebox.askyesno("Mark ready", msg + "\n\nMark these ready anyway?",
                                   parent=self._top()):
                RP.mark_ready(c.cycle_id, pids, actor=self.principal, force=True)
        else:
            self._info("Mark ready", msg)
        self.refresh_check()

    def withhold(self) -> None:
        got = self._need("Withhold")
        if not got:
            return
        c, pids = got

        def save(v):
            for pid in pids:
                RP.withhold(c.cycle_id, pid, v["reason"], actor=self.principal)
            self.refresh_check()
        _form(self.parent, "Withhold report", [("reason", "Reason", "", None)], save,
              note="A withheld report isn't issued or e-mailed. Reset it to include it again.")

    def reset(self) -> None:
        got = self._need("Reset")
        if not got:
            return
        c, pids = got
        errors = []
        for pid in pids:
            try:
                RP.reset(c.cycle_id, pid, actor=self.principal)
            except _ERRORS as e:
                errors.append(_problems(e))
        if errors:
            self._info("Reset", "\n".join(errors[:10]))
        self.refresh_check()

    def issue(self) -> None:
        c = self._cycle("Issue")
        if c is None:
            return
        pids = self._x_pids() or None
        what = f"the {len(pids)} selected report(s)" if pids else "every Ready report"
        email = messagebox.askyesnocancel(
            "Issue reports", f"Issue {what} for {c.title}?\n\nThey'll be frozen and shown in "
            "the parent portal.\n\nYes = also e-mail parents with parental responsibility\n"
            "No = portal only", parent=self._top())
        if email is None:
            return
        try:
            res = RP.issue(c.cycle_id, pids, actor=self.principal, email=email)
        except _ERRORS as e:
            self._err("Issue", e)
            return
        self.refresh_check()
        text = f"Issued {len(res['issued'])} report(s)."
        if res["skipped"]:
            text += "\n\nSkipped: " + ", ".join(f"{k} ({v})" for k, v in
                                               list(res["skipped"].items())[:20])
        if email and res["no_email"]:
            text += ("\n\nNo parent e-mail address for: "
                     + ", ".join(p.display_name for p in res["no_email"][:20]))
        if not res["message_id"]:
            self._info("Issue", text)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Issue", text + f"\n\n{res['emails']} e-mail(s) " + (
                    f"queued - delivery failed: {error}" if error else "sent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def withdraw(self) -> None:
        got = self._need("Withdraw")
        if not got:
            return
        c, pids = got
        reps = [self.x_rows[str(p)][1] for p in pids]
        reps = [r for r in reps if r and r.status == "Issued"]
        if not reps:
            self._info("Withdraw", "Select an issued report.")
            return

        def save(v):
            for r in reps:
                RP.withdraw(r.report_id, v["reason"], actor=self.principal)
            self.refresh_check()
        _form(self.parent, "Withdraw report", [("reason", "Reason", "", None)], save,
              note="Families stop seeing it. Correct it, mark it ready and issue it again - "
                   "it goes out as a new version.")

    def export_html(self) -> None:
        c = self._cycle("Export HTML")
        if c is None:
            return
        folder = filedialog.askdirectory(parent=self._top(), title="Folder for the reports")
        if not folder:
            return
        n = RP.export_html(c.cycle_id, folder, actor=self.principal,
                           pupil_ids=self._x_pids() or None)
        self._info("Export HTML", f"Saved {n} report(s) to print.")

    def export_csv(self) -> None:
        c = self._cycle("Export CSV")
        if c is None:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="reports.csv")
        if path:
            n = RP.export_csv(c.cycle_id, path, actor=self.principal)
            self._info("Export CSV", f"Exported {n} row(s).")

    # ── Progress ─────────────────────────────────────────────────────

    def _build_progress(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._picker(bar, self.refresh_progress)
        self._button(bar, "Refresh", self.refresh_progress)
        self.p_tree = _tree(tab, [("yr", "Yr", 35), ("form", "Form", 70),
                                  ("tutor", "Tutor", 150), ("n", "Pupils", 55),
                                  ("tc", "Tutor comments", 100), ("hc", "HoY comments", 95),
                                  ("draft", "Draft", 50), ("ready", "Ready", 50),
                                  ("issued", "Issued", 55), ("held", "Withheld", 65),
                                  ("viewed", "Viewed", 55)])

    def refresh_progress(self) -> None:
        if not hasattr(self, "p_tree"):
            return
        self.p_tree.delete(*self.p_tree.get_children())
        c = self._cycles.get(self.cycle_var.get())
        if c is None:
            return
        for g in RP.progress(c.cycle_id):
            self.p_tree.insert("", "end", tags=("good",) if g["Issued"] == g["pupils"] else (),
                               values=(g["year_group"], g["form_group"], g["tutor"],
                                       g["pupils"], f"{g['tutor_done']}/{g['pupils']}"
                                       if c.include_tutor else "-",
                                       f"{g['hoy_done']}/{g['pupils']}" if c.include_hoy
                                       else "-", g["Draft"], g["Ready"], g["Issued"],
                                       g["Withheld"], g["viewed"]))
        self.summary_var.set(f"{c.title} · {c.status}")

    # ── Comment bank ─────────────────────────────────────────────────

    def _build_bank(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._button(bar, "Add…", self.add_bank)
        self._button(bar, "Delete", self.delete_bank)
        self._button(bar, "Refresh", self.refresh_bank)
        self.b_tree = _tree(tab, [("kind", "For", 90), ("cat", "Category", 110),
                                  ("text", "Comment", 520), ("by", "Added by", 100)])

    def refresh_bank(self) -> None:
        self.b_tree.delete(*self.b_tree.get_children())
        items = RP.bank()
        for b in items:
            self.b_tree.insert("", "end", iid=str(b.bank_id), values=(
                {"any": "Any", **RP.COMMENT_KINDS}[b.kind], b.category, b.text,
                b.created_by or ""))
        self.summary_var.set(f"{len(items)} bank comment(s)")

    def add_bank(self) -> None:
        kinds = {"Any": "any", **{v: k for k, v in RP.COMMENT_KINDS.items()}}

        def save(v):
            RP.add_bank(v["text"], actor=self.principal, kind=kinds[v["kind"]],
                        category=v["category"])
            self.refresh_bank()
        _form(self.parent, "Add bank comment", [
            ("kind", "For", "Any", list(kinds)), ("category", "Category", "General", None),
            ("text", "Comment", "", "text")], save,
              note="Use {first_name} or {name} for the pupil.")

    def delete_bank(self) -> None:
        sel = self.b_tree.selection()
        if not sel or not messagebox.askyesno("Delete", "Remove this bank comment?",
                                              parent=self._top()):
            return
        try:
            RP.delete_bank(int(sel[0]), actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
        self.refresh_bank()


def draw_reports_to_parents(parent: ttk.Frame, *, principal: Principal, state: dict,
                            open_pupil: Callable[[int], None] | None = None
                            ) -> ReportsToParentsPage:
    return ReportsToParentsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
