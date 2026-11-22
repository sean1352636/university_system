"""HR Roles: who holds an HR role, grant/revoke, and the HR audit trail.

Shown under Admin Tools to HR administrators only (``access.can(..., 'hr_admin')``);
every call goes through ``domain/staff_hr/access``, which checks again.
"""

from __future__ import annotations

import json
import logging

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access as _hr
import tkinter as tk
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)


def _access():
    from education_system.systems.university.domains.staff.domain.staff_hr import access
    return access


class HRRolesPanel:
    """Two sub-tabs inside ``parent``: Role holders and Audit trail."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.current_user = getattr(auth, 'current_user', None)
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)
        book = ttk.Notebook(self.frame)
        book.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._build_holders(book)
        self._build_audit(book)
        self.refresh_holders()
        self.refresh_audit()

    # ── role holders ───────────────────────────────────────────────────
    def _build_holders(self, book):
        tab = ttk.Frame(book)
        book.add(tab, text=_t('gui.staff.staff_hr.hr_roles.tabs.holders', default="Role Holders"))

        form = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.hr_roles.labels.grant',
                                           default="Grant or revoke"))
        form.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        ttk.Label(form, text=_t('gui.staff.staff_hr.hr_roles.labels.username',
                                default="Username:")).pack(side=tk.LEFT, padx=5)
        self.user_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.user_var, width=24).pack(side=tk.LEFT, padx=5)
        ttk.Label(form, text=_t('gui.staff.staff_hr.hr_roles.labels.role',
                                default="Role:")).pack(side=tk.LEFT, padx=5)
        a = _access()
        self._role_by_label = {a.ROLE_LABELS.get(r, r): r for r in a.HR_ROLES}
        self.role_var = tk.StringVar(value=next(iter(self._role_by_label)))
        ttk.Combobox(form, textvariable=self.role_var, values=list(self._role_by_label),
                     state='readonly', width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(form, text=_t('gui.staff.staff_hr.hr_roles.buttons.grant', default="Grant"),
                   command=self._grant).pack(side=tk.LEFT, padx=5)
        ttk.Button(form, text=_t('gui.staff.staff_hr.hr_roles.buttons.revoke',
                                 default="Revoke Selected"),
                   command=self._revoke).pack(side=tk.LEFT, padx=5)
        ttk.Button(form, text=_t('gui.staff.staff_hr.hr_roles.buttons.refresh', default="Refresh"),
                   command=self.refresh_holders).pack(side=tk.RIGHT, padx=5)

        cols = ('username', 'name', 'role', 'granted_by', 'granted_at')
        self.holders = ttk.Treeview(tab, columns=cols, show='headings', height=15)
        for col, title, width in zip(cols, ("Username", "Name", "Role", "Granted by", "Granted at"),
                                     (140, 200, 160, 140, 160)):
            self.holders.heading(col, text=title)
            self.holders.column(col, width=width)
        self.holders.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.holders.bind('<<TreeviewSelect>>', self._on_select)
        ttk.Label(tab, foreground='gray', text=_t(
            'gui.staff.staff_hr.hr_roles.labels.admins_note',
            default="System administrators hold every HR role without a grant.")
        ).pack(anchor=tk.W, padx=5)

    def refresh_holders(self):
        a = _access()
        self.holders.delete(*self.holders.get_children())
        try:
            rows = a.list_role_holders(_hr.actor(self))
        except Exception as exc:
            logger.warning("Could not list HR role holders", exc_info=True)
            messagebox.showerror(_t('gui.staff.staff_hr.hr_roles.dialogs.error', default="Error"),
                                 str(exc))
            return
        for r in rows:
            self.holders.insert('', tk.END, values=(
                r['username'], a.display_name(r['username']),
                a.ROLE_LABELS.get(r['role'], r['role']),
                r.get('granted_by') or '', r.get('granted_at') or ''))

    def _on_select(self, _event=None):
        sel = self.holders.selection()
        if not sel:
            return
        values = self.holders.item(sel[0], 'values')
        self.user_var.set(values[0])
        self.role_var.set(values[2])

    def _chosen(self):
        username = self.user_var.get().strip()
        role = self._role_by_label.get(self.role_var.get())
        if not username or not role:
            messagebox.showwarning(
                _t('gui.staff.staff_hr.hr_roles.dialogs.missing', default="Missing data"),
                _t('gui.staff.staff_hr.hr_roles.dialogs.need_user_role',
                   default="Enter a username and choose a role."))
            return None, None
        return username, role

    def _grant(self):
        username, role = self._chosen()
        if not username:
            return
        try:
            added = _access().grant_role(_hr.actor(self), username, role)
        except (ValueError, PermissionError) as exc:
            messagebox.showerror(_t('gui.staff.staff_hr.hr_roles.dialogs.error', default="Error"),
                                 str(exc))
            return
        messagebox.showinfo(
            _t('gui.staff.staff_hr.hr_roles.dialogs.done', default="HR Roles"),
            f"{username} {'now holds' if added else 'already holds'} {self.role_var.get()}.")
        self.refresh_holders()
        self.refresh_audit()

    def _revoke(self):
        username, role = self._chosen()
        if not username:
            return
        if not messagebox.askyesno(
                _t('gui.staff.staff_hr.hr_roles.dialogs.confirm', default="Confirm"),
                f"Revoke {self.role_var.get()} from {username}?"):
            return
        if username == _hr.user_key(self) and role == 'hr_admin':
            if not messagebox.askyesno(
                    _t('gui.staff.staff_hr.hr_roles.dialogs.confirm', default="Confirm"),
                    "This removes your own HR administrator role. Continue?"):
                return
        try:
            removed = _access().revoke_role(_hr.actor(self), username, role)
        except (ValueError, PermissionError) as exc:
            messagebox.showerror(_t('gui.staff.staff_hr.hr_roles.dialogs.error', default="Error"),
                                 str(exc))
            return
        messagebox.showinfo(
            _t('gui.staff.staff_hr.hr_roles.dialogs.done', default="HR Roles"),
            f"Revoked {self.role_var.get()} from {username}." if removed
            else f"{username} did not hold {self.role_var.get()}.")
        self.refresh_holders()
        self.refresh_audit()

    # ── audit trail ────────────────────────────────────────────────────
    def _build_audit(self, book):
        tab = ttk.Frame(book)
        book.add(tab, text=_t('gui.staff.staff_hr.hr_roles.tabs.audit', default="Audit Trail"))
        bar = ttk.Frame(tab)
        bar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        ttk.Label(bar, text=_t('gui.staff.staff_hr.hr_roles.labels.subject',
                               default="Person (username, blank for all):")).pack(side=tk.LEFT)
        self.subject_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.subject_var, width=24)
        entry.pack(side=tk.LEFT, padx=5)
        entry.bind('<Return>', lambda e: self.refresh_audit())
        ttk.Label(bar, text=_t('gui.staff.staff_hr.hr_roles.labels.limit',
                               default="Rows:")).pack(side=tk.LEFT, padx=(10, 0))
        self.limit_var = tk.StringVar(value='500')
        ttk.Combobox(bar, textvariable=self.limit_var, values=('100', '500', '2000'),
                     state='readonly', width=6).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text=_t('gui.staff.staff_hr.hr_roles.buttons.show', default="Show"),
                   command=self.refresh_audit).pack(side=tk.LEFT, padx=5)

        cols = ('at', 'actor', 'action', 'subject', 'entity', 'entity_id', 'details')
        self.audit = ttk.Treeview(tab, columns=cols, show='headings', height=18)
        for col, title, width in zip(cols, ("When", "Who", "Action", "About", "Record", "Id",
                                            "Details"),
                                     (150, 110, 160, 110, 170, 70, 360)):
            self.audit.heading(col, text=title)
            self.audit.column(col, width=width)
        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.audit.yview)
        self.audit.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.audit.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_audit(self):
        self.audit.delete(*self.audit.get_children())
        subject = self.subject_var.get().strip() or None
        a = _access()
        if subject:
            subject = a.staff_key(subject) or subject
        try:
            rows = a.audit_trail(_hr.actor(self), subject=subject,
                                 limit=int(self.limit_var.get() or 500))
        except Exception as exc:
            logger.warning("Could not read the HR audit trail", exc_info=True)
            messagebox.showerror(_t('gui.staff.staff_hr.hr_roles.dialogs.error', default="Error"),
                                 str(exc))
            return
        for r in rows:
            details = r.get('details') or ''
            try:
                parsed = json.loads(details) if details else None
                if isinstance(parsed, dict):
                    details = ', '.join(f"{k}={v}" for k, v in parsed.items())
            except (TypeError, ValueError):
                pass
            self.audit.insert('', tk.END, values=(
                r.get('at') or '', r.get('actor') or '', r.get('action') or '',
                r.get('subject_username') or '', r.get('entity') or '',
                r.get('entity_id') or '', details))


__all__ = ['HRRolesPanel']
