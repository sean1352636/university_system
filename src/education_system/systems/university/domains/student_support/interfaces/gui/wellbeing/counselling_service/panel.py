"""Counselling Service — the referral-to-discharge pathway in one panel.

What the panel shows depends on who is signed in
(``domain/wellbeing/casework/access``):

* **the counselling team** (counsellors, the health team, administrators):
  Referrals & Triage, Waiting List, Caseload & Sessions, Discharge, Reports
  and Counsellors;
* **a student**: refer yourself, and your referral's progress (place on the
  waiting list, counsellor, sessions) — never triage, notes or scores;
* **other staff**: refer a student (they see nothing of it afterwards).

Everything goes through ``domain/mental_health/counselling_pathway``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.domains.student_support.domain.mental_health import (
    counselling_pathway as pathway,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service import (
    common,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

CRISIS_TEXT = ("In an emergency call 999. Samaritans: 116 123 (free, 24 hours). "
               "Shout: text SHOUT to 85258. NHS 111 (option 2 for mental health).")


class ReferralForm(ttk.LabelFrame):
    """Refer yourself (a student) or a student (staff)."""

    def __init__(self, master, auth, *, self_referral: bool, on_done=None):
        super().__init__(master, padding=10, text=(
            _t("gui.student_support.counselling_service.refer_yourself",
               default="Refer yourself to counselling") if self_referral else
            _t("gui.student_support.counselling_service.refer_student",
               default="Refer a student to counselling")))
        self.auth = auth
        self.self_referral = self_referral
        self.on_done = on_done
        row = 0
        self.student_var = tk.StringVar()
        if not self_referral:
            ttk.Label(self, text="Student number:").grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(self, textvariable=self.student_var, width=24).grid(
                row=row, column=1, sticky="w", pady=4)
            row += 1
        ttk.Label(self, text="What is it mainly about?").grid(row=row, column=0, sticky="w",
                                                             pady=4)
        self.issue_var = tk.StringVar()
        ttk.Combobox(self, textvariable=self.issue_var, values=pathway.PRESENTING_ISSUES,
                     state="readonly", width=30).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Label(self, text=("Tell us a little about what is going on:" if self_referral
                              else "Reason for the referral:")).grid(
            row=row, column=0, sticky="nw", pady=4)
        self.reason = common.text_box(self, height=7, width=56)
        self.reason.grid(row=row, column=1, sticky="we", pady=4)
        row += 1
        self.consent_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, variable=self.consent_var, text=(
            "The counselling team may contact me about this referral" if self_referral else
            "The student knows about and agrees to this referral")).grid(
            row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Button(self, text="Send referral", command=self._send).grid(
            row=row, column=1, sticky="e", pady=8)
        row += 1
        ttk.Label(self, text=CRISIS_TEXT, foreground="#8b0000", wraplength=560,
                  justify=tk.LEFT).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        self.columnconfigure(1, weight=1)

    def _send(self):
        if not self.self_referral and not self.consent_var.get():
            if not messagebox.askyesno(common.title(), "The student has not agreed to this "
                                       "referral. Refer them anyway?", parent=self):
                return
        student = None if self.self_referral else self.student_var.get().strip()
        referral_id = common.run(self, pathway.refer, self.auth, student,
                                 common.read_text(self.reason),
                                 presenting_issue=self.issue_var.get(),
                                 consent_to_contact=self.consent_var.get())
        if referral_id is None:
            return
        messagebox.showinfo(common.title(), f"Referral #{referral_id} has been sent to the "
                            "counselling team.", parent=self)
        self.reason.delete("1.0", tk.END)
        self.student_var.set("")
        if self.on_done:
            self.on_done()


class StudentView(ttk.Frame):
    """A student's own referral and appointments, and the self-referral form."""

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ReferralForm(left, auth, self_referral=True, on_done=self.refresh).pack(
            fill=tk.X)
        people = ttk.LabelFrame(left, text="Our counsellors", padding=8)
        people.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.people = tk.Text(people, height=10, wrap="word")
        self.people.pack(fill=tk.BOTH, expand=True)
        right = ttk.LabelFrame(self, text="My counselling", padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.mine = tk.Text(right, height=24, wrap="word")
        self.mine.pack(fill=tk.BOTH, expand=True)
        ttk.Button(right, text="Refresh", command=self.refresh).pack(anchor="e", pady=4)
        self.refresh()

    def refresh(self):
        self._show(self.mine, self._mine_text())
        self._show(self.people, self._people_text())

    @staticmethod
    def _show(box, text):
        box.configure(state="normal")
        box.delete("1.0", tk.END)
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _mine_text(self) -> str:
        try:
            refs = pathway.my_referrals(self.auth)
        except Exception as exc:
            return str(exc)
        if not refs:
            return "You have not been referred to counselling. Use the form to refer yourself."
        parts = []
        for ref in refs:
            lines = [f"Referral #{ref['referral_id']} — {ref['status_label']}",
                     f"  Referred: {str(ref['referred_at'])[:10]}"]
            if ref["position"]:
                lines.append(f"  Place on the waiting list: {ref['position']}")
            if ref["days_waiting"] is not None:
                lines.append(f"  Waiting: {ref['days_waiting']} days")
            if ref["counsellor_name"]:
                lines.append(f"  Counsellor: {ref['counsellor_name']} "
                             f"(up to {ref['session_cap']} sessions)")
            for sess in ref["sessions"]:
                lines.append(f"  Session {sess['session_number']}: {sess['session_date']} "
                             f"{sess['session_time'] or ''} — {sess['status']}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    @staticmethod
    def _people_text() -> str:
        try:
            people = pathway.active_counsellors_public()
        except Exception as exc:
            return str(exc)
        if not people:
            return "The counsellor list has not been set up yet."
        return "\n\n".join(
            f"{p['name']}" + (f" — {p['specialization']}" if p["specialization"] else "")
            + (f"\n  {p['qualifications']}" if p["qualifications"] else "")
            + (f"\n  Available: {p['availability_schedule']}"
               if p["availability_schedule"] else "")
            for p in people)


class CounsellingServicePanel(ttk.Frame):
    """The Counselling Service for whoever is signed in (see the module)."""

    def __init__(self, master, auth):
        super().__init__(master)
        self.auth = auth
        head = ttk.Frame(self, padding=(10, 8, 10, 0))
        head.pack(fill=tk.X)
        ttk.Label(head, text=common.title(), font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(head, text="🔒 Counselling records are confidential to the counselling team.",
                  foreground="#555555").pack(side=tk.LEFT, padx=12)
        self._build()

    def _build(self):
        if access.is_counselling_team(self.auth):
            self._team()
        elif access.own_student_id(self.auth):
            StudentView(self, self.auth).pack(fill=tk.BOTH, expand=True)
        elif access.is_staff(self.auth):
            body = ttk.Frame(self, padding=10)
            body.pack(fill=tk.BOTH, expand=True)
            ttk.Label(body, text="You can refer a student to the counselling team. You will "
                                 "not see the referral's progress or any clinical record.",
                      wraplength=900).pack(anchor="w", pady=(0, 8))
            ReferralForm(body, self.auth, self_referral=False).pack(fill=tk.X)
        else:
            ttk.Label(self, text="Sign in as a student or a member of staff to use the "
                                 "counselling service.", padding=20).pack()

    def _team(self):
        from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service import (
            sessions_tab,
            team_tabs,
        )
        book = ttk.Notebook(self)
        book.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        tabs = (("Referrals & Triage", team_tabs.ReferralsTab),
                ("Waiting List", team_tabs.WaitingListTab),
                ("Caseload & Sessions", sessions_tab.CaseloadTab),
                ("Discharge", team_tabs.DischargeTab),
                ("Reports", team_tabs.ReportsTab),
                ("Counsellors", team_tabs.CounsellorsTab))
        self.tabs = {}
        for label, cls in tabs:
            try:
                tab = cls(book, self.auth)
            except Exception as exc:  # one broken tab must not hide the rest
                tab = ttk.Label(book, text=f"{label} could not be loaded: {exc}", padding=20)
            book.add(tab, text=label)
            self.tabs[label] = tab
        book.bind("<<NotebookTabChanged>>", lambda _e: self._refresh_current(book))

    def _refresh_current(self, book):
        tab = book.nametowidget(book.select())
        refresh = getattr(tab, "refresh", None)
        if callable(refresh):
            refresh()


def open_window(parent=None, auth=None) -> tk.Toplevel:
    """The panel in its own window (1400x900, clamped to the screen)."""
    from education_system.platform.delivery.gui import window_sizing
    if auth is None:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
    window_sizing.install()
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title(common.title())
    window_sizing.center(win, 1400, 900, minsize=(1200, 800))
    CounsellingServicePanel(win, auth).pack(fill=tk.BOTH, expand=True)
    return win
