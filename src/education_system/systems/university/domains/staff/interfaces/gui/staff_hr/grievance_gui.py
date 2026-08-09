"""
Grievance & Disciplinary GUI

Provides interface for:
- Filing grievances
- Tracking grievance status
- Managing grievances (admin)
- Disciplinary record management (admin)
- Statistics and reports
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.grievance_manager import GrievanceManager
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, show_validation_error
)


class GrievanceGUI:
    """GUI for managing grievances and disciplinary records."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), _t('gui.staff.staff_hr.grievance.dialogs.login_required_to_access_grievance_management', default="Login required to access Grievance Management"))
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t('gui.staff.staff_hr.grievance.tabs.grievances', default="Grievances"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.grievance.windows.grievance_disciplinary_management', default="Grievance & Disciplinary Management"))
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t('gui.staff.staff_hr.grievance.buttons.close', default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text=_t('gui.staff.staff_hr.grievance.labels.ready', default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_file_grievance_tab()
        self._create_my_grievances_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_manage_grievances_tab()
            self._create_disciplinary_tab()
            self._create_statistics_tab()

    def _create_file_grievance_tab(self):
        """Create file grievance tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.grievance.tabs.file_grievance', default="File Grievance"))

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.grievance.labels.file_a_grievance', default="File a Grievance"), style='Header.TLabel').pack(side=tk.LEFT)

        # Form
        form_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.grievance.labels.grievance_details', default="Grievance Details"), padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text=_t('gui.staff.staff_hr.grievance.labels.category', default="Category:")).grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.grv_category = ttk.Combobox(form_frame, width=30, state='readonly')
        self._load_grievance_categories()
        self.grv_category.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text=_t('gui.staff.staff_hr.grievance.labels.respondent_optional', default="Respondent (optional):")).grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.grv_respondent = ttk.Entry(form_frame, width=25)
        self.grv_respondent.grid(row=1, column=1, padx=10, pady=8, sticky='w')
        ttk.Label(form_frame, text=_t('gui.staff.staff_hr.grievance.labels.user_id_of_person_complaint_is_against', default="(User ID of person complaint is against)")).grid(
            row=1, column=2, sticky='w', padx=10)

        # Row 3
        ttk.Label(form_frame, text=_t('gui.staff.staff_hr.grievance.labels.description_variant_2', default="Description:")).grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        self.grv_description = scrolledtext.ScrolledText(form_frame, width=60, height=8)
        self.grv_description.grid(row=2, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Anonymous option
        self.grv_anonymous = tk.BooleanVar()
        ttk.Checkbutton(form_frame, text=_t('gui.staff.staff_hr.grievance.buttons.file_anonymously_your_identity_will_be_protected', default="File Anonymously (your identity will be protected)"),
                        variable=self.grv_anonymous).grid(row=3, column=1, sticky='w', padx=10, pady=5)

        # Submit
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=15)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.grievance.buttons.submit_grievance', default="Submit Grievance"), command=self._submit_grievance).pack()

        # Info panel
        info_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.grievance.labels.information', default="Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        info_text = """
        - All grievances are handled confidentially
        - Anonymous submissions protect your identity from all parties
        - You will receive updates on your grievance status
        - Typical resolution time: 14-30 days depending on complexity
        """
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor='w')

    def _load_grievance_categories(self):
        """Load grievance categories."""
        categories = GrievanceManager.get_all_categories()
        if categories:
            self.grv_category['values'] = [c['name'] for c in categories]
        else:
            self.grv_category['values'] = [
                'Harassment', 'Discrimination', 'Workplace Safety',
                'Policy Violation', 'Management', 'Other'
            ]
        if self.grv_category['values']:
            self.grv_category.set(self.grv_category['values'][0])

    def _submit_grievance(self):
        """Submit a grievance."""
        category = self.grv_category.get()
        description = self.grv_description.get("1.0", tk.END).strip()

        if not description:
            messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), _t('gui.staff.staff_hr.grievance.dialogs.please_provide_a_description_of_your_grievance', default="Please provide a description of your grievance"))
            return

        respondent = self.grv_respondent.get().strip() or None
        is_anonymous = self.grv_anonymous.get()

        try:
            grievance_id = GrievanceManager.create_grievance(
                complainant_id=self._get_user_id(),
                category=category,
                description=description,
                respondent_id=respondent,
                is_anonymous=is_anonymous
            )

            msg = f"Grievance filed successfully.\nReference: GRV-{grievance_id}"
            if is_anonymous:
                msg += "\n\nYour identity will be kept confidential."
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.success', default="Success"), msg)

            # Clear form
            self.grv_description.delete("1.0", tk.END)
            self.grv_respondent.delete(0, tk.END)
            self.grv_anonymous.set(False)

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), str(e))

    def _create_my_grievances_tab(self):
        """Create my grievances tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.grievance.tabs.my_grievances', default="My Grievances"))

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.grievance.labels.my_grievances', default="My Grievances"), style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.grievance.buttons.refresh', default="Refresh"), command=self._load_my_grievances).pack(side=tk.RIGHT)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Category', 'Status', 'Filed Date', 'Resolution Date', 'Description')
        self.my_grv_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.my_grv_tree.yview)

        widths = {'ID': 60, 'Category': 120, 'Status': 100, 'Filed Date': 100, 'Resolution Date': 100, 'Description': 250}
        for col in columns:
            self.my_grv_tree.heading(col, text=col)
            self.my_grv_tree.column(col, width=widths.get(col, 100))

        self.my_grv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.my_grv_tree.tag_configure('open', background='#fff3cd')
        self.my_grv_tree.tag_configure('investigating', background='#cce5ff')
        self.my_grv_tree.tag_configure('resolved', background='#d4edda')

        self.my_grv_tree.bind('<Double-1>', self._view_grievance_details)

        # Details panel
        details_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.grievance.labels.selected_grievance_details', default="Selected Grievance Details"), padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        self.grv_detail_text = scrolledtext.ScrolledText(details_frame, height=6, state='disabled')
        self.grv_detail_text.pack(fill=tk.X)

        self._load_my_grievances()

    def _load_my_grievances(self):
        """Load my grievances."""
        for item in self.my_grv_tree.get_children():
            self.my_grv_tree.delete(item)

        grievances = GrievanceManager.get_user_grievances(self._get_user_id())

        for g in grievances:
            status = g.get('status', '').lower()
            self.my_grv_tree.insert('', tk.END, values=(
                f"GRV-{g.get('grievance_id')}",
                g.get('category', ''),
                g.get('status', '').title(),
                g.get('filed_date', ''),
                g.get('resolution_date', '-'),
                g.get('description', '')[:50]
            ), tags=(status,))

    def _view_grievance_details(self, event):
        """View grievance details."""
        selection = self.my_grv_tree.selection()
        if not selection:
            return

        item = self.my_grv_tree.item(selection[0])
        grv_id = int(item['values'][0].replace('GRV-', ''))

        grievance = GrievanceManager.get_grievance(grv_id)
        if not grievance:
            return

        self.grv_detail_text.config(state='normal')
        self.grv_detail_text.delete("1.0", tk.END)

        details = f"""Reference: GRV-{grv_id}
Category: {grievance.get('category')}
Status: {grievance.get('status', '').title()}
Filed: {grievance.get('filed_date')}
Priority: {grievance.get('priority', 'normal').title()}

Description:
{grievance.get('description')}

Resolution:
{grievance.get('resolution', 'Pending...')}
"""
        self.grv_detail_text.insert("1.0", details)
        self.grv_detail_text.config(state='disabled')

    def _create_manage_grievances_tab(self):
        """Create manage grievances tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.grievance.tabs.manage', default="Manage"))

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.grievance.labels.manage_grievances', default="Manage Grievances"), style='Header.TLabel').pack(side=tk.LEFT)

        # Filter
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.grievance.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
        self.admin_grv_status = ttk.Combobox(filter_frame,
            values=['All Active', 'Open', 'Investigating', 'Resolved', 'All'], width=12, state='readonly')
        self.admin_grv_status.set('All Active')
        self.admin_grv_status.pack(side=tk.LEFT, padx=5)
        self.admin_grv_status.bind('<<ComboboxSelected>>', lambda e: self._load_all_grievances())
        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.grievance.buttons.refresh', default="Refresh"), command=self._load_all_grievances).pack(side=tk.LEFT, padx=10)

        # Grievances list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Category', 'Status', 'Priority', 'Filed', 'Assigned', 'Anonymous')
        self.admin_grv_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.admin_grv_tree.yview)

        for col in columns:
            self.admin_grv_tree.heading(col, text=col)
            self.admin_grv_tree.column(col, width=100)

        self.admin_grv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.admin_grv_tree.tag_configure('urgent', background='#f8d7da')
        self.admin_grv_tree.tag_configure('high', background='#fff3cd')

        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text=_t('gui.staff.staff_hr.grievance.buttons.assign_to_me', default="Assign to Me"), command=self._assign_grievance).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.staff.staff_hr.grievance.buttons.update_status', default="Update Status"), command=self._update_grievance_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.staff.staff_hr.grievance.buttons.resolve', default="Resolve"), command=self._resolve_grievance).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.staff.staff_hr.grievance.buttons.view_details', default="View Details"), command=self._view_admin_grievance).pack(side=tk.LEFT, padx=5)

        self._load_all_grievances()

    def _load_all_grievances(self):
        """Load all grievances (admin)."""
        for item in self.admin_grv_tree.get_children():
            self.admin_grv_tree.delete(item)

        status_filter = self.admin_grv_status.get().lower()
        if status_filter == 'all active':
            status = 'active'
        elif status_filter == 'all':
            status = None
        else:
            status = status_filter

        grievances = GrievanceManager.search_grievances(status=status)

        for g in grievances:
            priority = g.get('priority', 'normal').lower()
            tag = 'urgent' if priority == 'urgent' else 'high' if priority == 'high' else ''

            self.admin_grv_tree.insert('', tk.END, values=(
                f"GRV-{g.get('grievance_id')}",
                g.get('category', ''),
                g.get('status', '').title(),
                g.get('priority', 'normal').title(),
                g.get('filed_date', ''),
                g.get('assigned_to', '-'),
                'Yes' if g.get('is_anonymous') else 'No'
            ), tags=(tag,))

    def _assign_grievance(self):
        """Assign grievance to current user."""
        selection = self.admin_grv_tree.selection()
        if not selection:
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.info', default="Info"), _t('gui.staff.staff_hr.grievance.dialogs.please_select_a_grievance', default="Please select a grievance"))
            return

        item = self.admin_grv_tree.item(selection[0])
        grv_id = int(item['values'][0].replace('GRV-', ''))

        GrievanceManager.update_grievance(grv_id, assigned_to=self._get_user_id())
        GrievanceManager.create_action(grv_id, 'assigned',
            details=f"Assigned to {self._get_user_id()}")
        messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.success', default="Success"), _t('gui.staff.staff_hr.grievance.dialogs.grievance_assigned_to_you', default="Grievance assigned to you"))
        self._load_all_grievances()

    def _update_grievance_status(self):
        """Update grievance status."""
        selection = self.admin_grv_tree.selection()
        if not selection:
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.info', default="Info"), _t('gui.staff.staff_hr.grievance.dialogs.please_select_a_grievance', default="Please select a grievance"))
            return

        item = self.admin_grv_tree.item(selection[0])
        grv_id = int(item['values'][0].replace('GRV-', ''))

        # Status dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.grievance.windows.update_status', default="Update Status"))
        dialog.geometry("300x150")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.new_status', default="New Status:")).pack(pady=5)
        status_combo = ttk.Combobox(frame,
            values=['open', 'investigating', 'pending_response', 'resolved', 'closed'], state='readonly')
        status_combo.set('investigating')
        status_combo.pack(pady=5)

        def save():
            new_status = status_combo.get()
            GrievanceManager.update_grievance(grv_id, status=new_status)
            GrievanceManager.create_action(grv_id, 'status_change',
                details=f"Status changed to {new_status}")
            dialog.destroy()
            self._load_all_grievances()
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.success', default="Success"), _t('gui.staff.staff_hr.grievance.dialogs.status_updated', default="Status updated"))

        ttk.Button(frame, text=_t('gui.staff.staff_hr.grievance.buttons.save', default="Save"), command=save).pack(pady=15)

    def _resolve_grievance(self):
        """Resolve grievance."""
        selection = self.admin_grv_tree.selection()
        if not selection:
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.info', default="Info"), _t('gui.staff.staff_hr.grievance.dialogs.please_select_a_grievance', default="Please select a grievance"))
            return

        item = self.admin_grv_tree.item(selection[0])
        grv_id = int(item['values'][0].replace('GRV-', ''))

        # Resolution dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.grievance.windows.resolve_grievance', default="Resolve Grievance"))
        dialog.geometry("500x300")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.resolution_details', default="Resolution Details:")).pack(anchor='w')
        resolution_text = scrolledtext.ScrolledText(frame, height=8)
        resolution_text.pack(fill=tk.BOTH, expand=True, pady=10)

        def save():
            resolution = resolution_text.get("1.0", tk.END).strip()
            if not resolution:
                messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), _t('gui.staff.staff_hr.grievance.dialogs.please_provide_resolution_details', default="Please provide resolution details"))
                return
            GrievanceManager.resolve_grievance(grv_id, resolution)
            dialog.destroy()
            self._load_all_grievances()
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.success', default="Success"), _t('gui.staff.staff_hr.grievance.dialogs.grievance_resolved', default="Grievance resolved"))

        ttk.Button(frame, text=_t('gui.staff.staff_hr.grievance.buttons.resolve', default="Resolve"), command=save).pack(pady=10)

    def _view_admin_grievance(self):
        """View grievance details (admin)."""
        selection = self.admin_grv_tree.selection()
        if not selection:
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.info', default="Info"), _t('gui.staff.staff_hr.grievance.dialogs.please_select_a_grievance', default="Please select a grievance"))
            return

        item = self.admin_grv_tree.item(selection[0])
        grv_id = int(item['values'][0].replace('GRV-', ''))

        grievance = GrievanceManager.get_grievance(grv_id)
        if not grievance:
            return

        # Details dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Grievance GRV-{grv_id}")
        dialog.geometry("600x500")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Info
        info_frame = ttk.LabelFrame(frame, text=_t('gui.staff.staff_hr.grievance.labels.details', default="Details"), padding=10)
        info_frame.pack(fill=tk.X, pady=5)

        fields = [
            ('Category', grievance.get('category')),
            ('Status', grievance.get('status', '').title()),
            ('Priority', grievance.get('priority', 'normal').title()),
            ('Filed', grievance.get('filed_date')),
            ('Assigned To', grievance.get('assigned_to', '-')),
        ]
        if not grievance.get('is_anonymous'):
            fields.insert(0, ('Complainant', grievance.get('complainant_id')))

        for i, (label, value) in enumerate(fields):
            row = i // 3
            col = (i % 3) * 2
            ttk.Label(info_frame, text=f"{label}:", font=('Arial', 9, 'bold')).grid(
                row=row, column=col, sticky='e', padx=5, pady=3)
            ttk.Label(info_frame, text=str(value)).grid(row=row, column=col+1, sticky='w', padx=5, pady=3)

        # Description
        desc_frame = ttk.LabelFrame(frame, text=_t('gui.staff.staff_hr.grievance.labels.description', default="Description"), padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        desc_text = scrolledtext.ScrolledText(desc_frame, height=8, state='normal')
        desc_text.insert("1.0", grievance.get('description', ''))
        desc_text.config(state='disabled')
        desc_text.pack(fill=tk.BOTH, expand=True)

        # Actions history
        actions_frame = ttk.LabelFrame(frame, text=_t('gui.staff.staff_hr.grievance.labels.action_history', default="Action History"), padding=10)
        actions_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        actions = GrievanceManager.get_grievance_actions(grv_id)
        actions_list = tk.Listbox(actions_frame, height=5)
        for a in actions:
            actions_list.insert(tk.END, f"{a.get('action_date')} - {a.get('action_type')}: {a.get('details', '')[:50]}")
        actions_list.pack(fill=tk.BOTH, expand=True)

        ttk.Button(frame, text=_t('gui.staff.staff_hr.grievance.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

    def _create_disciplinary_tab(self):
        """Create disciplinary records tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.grievance.tabs.disciplinary', default="Disciplinary"))

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.grievance.labels.disciplinary_records', default="Disciplinary Records"), style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.grievance.buttons.new_record', default="New Record"), command=self._create_disciplinary_record).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.grievance.buttons.refresh', default="Refresh"), command=self._load_disciplinary_records).pack(side=tk.RIGHT, padx=5)

        # Search
        search_frame = ttk.Frame(tab)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(search_frame, text=_t('gui.staff.staff_hr.grievance.labels.user_id', default="User ID:")).pack(side=tk.LEFT, padx=5)
        self.disc_search = ttk.Entry(search_frame, width=15)
        self.disc_search.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text=_t('gui.staff.staff_hr.grievance.buttons.search', default="Search"), command=self._search_disciplinary).pack(side=tk.LEFT, padx=10)

        # Records list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'User', 'Offense', 'Severity', 'Date', 'Status', 'Reported By')
        self.disc_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        for col in columns:
            self.disc_tree.heading(col, text=col)
            self.disc_tree.column(col, width=100)

        self.disc_tree.pack(fill=tk.BOTH, expand=True)

        self.disc_tree.tag_configure('severe', background='#f8d7da')
        self.disc_tree.tag_configure('major', background='#fff3cd')

        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text=_t('gui.staff.staff_hr.grievance.buttons.add_action', default="Add Action"), command=self._add_disciplinary_action).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.staff.staff_hr.grievance.buttons.view_details', default="View Details"), command=self._view_disciplinary_details).pack(side=tk.LEFT, padx=5)

        self._load_disciplinary_records()

    def _load_disciplinary_records(self):
        """Load disciplinary records."""
        for item in self.disc_tree.get_children():
            self.disc_tree.delete(item)

        records = GrievanceManager.search_disciplinary_records()

        for r in records:
            severity = r.get('severity', '').lower()
            tag = 'severe' if severity == 'severe' else 'major' if severity == 'major' else ''

            self.disc_tree.insert('', tk.END, values=(
                r.get('record_id'),
                r.get('user_id'),
                r.get('offense_type', '').replace('_', ' ').title(),
                r.get('severity', '').title(),
                r.get('date_occurred', ''),
                r.get('status', 'pending').title(),
                r.get('reported_by', '')
            ), tags=(tag,))

    def _search_disciplinary(self):
        """Search disciplinary records by user."""
        user_id = self.disc_search.get().strip()
        if not user_id:
            self._load_disciplinary_records()
            return

        for item in self.disc_tree.get_children():
            self.disc_tree.delete(item)

        records = GrievanceManager.get_user_disciplinary_records(user_id)

        for r in records:
            self.disc_tree.insert('', tk.END, values=(
                r.get('record_id'),
                r.get('user_id'),
                r.get('offense_type', ''),
                r.get('severity', '').title(),
                r.get('date_occurred', ''),
                r.get('status', 'pending').title(),
                r.get('reported_by', '')
            ))

    def _create_disciplinary_record(self):
        """Create disciplinary record dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.grievance.windows.create_disciplinary_record', default="Create Disciplinary Record"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.employee_user_id', default="Employee User ID:")).grid(row=0, column=0, sticky='e', padx=10, pady=8)
        user_entry = ttk.Entry(frame, width=20)
        user_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.offense_type', default="Offense Type:")).grid(row=1, column=0, sticky='e', padx=10, pady=8)
        offense_combo = ttk.Combobox(frame, values=[
            'misconduct', 'performance', 'attendance', 'policy_violation', 'harassment', 'other'
        ], width=18)
        offense_combo.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.severity', default="Severity:")).grid(row=2, column=0, sticky='e', padx=10, pady=8)
        severity_combo = ttk.Combobox(frame, values=['minor', 'moderate', 'major', 'severe'], width=15)
        severity_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.date_occurred', default="Date Occurred:")).grid(row=3, column=0, sticky='e', padx=10, pady=8)
        date_entry = ttk.Entry(frame, width=15)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.description_variant_2', default="Description:")).grid(row=4, column=0, sticky='ne', padx=10, pady=8)
        desc_text = scrolledtext.ScrolledText(frame, width=40, height=6)
        desc_text.grid(row=4, column=1, padx=10, pady=8)

        def save():
            user_id = user_entry.get().strip()
            if not user_id:
                messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), _t('gui.staff.staff_hr.grievance.dialogs.user_id_is_required', default="User ID is required"))
                return

            try:
                record_id = GrievanceManager.create_disciplinary_record(
                    user_id=user_id,
                    offense_type=offense_combo.get(),
                    severity=severity_combo.get(),
                    description=desc_text.get("1.0", tk.END).strip(),
                    date_occurred=date_entry.get(),
                    reported_by=self._get_user_id()
                )
                messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.success', default="Success"), f"Record created. ID: {record_id}")
                dialog.destroy()
                self._load_disciplinary_records()
            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), str(e))

        ttk.Button(frame, text=_t('gui.staff.staff_hr.grievance.buttons.create_record', default="Create Record"), command=save).grid(row=5, column=0, columnspan=2, pady=20)

    def _add_disciplinary_action(self):
        """Add disciplinary action."""
        selection = self.disc_tree.selection()
        if not selection:
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.info', default="Info"), _t('gui.staff.staff_hr.grievance.dialogs.please_select_a_record', default="Please select a record"))
            return

        item = self.disc_tree.item(selection[0])
        record_id = item['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Action to Record #{record_id}")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.action_type', default="Action Type:")).grid(row=0, column=0, sticky='e', padx=10, pady=8)
        action_combo = ttk.Combobox(frame, values=[
            'verbal_warning', 'written_warning', 'final_warning',
            'suspension', 'demotion', 'termination', 'training_required'
        ], width=18)
        action_combo.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.effective_date', default="Effective Date:")).grid(row=1, column=0, sticky='e', padx=10, pady=8)
        date_entry = ttk.Entry(frame, width=15)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.notes', default="Notes:")).grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        notes_text = scrolledtext.ScrolledText(frame, width=30, height=5)
        notes_text.grid(row=2, column=1, padx=10, pady=8)

        def save():
            try:
                GrievanceManager.create_disciplinary_action(
                    record_id,
                    action_type=action_combo.get(),
                    effective_date=date_entry.get(),
                    imposed_by=self._get_user_id(),
                    notes=notes_text.get("1.0", tk.END).strip()
                )
                messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.success', default="Success"), _t('gui.staff.staff_hr.grievance.dialogs.action_added', default="Action added"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.grievance.dialogs.error', default="Error"), str(e))

        ttk.Button(frame, text=_t('gui.staff.staff_hr.grievance.buttons.add_action', default="Add Action"), command=save).grid(row=3, column=0, columnspan=2, pady=15)

    def _view_disciplinary_details(self):
        """View disciplinary record details."""
        selection = self.disc_tree.selection()
        if not selection:
            messagebox.showinfo(_t('gui.staff.staff_hr.grievance.dialogs.info', default="Info"), _t('gui.staff.staff_hr.grievance.dialogs.please_select_a_record', default="Please select a record"))
            return

        item = self.disc_tree.item(selection[0])
        record_id = item['values'][0]

        record = GrievanceManager.get_disciplinary_record(record_id)
        if not record:
            return

        actions = GrievanceManager.get_disciplinary_actions(record_id)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Disciplinary Record #{record_id}")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        info = f"""Employee: {record.get('user_id')}
