"""
Intellectual Property Management GUI

Provides interface for:
- IP disclosure management
- Patent tracking
- License management
- Revenue reporting
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.staff.staff_hr.services.managers.ip_manager import IPManager
from education_system.systems.university.interfaces.gui.staff.staff_hr.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)


class IPGUI:
    """GUI for intellectual property management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access IP Management")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="IP")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Intellectual Property Management")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_ip_tab()
        self._create_new_disclosure_tab()
        self._create_patents_tab()
        self._create_licenses_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_reports_tab()

    # ==================== TAB 1: MY IP ====================

    def _create_my_ip_tab(self):
        """Create the My IP disclosures and patents tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My IP")

        # Header with filter
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Disclosures & Patents", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.ip_status_filter = ttk.Combobox(
            filter_frame,
            values=['All', 'Draft', 'Submitted', 'Approved', 'Rejected'],
            width=12, state='readonly'
        )
        self.ip_status_filter.set('All')
        self.ip_status_filter.pack(side=tk.LEFT, padx=5)
        self.ip_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_my_disclosures())
        ttk.Button(filter_frame, text="Refresh", command=self._load_my_disclosures).pack(side=tk.LEFT, padx=10)

        # Disclosures treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Type', 'Stage', 'Status', 'Created')
        self.ip_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                     yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.ip_tree.yview)

        widths = {'ID': 50, 'Title': 250, 'Type': 120, 'Stage': 120, 'Status': 100, 'Created': 140}
        for col in columns:
            self.ip_tree.heading(col, text=col)
            self.ip_tree.column(col, width=widths.get(col, 100))

        self.ip_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.ip_tree.tag_configure('draft', background='#e2e3e5')
        self.ip_tree.tag_configure('submitted', background='#fff3cd')
        self.ip_tree.tag_configure('approved', background='#d4edda')
        self.ip_tree.tag_configure('rejected', background='#f8d7da')

        # Double-click to view details
        self.ip_tree.bind('<Double-1>', self._view_disclosure_details)

        self._load_my_disclosures()

    def _load_my_disclosures(self):
        """Load the current user's IP disclosures."""
        for item in self.ip_tree.get_children():
            self.ip_tree.delete(item)

        status_filter = self.ip_status_filter.get().lower()
        if status_filter == 'all':
            status = None
        else:
            status = status_filter

        try:
            disclosures = IPManager.get_user_disclosures(self._get_user_id(), status=status)

            for d in disclosures:
                d_status = d.get('status', '').lower()
                display_status = d_status.replace('_', ' ').title()
                ip_type = d.get('ip_type', '').replace('_', ' ').title()
                stage = d.get('development_stage', '').replace('_', ' ').title()
                created = d.get('created_at', '')
                if created and len(created) > 16:
                    created = created[:16]

                self.ip_tree.insert('', tk.END, values=(
                    d.get('disclosure_id'),
                    d.get('title', ''),
                    ip_type,
                    stage,
                    display_status,
                    created
                ), tags=(d_status,))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load disclosures: {e}")

    def _view_disclosure_details(self, event):
        """View disclosure details in a popup dialog."""
        selection = self.ip_tree.selection()
        if not selection:
            return

        item = self.ip_tree.item(selection[0])
        disclosure_id = item['values'][0]

        try:
            disclosure = IPManager.get_disclosure(disclosure_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load disclosure details: {e}")
            return

        if not disclosure:
            messagebox.showerror("Error", "Disclosure not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"IP Disclosure #{disclosure_id}")
        dialog.geometry("700x600")
        dialog.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Disclosure details
        details_frame = ttk.LabelFrame(scroll_frame, text="Disclosure Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Disclosure ID', disclosure.get('disclosure_id')),
            ('Title', disclosure.get('title', '')),
            ('Type', disclosure.get('ip_type', '').replace('_', ' ').title()),
            ('Status', disclosure.get('status', '').replace('_', ' ').title()),
            ('Development Stage', disclosure.get('development_stage', '').replace('_', ' ').title()),
            ('Funding Source', disclosure.get('funding_source', '') or 'N/A'),
            ('Department', disclosure.get('department', '') or 'N/A'),
            ('Created By', disclosure.get('created_by', '')),
            ('Created', disclosure.get('created_at', '')),
            ('Updated', disclosure.get('updated_at', '')),
            ('Submitted Date', disclosure.get('submitted_date', '') or 'N/A'),
            ('Reviewed By', disclosure.get('reviewed_by', '') or 'N/A'),
            ('Review Date', disclosure.get('review_date', '') or 'N/A'),
            ('Review Comments', disclosure.get('review_comments', '') or 'N/A'),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Description
        description = disclosure.get('description', '')
        if description:
            desc_frame = ttk.LabelFrame(scroll_frame, text="Description", padding=10)
            desc_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(desc_frame, text=description, wraplength=600).pack(anchor='w')

        # Inventors list
        try:
            inventors = IPManager.get_inventors(disclosure_id=disclosure_id)
        except Exception:
            inventors = []

        inventors_frame = ttk.LabelFrame(scroll_frame, text="Inventors", padding=10)
        inventors_frame.pack(fill=tk.X, padx=10, pady=5)

        if inventors:
            inv_cols = ('Inventor ID', 'User ID', 'Contribution %', 'Primary')
            inv_tree = ttk.Treeview(inventors_frame, columns=inv_cols, show='headings', height=5)
            inv_widths = {'Inventor ID': 80, 'User ID': 150, 'Contribution %': 120, 'Primary': 80}
            for col in inv_cols:
                inv_tree.heading(col, text=col)
                inv_tree.column(col, width=inv_widths.get(col, 100))

            for inv in inventors:
                inv_tree.insert('', tk.END, values=(
                    inv.get('inventor_id'),
                    inv.get('user_id', ''),
                    f"{inv.get('contribution_percentage', 0)}%",
                    'Yes' if inv.get('is_primary') else 'No'
                ))
            inv_tree.pack(fill=tk.X)
        else:
            ttk.Label(inventors_frame, text="No inventors recorded.").pack(anchor='w')

        # Close button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 2: NEW DISCLOSURE ====================

    def _create_new_disclosure_tab(self):
        """Create the new IP disclosure tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="New Disclosure")

        # Scrollable area
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Header
        header_frame = ttk.Frame(scroll_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="New IP Disclosure", style='Header.TLabel').pack(side=tk.LEFT)

        # Disclosure details form
        form_frame = ttk.LabelFrame(scroll_frame, text="Disclosure Details", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 0: Title
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.disc_title_entry = ttk.Entry(form_frame, width=50)
        self.disc_title_entry.grid(row=0, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 1: Type
        ttk.Label(form_frame, text="Type:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.disc_type_combo = ttk.Combobox(form_frame, width=25, state='readonly',
            values=['invention', 'software', 'design', 'creative_work'])
        self.disc_type_combo.set('invention')
        self.disc_type_combo.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Row 2: Description
        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        self.disc_description_text = tk.Text(form_frame, width=60, height=6)
        self.disc_description_text.grid(row=2, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 3: Development Stage
        ttk.Label(form_frame, text="Development Stage:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.disc_stage_combo = ttk.Combobox(form_frame, width=25, state='readonly',
            values=['concept', 'prototype', 'developed', 'commercial'])
        self.disc_stage_combo.set('concept')
        self.disc_stage_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Row 4: Funding Source
        ttk.Label(form_frame, text="Funding Source:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        self.disc_funding_entry = ttk.Entry(form_frame, width=50)
        self.disc_funding_entry.grid(row=4, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Co-Inventors section
        coinv_frame = ttk.LabelFrame(scroll_frame, text="Co-Inventors", padding=15)
        coinv_frame.pack(fill=tk.X, padx=10, pady=10)

        # Co-inventor input row
        input_row = ttk.Frame(coinv_frame)
        input_row.pack(fill=tk.X, pady=5)

        ttk.Label(input_row, text="User ID:").pack(side=tk.LEFT, padx=5)
        self.coinv_user_entry = ttk.Entry(input_row, width=20)
        self.coinv_user_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(input_row, text="Contribution %:").pack(side=tk.LEFT, padx=5)
        self.coinv_pct_entry = ttk.Entry(input_row, width=8)
        self.coinv_pct_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(input_row, text="Add", command=self._add_coinventor).pack(side=tk.LEFT, padx=10)

        # Co-inventors treeview
        coinv_tree_frame = ttk.Frame(coinv_frame)
        coinv_tree_frame.pack(fill=tk.X, pady=5)

        coinv_cols = ('User ID', 'Contribution %')
        self.coinv_tree = ttk.Treeview(coinv_tree_frame, columns=coinv_cols, show='headings', height=4)
        self.coinv_tree.heading('User ID', text='User ID')
        self.coinv_tree.heading('Contribution %', text='Contribution %')
        self.coinv_tree.column('User ID', width=250)
        self.coinv_tree.column('Contribution %', width=150)
        self.coinv_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

        coinv_btn_frame = ttk.Frame(coinv_frame)
        coinv_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(coinv_btn_frame, text="Remove Selected",
                   command=self._remove_coinventor).pack(side=tk.LEFT, padx=5)

        # Submit buttons
        submit_frame = ttk.Frame(scroll_frame)
        submit_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(submit_frame, text="Save Draft", command=self._save_disclosure_draft).pack(side=tk.LEFT, padx=5)
        ttk.Button(submit_frame, text="Submit", command=self._submit_disclosure).pack(side=tk.LEFT, padx=5)

    def _add_coinventor(self):
        """Add a co-inventor to the treeview."""
        user_id = self.coinv_user_entry.get().strip()
        pct_str = self.coinv_pct_entry.get().strip()

        if not user_id:
            messagebox.showerror("Validation Error", "User ID is required.")
            return

        if not pct_str:
            messagebox.showerror("Validation Error", "Contribution percentage is required.")
            return

        try:
            pct = float(pct_str)
            if pct < 0 or pct > 100:
                messagebox.showerror("Validation Error", "Contribution percentage must be between 0 and 100.")
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Contribution percentage must be a valid number.")
            return

        # Check for duplicate user IDs
        for child in self.coinv_tree.get_children():
            values = self.coinv_tree.item(child)['values']
            if str(values[0]) == user_id:
                messagebox.showerror("Validation Error", f"User '{user_id}' is already added as a co-inventor.")
                return

        self.coinv_tree.insert('', tk.END, values=(user_id, f"{pct}%"))

        # Clear input fields
        self.coinv_user_entry.delete(0, tk.END)
        self.coinv_pct_entry.delete(0, tk.END)

    def _remove_coinventor(self):
        """Remove the selected co-inventor from the treeview."""
        selection = self.coinv_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a co-inventor to remove")
            return

        self.coinv_tree.delete(selection[0])

    def _get_coinventors(self):
        """Get co-inventors as a list of (user_id, contribution_pct) tuples."""
        coinventors = []
        for child in self.coinv_tree.get_children():
            values = self.coinv_tree.item(child)['values']
            user_id = str(values[0])
            pct_str = str(values[1]).replace('%', '')
            try:
                pct = float(pct_str)
            except ValueError:
                pct = 0
            coinventors.append((user_id, pct))
        return coinventors

    def _get_disclosure_form_data(self):
        """Gather disclosure form data with validation."""
        try:
            title = validate_entry(self.disc_title_entry, "Title")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        try:
            ip_type = validate_combobox(self.disc_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        try:
            stage = validate_combobox(self.disc_stage_combo, "Development Stage")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        description = self.disc_description_text.get("1.0", "end-1c").strip() or None
        funding_source = self.disc_funding_entry.get().strip() or None
        department = self.current_user.get('department')

        return {
            'title': title,
            'ip_type': ip_type,
            'description': description,
            'development_stage': stage,
            'funding_source': funding_source,
            'department': department,
        }

    def _save_disclosure_draft(self):
        """Save the disclosure as a draft."""
        data = self._get_disclosure_form_data()
        if not data:
            return

        try:
            disclosure_id = IPManager.create_disclosure(
                title=data['title'],
                created_by=self._get_user_id(),
                ip_type=data['ip_type'],
                description=data['description'],
                development_stage=data['development_stage'],
                funding_source=data['funding_source'],
                department=data['department'],
            )

            # Add co-inventors
            coinventors = self._get_coinventors()
            for user_id, pct in coinventors:
                IPManager.add_inventor(
                    disclosure_id=disclosure_id,
                    user_id=user_id,
                    contribution_percentage=pct,
                )

            messagebox.showinfo("Success", f"Draft saved successfully. Disclosure ID: {disclosure_id}")
            self._clear_disclosure_form()
            self._load_my_disclosures()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _submit_disclosure(self):
        """Save and submit the disclosure for review."""
        data = self._get_disclosure_form_data()
        if not data:
            return

        if not messagebox.askyesno("Confirm",
                "Are you sure you want to submit this disclosure for review?\n\n"
                "Once submitted, the disclosure cannot be edited."):
            return

        try:
            disclosure_id = IPManager.create_disclosure(
                title=data['title'],
                created_by=self._get_user_id(),
                ip_type=data['ip_type'],
                description=data['description'],
                development_stage=data['development_stage'],
                funding_source=data['funding_source'],
                department=data['department'],
            )

            # Add co-inventors
            coinventors = self._get_coinventors()
            for user_id, pct in coinventors:
                IPManager.add_inventor(
                    disclosure_id=disclosure_id,
                    user_id=user_id,
                    contribution_percentage=pct,
                )

            IPManager.submit_disclosure(disclosure_id)
            messagebox.showinfo("Success",
                f"Disclosure submitted successfully. Disclosure ID: {disclosure_id}\n\n"
                "Your disclosure will be reviewed.")
            self._clear_disclosure_form()
            self._load_my_disclosures()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _clear_disclosure_form(self):
        """Clear the disclosure form fields."""
        self.disc_title_entry.delete(0, tk.END)
        self.disc_type_combo.set('invention')
        self.disc_description_text.delete("1.0", tk.END)
        self.disc_stage_combo.set('concept')
        self.disc_funding_entry.delete(0, tk.END)
        self.coinv_user_entry.delete(0, tk.END)
        self.coinv_pct_entry.delete(0, tk.END)
        for child in self.coinv_tree.get_children():
            self.coinv_tree.delete(child)

    # ==================== TAB 3: PATENTS ====================

    def _create_patents_tab(self):
        """Create the patent tracking tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Patents")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Patent Tracking", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_patents).pack(side=tk.RIGHT, padx=5)

        # Patents treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Patent #', 'Office', 'Filing Date', 'Status')
        self.patents_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                          yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.patents_tree.yview)

        widths = {'ID': 50, 'Title': 250, 'Patent #': 140, 'Office': 100,
                  'Filing Date': 120, 'Status': 100}
        for col in columns:
            self.patents_tree.heading(col, text=col)
            self.patents_tree.column(col, width=widths.get(col, 100))

        self.patents_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.patents_tree.tag_configure('pending', background='#fff3cd')
        self.patents_tree.tag_configure('filed', background='#cce5ff')
        self.patents_tree.tag_configure('published', background='#ffeeba')
        self.patents_tree.tag_configure('granted', background='#d4edda')

        # Double-click to view details
        self.patents_tree.bind('<Double-1>', self._view_patent_details)

        # Admin: Update Status button
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            btn_frame = ttk.Frame(tab)
            btn_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Button(btn_frame, text="Update Status",
                       command=self._update_patent_status).pack(side=tk.LEFT, padx=5)

        self._load_patents()

    def _load_patents(self):
        """Load all patents."""
        for item in self.patents_tree.get_children():
            self.patents_tree.delete(item)

        try:
            patents = IPManager.get_patents()

            for p in patents:
                p_status = p.get('status', '').lower()
                display_status = p_status.replace('_', ' ').title()

                self.patents_tree.insert('', tk.END, values=(
                    p.get('patent_id'),
                    p.get('title', ''),
                    p.get('patent_number', '') or 'N/A',
                    p.get('patent_office', ''),
                    p.get('filing_date', '') or 'N/A',
                    display_status
                ), tags=(p_status,))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load patents: {e}")

    def _view_patent_details(self, event):
        """View patent details in a popup dialog."""
        selection = self.patents_tree.selection()
        if not selection:
            return

        item = self.patents_tree.item(selection[0])
        patent_id = item['values'][0]

        try:
            patent = IPManager.get_patent(patent_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load patent details: {e}")
            return

        if not patent:
            messagebox.showerror("Error", "Patent not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Patent #{patent_id}")
        dialog.geometry("700x600")
        dialog.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Patent details
        details_frame = ttk.LabelFrame(scroll_frame, text="Patent Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Patent ID', patent.get('patent_id')),
            ('Title', patent.get('title', '')),
            ('Patent Number', patent.get('patent_number', '') or 'N/A'),
            ('Patent Office', patent.get('patent_office', '')),
            ('Status', patent.get('status', '').replace('_', ' ').title()),
            ('Disclosure ID', patent.get('disclosure_id', '') or 'N/A'),
            ('Filing Date', patent.get('filing_date', '') or 'N/A'),
            ('Publication Date', patent.get('publication_date', '') or 'N/A'),
            ('Grant Date', patent.get('grant_date', '') or 'N/A'),
            ('Expiry Date', patent.get('expiry_date', '') or 'N/A'),
            ('Created', patent.get('created_at', '')),
            ('Updated', patent.get('updated_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Cost tracking
        cost_frame = ttk.LabelFrame(scroll_frame, text="Cost Tracking", padding=15)
        cost_frame.pack(fill=tk.X, padx=10, pady=5)

        cost_to_date = patent.get('cost_to_date', 0) or 0
        ttk.Label(cost_frame, text="Cost to Date:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='e', padx=(10, 5), pady=4)
        ttk.Label(cost_frame, text=f"£{float(cost_to_date):,.2f}").grid(
            row=0, column=1, sticky='w', padx=(5, 10), pady=4)

        notes = patent.get('notes', '')
        if notes:
            ttk.Label(cost_frame, text="Notes:", font=('Arial', 10, 'bold')).grid(
                row=1, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(cost_frame, text=notes, wraplength=400).grid(
                row=1, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Inventors
        try:
            inventors = IPManager.get_inventors(patent_id=patent_id)
        except Exception:
            inventors = []

        if inventors:
            inv_frame = ttk.LabelFrame(scroll_frame, text="Inventors", padding=10)
            inv_frame.pack(fill=tk.X, padx=10, pady=5)

            inv_cols = ('Inventor ID', 'User ID', 'Contribution %', 'Primary')
            inv_tree = ttk.Treeview(inv_frame, columns=inv_cols, show='headings', height=5)
            inv_widths = {'Inventor ID': 80, 'User ID': 150, 'Contribution %': 120, 'Primary': 80}
            for col in inv_cols:
                inv_tree.heading(col, text=col)
                inv_tree.column(col, width=inv_widths.get(col, 100))

            for inv in inventors:
                inv_tree.insert('', tk.END, values=(
                    inv.get('inventor_id'),
                    inv.get('user_id', ''),
                    f"{inv.get('contribution_percentage', 0)}%",
                    'Yes' if inv.get('is_primary') else 'No'
                ))
            inv_tree.pack(fill=tk.X)

        # Close button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _update_patent_status(self):
        """Update the status of the selected patent (admin only)."""
        selection = self.patents_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a patent to update")
            return

        item = self.patents_tree.item(selection[0])
        patent_id = item['values'][0]
        current_status = item['values'][5]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Update Patent #{patent_id} Status")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Current Status: {current_status}",
                  font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        ttk.Label(frame, text="New Status:").pack(anchor='w', padx=10)
        status_combo = ttk.Combobox(frame, width=20, state='readonly',
            values=['pending', 'filed', 'published', 'granted'])
        status_combo.pack(padx=10, pady=5, anchor='w')

        def save():
            new_status = status_combo.get().strip()
            if not new_status:
                messagebox.showerror("Validation Error", "Please select a new status.", parent=dialog)
                return

            try:
                IPManager.update_patent(patent_id, status=new_status)
                messagebox.showinfo("Success", f"Patent #{patent_id} status updated to '{new_status}'.",
                                    parent=dialog)
                dialog.destroy()
                self._load_patents()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=15)
        ttk.Button(btn_frame, text="Update", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ==================== TAB 4: LICENSES ====================

    def _create_licenses_tab(self):
        """Create the license management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Licenses")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="License Management", style='Header.TLabel').pack(side=tk.LEFT)

        btn_container = ttk.Frame(header_frame)
        btn_container.pack(side=tk.RIGHT)
        ttk.Button(btn_container, text="Record Revenue",
                   command=self._record_revenue_dialog).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_container, text="Add License",
                   command=self._add_license_dialog).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_container, text="Refresh",
                   command=self._load_licenses).pack(side=tk.RIGHT, padx=5)

        # Licenses treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Licensee', 'Type', 'Royalty Rate', 'Territory', 'Status')
        self.licenses_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                           yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.licenses_tree.yview)

        widths = {'ID': 50, 'Licensee': 200, 'Type': 120, 'Royalty Rate': 100,
                  'Territory': 130, 'Status': 100}
        for col in columns:
            self.licenses_tree.heading(col, text=col)
            self.licenses_tree.column(col, width=widths.get(col, 100))

        self.licenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.licenses_tree.tag_configure('active', background='#d4edda')
        self.licenses_tree.tag_configure('expired', background='#e2e3e5')
        self.licenses_tree.tag_configure('terminated', background='#f8d7da')

        self._load_licenses()

    def _load_licenses(self):
        """Load all licenses."""
        for item in self.licenses_tree.get_children():
            self.licenses_tree.delete(item)

        try:
            licenses = IPManager.get_licenses()

            for lic in licenses:
                lic_status = lic.get('status', '').lower()
                display_status = lic_status.replace('_', ' ').title()
                lic_type = lic.get('license_type', '').replace('_', ' ').title()
                royalty = lic.get('royalty_rate', 0) or 0

                self.licenses_tree.insert('', tk.END, values=(
                    lic.get('license_id'),
                    lic.get('licensee_name', ''),
                    lic_type,
                    f"{float(royalty):.1f}%",
                    lic.get('territory', ''),
                    display_status
                ), tags=(lic_status,))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load licenses: {e}")

    def _get_patent_options(self):
        """Get patent choices for selector comboboxes. Returns (display_values, id_map)."""
        patent_map = {}
        display_values = []
        try:
            patents = IPManager.get_patents()
            for p in patents:
                display = f"#{p['patent_id']} - {p.get('title', 'Untitled')}"
                display_values.append(display)
                patent_map[display] = p['patent_id']
        except Exception:
            pass
        return display_values, patent_map

    def _get_license_options(self):
        """Get license choices for selector comboboxes. Returns (display_values, id_map)."""
        license_map = {}
        display_values = []
        try:
            licenses = IPManager.get_licenses()
            for lic in licenses:
                display = (f"#{lic['license_id']} - {lic.get('licensee_name', 'Unknown')} "
                           f"({lic.get('license_type', '').replace('_', ' ').title()})")
                display_values.append(display)
                license_map[display] = lic['license_id']
        except Exception:
            pass
        return display_values, license_map

    def _add_license_dialog(self):
        """Open the Add License dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add License Agreement")
        dialog.geometry("500x520")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable form
        canvas = tk.Canvas(dialog)
        scroll = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        form_outer = ttk.Frame(canvas)

        form_outer.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=form_outer, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        frame = ttk.Frame(form_outer, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Patent selector
        ttk.Label(frame, text="Patent:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        patent_display_values, patent_id_map = self._get_patent_options()
        patent_combo = ttk.Combobox(frame, width=35, state='readonly', values=patent_display_values)
        patent_combo.grid(row=0, column=1, padx=10, pady=8)
        if patent_display_values:
            patent_combo.set(patent_display_values[0])

        # Licensee Name
        ttk.Label(frame, text="Licensee Name:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        licensee_entry = ttk.Entry(frame, width=35)
        licensee_entry.grid(row=1, column=1, padx=10, pady=8)

        # Type
        ttk.Label(frame, text="License Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(frame, width=20, state='readonly',
            values=['exclusive', 'non_exclusive'])
        type_combo.set('non_exclusive')
        type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Royalty Rate
        ttk.Label(frame, text="Royalty Rate (%):").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        royalty_entry = ttk.Entry(frame, width=15)
        royalty_entry.insert(0, "0")
        royalty_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Territory
        ttk.Label(frame, text="Territory:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        territory_entry = ttk.Entry(frame, width=35)
        territory_entry.insert(0, "worldwide")
        territory_entry.grid(row=4, column=1, padx=10, pady=8)

        # Start Date
        ttk.Label(frame, text="Start Date:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        start_entry = ttk.Entry(frame, width=15)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Annual Fee
        ttk.Label(frame, text="Annual Fee ($):").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        fee_entry = ttk.Entry(frame, width=15)
        fee_entry.insert(0, "0.00")
        fee_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        def save():
            # Validate required fields
            try:
                licensee = validate_entry(licensee_entry, "Licensee Name")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                lic_type = validate_combobox(type_combo, "License Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                start_date = validate_date_entry(start_entry, "Start Date")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Royalty rate
            royalty_str = royalty_entry.get().strip()
            try:
                royalty_rate = float(royalty_str)
                if royalty_rate < 0 or royalty_rate > 100:
                    messagebox.showerror("Validation Error",
                                         "Royalty rate must be between 0 and 100.", parent=dialog)
                    return
            except ValueError:
                messagebox.showerror("Validation Error",
                                     "Royalty rate must be a valid number.", parent=dialog)
                return

            # Annual fee
            try:
                annual_fee = validate_currency_entry(fee_entry, "Annual Fee", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            territory = territory_entry.get().strip() or 'worldwide'

            # Patent ID (optional)
            patent_id = None
            patent_selection = patent_combo.get()
            if patent_selection and patent_selection in patent_id_map:
                patent_id = patent_id_map[patent_selection]

            try:
                license_id = IPManager.create_license(
                    licensee_name=licensee,
                    start_date=start_date,
                    patent_id=patent_id,
                    license_type=lic_type,
                    royalty_rate=royalty_rate,
                    territory=territory,
                    annual_fee=annual_fee,
                )
                messagebox.showinfo("Success",
                                    f"License agreement created. License ID: {license_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_licenses()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        licensee_entry.focus_set()

    def _record_revenue_dialog(self):
        """Open the Record Revenue dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record License Revenue")
        dialog.geometry("500x420")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # License selector
        ttk.Label(frame, text="License:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        license_display_values, license_id_map = self._get_license_options()
        license_combo = ttk.Combobox(frame, width=40, state='readonly', values=license_display_values)
        license_combo.grid(row=0, column=1, padx=10, pady=8)
        if license_display_values:
            license_combo.set(license_display_values[0])

        # Period
        ttk.Label(frame, text="Period:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        period_entry = ttk.Entry(frame, width=20)
        period_entry.insert(0, datetime.now().strftime('%Y-Q1'))
        period_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')
        ttk.Label(frame, text="(e.g. 2026-Q1, 2026-H1, 2026)",
                  font=('Arial', 8)).grid(row=2, column=1, padx=10, sticky='w')

        # Total Revenue
        ttk.Label(frame, text="Total Revenue ($):").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        revenue_entry = ttk.Entry(frame, width=15)
        revenue_entry.insert(0, "0.00")
        revenue_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Revenue splits
        splits_frame = ttk.LabelFrame(frame, text="Revenue Splits ($)", padding=10)
        splits_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky='ew')

        ttk.Label(splits_frame, text="University Share:").grid(row=0, column=0, sticky='e', padx=10, pady=5)
        uni_share_entry = ttk.Entry(splits_frame, width=15)
        uni_share_entry.insert(0, "0.00")
        uni_share_entry.grid(row=0, column=1, padx=10, pady=5, sticky='w')

        ttk.Label(splits_frame, text="Inventor Share:").grid(row=1, column=0, sticky='e', padx=10, pady=5)
        inv_share_entry = ttk.Entry(splits_frame, width=15)
        inv_share_entry.insert(0, "0.00")
        inv_share_entry.grid(row=1, column=1, padx=10, pady=5, sticky='w')

        ttk.Label(splits_frame, text="Department Share:").grid(row=2, column=0, sticky='e', padx=10, pady=5)
        dept_share_entry = ttk.Entry(splits_frame, width=15)
        dept_share_entry.insert(0, "0.00")
        dept_share_entry.grid(row=2, column=1, padx=10, pady=5, sticky='w')

        def save():
            # Validate license selection
            license_selection = license_combo.get()
            if not license_selection or license_selection not in license_id_map:
                messagebox.showerror("Validation Error", "Please select a license.", parent=dialog)
                return

            license_id = license_id_map[license_selection]

            # Period
            period = period_entry.get().strip()
            if not period:
                messagebox.showerror("Validation Error", "Period is required.", parent=dialog)
                return

            # Total revenue
            try:
                total_revenue = validate_currency_entry(revenue_entry, "Total Revenue", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Shares
            try:
                uni_share = validate_currency_entry(uni_share_entry, "University Share", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                inv_share = validate_currency_entry(inv_share_entry, "Inventor Share", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                dept_share = validate_currency_entry(dept_share_entry, "Department Share", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                revenue_id = IPManager.record_revenue(
                    license_id=license_id,
                    period=period,
                    total_revenue=total_revenue,
                    university_share=uni_share,
                    inventor_share=inv_share,
                    department_share=dept_share,
                )
                messagebox.showinfo("Success",
                                    f"Revenue recorded successfully. Revenue ID: {revenue_id}",
                                    parent=dialog)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Record", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ==================== TAB 5: REPORTS (ADMIN) ====================

    def _create_reports_tab(self):
        """Create the IP portfolio reports tab (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="IP Portfolio Reports", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_portfolio_stats).pack(side=tk.RIGHT)

        # Portfolio summary statistics
        stats_frame = ttk.LabelFrame(tab, text="Portfolio Summary", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.portfolio_stats = {}
        for key, label in [('total_disclosures', 'Total Disclosures'),
                           ('active_patents', 'Active Patents'),
                           ('total_revenue', 'Total Revenue'),
                           ('active_licenses', 'Active Licenses')]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=30, pady=10)
            self.portfolio_stats[key] = ttk.Label(frame, text="0", font=('Arial', 18, 'bold'))
            self.portfolio_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # Disclosures by status breakdown
        disc_frame = ttk.LabelFrame(tab, text="Disclosures by Status", padding=10)
        disc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        disc_cols = ('Status', 'Count')
        self.disc_status_tree = ttk.Treeview(disc_frame, columns=disc_cols, show='headings', height=5)
        self.disc_status_tree.heading('Status', text='Status')
        self.disc_status_tree.heading('Count', text='Count')
        self.disc_status_tree.column('Status', width=250)
        self.disc_status_tree.column('Count', width=150)
        self.disc_status_tree.pack(fill=tk.BOTH, expand=True)

        self.disc_status_tree.tag_configure('draft', background='#e2e3e5')
        self.disc_status_tree.tag_configure('submitted', background='#fff3cd')
        self.disc_status_tree.tag_configure('approved', background='#d4edda')
        self.disc_status_tree.tag_configure('rejected', background='#f8d7da')

        # Patents by status breakdown
        pat_frame = ttk.LabelFrame(tab, text="Patents by Status", padding=10)
        pat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        pat_cols = ('Status', 'Count')
        self.pat_status_tree = ttk.Treeview(pat_frame, columns=pat_cols, show='headings', height=5)
        self.pat_status_tree.heading('Status', text='Status')
        self.pat_status_tree.heading('Count', text='Count')
        self.pat_status_tree.column('Status', width=250)
        self.pat_status_tree.column('Count', width=150)
        self.pat_status_tree.pack(fill=tk.BOTH, expand=True)

        self.pat_status_tree.tag_configure('pending', background='#fff3cd')
        self.pat_status_tree.tag_configure('filed', background='#cce5ff')
        self.pat_status_tree.tag_configure('published', background='#ffeeba')
        self.pat_status_tree.tag_configure('granted', background='#d4edda')

        self._load_portfolio_stats()

    def _load_portfolio_stats(self):
        """Load IP portfolio summary statistics."""
        try:
            summary = IPManager.get_portfolio_summary()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load portfolio statistics: {e}")
            return

        # Total disclosures
        disclosures_by_status = summary.get('disclosures_by_status', {})
        total_disclosures = sum(disclosures_by_status.values())
        self.portfolio_stats['total_disclosures'].config(text=str(total_disclosures))

        # Active patents (filed + published + granted)
        patents_by_status = summary.get('patents_by_status', {})
        active_patents = sum(
            count for status, count in patents_by_status.items()
            if status in ('filed', 'published', 'granted')
        )
        self.portfolio_stats['active_patents'].config(text=str(active_patents))

        # Total revenue
        total_revenue = summary.get('total_revenue', 0)
        self.portfolio_stats['total_revenue'].config(text=f"£{float(total_revenue):,.2f}")

        # Active licenses
        active_licenses = summary.get('active_licenses', 0)
        self.portfolio_stats['active_licenses'].config(text=str(active_licenses))

        # Disclosures by status breakdown
        for item in self.disc_status_tree.get_children():
            self.disc_status_tree.delete(item)

        for status, count in disclosures_by_status.items():
            display_status = status.replace('_', ' ').title()
            self.disc_status_tree.insert('', tk.END, values=(
                display_status, count
            ), tags=(status.lower(),))

        # Patents by status breakdown
        for item in self.pat_status_tree.get_children():
            self.pat_status_tree.delete(item)

        for status, count in patents_by_status.items():
            display_status = status.replace('_', ' ').title()
            self.pat_status_tree.insert('', tk.END, values=(
                display_status, count
            ), tags=(status.lower(),))
