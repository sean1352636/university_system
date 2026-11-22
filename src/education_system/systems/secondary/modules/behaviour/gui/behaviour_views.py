"""Behaviour & Rewards screen.

The old "Behaviour Log" window is the first tab, with its toolbar (Year,
Pupil, Polarity, Severity and Status filters; Apply, Log, Edit, Status,
Pupil summary, Threshold, Delete, Refresh), its columns (ID, Date, Time,
Pupil, Yr, Type, Pol, Pts, Severity, Status, Description), its log / edit
dialog (Pupil ID, Date, Time, Location, Subject, Type, Points, Severity,
Raised by, Status, Description, Action taken, Notes) and its threshold
window (Pupil, Net points). Added to it: Log for several pupils, Note home,
Open pupil, Cohort summary, History, Export CSV, and "Share with parents".

New tabs: Rewards, Houses, Concerns, Reports and Types. The rules are in
:mod:`modules.behaviour.domain.behaviour`.
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
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = (BH.ValidationError, BH.PermissionDenied, BH.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "desc", "reasons", "group", "house"}, tags=W.STANDARD_TAGS)


_text_window = W.text_window
_form = W.form_dialog


def _subjects() -> list[str]:
    try:
        return ["", *(f"{s.code} - {s.name}" for s in S.list_subjects())]
    except Exception:  # noqa: BLE001 - the list is a convenience
        return [""]


def _subject_code(value: str) -> str:
    return (value or "").split(" - ")[0].strip()


def _entry_fields(e: BH.Entry | None, *, with_pupil: bool = True) -> list:
    types = [t.name for t in BH.list_types()]
    subj = ""
    if e and e.subject_code:
        subj = next((s for s in _subjects() if s.startswith(e.subject_code + " - ")),
                    e.subject_code)
    fields = [("pupil", "Pupil ID / admission no.", e.admission_no if e else "", None)] \
        if with_pupil else []
    return fields + [
        ("entry_date", "Date", e.entry_date if e else BH._today().isoformat(), None),
        ("entry_time", "Time (HH:MM)", e.entry_time if e else "", None),
        ("location", "Location", e.location if e else "", None),
        ("subject", "Subject", subj, ("edit", _subjects())),
        ("incident_type", "Type", e.incident_type if e else "", types),
        ("points", "Points (blank = type default)", e.points if e else "", None),
        ("severity", "Severity", e.severity if e else BH.DEFAULT_SEVERITY, BH.SEVERITIES),
        ("raised_by", "Raised by", e.raised_by if e else "", None),
        ("status", "Status", e.status if e else BH.DEFAULT_STATUS, BH.INCIDENT_STATUSES),
        ("escalated_to", "Escalated to", e.escalated_to if e else "", None),
        ("description", "Description", e.description if e else "", "text"),
        ("action_taken", "Action taken", e.action_taken if e else "", "text"),
        ("notes", "Notes", e.notes if e else "", "text"),
        ("share_with_parents", "Share with parents", e.share_with_parents if e else None,
         ["", "yes", "no"] if e is None else "check"),
    ]


def _clean_values(v: dict[str, Any]) -> dict[str, Any]:
    out = dict(v)
    if "subject" in out:
        out["subject"] = _subject_code(out["subject"])
    if out.get("share_with_parents") == "":
        out.pop("share_with_parents")  # positive = shared by default
    return out


class BehaviourPage:
    TABS = ("Behaviour Log", "Rewards", "Houses", "Concerns", "Reports", "Types")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = BH.is_editor(principal)
        activity_log.record("behaviour.view")
        ttk.Label(parent, text="Behaviour & Rewards", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Behaviour Log"
        self.book.select(self.TABS.index(start))
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
        build = {"Behaviour Log": (self._build_log, self.refresh),
                 "Rewards": (self._build_rewards, self.refresh_rewards),
                 "Houses": (self._build_houses, self.refresh_houses),
                 "Concerns": (self._build_concerns, self.refresh_concerns),
                 "Reports": (self._build_reports, self.refresh_reports),
                 "Types": (self._build_types, self.refresh_types)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    # ── Behaviour Log (old window) ───────────────────────────────────

    def _build_log(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.pupil = tk.StringVar(value=self.state.get("pupil", ""))
        self.polarity = tk.StringVar(value=self.state.get("polarity", ""))
        self.severity = tk.StringVar(value=self.state.get("severity", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        for label, var, values, width in (
                ("Year:", self.year, ["", *YEARS], 5), ("Pupil:", self.pupil, None, 10),
                ("Polarity:", self.polarity, ["", *BH.POLARITIES], 9),
                ("Severity:", self.severity, ["", *BH.SEVERITIES], 9),
                ("Status:", self.status, ["", *BH.INCIDENT_STATUSES], 10)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            if values is None:
                ttk.Entry(bar, textvariable=var, width=width).pack(side="left", padx=(0, 6))
            else:
                ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                             width=width).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh)
        self._button(bar, "Log", self.log)
        self._button(bar, "Edit", self.edit)
        self._button(bar, "Status", self.set_status)
        self._button(bar, "Pupil summary", self.pupil_summary)
        self._button(bar, "Threshold", self.threshold)
        self._button(bar, "Delete", self.delete, True)
        self._button(bar, "Refresh", self.refresh)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        self._button(bar2, "Log for several pupils…", self.log_many)
        self._button(bar2, "Note home…", self.note_home)
        self._button(bar2, "Open pupil", self._open_selected_pupil)
        self._button(bar2, "Cohort summary", self.cohort)
        self._button(bar2, "History", self.history)
        self._button(bar2, "Export CSV…", self.export)
        self.tree = _tree(tab, [
            ("id", "ID", 50), ("date", "Date", 90), ("time", "Time", 55),
            ("pupil", "Pupil", 180), ("yr", "Yr", 35), ("type", "Type", 120),
            ("pol", "Pol", 40), ("pts", "Pts", 45), ("sev", "Severity", 70),
            ("status", "Status", 80), ("desc", "Description", 300)], select="extended")
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        self.rows: dict[str, BH.Entry] = {}

    def _pupil_filter(self) -> int | None:
        ref = self.pupil.get().strip()
        if not ref:
            return None
        p = BH._pupil(ref)
        if p is None:
            raise BH.ValidationError([f"No pupil {ref}"])
        return p.pupil_id

    def refresh(self) -> None:
        y, pol, sev, st = self.year.get(), self.polarity.get(), self.severity.get(), \
            self.status.get()
        self.state.update(year=y, pupil=self.pupil.get().strip(), polarity=pol, severity=sev,
                          status=st)
        try:
            rows = BH.list_entries(year_group=y or None, pupil_id=self._pupil_filter(),
                                   polarity=pol or None, severity=sev or None,
                                   status=st or None, limit=2000)
        except _ERRORS as e:
            self._err("Behaviour Log", e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for r in rows:
            self.rows[str(r.entry_id)] = r
            tag = "muted" if r.status == "Withdrawn" else (
                "good" if r.polarity == "positive" else
                "bad" if r.severity in ("High", "Critical") else "")
            self.tree.insert("", "end", iid=str(r.entry_id), tags=(tag,) if tag else (),
                             values=(r.entry_id, r.entry_date, r.entry_time or "",
                                     f"{r.pupil_name} ({r.admission_no})", r.pupil_year,
                                     r.incident_type, "+" if r.polarity == "positive" else "-",
                                     f"{r.points:+d}", r.severity, r.status, r.description))
        live = [r for r in rows if r.counts]
        self.summary_var.set(
            f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} · "
            f"{sum(1 for r in live if r.polarity == 'positive')} positive · "
            f"{sum(1 for r in live if r.polarity == 'negative')} negative · "
            f"net {sum(r.points for r in live):+d} points")

    def _selected(self, title: str, many: bool = False):
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select an entry first.")
            return None
        return [self.rows[i] for i in sel] if many else self.rows[sel[0]]

    def log(self) -> None:
        def save(v):
            e = BH.log_incident(_clean_values(v), actor=self.principal)
            self.refresh()
            self._after_log([e])
        pupil = self.pupil.get().strip()
        fields = _entry_fields(None)
        fields[0] = ("pupil", fields[0][1], pupil, None)
        _form(self.parent, "Log behaviour", fields, save,
              note="Positive entries are shared with parents unless you choose 'no'.")

    def _after_log(self, entries: list[BH.Entry]) -> None:
        for e in entries:
            for m in BH.milestones(pupil_id=e.pupil_id, academic_year=e.academic_year,
                                   unpresented=True):
                if m["reached_at"][:10] == BH._today().isoformat():
                    self._info("Reward", f"{m['pupil_name']} has reached {m['level']} "
                                         f"({m['points']} positive points).")

    def log_many(self) -> None:
        forms = {f.label: f.name for f in FG.list_forms()}
        if not forms:
            self._info("Log for several pupils", "There are no form groups yet.")
            return

        def pick(v):
            name = forms.get(v["form"])
            pupils = P.list_pupils(form_group=name) if name else []
            if not pupils:
                raise BH.ValidationError(["That form has no pupils on roll"])
            self.parent.after(10, lambda: self._log_many_form(pupils))
        _form(self.parent, "Log for several pupils", [("form", "Form", "", list(forms))],
              pick)

    def _log_many_form(self, pupils: list[P.Pupil]) -> None:
        def save(v):
            ids = v.pop("pupils")
            done = BH.log_many(ids, _clean_values(v), actor=self.principal)
            self.refresh()
            self._info("Log for several pupils", f"Logged {len(done)} entr"
                                                 f"{'y' if len(done) == 1 else 'ies'}.")
            self._after_log(done)
        _form(self.parent, "Log for several pupils",
              [("pupils", "Pupils", (), ("pupils", [(p.pupil_id, f"{p.display_name} "
                                                                 f"({p.admission_no})")
                                                    for p in pupils]))]
              + _entry_fields(None, with_pupil=False), save,
              note="Click each pupil to tick them; the same entry is "
                   "logged for each.")

    def edit(self) -> None:
        e = self._selected("Edit")
        if e is None:
            return
        if not BH.can_edit(self.principal, e):
            self._info("Edit", "Only the person who logged it (while it's open) or the "
                               "behaviour lead can change it. Use Status to update it.")
            return

        def save(v):
            v = _clean_values(v)
            v.pop("pupil", None)
            BH.update(e.entry_id, v, actor=self.principal)
            self.refresh()
        _form(self.parent, f"Edit entry #{e.entry_id} - {e.pupil_name}",
              _entry_fields(e, with_pupil=False), save)

    def set_status(self) -> None:
        e = self._selected("Status")
        if e is None:
            return

        def save(v):
            BH.set_status(e.entry_id, v["status"], actor=self.principal,
                          escalated_to=v["escalated_to"], action_taken=v["action_taken"])
            self.refresh()
        _form(self.parent, f"Status - entry #{e.entry_id}",
              [("status", "Status", e.status, BH.INCIDENT_STATUSES),
               ("escalated_to", "Escalated to", e.escalated_to or "", None),
               ("action_taken", "Add to action taken", "", "text")], save,
              note="Withdrawn entries stop counting towards points.")

    def delete(self) -> None:
        e = self._selected("Delete")
        if e is None:
            return
        if not messagebox.askyesno("Delete", f"Delete entry #{e.entry_id} for "
                                             f"{e.pupil_name}?\n\nOthers can Withdraw it "
                                             "instead, which keeps the record.",
                                   parent=self._top()):
            return
        try:
            BH.delete(e.entry_id, actor=self.principal)
        except _ERRORS as x:
            self._err("Delete", x)
            return
        self.refresh()

    def pupil_summary(self) -> None:
        e = self.tree.selection() and self.rows[self.tree.selection()[0]]
        try:
            pid = e.pupil_id if e else self._pupil_filter()
        except _ERRORS as x:
            self._err("Pupil summary", x)
            return
        if pid is None:
            self._info("Pupil summary", "Select an entry or type a pupil in the Pupil box.")
            return
        s = BH.pupil_summary(pid, academic_year=BH.current_year())
        p = P.get_pupil(pid)
        nxt = BH.next_level(pid)
        lines = [f"{p.display_name} ({p.admission_no}) - Year {p.year_group} "
                 f"{p.form_group or ''}", f"School year {BH.current_year()}", "",
                 f"Entries: {s['total']}  (positive {s['positive']}, negative {s['negative']})",
                 f"Points: {s['total_points']:+d}  (positive {s['positive_points']}, "
                 f"negative {s['negative_points']})",
                 f"House: {s['house'].name if s['house'] else '-'}",
                 "Rewards: " + (", ".join(m["level"] for m in reversed(s["milestones"]))
                                or "none yet")
                 + (f" · {nxt['needed']} to {nxt['next']}" if nxt["next"] else ""), "",
                 "By type:"] + [f"  {k:<20} {v}" for k, v in s["by_type"].items()] + \
                ["", "By status:"] + [f"  {k:<20} {v}" for k, v in s["by_status"].items()] + \
                ["", "Entries:"] + [f"  {r.entry_date} {r.incident_type:<18} "
                                    f"{r.points:+4d} {r.status:<9} {r.description[:60]}"
                                    for r in s["incidents"]]
        _text_window(self.parent, "Pupil summary", "\n".join(lines))

    def threshold(self) -> None:
        win = make_toplevel(self._top())
        win.title("Pupils on the negative threshold")
        win.geometry("560x420")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        pts = tk.StringVar(value=str(BH.THRESHOLD))
        ttk.Label(bar, text="Net points at or below:").pack(side="left")
        ttk.Entry(bar, textvariable=pts, width=6).pack(side="left", padx=4)
        tree = _tree(frm, [("pupil", "Pupil", 260), ("yr", "Yr", 40),
                           ("net", "Net points", 80)])

        def load() -> None:
            try:
                limit = int(pts.get())
            except ValueError:
                messagebox.showerror("Threshold", "Enter a whole number.", parent=win)
                return
            tree.delete(*tree.get_children())
            for t in BH.pupils_above_threshold(points_below=limit,
                                               year_group=self.year.get() or None):
                tree.insert("", "end", iid=str(t["pupil_id"]), values=(
                    f"{t['pupil_name']} ({t['admission_no']})", t["year_group"], t["net"]))
        ttk.Button(bar, text="Apply", command=load).pack(side="left")
        if self.open_pupil:
            tree.bind("<Double-1>", lambda _e: tree.selection() and self.open_pupil(
                int(tree.selection()[0])))
        load()

    def note_home(self) -> None:
        rows = self._selected("Note home", many=True)
        if not rows:
            return

        def save(v):
            res = BH.notify_parents([r.entry_id for r in rows], actor=self.principal,
                                    note=v["note"])
            self.refresh()
            text = f"{res['emails']} e-mail(s) prepared."
            if res["no_email"]:
                text += "\n\nNo parent e-mail address for: " + ", ".join(
                    p.display_name for p in res["no_email"][:20])
            if not res["message_id"]:
                self._info("Note home", text)
                return
            from education_system.systems.secondary.modules.communication.gui import email_views

            def done(_report, error) -> None:
                try:
                    self._info("Note home", text + (f"\n\nQueued - delivery failed: {error}"
                                                    if error else "\n\nSent."))
                except tk.TclError:
                    pass
            email_views.deliver_in_background(self.parent, res["message_id"], self.principal,
                                              done)
        _form(self.parent, "Note home",
              [("note", "Extra message (optional)", "", "text")], save,
              note=f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} will be e-mailed to "
                   "contacts with parental responsibility and shown in the portal.")

    def _open_selected_pupil(self) -> None:
        e = self._selected("Open pupil")
        if e and self.open_pupil:
            self.open_pupil(e.pupil_id)

    def cohort(self) -> None:
        y = self.year.get() or None
        s = BH.cohort_summary(year_group=y, academic_year=BH.current_year())
        lines = [f"{'Year ' + y if y else 'Whole school'} - {BH.current_year()}", "",
                 f"Entries: {s['total']}  ({s['pupils']} pupils)",
                 f"Positive: {s['positive']}   Negative: {s['negative']}   "
                 f"Ratio {s['ratio']}:1", f"Open: {s['open']}", "", "By type:"] + \
            [f"  {k:<20} {v}" for k, v in s["by_type"].items()] + ["", "By severity:"] + \
            [f"  {k:<20} {v}" for k, v in s["by_severity"].items()] + ["", "By status:"] + \
            [f"  {k:<20} {v}" for k, v in s["by_status"].items()]
        _text_window(self.parent, "Cohort summary", "\n".join(lines))

    def history(self) -> None:
        e = self._selected("History")
        if e is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<10} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in BH.history(e.entry_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="behaviour.csv")
        if not path:
            return
        try:
            n = BH.export_csv(path, actor=self.principal, year_group=self.year.get() or None,
                              pupil_id=self._pupil_filter(),
                              polarity=self.polarity.get() or None,
                              severity=self.severity.get() or None,
                              status=self.status.get() or None)
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} entr{'y' if n == 1 else 'ies'}.")

    # ── Rewards ──────────────────────────────────────────────────────

    def _build_rewards(self, tab) -> None:
        ttk.Label(tab, text="Positive points this school year reach "
                  + ", ".join(f"{lv} ({n})" for lv, n in BH.REWARD_LEVELS)
                  + ". Mark certificates as presented when they're handed out.",
                  foreground="#555").pack(anchor="w", pady=(0, 4))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.r_level = tk.StringVar(value="")
        self.r_open = tk.BooleanVar(value=True)
        ttk.Label(bar, text="Level:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.r_level, values=["", *(lv for lv, _n in
                                                                   BH.REWARD_LEVELS)],
                     state="readonly", width=9).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Not yet presented", variable=self.r_open).pack(
            side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_rewards)
        self._button(bar, "Mark presented", self.present)
        self._button(bar, "Undo presented", lambda: self.present(undo=True))
        self.r_tree = _tree(tab, [("pupil", "Pupil", 220), ("yr", "Yr", 35),
                                  ("form", "Form", 60), ("level", "Level", 80),
                                  ("pts", "Points", 60), ("reached", "Reached", 140),
                                  ("presented", "Presented", 140)], height=9,
                            select="extended")
        ttk.Label(tab, text="Leaderboard (positive points this year)",
                  font=("", 11, "bold")).pack(anchor="w", pady=(8, 2))
        self.l_tree = _tree(tab, [("rank", "#", 35), ("pupil", "Pupil", 220),
                                  ("yr", "Yr", 35), ("pts", "Positive", 70),
                                  ("next", "Next level", 160)], height=8)

    def refresh_rewards(self) -> None:
        self.r_tree.delete(*self.r_tree.get_children())
        rows = BH.milestones(academic_year=BH.current_year(), level=self.r_level.get() or None,
                             unpresented=self.r_open.get())
        for m in rows:
            self.r_tree.insert("", "end", iid=str(m["milestone_id"]),
                               tags=("muted",) if m["presented_at"] else ("good",),
                               values=(f"{m['pupil_name']} ({m['admission_no']})",
                                       m["year_group"], m["form_group"] or "", m["level"],
                                       m["points"], m["reached_at"],
                                       f"{m['presented_at']} {m['presented_by'] or ''}"
                                       if m["presented_at"] else ""))
        self.l_tree.delete(*self.l_tree.get_children())
        for i, t in enumerate(BH.leaderboard(year_group=self.state.get("year") or None),
                              start=1):
            nxt = BH.next_level(t["pupil_id"])
            self.l_tree.insert("", "end", values=(
                i, f"{t['pupil_name']} ({t['admission_no']})", t["year_group"], t["positive"],
                f"{nxt['needed']} to {nxt['next']}" if nxt["next"] else "top level"))
        self.summary_var.set(f"{len(rows)} reward(s) shown")

    def present(self, undo: bool = False) -> None:
        sel = self.r_tree.selection()
        if not sel:
            self._info("Rewards", "Select one or more rewards.")
            return
        try:
            BH.present([int(i) for i in sel], actor=self.principal, undo=undo)
        except _ERRORS as e:
            self._err("Rewards", e)
            return
        self.refresh_rewards()

    # ── Houses ───────────────────────────────────────────────────────

    def _build_houses(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "New / edit house…", self.edit_house, True)
        self._button(bar, "Retire house…", self.retire_house, True)
        self._button(bar, "Assign pupils…", self.assign_pupils, True)
        self._button(bar, "Assign a form…", self.assign_form, True)
        self._button(bar, "Refresh", self.refresh_houses)
        self.h_tree = _tree(tab, [("house", "House", 200), ("colour", "Colour", 80),
                                  ("pupils", "Pupils", 70), ("pts", "Points", 80),
                                  ("pp", "Per pupil", 80)], height=8)
        self.h_none = tk.StringVar()
        ttk.Label(tab, textvariable=self.h_none, foreground="#555").pack(anchor="w",
                                                                         pady=(6, 0))

    def refresh_houses(self) -> None:
        self.h_tree.delete(*self.h_tree.get_children())
        table = BH.house_table()
        for i, h in enumerate(table):
            self.h_tree.insert("", "end", iid=h["house"], tags=("good",) if i == 0 and
                               h["points"] else (),
                               values=(h["house"], h["colour"] or "", h["pupils"],
                                       h["points"], h["per_pupil"]))
        n = len(BH.without_house()) if table else 0
        self.h_none.set(f"{n} pupil(s) on roll have no house." if table else
                        "No houses yet - the behaviour lead can add them.")
        self.summary_var.set(f"{len(table)} house(s) · {BH.current_year()}")

    def edit_house(self) -> None:
        sel = self.h_tree.selection()
        cur = next((h for h in BH.list_houses() if sel and h.name == sel[0]), None)

        def save(v):
            BH.save_house(v["name"], actor=self.principal, colour=v["colour"])
            self.refresh_houses()
        _form(self.parent, "House", [("name", "Name", cur.name if cur else "", None),
                                     ("colour", "Colour (#RRGGBB)",
                                      cur.colour if cur else "", None)], save)

    def retire_house(self) -> None:
        sel = self.h_tree.selection()
        if not sel:
            self._info("Retire house", "Select a house.")
            return
        if not messagebox.askyesno("Retire house", f"Retire {sel[0]}?", parent=self._top()):
            return
        try:
            BH.save_house(sel[0], actor=self.principal, active=False)
        except _ERRORS as e:
            self._err("Retire house", e)
            return
        self.refresh_houses()

    def _house_names(self) -> list[str]:
        return [h.name for h in BH.list_houses()]

    def assign_pupils(self) -> None:
        houses = self._house_names()
        if not houses:
            self._info("Assign pupils", "Add a house first.")
            return
        pupils = BH.without_house() or P.list_pupils()

        def save(v):
            BH.assign_house(v["pupils"], v["house"] or None, actor=self.principal)
            self.refresh_houses()
        _form(self.parent, "Assign pupils",
              [("house", "House (blank = none)", houses[0], ["", *houses]),
               ("pupils", "Pupils", (), ("pupils", [(p.pupil_id, f"{p.display_name} "
                                                                f"({p.form_group or '-'})")
                                                    for p in pupils]))], save,
              note="Pupils without a house are listed (or everyone, once all have one).")

    def assign_form(self) -> None:
        houses = self._house_names()
        forms = {f.label: f.name for f in FG.list_forms()}
        if not houses or not forms:
            self._info("Assign a form", "Add a house and a form group first.")
            return

        def save(v):
            pupils = P.list_pupils(form_group=forms.get(v["form"]))
            n = BH.assign_house([p.pupil_id for p in pupils], v["house"],
                                actor=self.principal)
            self.refresh_houses()
            self._info("Assign a form", f"{n} pupil(s) put in {v['house']}.")
        _form(self.parent, "Assign a form", [("form", "Form", "", list(forms)),
                                             ("house", "House", houses[0], houses)], save)

    # ── Concerns ─────────────────────────────────────────────────────

    def _build_concerns(self, tab) -> None:
        ttk.Label(tab, text=f"Pupils with {BH.CONCERN_COUNT}+ negative entries in "
                            f"{BH.CONCERN_DAYS} days, an open High / Critical incident, or "
                            f"net points at or below {BH.THRESHOLD} this year.",
                  foreground="#555").pack(anchor="w", pady=(0, 4))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Refresh", self.refresh_concerns)
        self._button(bar, "Show entries", self._concern_entries)
        self._button(bar, "Open pupil", self._concern_pupil)
        self.c_tree = _tree(tab, [("pupil", "Pupil", 220), ("yr", "Yr", 35),
                                  ("reasons", "Why", 480)])
        self.c_tree.bind("<Double-1>", lambda _e: self._concern_entries())

    def refresh_concerns(self) -> None:
        self.c_tree.delete(*self.c_tree.get_children())
        rows = BH.concerns(year_group=self.state.get("year") or None)
        for c in rows:
            self.c_tree.insert("", "end", iid=str(c["pupil_id"]),
                               tags=("bad",) if c["severity"] > 1 else ("warn",),
                               values=(f"{c['pupil_name']} ({c['admission_no']})",
                                       c["year_group"], "; ".join(c["reasons"])))
        self.summary_var.set(f"{len(rows)} pupil(s) to look at")

    def _concern_entries(self) -> None:
        sel = self.c_tree.selection()
        if not sel:
            return
        p = P.get_pupil(int(sel[0]))
        self.state["pupil"] = p.admission_no
        if "Behaviour Log" in self._built:
            self.pupil.set(p.admission_no)
        self.book.select(0)  # builds / refreshes the log through _on_tab

    def _concern_pupil(self) -> None:
        sel = self.c_tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(int(sel[0]))

    # ── Reports ──────────────────────────────────────────────────────

    def _build_reports(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.a_by = tk.StringVar(value=self.state.get("by", "type"))
        self.a_from = tk.StringVar(value="")
        self.a_to = tk.StringVar(value="")
        ttk.Label(bar, text="Group by:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.a_by, values=["type", "subject", "staff",
                                                          "weekday", "hour", "year"],
                     state="readonly", width=9).pack(side="left", padx=(0, 6))
        for label, var in (("From:", self.a_from), ("To:", self.a_to)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            ttk.Entry(bar, textvariable=var, width=11).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_reports)
        self.a_tree = _tree(tab, [("group", "Group", 220), ("pos", "Positive", 70),
                                  ("neg", "Negative", 70), ("pts", "Net points", 80),
                                  ("pupils", "Pupils", 60)])

    def refresh_reports(self) -> None:
        self.state["by"] = self.a_by.get()
        try:
            rows = BH.analysis(by=self.a_by.get(), year_group=self.state.get("year") or None,
                               date_from=self.a_from.get().strip() or None,
                               date_to=self.a_to.get().strip() or None,
                               academic_year=None if self.a_from.get().strip()
                               else BH.current_year())
        except _ERRORS as e:
            self._err("Reports", e)
            return
        self.a_tree.delete(*self.a_tree.get_children())
        for g in rows:
            self.a_tree.insert("", "end", values=(g["group"], g["positive"], g["negative"],
                                                  f"{g['points']:+d}", g["pupils"]))
        self.summary_var.set(f"{len(rows)} group(s)")

    # ── Types ────────────────────────────────────────────────────────

    def _build_types(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "New / edit type…", self.edit_type, True)
        self._button(bar, "Retire / restore", self.toggle_type, True)
        self._button(bar, "Refresh", self.refresh_types)
        self.t_tree = _tree(tab, [("name", "Type", 200), ("pol", "Polarity", 80),
                                  ("pts", "Default points", 100), ("active", "In use", 70)])

    def refresh_types(self) -> None:
        self.t_tree.delete(*self.t_tree.get_children())
        types = BH.list_types(include_retired=True)
        for t in types:
            self.t_tree.insert("", "end", iid=t.name, tags=() if t.active else ("muted",),
                               values=(t.name, t.polarity, f"{t.default_points:+d}",
                                       "yes" if t.active else "retired"))
        self.summary_var.set(f"{sum(t.active for t in types)} type(s) in use")

    def edit_type(self) -> None:
        sel = self.t_tree.selection()
        cur = BH.get_type(sel[0]) if sel else None

        def save(v):
            BH.save_type(v["name"], v["polarity"], v["points"], actor=self.principal,
                         active=cur.active if cur else True)
            self.refresh_types()
        _form(self.parent, "Behaviour type",
              [("name", "Name", cur.name if cur else "", None),
               ("polarity", "Polarity", cur.polarity if cur else "positive", BH.POLARITIES),
               ("points", "Default points", cur.default_points if cur else "", None)], save)

    def toggle_type(self) -> None:
        sel = self.t_tree.selection()
        if not sel:
            self._info("Types", "Select a type.")
            return
        t = BH.get_type(sel[0])
        try:
            BH.save_type(t.name, t.polarity, t.default_points, actor=self.principal,
                         active=not t.active)
        except _ERRORS as e:
            self._err("Types", e)
            return
        self.refresh_types()


def draw_behaviour(parent: ttk.Frame, *, principal: Principal, state: dict,
                   open_pupil: Callable[[int], None] | None = None) -> BehaviourPage:
    return BehaviourPage(parent, principal=principal, state=state, open_pupil=open_pupil)
