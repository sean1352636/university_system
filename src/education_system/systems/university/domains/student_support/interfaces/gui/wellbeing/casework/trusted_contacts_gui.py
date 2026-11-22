"""Trusted contacts (UUK 2022 guidance): a student's own contacts and
consent; for support staff, a student's contacts, the record of each use
(request → approval → contact → telling the student) and the follow-up queue.

Everything goes through ``domain/wellbeing/casework/trusted_contacts``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    trusted_contacts as tc,
)
from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.casework.widgets import (
    Table,
    ask,
    form_dialog,
    info,
    show_error,
)

TITLE = "Trusted Contacts"
CONTACT_COLUMNS = (("contact_id", "#", 50), ("priority", "Order", 50), ("name", "Name", 170),
                   ("relationship", "Relationship", 120), ("phone", "Phone", 130),
                   ("email", "E-mail", 200))
USE_COLUMNS = (("use_id", "#", 50), ("contact_name", "Contact", 150), ("status", "Status", 90),
               ("basis", "Basis", 110), ("emergency", "Emergency", 80),
               ("requested_by", "Asked by", 100), ("approved_by", "Approved by", 100),
               ("contacted_at", "Contacted", 140), ("student_informed", "Told", 50),
               ("reason", "Why", 320))


class TrustedContactsPanel(ttk.Frame):
    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        self.student_id = None
        try:
            self.staff = access.support_scope(auth) is None
        except PermissionError as exc:
            ttk.Label(self, text=str(exc), wraplength=900).pack(padx=20, pady=20)
            return
        if self.staff:
            self._build_staff()
        else:
            self.student_id = access.support_scope(auth)
            self._build_student()
            self.refresh()

    # ------------------------------------------------------------- student
    def _build_student(self):
        ttk.Label(self, text="My trusted contacts", font=("Arial", 13, "bold")).pack(anchor="w")
        ttk.Label(self, wraplength=1100, justify=tk.LEFT, foreground="#444444", text=(
            "You can name up to three people the university may contact if it is seriously "
            "concerned about your safety or wellbeing — for example a parent, partner or close "
            "friend. We will only share what is needed, record each time we do, and normally "
            "tell you afterwards. You can change them or withdraw consent at any time.")).pack(
            anchor="w", pady=4)
        self.consent_var = tk.StringVar()
        row = ttk.Frame(self)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, textvariable=self.consent_var, font=("Arial", 10, "bold")).pack(
            side=tk.LEFT)
        ttk.Button(row, text="Give consent…", command=lambda: self._consent(True)).pack(
            side=tk.LEFT, padx=8)
        ttk.Button(row, text="Withdraw consent", command=lambda: self._consent(False)).pack(
            side=tk.LEFT)
        self._contact_block()
        ttk.Label(self, text="Times we have contacted them",
                  font=("Arial", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.uses = Table(self, (("use_id", "#", 50), ("contact_name", "Contact", 160),
                                 ("contacted_at", "When", 140), ("method", "How", 90),
                                 ("reason", "Why", 520)), height=6)
        self.uses.pack(fill=tk.BOTH, expand=True)

    def _contact_block(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(8, 2))
        ttk.Label(bar, text="Contacts", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(bar, text="Add…", command=self._add).pack(side=tk.LEFT, padx=8)
        ttk.Button(bar, text="Edit…", command=self._edit).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove", command=self._remove).pack(side=tk.LEFT, padx=4)
        self.contacts = Table(self, CONTACT_COLUMNS, height=4)
        self.contacts.pack(fill=tk.X)
        self.contacts.bind_open(self._edit)

    # ------------------------------------------------------------- staff
    def _build_staff(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        ttk.Label(top, text=TITLE, font=("Arial", 13, "bold")).pack(side=tk.LEFT)
        ttk.Label(top, text="Student number:").pack(side=tk.LEFT, padx=(20, 4))
        self.sid_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.sid_var, width=14)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda _e: self._choose())
        ttk.Button(top, text="Open", command=self._choose).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Follow-up queue", command=self._queue).pack(side=tk.LEFT, padx=10)
        self.consent_var = tk.StringVar(value="Open a student to see their trusted contacts. "
                                              "Each look is recorded.")
        ttk.Label(self, textvariable=self.consent_var, font=("Arial", 10, "bold")).pack(
            anchor="w", pady=6)
        ttk.Button(self, text="Record a withdrawal of consent the student asked for",
                   command=lambda: self._consent(False)).pack(anchor="w")
        self._contact_block()
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(10, 2))
        ttk.Label(bar, text="Uses", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        for label, cmd in (("Request contact…", self._request), ("Approve…", lambda:
                           self._decide(True)), ("Decline…", lambda: self._decide(False)),
                           ("Record contact made…", self._record),
                           ("Tell the student…", self._inform),
                           ("Defer telling…", self._defer)):
            ttk.Button(bar, text=label, command=cmd).pack(side=tk.LEFT, padx=2)
        self.uses = Table(self, USE_COLUMNS, height=7)
        self.uses.pack(fill=tk.BOTH, expand=True)

    def _choose(self):
        sid = self.sid_var.get().strip()
        if not sid:
            info(self, "Type a student number.", TITLE)
            return
        self.student_id = sid
        self.refresh()

    def refresh(self):
        if not self.student_id:
            return
        try:
            state = tc.consent(self.auth, self.student_id)
            contacts = tc.list_contacts(self.auth, self.student_id)
            uses = tc.uses(self.auth, self.student_id)
        except Exception as exc:
            show_error(self, exc, TITLE)
            return
        if state["consent_given"]:
            text = f"Consent given {str(state.get('given_at') or '')[:10]}."
        elif state.get("withdrawn_at"):
            text = f"Consent withdrawn {str(state['withdrawn_at'])[:10]}."
        else:
            text = "No consent given."
        if self.staff:
            text = f"Student {self.student_id}: {text}"
        self.consent_var.set(text)
        self.contacts.load(contacts)
        self.uses.load(uses)

    def _call(self, fn, *args, **kwargs):
        try:
            fn(self.auth, *args, **kwargs)
        except Exception as exc:
            show_error(self, exc, TITLE)
            return False
        self.refresh()
        return True

    def _need_student(self):
        if not self.student_id:
            info(self, "Open a student first.", TITLE)
            return False
        return True

    def _consent(self, given):
        if not self._need_student():
            return
        if given and not ask(self, tc.CONSENT_STATEMENT + "\n\nDo you agree?", TITLE):
            return
        if not given and not ask(self, "Withdraw consent to contact your trusted contacts?"
                                 if not self.staff else "Record that the student has "
                                 "withdrawn consent?", TITLE):
            return
        self._call(tc.set_consent, given, student_id=self.student_id)

    def _contact_fields(self, row=None):
        row = row or {}
        return [("name", "Name", "entry", row.get("name", "")),
                ("relationship", "Relationship", "entry", row.get("relationship") or ""),
                ("phone", "Phone", "entry", row.get("phone") or ""),
                ("email", "E-mail", "entry", row.get("email") or ""),
                ("address", "Address (optional)", "entry", row.get("address") or ""),
                ("priority", "Order to try (1 first)", "entry", row.get("priority") or "")]

    def _add(self):
        if not self._need_student():
            return
        form_dialog(self, "Add a trusted contact", self._contact_fields(), lambda v: self._save(
            tc.add_contact(self.auth, v["name"], v["relationship"], v["phone"], v["email"],
                           address=v["address"], student_id=self.student_id,
                           priority=v["priority"] or None)))

    def _edit(self):
        row = self.contacts.selected()
        if not row:
            info(self, "Select a contact.", TITLE)
            return
        form_dialog(self, "Edit trusted contact", self._contact_fields(row), lambda v: self._save(
            tc.update_contact(self.auth, row["contact_id"], v["name"], v["relationship"],
                              v["phone"], v["email"], address=v["address"],
                              priority=v["priority"] or None)))

    def _save(self, _result):
        self.after(10, self.refresh)

    def _remove(self):
        row = self.contacts.selected()
        if row and ask(self, f"Remove {row['name']} as a trusted contact?", TITLE):
            self._call(tc.remove_contact, row["contact_id"],
                       "Removed by the student" if not self.staff else "Removed by staff")

    def _selected_use(self):
        row = self.uses.selected()
        if not row:
            info(self, "Select a use in the table.", TITLE)
        return row

    def _request(self):
        if not self._need_student():
            return
        contact = self.contacts.selected()
        if not contact:
            info(self, "Select the contact to use.", TITLE)
            return
        form_dialog(self, f"Request contact with {contact['name']}", [
            ("reason", "The serious concern (shared with the student later)", "text", ""),
            ("circumstances", "Circumstances (staff only, sealed)", "text", ""),
            ("emergency", "Emergency — risk to life (contact may be made before approval)",
             "check", False)],
            lambda v: self._save(tc.request_use(self.auth, self.student_id, contact["contact_id"],
                                                v["reason"], v["circumstances"],
                                                emergency=v["emergency"])), size="620x460")

    def _decide(self, approve):
        row = self._selected_use()
        if row:
            form_dialog(self, ("Approve" if approve else "Decline") + f" use #{row['use_id']}",
                        [("note", "Note", "text", "")],
                        lambda v: self._save(tc.decide_use(self.auth, row["use_id"], approve,
                                                           v["note"])), size="520x260")

    def _record(self):
        row = self._selected_use()
        if row:
            form_dialog(self, f"Contact made — use #{row['use_id']}", [
                ("method", "How", tc.METHODS, "phone"),
                ("when", "When (YYYY-MM-DD HH:MM; blank = now)", "entry", ""),
                ("outcome", "What was said and agreed", "text", "")],
                lambda v: self._save(tc.record_contact(self.auth, row["use_id"], v["method"],
                                                       v["outcome"],
                                                       contacted_at=v["when"] or None)))

    def _inform(self):
        row = self._selected_use()
        if row:
            form_dialog(self, f"Tell the student — use #{row['use_id']}", [
                ("message", "Anything to add to the message", "text", "")],
                lambda v: self._save(tc.inform_student(self.auth, row["use_id"], v["message"])),
                size="560x280")

    def _defer(self):
        row = self._selected_use()
        if row:
            form_dialog(self, f"Defer telling the student — use #{row['use_id']}", [
                ("reason", "Why telling them now would increase the risk", "text", ""),
                ("review", "Review on (YYYY-MM-DD)", "entry", "")],
                lambda v: self._save(tc.defer_informing(self.auth, row["use_id"], v["reason"],
                                                        v["review"])))

    def _queue(self):
        try:
            queue = tc.work_queue(self.auth)
        except Exception as exc:
            show_error(self, exc, TITLE)
            return
        labels = {"awaiting_approval": "Awaiting approval",
                  "approved_not_contacted": "Approved, contact not yet recorded",
                  "student_not_told": "Student not yet told",
                  "told_later": "Telling deferred (review date ahead)"}
        lines = []
        for key, label in labels.items():
            lines.append(f"{label} ({len(queue[key])})")
            lines += [f"   #{r['use_id']} {r['student_id']} → {r['contact_name']}"
                      f"{' [EMERGENCY]' if r['emergency'] else ''} {r['reason'][:60]}"
                      for r in queue[key]]
        info(self, "\n".join(lines), TITLE)
