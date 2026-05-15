"""
Travel & Conference Management GUI

Provides interface for:
- Travel request management
- Conference registration
- Approval workflows
- Expense claim linking
- Travel reports
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.travel_manager import TravelManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)


class TravelGUI:
    """GUI for travel and conference management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Travel Management")
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
        notebook.add(self.tab_frame, text="Travel")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Travel & Conference Management")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_trips_tab()
        self._create_new_request_tab()
        self._create_conferences_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_approvals_tab()
            self._create_expenses_tab()
            self._create_reports_tab()

    # ==================== TAB 1: MY TRIPS ====================

    def _create_my_trips_tab(self):
        """Create my trips tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Trips")

        # Header with filter
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Travel Requests", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.trips_status_filter = ttk.Combobox(
            filter_frame,
            values=['All', 'Draft', 'Pending', 'Approved', 'Rejected', 'Completed', 'Cancelled'],
            width=12, state='readonly'
        )
        self.trips_status_filter.set('All')
        self.trips_status_filter.pack(side=tk.LEFT, padx=5)
        self.trips_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_my_trips())
        ttk.Button(filter_frame, text="Refresh", command=self._load_my_trips).pack(side=tk.LEFT, padx=10)

        # Trips treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Purpose', 'Destination', 'Departure', 'Return', 'Budget', 'Status')
        self.trips_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.trips_tree.yview)

        widths = {'ID': 50, 'Purpose': 200, 'Destination': 150, 'Departure': 100, 'Return': 100, 'Budget': 100, 'Status': 100}
        for col in columns:
            self.trips_tree.heading(col, text=col)
            self.trips_tree.column(col, width=widths.get(col, 100))

        self.trips_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.trips_tree.tag_configure('draft', background='#e2e3e5')
        self.trips_tree.tag_configure('pending_approval', background='#fff3cd')
        self.trips_tree.tag_configure('approved', background='#d4edda')
        self.trips_tree.tag_configure('rejected', background='#f8d7da')
        self.trips_tree.tag_configure('completed', background='#cce5ff')
        self.trips_tree.tag_configure('cancelled', background='#f5c6cb')

        # Double-click to view details
        self.trips_tree.bind('<Double-1>', self._view_trip_details)

        self._load_my_trips()

    def _load_my_trips(self):
        """Load user's travel requests."""
        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)

        status_filter = self.trips_status_filter.get().lower()
        if status_filter == 'all':
            status = None
        elif status_filter == 'pending':
            status = 'pending_approval'
        else:
            status = status_filter

        try:
            requests = TravelManager.get_user_requests(self._get_user_id(), status=status)
        except Exception:
            requests = []

        for r in requests:
            req_status = r.get('status', '').lower()
            display_status = req_status.replace('_', ' ').title()
            self.trips_tree.insert('', tk.END, values=(
                r.get('request_id'),
                r.get('purpose', '')[:40],
                r.get('destination', ''),
                r.get('departure_date', ''),
                r.get('return_date', ''),
                f"£{r.get('estimated_budget', 0):.2f}",
                display_status
            ), tags=(req_status,))

    def _view_trip_details(self, event):
        """View trip details in a popup dialog."""
        selection = self.trips_tree.selection()
        if not selection:
            return

        item = self.trips_tree.item(selection[0])
        request_id = item['values'][0]

        try:
            request = TravelManager.get_request(request_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load trip details: {e}")
            return

        if not request:
            messagebox.showerror("Error", "Travel request not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Travel Request #{request_id}")
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

        # Request details
        details_frame = ttk.LabelFrame(scroll_frame, text="Request Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Request ID', request.get('request_id')),
            ('Status', request.get('status', '').replace('_', ' ').title()),
            ('Purpose', request.get('purpose', '')),
            ('Destination', request.get('destination', '')),
            ('Departure Date', request.get('departure_date', '')),
            ('Return Date', request.get('return_date', '')),
            ('Estimated Budget', f"£{request.get('estimated_budget', 0):.2f}"),
            ('Funding Source', request.get('funding_source', '').title()),
            ('Department', request.get('department', 'N/A')),
            ('Created', request.get('created_at', '')),
            ('Last Updated', request.get('updated_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Justification
        justification = request.get('justification', '')
        if justification:
            just_frame = ttk.LabelFrame(scroll_frame, text="Justification", padding=10)
            just_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(just_frame, text=justification, wraplength=600).pack(anchor='w')

        # Budget breakdown
        breakdown_json = request.get('budget_breakdown_json')
        if breakdown_json:
            try:
                breakdown = json.loads(breakdown_json)
            except (json.JSONDecodeError, TypeError):
                breakdown = []

            if breakdown:
                budget_frame = ttk.LabelFrame(scroll_frame, text="Budget Breakdown", padding=10)
                budget_frame.pack(fill=tk.X, padx=10, pady=5)

                budget_cols = ('Item', 'Amount')
                budget_tree = ttk.Treeview(budget_frame, columns=budget_cols, show='headings', height=5)
                budget_tree.heading('Item', text='Item')
                budget_tree.heading('Amount', text='Amount')
                budget_tree.column('Item', width=300)
                budget_tree.column('Amount', width=150)

                for b_item in breakdown:
                    budget_tree.insert('', tk.END, values=(
                        b_item.get('item', ''),
                        f"£{b_item.get('amount', 0):.2f}"
                    ))
                budget_tree.pack(fill=tk.X)

        # Itinerary
        try:
            itinerary = TravelManager.get_itinerary(request_id)
        except Exception:
            itinerary = []

        if itinerary:
            itin_frame = ttk.LabelFrame(scroll_frame, text="Itinerary", padding=10)
            itin_frame.pack(fill=tk.X, padx=10, pady=5)

            itin_cols = ('Leg', 'Type', 'From', 'To', 'Departure', 'Arrival', 'Carrier', 'Cost')
            itin_tree = ttk.Treeview(itin_frame, columns=itin_cols, show='headings', height=5)

            itin_widths = {'Leg': 40, 'Type': 70, 'From': 100, 'To': 100,
                           'Departure': 120, 'Arrival': 120, 'Carrier': 80, 'Cost': 70}
            for col in itin_cols:
                itin_tree.heading(col, text=col)
                itin_tree.column(col, width=itin_widths.get(col, 80))

            for leg in itinerary:
                itin_tree.insert('', tk.END, values=(
                    leg.get('leg_order', ''),
                    leg.get('transport_type', ''),
                    leg.get('departure_location', ''),
                    leg.get('arrival_location', ''),
                    leg.get('departure_datetime', ''),
                    leg.get('arrival_datetime', ''),
                    leg.get('carrier', ''),
                    f"£{leg.get('cost', 0):.2f}"
                ))
            itin_tree.pack(fill=tk.X)

        # Close button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 2: NEW REQUEST ====================

    def _create_new_request_tab(self):
        """Create new travel request tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="New Request")

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
        ttk.Label(header_frame, text="New Travel Request", style='Header.TLabel').pack(side=tk.LEFT)

        # Form
        form_frame = ttk.LabelFrame(scroll_frame, text="Request Details", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 0: Purpose
        ttk.Label(form_frame, text="Purpose:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.purpose_entry = ttk.Entry(form_frame, width=50)
        self.purpose_entry.grid(row=0, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 1: Destination
        ttk.Label(form_frame, text="Destination:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.destination_entry = ttk.Entry(form_frame, width=50)
        self.destination_entry.grid(row=1, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 2: Departure Date, Return Date
        ttk.Label(form_frame, text="Departure Date:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.departure_entry = ttk.Entry(form_frame, width=15)
        self.departure_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.departure_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Return Date:").grid(row=2, column=2, sticky='e', padx=10, pady=8)
        self.return_entry = ttk.Entry(form_frame, width=15)
        self.return_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.return_entry.grid(row=2, column=3, padx=10, pady=8, sticky='w')

        # Row 3: Funding Source
        ttk.Label(form_frame, text="Funding Source:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.funding_combo = ttk.Combobox(
            form_frame, values=['department', 'grant', 'personal', 'mixed'],
            width=15, state='readonly'
        )
        self.funding_combo.set('department')
        self.funding_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Row 4: Justification
        ttk.Label(form_frame, text="Justification:").grid(row=4, column=0, sticky='ne', padx=10, pady=8)
        self.justification_text = tk.Text(form_frame, width=60, height=4)
        self.justification_text.grid(row=4, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Budget Breakdown
        budget_frame = ttk.LabelFrame(scroll_frame, text="Budget Breakdown", padding=10)
        budget_frame.pack(fill=tk.X, padx=10, pady=10)

        budget_tree_frame = ttk.Frame(budget_frame)
        budget_tree_frame.pack(fill=tk.X, pady=5)

        budget_cols = ('Item', 'Amount')
        self.budget_tree = ttk.Treeview(budget_tree_frame, columns=budget_cols, show='headings', height=5)
        self.budget_tree.heading('Item', text='Item')
        self.budget_tree.heading('Amount', text='Amount')
        self.budget_tree.column('Item', width=350)
        self.budget_tree.column('Amount', width=150)
        self.budget_tree.pack(fill=tk.X)

        budget_btn_frame = ttk.Frame(budget_frame)
        budget_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(budget_btn_frame, text="Add Item", command=self._add_budget_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(budget_btn_frame, text="Remove Selected", command=self._remove_budget_item).pack(side=tk.LEFT, padx=5)

        self.budget_total_label = ttk.Label(budget_btn_frame, text="Total: £0.00", font=('Arial', 10, 'bold'))
        self.budget_total_label.pack(side=tk.RIGHT, padx=10)

        # Submit buttons
        submit_frame = ttk.Frame(scroll_frame)
        submit_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(submit_frame, text="Save Draft", command=self._save_draft).pack(side=tk.LEFT, padx=5)
        ttk.Button(submit_frame, text="Submit Request", command=self._submit_request).pack(side=tk.LEFT, padx=5)

    def _add_budget_item(self):
        """Add a budget line item via dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Budget Item")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Item Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        item_entry = ttk.Entry(frame, width=25)
        item_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Amount ($):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        amount_entry = ttk.Entry(frame, width=15)
        amount_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                item_name = validate_entry(item_entry, "Item Name")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                amount = validate_currency_entry(amount_entry, "Amount", min_value=0.01)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            self.budget_tree.insert('', tk.END, values=(item_name, f"£{amount:.2f}"))
            self._update_budget_total()
            dialog.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        item_entry.focus_set()

    def _remove_budget_item(self):
        """Remove selected budget item."""
        selection = self.budget_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a budget item to remove")
            return

        self.budget_tree.delete(selection[0])
        self._update_budget_total()

    def _update_budget_total(self):
        """Update the budget total label."""
        total = 0.0
        for child in self.budget_tree.get_children():
            values = self.budget_tree.item(child)['values']
            try:
                amount_str = str(values[1]).replace('$', '').replace(',', '')
                total += float(amount_str)
            except (ValueError, IndexError):
                pass
        self.budget_total_label.config(text=f"Total: £{total:.2f}")

    def _get_budget_breakdown(self):
        """Get budget breakdown as list of dicts and total."""
        items = []
        total = 0.0
        for child in self.budget_tree.get_children():
            values = self.budget_tree.item(child)['values']
            try:
                amount_str = str(values[1]).replace('$', '').replace(',', '')
                amount = float(amount_str)
            except (ValueError, IndexError):
                amount = 0.0
            items.append({'item': str(values[0]), 'amount': amount})
            total += amount
        return items, total

    def _save_draft(self):
        """Save travel request as draft."""
        # Validate required fields
        try:
            purpose = validate_entry(self.purpose_entry, "Purpose")
            destination = validate_entry(self.destination_entry, "Destination")
            departure_date = validate_date_entry(self.departure_entry, "Departure Date")
            return_date = validate_date_entry(self.return_entry, "Return Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        # Check date order
        try:
            dep_dt = datetime.strptime(departure_date, '%Y-%m-%d')
            ret_dt = datetime.strptime(return_date, '%Y-%m-%d')
            if ret_dt < dep_dt:
                messagebox.showerror("Validation Error", "Return date cannot be before departure date.")
                return
        except ValueError:
            pass

        justification = self.justification_text.get("1.0", "end-1c").strip() or None

        try:
            funding_source = validate_combobox(self.funding_combo, "Funding Source")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        breakdown, total_budget = self._get_budget_breakdown()
        breakdown_json = json.dumps(breakdown) if breakdown else None

        department = self.current_user.get('department')

        try:
            request_id = TravelManager.create_request(
                user_id=self._get_user_id(),
                purpose=purpose,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                estimated_budget=total_budget,
                budget_breakdown_json=breakdown_json,
                funding_source=funding_source,
                justification=justification,
                department=department
            )
            messagebox.showinfo("Success", f"Travel request saved as draft. ID: {request_id}")
            self._clear_request_form()
            self._load_my_trips()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _submit_request(self):
        """Save and submit travel request for approval."""
        # Validate required fields
        try:
            purpose = validate_entry(self.purpose_entry, "Purpose")
            destination = validate_entry(self.destination_entry, "Destination")
            departure_date = validate_date_entry(self.departure_entry, "Departure Date")
            return_date = validate_date_entry(self.return_entry, "Return Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        # Check date order
        try:
            dep_dt = datetime.strptime(departure_date, '%Y-%m-%d')
            ret_dt = datetime.strptime(return_date, '%Y-%m-%d')
            if ret_dt < dep_dt:
                messagebox.showerror("Validation Error", "Return date cannot be before departure date.")
                return
        except ValueError:
            pass

        justification = self.justification_text.get("1.0", "end-1c").strip() or None

        try:
            funding_source = validate_combobox(self.funding_combo, "Funding Source")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        breakdown, total_budget = self._get_budget_breakdown()
        breakdown_json = json.dumps(breakdown) if breakdown else None

        department = self.current_user.get('department')

        try:
            request_id = TravelManager.create_request(
                user_id=self._get_user_id(),
                purpose=purpose,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                estimated_budget=total_budget,
                budget_breakdown_json=breakdown_json,
                funding_source=funding_source,
                justification=justification,
                department=department
            )
            TravelManager.submit_request(request_id, self._get_user_id())
            messagebox.showinfo("Success", f"Travel request submitted for approval. ID: {request_id}")
            self._clear_request_form()
            self._load_my_trips()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _clear_request_form(self):
        """Clear the new request form."""
        self.purpose_entry.delete(0, tk.END)
        self.destination_entry.delete(0, tk.END)
        self.departure_entry.delete(0, tk.END)
        self.departure_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.return_entry.delete(0, tk.END)
        self.return_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.justification_text.delete("1.0", tk.END)
        self.funding_combo.set('department')
        for child in self.budget_tree.get_children():
            self.budget_tree.delete(child)
        self._update_budget_total()

    # ==================== TAB 3: CONFERENCES ====================

    def _create_conferences_tab(self):
        """Create conferences tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Conferences")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Conference Registrations", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Register", command=self._register_conference).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh", command=self._load_conferences).pack(side=tk.RIGHT, padx=5)

        # Conferences treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Conference', 'Location', 'Start', 'End', 'Fee', 'Presenting', 'Status')
        self.conf_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.conf_tree.yview)

        widths = {'ID': 50, 'Conference': 200, 'Location': 130, 'Start': 100,
                  'End': 100, 'Fee': 80, 'Presenting': 80, 'Status': 90}
        for col in columns:
            self.conf_tree.heading(col, text=col)
            self.conf_tree.column(col, width=widths.get(col, 100))

        self.conf_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_conferences()

    def _load_conferences(self):
        """Load user's conference registrations."""
        for item in self.conf_tree.get_children():
            self.conf_tree.delete(item)

        try:
            conferences = TravelManager.get_user_conferences(self._get_user_id())
        except Exception:
            conferences = []

        for c in conferences:
            presenting = 'Yes' if c.get('is_presenting') else 'No'
            # Derive a display status from the linked travel request if available
            status = 'Registered'
            if c.get('travel_request_id'):
                try:
                    req = TravelManager.get_request(c['travel_request_id'])
                    if req:
                        status = req.get('status', 'registered').replace('_', ' ').title()
                except Exception:
                    pass

            self.conf_tree.insert('', tk.END, values=(
                c.get('registration_id'),
                c.get('conference_name', '')[:40],
                c.get('location', ''),
                c.get('start_date', ''),
                c.get('end_date', ''),
                f"£{c.get('registration_fee', 0):.2f}",
                presenting,
                status
            ))

    def _register_conference(self):
        """Open conference registration dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register for Conference")
        dialog.geometry("500x550")
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

        # Conference Name
        ttk.Label(frame, text="Conference Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        conf_name_entry = ttk.Entry(frame, width=35)
        conf_name_entry.grid(row=0, column=1, padx=10, pady=8)

        # URL
        ttk.Label(frame, text="Conference URL:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        conf_url_entry = ttk.Entry(frame, width=35)
        conf_url_entry.grid(row=1, column=1, padx=10, pady=8)

        # Location
        ttk.Label(frame, text="Location:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        conf_location_entry = ttk.Entry(frame, width=35)
        conf_location_entry.grid(row=2, column=1, padx=10, pady=8)

        # Start Date
        ttk.Label(frame, text="Start Date:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        conf_start_entry = ttk.Entry(frame, width=15)
        conf_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        conf_start_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # End Date
        ttk.Label(frame, text="End Date:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        conf_end_entry = ttk.Entry(frame, width=15)
        conf_end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        conf_end_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Fee
        ttk.Label(frame, text="Registration Fee ($):").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        conf_fee_entry = ttk.Entry(frame, width=15)
        conf_fee_entry.insert(0, "0.00")
        conf_fee_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Is Presenting
        presenting_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Presenting at Conference", variable=presenting_var).grid(
            row=6, column=0, columnspan=2, pady=8)

        # Presentation Title
        ttk.Label(frame, text="Presentation Title:").grid(row=7, column=0, sticky='e', padx=10, pady=8)
        conf_pres_title_entry = ttk.Entry(frame, width=35)
        conf_pres_title_entry.grid(row=7, column=1, padx=10, pady=8)

        # Presentation Type
        ttk.Label(frame, text="Presentation Type:").grid(row=8, column=0, sticky='e', padx=10, pady=8)
        conf_pres_type_combo = ttk.Combobox(
            frame, values=['paper', 'poster', 'talk'], width=15, state='readonly'
        )
        conf_pres_type_combo.grid(row=8, column=1, padx=10, pady=8, sticky='w')

        # Travel Request ID (optional link)
        ttk.Label(frame, text="Travel Request ID:").grid(row=9, column=0, sticky='e', padx=10, pady=8)
        conf_travel_id_entry = ttk.Entry(frame, width=15)
        conf_travel_id_entry.grid(row=9, column=1, padx=10, pady=8, sticky='w')
        ttk.Label(frame, text="(optional - link to existing travel request)",
                  font=('Arial', 8)).grid(row=10, column=1, padx=10, sticky='w')

        def save():
            # Validate required fields
            try:
                conf_name = validate_entry(conf_name_entry, "Conference Name")
                start_date = validate_date_entry(conf_start_entry, "Start Date")
                end_date = validate_date_entry(conf_end_entry, "End Date")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Check date order
            try:
                s_dt = datetime.strptime(start_date, '%Y-%m-%d')
                e_dt = datetime.strptime(end_date, '%Y-%m-%d')
                if e_dt < s_dt:
                    messagebox.showerror("Validation Error", "End date cannot be before start date.",
                                         parent=dialog)
                    return
            except ValueError:
                pass

            # Fee (optional, default 0)
            try:
                fee = validate_currency_entry(conf_fee_entry, "Registration Fee", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            conf_url = conf_url_entry.get().strip() or None
            location = conf_location_entry.get().strip() or None
            pres_title = conf_pres_title_entry.get().strip() or None
            pres_type = conf_pres_type_combo.get().strip() or None

            # Travel request ID (optional)
            travel_id_str = conf_travel_id_entry.get().strip()
            travel_request_id = None
            if travel_id_str:
                try:
                    travel_request_id = int(travel_id_str)
                except ValueError:
                    messagebox.showerror("Validation Error",
                                         "Travel Request ID must be a number.", parent=dialog)
                    return

            try:
                reg_id = TravelManager.register_conference(
                    user_id=self._get_user_id(),
                    conference_name=conf_name,
                    start_date=start_date,
                    end_date=end_date,
                    travel_request_id=travel_request_id,
                    conference_url=conf_url,
                    location=location,
                    registration_fee=fee,
                    presentation_title=pres_title,
                    presentation_type=pres_type,
                    is_presenting=presenting_var.get()
                )
                messagebox.showinfo("Success",
                                    f"Conference registration saved. ID: {reg_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_conferences()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=11, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        conf_name_entry.focus_set()

    # ==================== TAB 4: APPROVALS (ADMIN) ====================

    def _create_approvals_tab(self):
        """Create travel approvals tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Approvals")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Travel Approvals", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_travel_approvals).pack(side=tk.RIGHT)

        # Approvals treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Approval ID', 'User', 'Purpose', 'Destination', 'Dates', 'Budget', 'Level', 'Status')
        self.travel_approvals_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.travel_approvals_tree.yview)

        widths = {'Approval ID': 80, 'User': 100, 'Purpose': 180, 'Destination': 130,
                  'Dates': 160, 'Budget': 90, 'Level': 120, 'Status': 90}
        for col in columns:
            self.travel_approvals_tree.heading(col, text=col)
            self.travel_approvals_tree.column(col, width=widths.get(col, 100))

        self.travel_approvals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.travel_approvals_tree.tag_configure('pending', background='#fff3cd')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Approve Selected",
                   command=self._approve_travel_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reject Selected",
                   command=self._reject_travel_request).pack(side=tk.LEFT, padx=5)

        self._load_travel_approvals()

    def _load_travel_approvals(self):
        """Load pending travel approvals."""
        for item in self.travel_approvals_tree.get_children():
            self.travel_approvals_tree.delete(item)

        try:
            approvals = TravelManager.get_pending_approvals()
        except Exception:
            approvals = []

        for a in approvals:
            departure = a.get('departure_date', '')
            return_d = a.get('return_date', '')
            dates = f"{departure} - {return_d}" if departure and return_d else departure or return_d
            level = a.get('approval_level', '').replace('_', ' ').title()

            self.travel_approvals_tree.insert('', tk.END, values=(
                a.get('approval_id'),
                a.get('user_id', ''),
                a.get('purpose', '')[:35],
                a.get('destination', ''),
                dates,
                f"£{a.get('estimated_budget', 0):.2f}",
                level,
                a.get('status', '').title()
            ), tags=('pending',))

    def _approve_travel_request(self):
        """Approve selected travel request."""
        selection = self.travel_approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to process")
            return

        item = self.travel_approvals_tree.item(selection[0])
        approval_id = item['values'][0]

        # Comment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Approval Comments")
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Enter approval comments (optional):").pack(anchor='w', pady=(0, 5))
        comments_text = tk.Text(frame, width=45, height=4)
        comments_text.pack(fill=tk.X, pady=5)

        def confirm():
            comments = comments_text.get("1.0", "end-1c").strip() or None
            try:
                TravelManager.approve_request(approval_id, self._get_user_id(), comments)
                messagebox.showinfo("Success", "Travel request approved")
                dialog.destroy()
                self._load_travel_approvals()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Approve", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _reject_travel_request(self):
        """Reject selected travel request."""
        selection = self.travel_approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to process")
            return

        item = self.travel_approvals_tree.item(selection[0])
        approval_id = item['values'][0]

        # Reason dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Rejection Reason")
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Enter rejection reason (required):").pack(anchor='w', pady=(0, 5))
        reason_text = tk.Text(frame, width=45, height=4)
        reason_text.pack(fill=tk.X, pady=5)

        def confirm():
            reason = reason_text.get("1.0", "end-1c").strip()
            if not reason:
                messagebox.showerror("Error", "Rejection reason is required", parent=dialog)
                return
            try:
                TravelManager.reject_request(approval_id, self._get_user_id(), reason)
                messagebox.showinfo("Success", "Travel request rejected")
                dialog.destroy()
                self._load_travel_approvals()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Reject", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ==================== TAB 5: EXPENSES (ADMIN) ====================

    def _create_expenses_tab(self):
        """Create travel expenses tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Expenses")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Travel Expenses", style='Header.TLabel').pack(side=tk.LEFT)

        # Request selector
        selector_frame = ttk.LabelFrame(tab, text="Select Travel Request", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text="Travel Request:").pack(side=tk.LEFT, padx=5)
        self.expense_request_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.expense_request_combo.pack(side=tk.LEFT, padx=5)
        self.expense_request_combo.bind('<<ComboboxSelected>>', lambda e: self._load_travel_expenses())
        ttk.Button(selector_frame, text="Refresh List",
                   command=self._load_expense_requests).pack(side=tk.LEFT, padx=10)

        # Store request mapping
        self.expense_request_map = {}

        # Linked expenses treeview
        tree_frame = ttk.LabelFrame(tab, text="Linked Expense Claims", padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Claim ID', 'Amount', 'Status', 'Date')
        self.travel_expense_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.travel_expense_tree.yview)

        widths = {'Claim ID': 80, 'Amount': 100, 'Status': 100, 'Date': 120}
        for col in columns:
            self.travel_expense_tree.heading(col, text=col)
            self.travel_expense_tree.column(col, width=widths.get(col, 100))

        self.travel_expense_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Create Expense Claim",
                   command=self._create_expense_from_travel).pack(side=tk.LEFT, padx=5)

        # Load initial request list
        self._load_expense_requests()

    def _load_expense_requests(self):
        """Load user's approved/completed travel requests for the expense selector."""
        self.expense_request_map = {}

        try:
            all_requests = TravelManager.get_user_requests(self._get_user_id())
        except Exception:
            all_requests = []

        # Filter to approved or completed requests
        eligible = [r for r in all_requests if r.get('status') in ('approved', 'completed')]

        display_values = []
        for r in eligible:
            label = f"#{r['request_id']} - {r.get('purpose', '')[:30]} ({r.get('destination', '')})"
            display_values.append(label)
            self.expense_request_map[label] = r['request_id']

        self.expense_request_combo['values'] = display_values
        if display_values:
            self.expense_request_combo.set(display_values[0])
            self._load_travel_expenses()
        else:
            self.expense_request_combo.set('')
            # Clear tree
            for item in self.travel_expense_tree.get_children():
                self.travel_expense_tree.delete(item)

    def _get_selected_request_id(self):
        """Get the request ID from the expense request combo selection."""
        selected = self.expense_request_combo.get()
        return self.expense_request_map.get(selected)

    def _load_travel_expenses(self):
        """Load linked expenses for the selected travel request."""
        for item in self.travel_expense_tree.get_children():
            self.travel_expense_tree.delete(item)

        request_id = self._get_selected_request_id()
        if not request_id:
            return

        try:
            expenses = TravelManager.get_travel_expenses(request_id)
        except Exception:
            expenses = []

        for exp in expenses:
            self.travel_expense_tree.insert('', tk.END, values=(
                exp.get('claim_id'),
                f"£{exp.get('amount', 0):.2f}",
                exp.get('claim_status', '').title(),
                exp.get('expense_date', '')
            ))

    def _create_expense_from_travel(self):
        """Create an expense claim from the selected travel request."""
        request_id = self._get_selected_request_id()
        if not request_id:
            messagebox.showinfo("Info", "Please select a travel request first")
            return

        if not messagebox.askyesno("Confirm",
                                    f"Create expense claim for travel request #{request_id}?"):
            return

        try:
            claim_id = TravelManager.create_expense_from_travel(request_id, self._get_user_id())
            messagebox.showinfo("Success", f"Expense claim created. Claim ID: {claim_id}")
            self._load_travel_expenses()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 6: REPORTS (ADMIN) ====================

    def _create_reports_tab(self):
        """Create travel reports tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Travel Reports", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_travel_stats).pack(side=tk.RIGHT)

        # Statistics overview
        stats_frame = ttk.LabelFrame(tab, text="Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.travel_stats = {}
        for key, label in [('total_requests', 'Total Requests'), ('total_budget', 'Total Budget')]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=30, pady=10)
            self.travel_stats[key] = ttk.Label(frame, text="0", font=('Arial', 18, 'bold'))
            self.travel_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # By Department summary
        dept_frame = ttk.LabelFrame(tab, text="By Department", padding=10)
        dept_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Department', 'Requests', 'Total Budget')
        self.dept_stats_tree = ttk.Treeview(dept_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.dept_stats_tree.heading(col, text=col)
            self.dept_stats_tree.column(col, width=200)

        self.dept_stats_tree.pack(fill=tk.BOTH, expand=True)

        self._load_travel_stats()

    def _load_travel_stats(self):
        """Load travel statistics."""
        try:
            stats = TravelManager.get_travel_statistics()
        except Exception:
            stats = {}

        # Update overview labels
        total_requests = stats.get('total_requests', 0)
        total_budget = stats.get('total_budget', 0)

        self.travel_stats['total_requests'].config(text=str(total_requests))
        self.travel_stats['total_budget'].config(text=f"£{total_budget:.2f}")

        # By department
        for item in self.dept_stats_tree.get_children():
            self.dept_stats_tree.delete(item)

        by_department = stats.get('by_department', {})
        for dept, data in by_department.items():
            self.dept_stats_tree.insert('', tk.END, values=(
                dept,
                data.get('count', 0),
                f"£{data.get('budget', 0):.2f}"
            ))


# Add simpledialog import for potential future use
try:
    from tkinter import simpledialog
    tk.simpledialog = simpledialog
except ImportError:
    pass
