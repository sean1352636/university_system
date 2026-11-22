"""Counselling team tabs: Referrals & Triage, Waiting List, Discharge,
Reports and Counsellors (Caseload & Sessions is ``sessions_tab``)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui import tk_threads
from education_system.systems.university.domains.student_support.domain.mental_health import (
    counselling_pathway as pathway,
    counselling_reports as reports,
)
from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service import (
    common,
)


# ------------------------------------------------------------------ referrals

class ReferralsTab(ttk.Frame):
    """New referrals awaiting triage; triage, close with signposting, or add one."""

    COLUMNS = (("referral_id", "#", 50), ("student_id", "Student", 90),
               ("student_name", "Name", 170), ("source", "Source", 70),
               ("referred_by", "Referred by", 120), ("presenting_issue", "About", 150),
               ("referred_at", "Referred", 140), ("days_waiting", "Days", 50))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="Triage…", command=self._triage).pack(side=tk.LEFT)
        ttk.Button(bar, text="Close with signposting…", command=self._decline).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Open case…", command=self._open).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="New referral…", command=self._new).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)
        self.view = common.tree(self, self.COLUMNS)
        self.view.bind("<Double-1>", lambda _e: self._triage())
        self.rows = {}
        self.refresh()

    def refresh(self):
        rows = common.run(self, pathway.triage_queue, self.auth) or []
        self.rows = common.fill(self.view, rows, self.COLUMNS, "No referrals awaiting triage")

    def _pick(self):
        return common.selected(self.view, self.rows, self, "a referral")

    def _open(self):
        row = self._pick()
        if row:
            from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service.sessions_tab import (
                CaseWindow,
            )
            CaseWindow(self, self.auth, row["referral_id"])

    def _new(self):
        from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service.panel import (
            ReferralForm,
        )
        win = common.dialog(self, "New counselling referral", "720x480")
        ReferralForm(win, self.auth, self_referral=False,
                     on_done=lambda: (win.destroy(), self.refresh())).pack(
            fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _triage(self):
        row = self._pick()
        if row:
            TriageDialog(self, self.auth, row, on_done=self.refresh)

    def _decline(self):
        row = self._pick()
        if not row:
            return
        win = common.dialog(self, f"Close referral #{row['referral_id']}", "560x300")
        ttk.Label(win, text="Where has the student been signposted, and why is counselling "
                            "not the right service?", wraplength=520).pack(anchor="w",
                                                                          padx=8, pady=6)
        box = common.text_box(win, height=8)
        box.pack(fill=tk.BOTH, expand=True, padx=8)

        def save():
            try:
                pathway.decline(self.auth, row["referral_id"], common.read_text(box))
            except Exception as exc:
                common.show_error(win, exc)
                return
            win.destroy()
            self.refresh()
        ttk.Button(win, text="Close referral", command=save).pack(anchor="e", padx=8, pady=8)


class TriageDialog:
    """Rate the risk, name the triage clinician and record notes."""

    def __init__(self, parent, auth, row, on_done=None):
        self.auth, self.row, self.on_done = auth, row, on_done
        self.win = win = common.dialog(parent, f"Triage referral #{row['referral_id']} — "
                                               f"{row.get('student_name') or row['student_id']}",
                                       "640x520")
        form = ttk.Frame(win, padding=10)
        form.pack(fill=tk.BOTH, expand=True)
        ttk.Label(form, text="Risk rating:").grid(row=0, column=0, sticky="w", pady=4)
        self.risk = tk.StringVar(value="low")
        risks = ttk.Frame(form)
        risks.grid(row=0, column=1, sticky="w")
        for level in pathway.RISK_LEVELS:
            ttk.Radiobutton(risks, text=level.title(), value=level,
                            variable=self.risk).pack(side=tk.LEFT, padx=4)
        ttk.Label(form, text="Triage clinician:").grid(row=1, column=0, sticky="w", pady=4)
        self.clinician = tk.StringVar()
        ttk.Entry(form, textvariable=self.clinician, width=30).grid(row=1, column=1,
                                                                    sticky="w")
        ttk.Label(form, text="(blank = you)", foreground="#777777").grid(row=1, column=2,
                                                                          sticky="w")
        ttk.Label(form, text="Triage notes:").grid(row=2, column=0, sticky="nw", pady=4)
        self.notes = common.text_box(form, height=12, width=56)
        self.notes.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=4)
        ttk.Label(form, text="High or urgent risk puts the student on the same-day pathway "
                             "and raises a safeguarding concern.", foreground="#8b0000",
                  wraplength=560).grid(row=3, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Button(form, text="Save triage", command=self._save).grid(row=4, column=2,
                                                                      sticky="e", pady=8)
        form.columnconfigure(1, weight=1)
        form.rowconfigure(2, weight=1)

    def _save(self):
        result = common.run(self.win, pathway.triage, self.auth, self.row["referral_id"],
                            self.risk.get(), notes=common.read_text(self.notes),
                            triage_clinician=self.clinician.get())
        if result is None:
            return
        if result["same_day"] and result["concern_error"]:
            messagebox.showwarning(
                common.title(), "The student is on the same-day pathway, but the safeguarding "
                f"concern could not be raised ({result['concern_error']}). Raise it by hand "
                "in Safeguarding now.", parent=self.win)
        elif result["same_day"]:
            messagebox.showinfo(common.title(), "Same-day pathway: safeguarding concern "
                                f"#{result['concern_id']} raised. Allocate today.",
                                parent=self.win)
        self.win.destroy()
        if self.on_done:
            self.on_done()


# ------------------------------------------------------------------ waiting list

class WaitingListTab(ttk.Frame):
    COLUMNS = (("position", "Pos", 45), ("referral_id", "#", 50),
               ("student_id", "Student", 90), ("student_name", "Name", 170),
               ("risk_rating", "Risk", 80), ("pathway", "Pathway", 90),
               ("same_day_due", "Same day", 90), ("days_waiting", "Days", 50),
               ("triage_clinician", "Triaged by", 110),
               ("safeguarding_concern_id", "Concern", 70))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="Allocate…", command=self._allocate).pack(side=tk.LEFT)
        ttk.Button(bar, text="Re-triage…", command=self._retriage).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Escalate to crisis…", command=self._escalate).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Open case…", command=self._open).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)
        self.summary = tk.StringVar()
        ttk.Label(self, textvariable=self.summary, font=("Arial", 10, "bold")).pack(anchor="w")
        self.view = common.tree(self, self.COLUMNS)
        self.view.bind("<Double-1>", lambda _e: self._allocate())
        self.rows = {}
        self.refresh()

    def refresh(self):
        rows = common.run(self, pathway.waiting_list, self.auth) or []
        self.rows = common.fill(self.view, rows, self.COLUMNS, "Nobody is waiting")
        same_day = sum(1 for r in rows if r["same_day"])
        oldest = max((r["days_waiting"] or 0 for r in rows), default=0)
        self.summary.set(f"{len(rows)} waiting — {same_day} on the same-day pathway — "
                         f"longest wait {oldest} days")

    def _pick(self):
        return common.selected(self.view, self.rows, self, "a referral")

    def _open(self):
        row = self._pick()
        if row:
            from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service.sessions_tab import (
                CaseWindow,
            )
            CaseWindow(self, self.auth, row["referral_id"])

    def _retriage(self):
        row = self._pick()
        if row:
            TriageDialog(self, self.auth, row, on_done=self.refresh)

    def _escalate(self):
        row = self._pick()
        if row:
            escalate_dialog(self, self.auth, row["referral_id"], self.refresh)

    def _allocate(self):
        row = self._pick()
        if not row:
            return
        people = common.run(self, pathway.counsellors, self.auth, active_only=True) or []
        if not people:
            messagebox.showinfo(common.title(), "No active counsellors. Add one on the "
                                "Counsellors tab first.", parent=self)
            return
        win = common.dialog(self, f"Allocate referral #{row['referral_id']}", "520x240")
        labels = {f"{p['name']} ({p['open_caseload']} open)": p["counselor_id"]
                  for p in people}
        choice = tk.StringVar(value=next(iter(labels)))
        ttk.Label(win, text="Counsellor:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Combobox(win, textvariable=choice, values=list(labels), state="readonly",
                     width=36).grid(row=0, column=1, padx=8)
        ttk.Label(win, text="Session cap:").grid(row=1, column=0, sticky="w", padx=8)
        cap = tk.StringVar(value=str(pathway.DEFAULT_SESSION_CAP))
        ttk.Spinbox(win, from_=1, to=pathway.MAX_SESSION_CAP, textvariable=cap,
                    width=6).grid(row=1, column=1, sticky="w", padx=8)

        def save():
            try:
                pathway.allocate(self.auth, row["referral_id"], labels[choice.get()],
                                 session_cap=cap.get())
            except Exception as exc:
                common.show_error(win, exc)
                return
            win.destroy()
            self.refresh()
        ttk.Button(win, text="Allocate", command=save).grid(row=2, column=1, sticky="e",
                                                            padx=8, pady=12)


def escalate_dialog(parent, auth, referral_id, on_done=None):
    win = common.dialog(parent, f"Escalate referral #{referral_id} to the crisis pathway",
                        "580x320")
    ttk.Label(win, text="Record the risk you have identified. This raises a safeguarding "
                        "concern and puts the student at the top of the list.",
              wraplength=540, foreground="#8b0000").pack(anchor="w", padx=8, pady=6)
    box = common.text_box(win, height=8)
    box.pack(fill=tk.BOTH, expand=True, padx=8)

    def save():
        try:
            result = pathway.escalate(auth, referral_id, common.read_text(box))
        except Exception as exc:
            common.show_error(win, exc)
            return
        if result["concern_error"]:
            messagebox.showwarning(common.title(), "Escalated, but the safeguarding concern "
                                   f"could not be raised ({result['concern_error']}). Raise "
                                   "it by hand now.", parent=win)
        else:
            messagebox.showinfo(common.title(), f"Safeguarding concern "
                                f"#{result['concern_id']} raised.", parent=win)
        win.destroy()
        if on_done:
            on_done()
    ttk.Button(win, text="Escalate", command=save).pack(anchor="e", padx=8, pady=8)


# ------------------------------------------------------------------ discharge

class DischargeTab(ttk.Frame):
    """Open episodes (waiting or allocated) and the discharge form."""

    COLUMNS = (("referral_id", "#", 50), ("student_id", "Student", 90),
               ("student_name", "Name", 170), ("counsellor_name", "Counsellor", 140),
               ("sessions_used", "Sessions", 70), ("session_cap", "Cap", 50),
               ("allocated_at", "Allocated", 140))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        top = ttk.Frame(self)
        top.pack(fill=tk.BOTH, expand=True)
        self.view = common.tree(top, self.COLUMNS, height=12)
        self.rows = {}
        form = ttk.LabelFrame(self, text="Discharge the selected episode", padding=8)
        form.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(form, text="Reason:").grid(row=0, column=0, sticky="w")
        self.reason = tk.StringVar(value=pathway.DISCHARGE_REASONS[0])
        ttk.Combobox(form, textvariable=self.reason, values=pathway.DISCHARGE_REASONS,
                     state="readonly", width=36).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Discharge summary:").grid(row=1, column=0, sticky="nw", pady=4)
        self.summary = common.text_box(form, height=5, width=80)
        self.summary.grid(row=1, column=1, sticky="we", padx=6, pady=4)
        ttk.Label(form, text="Remember the last-session outcome measures before "
                             "discharging.", foreground="#555555").grid(row=2, column=1,
                                                                        sticky="w", padx=6)
        ttk.Button(form, text="Discharge", command=self._discharge).grid(row=3, column=1,
                                                                         sticky="e", pady=6)
        ttk.Button(form, text="Refresh", command=self.refresh).grid(row=3, column=0,
                                                                    sticky="w")
        form.columnconfigure(1, weight=1)
        self.refresh()

    def refresh(self):
        rows = common.run(self, pathway.caseload, self.auth) or []
        self.rows = common.fill(self.view, rows, self.COLUMNS, "No allocated episodes")

    def _discharge(self):
        row = common.selected(self.view, self.rows, self, "an episode")
        if not row:
            return
        if not messagebox.askyesno(common.title(), f"Discharge referral #{row['referral_id']} "
                                   f"({self.reason.get()})? Future sessions are cancelled.",
                                   parent=self):
            return
        cancelled = common.run(self, pathway.discharge, self.auth, row["referral_id"],
                               self.reason.get(), summary=common.read_text(self.summary))
        if cancelled is None:
            return
        messagebox.showinfo(common.title(), f"Discharged; {cancelled} future session(s) "
                            "cancelled.", parent=self)
        self.summary.delete("1.0", tk.END)
        self.refresh()


# ------------------------------------------------------------------ reports

class ReportsTab(ttk.Frame):
    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="From (YYYY-MM-DD):").pack(side=tk.LEFT)
        self.date_from = tk.StringVar()
        ttk.Entry(bar, textvariable=self.date_from, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="To:").pack(side=tk.LEFT)
        self.date_to = tk.StringVar()
        ttk.Entry(bar, textvariable=self.date_to, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Run reports", command=self.refresh).pack(side=tk.LEFT, padx=8)
        self.status = tk.StringVar()
        ttk.Label(bar, textvariable=self.status, foreground="#555555").pack(side=tk.LEFT)
        self.text = tk.Text(self, wrap="word", height=30)
        self.text.pack(fill=tk.BOTH, expand=True, pady=6)
        self.refresh()

    def refresh(self):
        self.status.set("Working…")
        start, end = self.date_from.get().strip() or None, self.date_to.get().strip() or None
        tk_threads.start_thread(self, self._work, start, end)

    def _work(self, start, end):
        try:
            text = reports.as_text(reports.wait_times(self.auth, start, end),
                                   reports.outcomes(self.auth, start, end))
        except Exception as exc:
            text = f"The reports could not be run: {exc}"
        tk_threads.ui(self, self._show, text)

    def _show(self, text):
        self.status.set("")
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")


# ------------------------------------------------------------------ counsellors

class CounsellorsTab(ttk.Frame):
    COLUMNS = (("counselor_id", "#", 45), ("name", "Name", 170), ("user_id", "Username", 110),
               ("specialization", "Specialism", 160), ("qualifications", "Qualifications", 170),
               ("availability_schedule", "Availability", 170),
               ("open_caseload", "Open caseload", 90), ("is_active", "Active", 60))
    FIELDS = (("user_id", "Username (sign-in)"), ("name", "Name"),
              ("specialization", "Specialism"), ("qualifications", "Qualifications"),
              ("availability_schedule", "Availability"),
              ("max_daily_appointments", "Max appointments a day"))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="Add counsellor…", command=lambda: self._edit(None)).pack(
            side=tk.LEFT)
        ttk.Button(bar, text="Edit…", command=self._edit_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Activate / deactivate", command=self._toggle).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)
        self.view = common.tree(self, self.COLUMNS)
        self.rows = {}
        self.refresh()

    def refresh(self):
        rows = common.run(self, pathway.counsellors, self.auth) or []
        for row in rows:
            row["is_active"] = bool(row.get("is_active"))
        self.rows = common.fill(self.view, rows, self.COLUMNS, "No counsellors registered")

    def _edit_selected(self):
        row = common.selected(self.view, self.rows, self, "a counsellor")
        if row:
            self._edit(row)

    def _toggle(self):
        row = common.selected(self.view, self.rows, self, "a counsellor")
        if row and common.run(self, pathway.set_counsellor_active, self.auth,
                              row["counselor_id"], not row["is_active"]) is not None:
            self.refresh()

    def _edit(self, row):
        win = common.dialog(self, "Counsellor" if row is None else f"Edit {row['name']}",
                            "520x320")
        values = {}
        for i, (key, label) in enumerate(self.FIELDS):
            ttk.Label(win, text=f"{label}:").grid(row=i, column=0, sticky="w", padx=8, pady=4)
            values[key] = tk.StringVar(value="" if row is None else str(row.get(key) or ""))
            ttk.Entry(win, textvariable=values[key], width=40).grid(row=i, column=1, padx=8)
        if row is None:
            values["max_daily_appointments"].set("8")

        def save():
            data = {k: v.get().strip() for k, v in values.items()}
            try:
                if row is None:
                    pathway.register_counsellor(
                        self.auth, data["user_id"], data["name"],
                        specialization=data["specialization"],
                        qualifications=data["qualifications"],
                        availability_schedule=data["availability_schedule"],
                        max_daily_appointments=int(data["max_daily_appointments"] or 8))
                else:
                    data["max_daily_appointments"] = int(data["max_daily_appointments"] or 8)
                    pathway.update_counsellor(self.auth, row["counselor_id"], **data)
            except Exception as exc:
                common.show_error(win, exc)
                return
            win.destroy()
            self.refresh()
        ttk.Button(win, text="Save", command=save).grid(row=len(self.FIELDS), column=1,
                                                        sticky="e", padx=8, pady=10)