Offense: {record.get('offense_type', '').replace('_', ' ').title()}
Severity: {record.get('severity', '').title()}
Date: {record.get('date_occurred')}
Status: {record.get('status', 'pending').title()}
Reported By: {record.get('reported_by')}

Description:
{record.get('description', '')}
"""
        info_text = scrolledtext.ScrolledText(frame, height=10)
        info_text.insert("1.0", info)
        info_text.config(state='disabled')
        info_text.pack(fill=tk.BOTH, expand=True, pady=5)

        if actions:
            ttk.Label(frame, text=_t('gui.staff.staff_hr.grievance.labels.actions_taken', default="Actions Taken:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
            for a in actions:
                ttk.Label(frame, text=f"  - {a.get('action_type')}: {a.get('effective_date')}").pack(anchor='w')

        ttk.Button(frame, text=_t('gui.staff.staff_hr.grievance.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

    def _create_statistics_tab(self):
        """Create statistics tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.grievance.tabs.statistics', default="Statistics"))

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.grievance.labels.statistics_reports', default="Statistics & Reports"), style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.grievance.buttons.refresh', default="Refresh"), command=self._load_statistics).pack(side=tk.RIGHT)

        # Grievance stats
        grv_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.grievance.labels.grievance_statistics', default="Grievance Statistics"), padding=15)
        grv_frame.pack(fill=tk.X, padx=10, pady=10)

        self.grv_stats = {}
        for key, label in [('open', 'Open'), ('investigating', 'Investigating'), ('resolved', 'Resolved')]:
            frame = ttk.Frame(grv_frame)
            frame.pack(side=tk.LEFT, padx=30)
            self.grv_stats[key] = ttk.Label(frame, text="0", font=('Arial', 20, 'bold'))
            self.grv_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # Disciplinary stats
        disc_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.grievance.labels.disciplinary_statistics', default="Disciplinary Statistics"), padding=15)
        disc_frame.pack(fill=tk.X, padx=10, pady=10)

        self.disc_stats = {}
        for key, label in [('total', 'Total Records'), ('pending', 'Pending'), ('appeals', 'Appeals')]:
            frame = ttk.Frame(disc_frame)
            frame.pack(side=tk.LEFT, padx=30)
            self.disc_stats[key] = ttk.Label(frame, text="0", font=('Arial', 20, 'bold'))
            self.disc_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        self._load_statistics()

    def _load_statistics(self):
        """Load statistics."""
        grv_stats = GrievanceManager.get_grievance_statistics()
        self.grv_stats['open'].config(text=str(grv_stats.get('total_open', 0)))
        self.grv_stats['investigating'].config(text=str(grv_stats.get('total_investigating', 0)))
        self.grv_stats['resolved'].config(text=str(grv_stats.get('resolved_this_month', 0)))

        disc_stats = GrievanceManager.get_disciplinary_statistics()
        self.disc_stats['total'].config(text=str(disc_stats.get('total_active', 0)))
        self.disc_stats['pending'].config(text=str(disc_stats.get('actions_this_month', 0)))
        self.disc_stats['appeals'].config(text=str(disc_stats.get('pending_appeals', 0)))
