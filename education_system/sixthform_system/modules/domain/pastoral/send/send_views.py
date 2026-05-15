"""Tkinter views for Sixth Form SEND register."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.pastoral.send import (
    send as data,
)
from education_system.sixthform_system.modules.domain.pastoral.send.send import (
    CYCLE_STAGES,
    DEFAULT_CYCLE_STAGE,
    DEFAULT_NEED_TYPE,
    DEFAULT_REGISTER_STATUS,
    DEFAULT_STATUS,
    NEED_TYPES,
    REGISTER_STATUSES,
    SENDEntry,
    STATUSES,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Active":          ("#e6f7e6", "#0d6b2a"),
    "Awaiting Review": ("#fff7e6", "#7a5800"),
    "Under Review":    ("#fff0d6", "#7a5800"),
    "Exited":          ("#eeeeee", "#444444"),
    "Archived":        ("#dddddd", "#444444"),
}


def open_send_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"SEND Register — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    SENDTab(nb, scope="open",    label="Open")
    SENDTab(nb, scope="overdue", label="Overdue Reviews")
    SENDTab(nb, scope="all",     label="All")
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


class SENDTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Register:").pack(side="left")
        self.f_register = ttk.Combobox(
            bar, values=("",) + REGISTER_STATUSES,
            state="readonly", width=18)
        self.f_register.current(0)
        self.f_register.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Need:").pack(side="left")
        self.f_need = ttk.Combobox(bar, values=("",) + NEED_TYPES,
                                     state="readonly", width=28)
        self.f_need.current(0)
        self.f_need.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "register", "primary_need",
                "secondary_need", "cycle", "status",
                "next_review")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings", selectmode="browse")
        widths = {"id": 60, "student": 100, "register": 140,
                   "primary_need": 220, "secondary_need": 200,
                   "cycle": 90, "status": 120, "next_review": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c in ("id",
                                                          "cycle")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("overdue", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",      self._edit),
                ("Advance cycle",    self._advance),
                ("Record review",    self._review),
                ("Exit register",    self._exit),
                ("Change status",    self._set_status),
                ("Delete",           self._delete),
                ("Refresh",          self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_register.current(0)
        self.f_need.current(0)
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.f_register.get():
            f["register_status"] = self.f_register.get()
        if self.f_need.get():
            f["primary_need"] = self.f_need.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "overdue":
            f["overdue_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_entries(**self._filters())
        except ValidationError as e:
            messagebox.showerror("SEND", str(e),
                                    parent=self.frame)
            return
        for e in rows:
            nr = e.next_review_due or "—"
            if e.review_overdue:
                nr = f"OVERDUE ({nr})"
            cyc = f"{e.cycle_number}-{e.cycle_stage[:3]}"
            tag = "overdue" if e.review_overdue else e.status
            self.tree.insert("", "end", iid=str(e.entry_id),
                              values=(e.entry_id, e.student_id,
                                       e.register_status,
                                       e.primary_need,
                                       e.secondary_need or "—",
                                       cyc, e.status, nr),
                              tags=(tag,))
        self.count.config(text=f"{len(rows)} entry(ies)")

    def _selected(self) -> SENDEntry | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("SEND",
                                  "Select an entry first.",
                                  parent=self.frame)
            return None
        return data.get_entry(int(sel[0]))

    def _new(self) -> None:
        if SENDEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        e = self._selected()
        if e and SENDEditor(self.frame,
                              entry=e).result is not None:
            self.refresh()

    def _advance(self) -> None:
        e = self._selected()
        if not e:
            return
        try:
            data.advance_cycle(e.entry_id)
        except ValidationError as exc:
            messagebox.showerror("SEND", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _review(self) -> None:
        e = self._selected()
        if not e:
            return
        if ReviewDialog(self.frame, entry=e).result is not None:
            self.refresh()

    def _exit(self) -> None:
        e = self._selected()
        if not e:
            return
        if ExitDialog(self.frame, entry=e).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        e = self._selected()
        if not e:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=e.status)
        if not new:
            return
        try:
            data.set_status(e.entry_id, new)
        except ValidationError as exc:
            messagebox.showerror("SEND", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        e = self._selected()
        if not e:
            return
        if not messagebox.askyesno(
                "SEND", f"Delete entry #{e.entry_id}?",
                parent=self.frame):
            return
        data.delete_entry(e.entry_id)
        self.refresh()


class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Student")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.combo = ttk.Combobox(bar, state="readonly", width=42)
        opts = _student_options()
        self._opts = opts
        self.combo["values"] = [lbl for _, lbl in opts]
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        idx = self.combo.current()
        if idx < 0:
            return
        sid = self._opts[idx][0]
        rows = data.entries_for_student(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"SEND history for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total entries     : {len(rows)}\n\n")
        for e in rows:
            self.text.insert("end",
                                f"#{e.entry_id}  added {e.date_added}  "
                                f"{e.register_status}  "
                                f"{e.primary_need}  "
                                f"[{e.status}]\n"
                                f"  Cycle {e.cycle_number} — "
                                f"{e.cycle_stage}; "
                                f"next review {e.next_review_due or '—'}"
                                + ("  (OVERDUE)" if e.review_overdue
                                    else "") + "\n")
            if e.provision_summary:
                self.text.insert("end",
                                    f"  Provision: "
                                    f"{e.provision_summary.splitlines()[0]}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "SEND Register Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total              : {s.total}\n"
                            f"Open               : {s.open_count}\n"
                            f"EHCP entries       : {s.ehcp_count}\n"
                            f"Overdue reviews    : {s.overdue_reviews}\n"
                            f"Distinct students  : {s.distinct_students}\n\n")
        self.text.insert("end", "By register status:\n")
        for k in REGISTER_STATUSES:
            n = s.by_register_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy primary need:\n")
        for k in NEED_TYPES:
            n = s.by_primary_need.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<34}: {n}\n")
        self.text.insert("end", "\nBy cycle stage:\n")
        for k in CYCLE_STAGES:
            n = s.by_cycle_stage.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<10}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ────────────────────────────────────────────────────────

class SENDEditor:
    def __init__(self, parent, *,
                 entry: SENDEntry | None = None) -> None:
        self.entry = entry
        self.result: SENDEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit SEND #{entry.entry_id}"
                          if entry else "New SEND entry")
        self.win.geometry("820x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if entry:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        ttk.Label(body, text="Student*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.student_combo = ttk.Combobox(body, state="readonly",
                                              width=42)
        opts = _student_options()
        self._student_opts = opts
        self.student_combo["values"] = [lbl for _, lbl in opts]
        self.student_combo.grid(row=0, column=1, columnspan=3,
                                  sticky="ew", padx=4, pady=2)

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        combo(1, 0, "Register status*", "register_status",
                 REGISTER_STATUSES)
        combo(1, 2, "Status*", "status", STATUSES)
        combo(2, 0, "Primary need*", "primary_need", NEED_TYPES)
        combo(2, 2, "Secondary need", "secondary_need",
                 ("",) + NEED_TYPES)
        entry(3, 0, "Date added*", "date_added")
        entry(3, 2, "Cycle number", "cycle_number")
        combo(4, 0, "Cycle stage*", "cycle_stage", CYCLE_STAGES)
        entry(4, 2, "Next review due", "next_review_due")
        entry(5, 0, "Last review on", "last_review_on")
        entry(5, 2, "EHCP reference", "ehcp_reference")
        entry(6, 0, "EHCP issued on", "ehcp_issued_on")
        entry(6, 2, "Key worker", "key_worker")
        entry(7, 0, "SENCo", "senco")
        self.parent_consent = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text="Parent consent",
                         variable=self.parent_consent).grid(
            row=7, column=2, columnspan=2, sticky="w",
            padx=4, pady=2)
        entry(8, 0, "Exit reason", "exit_reason")
        entry(8, 2, "Exit on", "exit_on")

        row = 9
        for key, label in (
                ("provision_summary",  "Provision summary"),
                ("outcomes",           "Outcomes / targets"),
                ("strategies",         "Strategies"),
                ("external_agencies",  "External agencies"),
                ("pupil_voice",        "Pupil voice"),
                ("notes",              "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=70, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["date_added"].set(_dt.date.today().isoformat())
        self.vars["register_status"].set(DEFAULT_REGISTER_STATUS)
        self.vars["primary_need"].set(DEFAULT_NEED_TYPE)
        self.vars["cycle_number"].set("1")
        self.vars["cycle_stage"].set(DEFAULT_CYCLE_STAGE)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        e = self.entry
        assert e is not None
        for i, (sid, _) in enumerate(self._student_opts):
            if sid == e.student_id:
                self.student_combo.current(i)
                break
        for key in ("register_status", "status",
                     "primary_need", "secondary_need",
                     "date_added", "cycle_stage",
                     "next_review_due", "last_review_on",
                     "ehcp_reference", "ehcp_issued_on",
                     "key_worker", "senco",
                     "exit_reason", "exit_on"):
            self.vars[key].set(getattr(e, key) or "")
        self.vars["cycle_number"].set(str(e.cycle_number))
        self.parent_consent.set(e.parent_consent)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(e, k) or "")

    def _save(self) -> None:
        idx = self.student_combo.current()
        if idx < 0:
            messagebox.showerror("SEND", "Pick a student.",
                                    parent=self.win)
            return
        payload: dict = {
            "student_id": self._student_opts[idx][0],
            "parent_consent": self.parent_consent.get(),
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.entry:
                self.result = data.update_entry(
                    self.entry.entry_id, payload)
            else:
                self.result = data.create_entry(payload)
        except ValidationError as exc:
            messagebox.showerror("SEND", str(exc), parent=self.win)
            return
        self.win.destroy()


class ReviewDialog:
    def __init__(self, parent, *, entry: SENDEntry) -> None:
        self.entry = entry
        self.result: SENDEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Record review — #{entry.entry_id}")
        self.win.geometry("520x360")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reviewed on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Next review due").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.next_due = tk.StringVar(value=entry.next_review_due or "")
        ttk.Entry(body, textvariable=self.next_due, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Outcomes update").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.outcomes = tk.Text(body, height=6, width=48,
                                  wrap="word")
        self.outcomes.insert("1.0", entry.outcomes or "")
        self.outcomes.grid(row=2, column=1, sticky="ew",
                              padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.record_review(
                self.entry.entry_id,
                next_review_due=self.next_due.get().strip() or None,
                outcomes=self.outcomes.get("1.0", "end").rstrip()
                or None,
                reviewed_on=self.when.get().strip())
        except ValidationError as exc:
            messagebox.showerror("SEND", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ExitDialog:
    def __init__(self, parent, *, entry: SENDEntry) -> None:
        self.entry = entry
        self.result: SENDEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Exit register — #{entry.entry_id}")
        self.win.geometry("460x240")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reason*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.reason = tk.Text(body, height=4, width=40, wrap="word")
        self.reason.insert("1.0", entry.exit_reason or "")
        self.reason.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Exit on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Exit",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.exit_register(
                self.entry.entry_id,
                reason=self.reason.get("1.0", "end").rstrip(),
                exit_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as exc:
            messagebox.showerror("SEND", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_send_window"]
