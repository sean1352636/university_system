"""Data protection for support records (administrators): the retention
policy, subject access exports and erasure requests.

All of it is ``student_support.gdpr``: ``retention_policy`` /
``set_retention`` / ``purge(dry_run=True)``, ``subject_access_export``
(recorded in the immutable audit log first, fail closed), and the
two-administrator erasure flow — one administrator requests
(``erase_student``), a different one approves or rejects after re-entering
their password (``decide_erasure``), then it is carried out
(``execute_erasure``). Safeguarding and legal-hold tickets are kept.
"""

from __future__ import annotations

import csv
import json
import logging
import tkinter as tk
from tkinter import scrolledtext, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

from . import common as _c
from ._dialogs import filedialog, messagebox, simpledialog

logger = logging.getLogger(__name__)


class DataProtectionMixin:
    """Mixin for StudentSupportGUI: the Data Protection screen."""

    def show_data_protection(self):
        self.clear_content()
        self.set_view('data_protection')
        frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(frame, text=_t('gui.pastoral.student_support.data_protection.tabs.data_protection', default="🛡️ Data Protection"))
        if not self.is_admin():
            ttk.Label(frame, text=_t('gui.pastoral.student_support.data_protection.labels.admin_only', default="❌ Administrators only"),
                      style='Title.TLabel').pack(pady=20)
            return
        ttk.Label(frame, text=_t('gui.pastoral.student_support.data_protection.labels.title', default="🛡️ Support records: data protection"), style='Title.TLabel').pack(anchor="w", pady=(0, 6))
        tabs = ttk.Notebook(frame)
        tabs.pack(fill="both", expand=True)

        # Retention
        ret = ttk.Frame(tabs, padding=12)
        tabs.add(ret, text=_t('gui.pastoral.student_support.data_protection.tabs.retention', default="Retention"))
        ttk.Label(ret, wraplength=1000, text=_t('gui.pastoral.student_support.data_protection.labels.retention_explain', default="Closed tickets are purged automatically once they are older than their tier's period: the text, replies and files are removed and the ticket keeps only its number, dates and category. Safeguarding and crisis tickets are never purged automatically; tickets under a legal hold are skipped.")).pack(anchor="w")
        grid = ttk.Frame(ret)
        grid.pack(anchor="w", pady=10)
        self.retention_spins = {}
        for row, (tier, label) in enumerate((('standard', 'Standard tickets'), ('restricted', 'Restricted tickets'))):
            ttk.Label(grid, text=f"{label} (years):").grid(row=row, column=0, sticky="w", pady=3)
            spin = tk.Spinbox(grid, from_=1, to=25, width=5)
            spin.grid(row=row, column=1, sticky="w", padx=8)
            self.retention_spins[tier] = spin
        ttk.Label(grid, text=_t('gui.pastoral.student_support.data_protection.labels.safeguarding_never', default="Safeguarding tickets: kept (never purged automatically)")).grid(row=2, column=0, columnspan=2, sticky="w", pady=3)
        bar = ttk.Frame(ret)
        bar.pack(anchor="w")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.data_protection.buttons.save_policy', default="💾 Save policy"),
                   command=self._save_retention).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.data_protection.buttons.preview', default="🔍 Which tickets are due now?"),
                   command=self._preview_purge).pack(side="left", padx=8)
        self.retention_status = ttk.Label(ret, foreground=self.colors['text_secondary'], wraplength=1000)
        self.retention_status.pack(anchor="w", pady=(10, 0))

        # Subject access
        sar = ttk.Frame(tabs, padding=12)
        tabs.add(sar, text=_t('gui.pastoral.student_support.data_protection.tabs.subject_access', default="Subject access"))
        ttk.Label(sar, wraplength=1000, text=_t('gui.pastoral.student_support.data_protection.labels.sar_explain', default="Everything the support tickets hold about one person. Internal staff notes, private staff attachments and safeguarding references are listed separately for review before disclosure. The disclosure is recorded in the audit log first; if it cannot be recorded it is refused.")).pack(anchor="w")
        row = ttk.Frame(sar)
        row.pack(anchor="w", pady=10)
        ttk.Label(row, text=_t('gui.pastoral.student_support.data_protection.labels.person', default="Student number or username:")).pack(side="left")
        self.sar_person = ttk.Entry(row, width=24)
        self.sar_person.pack(side="left", padx=6)
        ttk.Button(row, text=_t('gui.pastoral.student_support.data_protection.buttons.export_json', default="Export JSON…"),
                   command=lambda: self._subject_access('json')).pack(side="left")
        ttk.Button(row, text=_t('gui.pastoral.student_support.data_protection.buttons.export_csv', default="Export CSV…"),
                   command=lambda: self._subject_access('csv')).pack(side="left", padx=6)
        self.sar_status = ttk.Label(sar, foreground=self.colors['text_secondary'], wraplength=1000)
        self.sar_status.pack(anchor="w")

        # Erasure
        era = ttk.Frame(tabs, padding=12)
        tabs.add(era, text=_t('gui.pastoral.student_support.data_protection.tabs.erasure', default="Erasure requests"))
        ttk.Label(era, wraplength=1000, text=_t('gui.pastoral.student_support.data_protection.labels.erasure_explain', default="Erasure needs two administrators: one requests it, a different one approves or rejects it after re-entering their password, then it is carried out. Open tickets must be closed first; safeguarding, crisis and legal-hold tickets are kept.")).pack(anchor="w")
        ebar = ttk.Frame(era)
        ebar.pack(side="bottom", fill="x", pady=(8, 0))
        for text, command in (
                (_t('gui.pastoral.student_support.data_protection.buttons.request', default="➕ Request erasure…"), self._request_erasure),
                (_t('gui.pastoral.student_support.data_protection.buttons.approve', default="✅ Approve…"), lambda: self._decide_erasure(True)),
                (_t('gui.pastoral.student_support.data_protection.buttons.reject', default="❌ Reject…"), lambda: self._decide_erasure(False)),
                (_t('gui.pastoral.student_support.data_protection.buttons.execute', default="🗑️ Carry out approved"), self._execute_erasure),
                (_t('gui.pastoral.student_support.data_protection.buttons.details', default="Details"), self._erasure_details)):
            ttk.Button(ebar, text=text, command=command).pack(side="left", padx=(0, 6))
        self.erasure_tree = _c.tree_with_scroll(
            era, ('id', 'person', 'case', 'status', 'requested_by', 'requested_at', 'decided_by', 'plan'),
            {'id': '#', 'person': 'Student / user', 'case': 'Case', 'status': 'Status',
             'requested_by': 'Requested by', 'requested_at': 'Requested', 'decided_by': 'Decided by',
             'plan': 'Tickets'},
            {'id': 45, 'person': 130, 'case': 170, 'status': 90, 'requested_by': 110,
             'requested_at': 140, 'decided_by': 110, 'plan': 260}, height=14)
        self._erasure_rows = {}
        self.refresh_data_protection()

    def refresh_data_protection(self):
        if not getattr(self, 'erasure_tree', None) or not self.erasure_tree.winfo_exists():
            return
        gdpr = _c.ss('gdpr')
        policy = _c.run(None, gdpr.retention_policy) or {}
        for tier, spin in self.retention_spins.items():
            spin.delete(0, tk.END)
            spin.insert(0, str(policy.get(tier) or ''))
        rows = _c.run(None, gdpr.erasure_requests, _c.actor(self)) or []
        self.erasure_tree.delete(*self.erasure_tree.get_children())
        self._erasure_rows = {}
        for r in rows:
            plan = r.get('tickets') or {}
            summary = (f"erase {len(plan.get('erase') or [])}, keep {len(plan.get('keep') or [])}"
                       if plan else '')
            iid = str(r['request_id'])
            self._erasure_rows[iid] = r
            self.erasure_tree.insert('', 'end', iid=iid, values=(
                r['request_id'], r.get('student_id') or r.get('requester_username') or '',
                r.get('case_reference') or '', r.get('status') or '', r.get('requested_by') or '',
                r.get('requested_at') or '', r.get('decided_by') or '', summary))

    # ── retention ────────────────────────────────────────────────────────

    def _save_retention(self):
        try:
            standard = int(self.retention_spins['standard'].get())
            restricted = int(self.retention_spins['restricted'].get())
        except ValueError:
            messagebox.showerror(_t('gui.pastoral.student_support.data_protection.dialogs.retention', default="Retention"),
                                 _t('gui.pastoral.student_support.data_protection.dialogs.whole_years', default="Give whole numbers of years."))
            return
        policy = _c.run(None, _c.ss('gdpr').set_retention, _c.actor(self),
                        standard_years=standard, restricted_years=restricted)
        if policy:
            self.retention_status.config(text=_t('gui.pastoral.student_support.data_protection.labels.saved', default="Saved: standard {standard} years, restricted {restricted} years.").format(
                standard=policy.get('standard'), restricted=policy.get('restricted')))

    def _preview_purge(self):
        result = _c.run(None, _c.ss('gdpr').purge, _c.actor(self), dry_run=True)
        if result is not None:
            due = result.get('due') or []
            text = (", ".join(f"#{t}" for t in due[:50]) + (" …" if len(due) > 50 else "")) if due else "none"
            self.retention_status.config(text=_t('gui.pastoral.student_support.data_protection.labels.due', default="{count} ticket(s) past their retention period (the daily job purges them): {list}").format(count=len(due), list=text))

    # ── subject access ───────────────────────────────────────────────────

    def _subject_access(self, fmt):
        person = self.sar_person.get().strip()
        if not person:
            messagebox.showerror(_t('gui.pastoral.student_support.data_protection.dialogs.sar', default="Subject access"),
                                 _t('gui.pastoral.student_support.data_protection.dialogs.say_who', default="Enter a student number or username."))
            return
        path = filedialog.asksaveasfilename(
            title=_t('gui.pastoral.student_support.data_protection.dialogs.save_sar', default="Save subject access export"),
            defaultextension=f".{fmt}", initialfile=f"support_sar_{person}.{fmt}",
            filetypes=[(f"{fmt.upper()} files", f"*.{fmt}")])
        if not path:
            return
        section = _c.run(None, _c.ss('gdpr').subject_access_export, _c.actor(self), person)
        if section is None:
            return
        try:
            if fmt == 'json':
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump(section, fh, indent=2, default=str)
            else:
                self._write_sar_csv(path, section)
        except OSError as exc:
            messagebox.showerror(_t('gui.pastoral.student_support.data_protection.dialogs.sar', default="Subject access"), str(exc))
            return
        withheld = ", ".join(f"{k}: {v}" for k, v in (section.get('withheld') or {}).items()) or "nothing"
        self.sar_status.config(text=_t('gui.pastoral.student_support.data_protection.labels.sar_saved', default="{count} ticket(s) saved to {path}. Held back for review: {withheld}.").format(
            count=len(section.get('records') or []), path=path, withheld=withheld))

    @staticmethod
    def _write_sar_csv(path, section):
        """One row per item: the ticket, each reply, attachment and
        referral, then the items held back for review."""
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(['section', 'ticket_id', 'date', 'by', 'what', 'text'])
            for t in section.get('records') or []:
                writer.writerow(['ticket', t.get('ticket_id'), t.get('created_at'),
                                 t.get('requester_username') or t.get('student_id'),
                                 f"{t.get('subject') or ''} [{t.get('status') or ''}, {t.get('category') or ''}]",
                                 t.get('description') or ''])
                if t.get('resolution'):
                    writer.writerow(['resolution', t.get('ticket_id'), t.get('resolved_at'), '', '', t['resolution']])
                for r in t.get('responses') or []:
                    writer.writerow(['reply', t.get('ticket_id'), r.get('response_datetime'),
                                     r.get('responder_username') or r.get('responder_role'), '',
                                     r.get('response_text') or ''])
                for a in t.get('attachments') or []:
                    writer.writerow(['attachment', t.get('ticket_id'), a.get('created_at'),
                                     a.get('uploaded_by'), a.get('original_filename'), ''])
                for ref in t.get('referrals') or []:
                    writer.writerow(['referral', t.get('ticket_id'), ref.get('created_at'), '',
                                     ref.get('kind'), ref.get('target_ref') or ''])
            for item in section.get('for_review') or []:
                row = item.get('row') or {}
                writer.writerow(['for review', item.get('ticket_id'), row.get('response_datetime') or row.get('created_at'),
                                 row.get('responder_username') or row.get('uploaded_by') or '', item.get('what'),
                                 row.get('response_text') or row.get('original_filename') or row.get('target_ref') or ''])

    # ── erasure ──────────────────────────────────────────────────────────

    def _selected_erasure(self):
        sel = self.erasure_tree.selection()
        if not sel:
            messagebox.showinfo(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
                                _t('gui.pastoral.student_support.data_protection.dialogs.select_request', default="Select a request first."))
            return None
        return self._erasure_rows.get(sel[0])

    def _request_erasure(self):
        win = _c.dialog(self, _t('gui.pastoral.student_support.data_protection.windows.request', default="Request erasure"), 640, 420, modal=True)
        form = ttk.Frame(win, padding=15)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=_t('gui.pastoral.student_support.data_protection.labels.person', default="Student number or username:")).pack(anchor="w")
        person = ttk.Entry(form, width=30)
        person.pack(anchor="w", pady=(2, 8))
        ttk.Label(form, text=_t('gui.pastoral.student_support.data_protection.labels.case_ref', default="Case reference (optional):")).pack(anchor="w")
        case = ttk.Entry(form, width=30)
        case.pack(anchor="w", pady=(2, 8))
        ttk.Label(form, text=_t('gui.pastoral.student_support.data_protection.labels.reason', default="Reason (a sentence):")).pack(anchor="w")
        reason = scrolledtext.ScrolledText(form, height=5, wrap=tk.WORD)
        reason.pack(fill="both", expand=True, pady=(2, 8))

        def submit():
            rid = _c.run(win, _c.ss('gdpr').erase_student, _c.actor(self), person.get().strip(),
                         reason.get(1.0, tk.END).strip(), case_reference=case.get().strip() or None)
            if rid:
                win.destroy()
                messagebox.showinfo(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
                                    _t('gui.pastoral.student_support.data_protection.dialogs.requested', default="Request #{rid} recorded. A different administrator must approve it.").format(rid=rid))
                self.refresh_data_protection()

        bar = ttk.Frame(form)
        bar.pack(fill="x")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.data_protection.buttons.submit', default="Request"), command=submit).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.data_protection.buttons.cancel', default="Cancel"), command=win.destroy).pack(side="left", padx=8)

    def _decide_erasure(self, approve):
        r = self._selected_erasure()
        if not r:
            return
        password = simpledialog.askstring(
            _t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
            _t('gui.pastoral.student_support.data_protection.dialogs.reenter_password', default="Re-enter your password to decide request #{rid}:").format(rid=r['request_id']),
            show='*')
        if password is None:
            return
        from education_system.systems.university.services.student_provisioning import (
            verify_staff_password,
        )
        ok = verify_staff_password(_c.username(self), password)
        if not ok:
            messagebox.showerror(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
                                 _t('gui.pastoral.student_support.data_protection.dialogs.wrong_password', default="That password is not right."))
            return
        note = simpledialog.askstring(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
                                      _t('gui.pastoral.student_support.data_protection.dialogs.note', default="Note (optional):")) or ''
        status = _c.run(None, _c.ss('gdpr').decide_erasure, _c.actor(self), r['request_id'],
                        bool(approve), reauthenticated=ok, note=note)
        if status:
            self.refresh_data_protection()

    def _execute_erasure(self):
        r = self._selected_erasure()
        if not r:
            return
        plan = r.get('tickets') or {}
        if not messagebox.askyesno(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
                                   _t('gui.pastoral.student_support.data_protection.dialogs.execute_confirm', default="Carry out request #{rid}? {erase} ticket(s) will be erased; {keep} kept (safeguarding / legal hold). This cannot be undone.").format(
                                       rid=r['request_id'], erase=len(plan.get('erase') or []), keep=len(plan.get('keep') or [])),
                                   icon='warning'):
            return
        result = _c.run(None, _c.ss('gdpr').execute_erasure, _c.actor(self), r['request_id'])
        if result:
            messagebox.showinfo(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"),
                                _t('gui.pastoral.student_support.data_protection.dialogs.executed', default="Erased {erased} ticket(s), kept {kept}, deleted {files} file(s).").format(
                                    erased=len(result.get('erased') or []), kept=len(result.get('kept') or []),
                                    files=result.get('files_deleted', 0)))
            self.refresh_data_protection()

    def _erasure_details(self):
        r = self._selected_erasure()
        if not r:
            return
        plan = r.get('tickets') or {}
        lines = [f"Request #{r['request_id']} — {r.get('status')}",
                 f"Person: {r.get('student_id') or r.get('requester_username') or ''}",
                 f"Case: {r.get('case_reference') or ''}",
                 f"Reason: {r.get('reason') or ''}",
                 f"Requested by {r.get('requested_by')} at {r.get('requested_at')}"]
        if r.get('decided_by'):
            lines.append(f"Decided by {r['decided_by']} at {r.get('decided_at')}: {r.get('decision_note') or ''}")
        for key in ('erase', 'keep', 'active'):
            if plan.get(key):
                lines.append(f"{key.title()}: " + ", ".join(f"#{t}" for t in plan[key]))
        if r.get('result'):
            lines.append(f"Result: {r['result']}")
        messagebox.showinfo(_t('gui.pastoral.student_support.data_protection.dialogs.erasure', default="Erasure"), "\n".join(lines))
