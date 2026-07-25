import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domain.safeguarding.api import (
    OUTCOME_CODES,
    SELF_HARM_ESCALATION,
    SUPPORT_PLAN_TEMPLATES,
    acknowledge_mandatory_report,
    apply_support_plan_template,
    assign_case,
    close_case,
    create_health_referral,
    create_wellbeing_appointment,
    decrypt_to_temp,
    get_oncall_dsl,
    link_conduct_case,
    link_halls_incident,
    merge_cases,
    notify_reporter_on_status_change,
    notify_tutor,
    require,
    schedule_review,
    set_lifecycle_state,
    split_case,
    update_submission_status,
)


class CaseActionsMixin:
    def _escalate_to_dsl(self, sid, note_box):
        oncall = get_oncall_dsl()
        if oncall:
            assign_case(
                sid,
                oncall["username"],
                assigned_by=self.user.get("username") or "?",
                note="Escalated to on-call DSL",
            )
        update_submission_status(
            sid,
            "In progress",
            self.user["full_name"],
            (note_box.get("1.0", "end").strip() + "\n[ESCALATED]").strip(),
        )
        set_lifecycle_state(sid, "Action", actor=self.user.get("username") or "")
        logger.warning(
            "Safeguarding submission %s ESCALATED by %s -> %s",
            sid,
            self.user.get("username"),
            (oncall or {}).get("username", "(no on-call)"),
        )
        msg = "Case escalated to senior safeguarding lead."
        if oncall:
            msg += f"\nAssigned to on-call DSL: {oncall['full_name']} ({oncall['username']})."
        else:
            msg += "\n⚠ No on-call DSL configured — please assign manually."
        messagebox.showwarning("Escalated", msg + "\n\n" + SELF_HARM_ESCALATION)
        self._refresh_staff_list()
        self._render_empty_detail()

    def _open_close_dialog(self, sid):
        if not require(self.user, "close"):
            messagebox.showerror("Permission denied", "Your role cannot close cases.")
            return
        win = tk.Toplevel(self._host)
        win.title(f"Close case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Outcome code:", bg="#f4f6fa").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4)
        )
        code_var = tk.StringVar(value=OUTCOME_CODES[0][0])
        opts = [f"{c} — {d}" for c, d in OUTCOME_CODES]
        combo = ttk.Combobox(win, values=opts, state="readonly", width=46)
        combo.current(0)
        combo.grid(row=0, column=1, padx=12, pady=(12, 4))
        tk.Label(win, text="Reason / detail:", bg="#f4f6fa").grid(
            row=1, column=0, sticky="nw", padx=12, pady=4
        )
        reason = tk.Text(win, width=46, height=5, font=("Segoe UI", 9))
        reason.grid(row=1, column=1, padx=12, pady=4)

        def _do():
            code = OUTCOME_CODES[combo.current()][0]
            close_case(
                sid, code, reason.get("1.0", "end").strip(), actor=self.user.get("username", "?")
            )
            notify_reporter_on_status_change(sid, "Closed", actor=self.user.get("username", "?"))
            messagebox.showinfo("Closed", f"Case #{sid} closed with outcome '{code}'.")
            win.destroy()
            self._refresh_staff_list()
            self._render_empty_detail()

        ttk.Button(win, text="Close case", command=_do).grid(
            row=2, column=1, sticky="e", padx=12, pady=(0, 12)
        )

    def _open_template_dialog(self, sid):
        win = tk.Toplevel(self._host)
        win.title(f"Apply support template — case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Category template:", bg="#f4f6fa").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4)
        )
        cats = list(SUPPORT_PLAN_TEMPLATES.keys())
        combo = ttk.Combobox(win, values=cats, state="readonly", width=34)
        combo.current(0)
        combo.grid(row=0, column=1, padx=12, pady=(12, 4))
        tk.Label(win, text="Default owner (username):", bg="#f4f6fa").grid(
            row=1, column=0, sticky="w", padx=12, pady=4
        )
        owner = ttk.Entry(win, width=20)
        owner.grid(row=1, column=1, padx=12, pady=4, sticky="w")

        def _apply():
            cat = combo.get()
            n = apply_support_plan_template(
                sid, cat, owner=owner.get().strip() or None, actor=self.user.get("username", "?")
            )
            messagebox.showinfo("Template applied", f"Added {n} action items from '{cat}'.")
            win.destroy()
            self._render_empty_detail()
            self._refresh_staff_list()

        ttk.Button(win, text="Apply", command=_apply).grid(
            row=2, column=1, sticky="e", padx=12, pady=(8, 12)
        )

    def _open_review_dialog(self, sid):
        win = tk.Toplevel(self._host)
        win.title(f"Schedule review — case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Days until next review:", bg="#f4f6fa").grid(
            row=0, column=0, sticky="w", padx=12, pady=12
        )
        days_var = tk.StringVar(value="14")
        ttk.Entry(win, textvariable=days_var, width=8).grid(
            row=0, column=1, padx=12, pady=12, sticky="w"
        )

        def _go():
            try:
                d = int(days_var.get())
            except ValueError:
                messagebox.showerror("Invalid", "Enter a whole number of days.")
                return
            schedule_review(sid, d, actor=self.user.get("username", "?"))
            messagebox.showinfo("Scheduled", f"Next review in {d} days.")
            win.destroy()
            self._render_empty_detail()

        ttk.Button(win, text="Schedule", command=_go).grid(
            row=1, column=1, sticky="e", padx=12, pady=(0, 12)
        )

    def _open_merge_dialog(self, sid):
        if not require(self.user, "merge_split"):
            messagebox.showerror("Permission denied", "Your role cannot merge cases.")
            return
        win = tk.Toplevel(self._host)
        win.title(f"Merge cases into #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text=f"Comma-separated case ids to merge INTO #{sid}:", bg="#f4f6fa").pack(
            padx=12, pady=(12, 4)
        )
        entry = ttk.Entry(win, width=36)
        entry.pack(padx=12)

        def _go():
            try:
                ids = [int(p.strip()) for p in entry.get().split(",") if p.strip()]
            except ValueError:
                messagebox.showerror("Invalid", "Numeric ids only.")
                return
            n = merge_cases(sid, ids, actor=self.user.get("username", "?"))
            messagebox.showinfo("Merged", f"{n} case(s) merged into #{sid}.")
            win.destroy()
            self._refresh_staff_list()
            self._render_empty_detail()

        ttk.Button(win, text="Merge", command=_go).pack(pady=10)

    def _open_split_dialog(self, sid):
        if not require(self.user, "merge_split"):
            messagebox.showerror("Permission denied", "Your role cannot split cases.")
            return
        win = tk.Toplevel(self._host)
        win.title(f"Split case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Extract text that should become a separate case:", bg="#f4f6fa").pack(
            padx=12, pady=(12, 4)
        )
        box = scrolledtext.ScrolledText(win, wrap="word", height=8, width=60, font=("Segoe UI", 9))
        box.pack(padx=12)

        def _go():
            text = box.get("1.0", "end").strip()
            if not text:
                messagebox.showinfo("Empty", "Please paste extract text.")
                return
            nid = split_case(sid, text, actor=self.user.get("username", "?"))
            messagebox.showinfo("Split", f"Created case #{nid} from #{sid}.")
            win.destroy()
            self._refresh_staff_list()
            self._render_empty_detail()

        ttk.Button(win, text="Create split case", command=_go).pack(pady=10)

    def _prompt(self, title, prompt):
        from tkinter import simpledialog

        return simpledialog.askstring(title, prompt, parent=self._host)

    def _ack_mandatory(self, sid):
        ref = (
            self._prompt("Mandatory report", "External reference (LADO / Prevent / Police):") or ""
        )
        acknowledge_mandatory_report(
            sid, actor=self.user.get("username", "?"), external_reference=ref
        )
        messagebox.showinfo("Mandatory report", f"Case #{sid} marked as reported.")
        self._refresh_staff_list()
        self._render_empty_detail()

    def _book_wellbeing(self, sid):
        when = self._prompt(
            "Wellbeing booking", "Appointment datetime ISO (e.g. 2026-05-22T14:00):"
        )
        if not when:
            return
        ref = create_wellbeing_appointment(sid, when, actor=self.user.get("username", "?"))
        messagebox.showinfo("Booked", f"Wellbeing appointment ref: {ref}")
        self._render_empty_detail()

    def _link_conduct(self, sid):
        ref = self._prompt("Conduct link", "Conduct case reference:")
        if not ref:
            return
        link_conduct_case(sid, ref, actor=self.user.get("username", "?"))
        messagebox.showinfo("Linked", f"Linked to conduct case {ref}")
        self._render_empty_detail()

    def _link_halls(self, sid):
        ref = self._prompt("Halls link", "Accommodation incident reference:")
        if not ref:
            return
        link_halls_incident(sid, ref, actor=self.user.get("username", "?"))
        messagebox.showinfo("Linked", f"Linked to halls incident {ref}")
        self._render_empty_detail()

    def _health_referral(self, sid):
        if not messagebox.askyesno(
            "Health referral consent",
            "Has the student given explicit consent for a Health Centre referral to be made?",
        ):
            return
        notes = self._prompt("Health referral", "Referral notes:") or ""
        try:
            create_health_referral(
                sid, consent=True, notes=notes, actor=self.user.get("username", "?")
            )
        except PermissionError as e:
            messagebox.showerror("Consent required", str(e))
            return
        messagebox.showinfo("Referred", "Health Centre referral logged.")
        self._render_empty_detail()

    def _notify_tutor(self, sid):
        tutor = self._prompt("Notify tutor", "Tutor / Personal Advisor username:")
        if not tutor:
            return
        notify_tutor(sid, tutor, actor=self.user.get("username", "?"))
        messagebox.showinfo("Notified", f"Redacted pastoral note sent to {tutor}.")
        self._render_empty_detail()

    def _open_attachment(self, stored_name: str):
        path = decrypt_to_temp(stored_name)
        if not path:
            messagebox.showerror("Attachment", "Could not open attachment.")
            return
        try:
            webbrowser.open_new("file://" + path)
        except Exception:
            messagebox.showinfo("Attachment", f"Decrypted to:\n{path}")
