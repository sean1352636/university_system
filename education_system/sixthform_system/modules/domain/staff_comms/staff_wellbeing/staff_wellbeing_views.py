"""Tkinter views for Sixth Form Staff Wellbeing."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.staff_comms.staff_wellbeing import (
    staff_wellbeing as data,
)
from education_system.sixthform_system.modules.domain.staff_comms.staff_wellbeing.staff_wellbeing import (
    ACTION_TYPES,
    CONCERN_FLAGS,
    DEFAULT_ENTRY_TYPE,
    DEFAULT_STATUS,
    ENTRY_TYPES,
    LIKERTS,
    STATUSES,
    ValidationError,
    WellbeingEntry,
    likert_label,
)
from education_system.sixthform_system.modules.domain.staff_comms.staff import (
    staff as staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Recorded":        ("#fff7e6", "#7a5800"),
    "Reviewing":       ("#e6f0ff", "#1a3f8c"),
    "Action Plan Set": ("#fff0d6", "#7a5800"),
    "Monitoring":      ("#e6e6ff", "#3a3a8c"),
    "Resolved":        ("#e6f7e6", "#0d6b2a"),
    "Closed":          ("#eeeeee", "#444444"),
}


def open_staff_wellbeing_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Staff Wellbeing — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    WellbeingTab(nb, scope="open",      label="Open")
    WellbeingTab(nb, scope="at_risk",   label="At Risk")
    WellbeingTab(nb, scope="overdue",   label="Follow-Up Overdue")
    WellbeingTab(nb, scope="all",       label="All")
    SummaryTab(nb)


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    return [(s.staff_id,
             f"{s.staff_id} — "
             f"{getattr(s, 'first_name', '')} "
             f"{getattr(s, 'last_name', '')}".strip())
            for s in rows]


class WellbeingTab:
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
        ttk.Label(bar, text="Staff id:").pack(side="left")
        self.f_staff = ttk.Entry(bar, width=12)
        self.f_staff.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ENTRY_TYPES,
                                     state="readonly", width=26)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly",
                                           width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Action:").pack(side="left")
        self.f_action = ttk.Combobox(bar,
                                       values=("",) + ACTION_TYPES,
                                       state="readonly", width=22)
        self.f_action.current(0)
        self.f_action.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Concern:").pack(side="left")
        self.f_flag = ttk.Combobox(bar,
                                     values=("",) + CONCERN_FLAGS,
                                     state="readonly", width=18)
        self.f_flag.current(0)
        self.f_flag.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "staff", "type", "mood", "stress",
                "workload", "avg", "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "staff": 110,
                   "type": 190, "mood": 50, "stress": 60,
                   "workload": 70, "avg": 60, "status": 120,
                   "flags": 200}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "mood",
                                                  "stress",
                                                  "workload",
                                                  "avg")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("at_risk", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",                self._edit),
                ("Set action plan",     self._action_plan),
                ("Complete follow-up",  self._follow_up),
                ("Resolve",             self._resolve),
                ("Close",               self._close),
                ("Change status",       self._set_status),
                ("Delete",              self._delete),
                ("Refresh",             self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_staff.get().strip():
            f["staff_id"] = self.f_staff.get().strip()
        if self.f_type.get():
            f["entry_type"] = self.f_type.get()
        if self.f_action.get():
            f["action_type"] = self.f_action.get()
        if self.f_flag.get():
            f["with_concern_flag"] = self.f_flag.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "at_risk":
            f["at_risk_only"] = True
        elif self.scope == "overdue":
            f["follow_up_overdue"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_entries(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Staff Wellbeing", str(e),
                                    parent=self.frame)
            return
        for e in rows:
            flags = []
            if e.at_risk:
                flags.append("AT-RISK")
            if e.follow_up_overdue:
                flags.append("FU-OVERDUE")
            if e.confidential:
                flags.append("CONFID")
            if e.concern_flag_list:
                flags.append(",".join(e.concern_flag_list[:2]))
            avg = (f"{e.average_score:.1f}"
                    if e.average_score is not None else "—")
            tag = ("at_risk" if e.at_risk else e.status)
            self.tree.insert(
                "", "end", iid=str(e.entry_id),
                values=(e.entry_id, e.entry_date, e.staff_id,
                         e.entry_type,
                         e.mood if e.mood is not None else "—",
                         (e.stress
                          if e.stress is not None else "—"),
                         (e.workload_pressure
                          if e.workload_pressure is not None
                          else "—"),
                         avg, e.status,
                         ", ".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} entry(ies)")

    def _selected(self) -> WellbeingEntry | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Staff Wellbeing",
                                  "Select an entry first.",
                                  parent=self.frame)
            return None
        return data.get_entry(int(sel[0]))

    def _new(self) -> None:
        if WellbeingEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        e = self._selected()
        if e and WellbeingEditor(self.frame,
                                       entry=e).result is not None:
            self.refresh()

    def _action_plan(self) -> None:
        e = self._selected()
        if not e:
            return
        if ActionPlanDialog(self.frame,
                                entry=e).result is not None:
            self.refresh()

    def _follow_up(self) -> None:
        e = self._selected()
        if not e:
            return
        if FollowUpDialog(self.frame,
                              entry=e).result is not None:
            self.refresh()

    def _resolve(self) -> None:
        e = self._selected()
        if not e:
            return
        try:
            data.resolve(e.entry_id)
        except ValidationError as exc:
            messagebox.showerror("Staff Wellbeing", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _close(self) -> None:
        e = self._selected()
        if not e:
            return
        try:
            data.close_entry(e.entry_id)
        except ValidationError as exc:
            messagebox.showerror("Staff Wellbeing", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        e = self._selected()
        if not e:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=e.status)
        if not new:
            return
        try:
            data.set_status(e.entry_id, new)
        except ValidationError as exc:
            messagebox.showerror("Staff Wellbeing", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        e = self._selected()
        if not e:
            return
        if not messagebox.askyesno(
                "Staff Wellbeing",
                f"Delete entry #{e.entry_id}?",
                parent=self.frame):
            return
        data.delete_entry(e.entry_id)
        self.refresh()


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
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Staff Wellbeing Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total entries        : {s.total}\n"
                            f"Open                 : {s.open_count}\n"
                            f"At risk              : {s.at_risk}\n"
                            f"Follow-up overdue    : {s.follow_up_overdue}\n"
                            f"Referrals made       : {s.referrals_made}\n"
                            f"Distinct staff       : {s.distinct_staff}\n"
                            f"Avg mood             : "
                            f"{s.average_mood if s.average_mood is not None else '—'}\n"
                            f"Avg stress           : "
                            f"{s.average_stress if s.average_stress is not None else '—'}\n"
                            f"Avg workload pres.   : "
                            f"{s.average_workload if s.average_workload is not None else '—'}\n"
                            f"Avg satisfaction     : "
                            f"{s.average_satisfaction if s.average_satisfaction is not None else '—'}\n"
                            f"Avg energy           : "
                            f"{s.average_energy if s.average_energy is not None else '—'}\n\n")
        self.text.insert("end", "By entry type:\n")
        for k in ENTRY_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<32}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<16}: {n}\n")
        if s.by_action:
            self.text.insert("end", "\nBy action type:\n")
            for k in ACTION_TYPES:
                n = s.by_action.get(k, 0)
                if n:
                    self.text.insert("end",
                                        f"  {k:<28}: {n}\n")
        if s.by_concern_flag:
            self.text.insert("end", "\nBy concern flag:\n")
            for k in CONCERN_FLAGS:
                n = s.by_concern_flag.get(k, 0)
                if n:
                    self.text.insert("end",
                                        f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class WellbeingEditor:
    def __init__(self, parent, *,
                 entry: WellbeingEntry | None = None) -> None:
        self.entry = entry
        self.result: WellbeingEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit entry #{entry.entry_id}"
                          if entry else "New wellbeing entry")
        self.win.geometry("880x880")
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
        self.bools: dict[str, tk.BooleanVar] = {}

        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.staff_combo = ttk.Combobox(body, state="readonly",
                                            width=42)
        opts = _staff_options()
        self._staff_opts = opts
        self.staff_combo["values"] = [lbl for _, lbl in opts]
        self.staff_combo.grid(row=0, column=1, columnspan=3,
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

        entry(1, 0, "Date*", "entry_date")
        combo(1, 2, "Entry type*", "entry_type", ENTRY_TYPES)
        entry(2, 0, "Recorded by", "recorded_by")
        combo(2, 2, "Status*", "status", STATUSES)

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=3, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("confidential",     "Confidential"),
                ("anonymous",        "Anonymous"),
                ("consent_to_share", "Consent to share"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        # Ratings panel
        ratings = ttk.LabelFrame(
            body, text="Ratings (1=Very Low .. 5=Very High)")
        ratings.grid(row=4, column=0, columnspan=4,
                       sticky="ew", padx=4, pady=(8, 4))
        rvals = ("", "1", "2", "3", "4", "5")
        for i, (key, label) in enumerate((
                ("mood",              "Mood"),
                ("stress",            "Stress"),
                ("workload_pressure", "Workload pressure"),
                ("job_satisfaction",  "Job satisfaction"),
                ("energy",            "Energy"),
        )):
            r, c = divmod(i, 3)
            ttk.Label(ratings, text=label).grid(
                row=r, column=c * 2, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(ratings, textvariable=v,
                          values=rvals, state="readonly",
                          width=6).grid(
                row=r, column=c * 2 + 1, sticky="w",
                padx=4, pady=2)

        # Concern flags checkboxes
        cflags = ttk.LabelFrame(body, text="Concern flags")
        cflags.grid(row=5, column=0, columnspan=4,
                      sticky="ew", padx=4, pady=(8, 4))
        self.concern_vars: dict[str, tk.BooleanVar] = {}
        for i, flag in enumerate(CONCERN_FLAGS):
            r, c = divmod(i, 4)
            v = tk.BooleanVar()
            self.concern_vars[flag] = v
            ttk.Checkbutton(cflags, text=flag,
                             variable=v).grid(
                row=r, column=c, sticky="w", padx=6, pady=2)

        combo(6, 0, "Action type", "action_type",
                 ("",) + ACTION_TYPES)
        entry(6, 2, "Referred to", "referred_to")
        entry(7, 0, "Follow-up due", "follow_up_due")
        entry(7, 2, "Follow-up done on", "follow_up_done_on")
        entry(8, 0, "Closed on", "closed_on")

        row = 9
        for key, label in (
                ("presenting_issue", "Presenting issue"),
                ("summary_notes",    "Summary notes"),
                ("actions_taken",    "Actions taken"),
                ("support_plan",     "Support plan"),
                ("notes",            "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=74, wrap="word")
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

        self.vars["entry_date"].set(_dt.date.today().isoformat())
        self.vars["entry_type"].set(DEFAULT_ENTRY_TYPE)
        self.vars["status"].set(DEFAULT_STATUS)
        self.bools["confidential"].set(True)

    def _load(self) -> None:
        e = self.entry
        assert e is not None
        for i, (sid, _) in enumerate(self._staff_opts):
            if sid == e.staff_id:
                self.staff_combo.current(i)
                break
        for key in ("entry_date", "entry_type", "status",
                     "recorded_by", "action_type", "referred_to",
                     "follow_up_due", "follow_up_done_on",
                     "closed_on"):
            self.vars[key].set(getattr(e, key) or "")
        for key in ("mood", "stress", "workload_pressure",
                     "job_satisfaction", "energy"):
            v = getattr(e, key)
            self.vars[key].set(str(v) if v is not None else "")
        for k in self.bools:
            self.bools[k].set(getattr(e, k))
        for flag in CONCERN_FLAGS:
            self.concern_vars[flag].set(
                flag in e.concern_flag_list)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(e, k) or "")

    def _save(self) -> None:
        idx = self.staff_combo.current()
        if idx < 0:
            messagebox.showerror("Staff Wellbeing",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        flags = [c for c, v in self.concern_vars.items()
                   if v.get()]
        payload: dict = {
            "staff_id": self._staff_opts[idx][0],
            "concern_flags": flags,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.entry:
                self.result = data.update_entry(
                    self.entry.entry_id, payload)
            else:
                self.result = data.create_entry(payload)
        except ValidationError as exc:
            messagebox.showerror("Staff Wellbeing", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ActionPlanDialog:
    def __init__(self, parent, *, entry: WellbeingEntry) -> None:
        self.entry = entry
        self.result: WellbeingEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Action plan — #{entry.entry_id}")
        self.win.geometry("600x600")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Action type*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.action = tk.StringVar(
            value=entry.action_type or ACTION_TYPES[0])
        ttk.Combobox(body, textvariable=self.action,
                      values=ACTION_TYPES,
                      state="readonly").grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Referred to").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.referred = tk.StringVar(value=entry.referred_to or "")
        ttk.Entry(body, textvariable=self.referred).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Follow-up due").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.follow_up = tk.StringVar(
            value=entry.follow_up_due or "")
        ttk.Entry(body, textvariable=self.follow_up,
                    width=14).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Actions taken*").grid(
            row=3, column=0, sticky="nw", padx=4, pady=4)
        self.actions = tk.Text(body, height=5, width=56,
                                  wrap="word")
        self.actions.insert("1.0", entry.actions_taken or "")
        self.actions.grid(row=3, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Support plan").grid(
            row=4, column=0, sticky="nw", padx=4, pady=4)
        self.support = tk.Text(body, height=5, width=56,
                                  wrap="word")
        self.support.insert("1.0", entry.support_plan or "")
        self.support.grid(row=4, column=1, sticky="ew",
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
            self.result = data.set_action_plan(
                self.entry.entry_id,
                action_type=self.action.get(),
                actions_taken=self.actions.get(
                    "1.0", "end").rstrip(),
                support_plan=self.support.get(
                    "1.0", "end").rstrip() or None,
                follow_up_due=self.follow_up.get().strip() or None,
                referred_to=self.referred.get().strip() or None)
        except ValidationError as exc:
            messagebox.showerror("Staff Wellbeing", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class FollowUpDialog:
    def __init__(self, parent, *, entry: WellbeingEntry) -> None:
        self.entry = entry
        self.result: WellbeingEntry | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Follow-up — #{entry.entry_id}")
        self.win.geometry("520x340")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Done on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when,
                    width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Follow-up notes").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=8, width=48,
                                wrap="word")
        self.notes.grid(row=1, column=1, sticky="ew",
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
            self.result = data.complete_follow_up(
                self.entry.entry_id,
                done_on=self.when.get().strip(),
                notes=self.notes.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Staff Wellbeing", str(exc),
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


__all__ = ["open_staff_wellbeing_window"]
