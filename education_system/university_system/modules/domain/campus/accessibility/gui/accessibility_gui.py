"""
Accessibility Services Portal - GUI Interface

This module provides a graphical user interface for students to interact with
accessibility services, submit accommodation requests, and manage their accommodations.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime
from typing import Optional
import os

from education_system.university_system.modules.domain.campus.accessibility.services.accessibility_service import AccessibilityService
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.localization import get_translation

_t = get_translation


class AccessibilityGUI:
    """GUI interface for accessibility services."""

    def __init__(self, parent=None):
        """
        Initialize the accessibility GUI.

        Args:
            parent: Parent window (if None, creates root window)
        """
        self.service = AccessibilityService()
        self.auth = get_auth()

        if parent is None:
            self.root = tk.Tk()
            self.root.title(_t("accessibility.window_title", default="Accessibility Services Portal"))
            self.root.geometry("1000x700")
            self.is_standalone = True
        else:
            self.root = tk.Toplevel(parent)
            self.root.title(_t("accessibility.window_title", default="Accessibility Services Portal"))
            self.root.geometry("1000x700")
            self.is_standalone = False

        # Get current user
        if not self.auth.current_user:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.not_logged_in", default="You must be logged in to access accessibility services.")
            )
            self.root.destroy()
            return

        current_user = self.auth.get_current_user()
        self.student_id = current_user.get('user_id') or current_user.get('username')

        self._create_widgets()
        self._load_dashboard()

    def _create_widgets(self):
        """Create the main GUI widgets."""
        # Main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(
            main_container,
            text=_t("accessibility.title", default="Accessibility Services Portal"),
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create tabs
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.request_frame = ttk.Frame(self.notebook)
        self.messages_frame = ttk.Frame(self.notebook)
        self.accommodations_frame = ttk.Frame(self.notebook)
        self.renewals_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.dashboard_frame, text=_t("accessibility.tabs.dashboard", default="Dashboard"))
        self.notebook.add(self.request_frame, text=_t("accessibility.tabs.submit_request", default="Submit Request"))
        self.notebook.add(self.messages_frame, text=_t("accessibility.tabs.messages", default="Messages"))
        self.notebook.add(self.accommodations_frame, text=_t("accessibility.tabs.my_accommodations", default="My Accommodations"))
        self.notebook.add(self.renewals_frame, text=_t("accessibility.tabs.renewals", default="Renewals"))

        # Build each tab
        self._build_dashboard_tab()
        self._build_request_tab()
        self._build_messages_tab()
        self._build_accommodations_tab()
        self._build_renewals_tab()

        # Close button
        close_btn = ttk.Button(main_container, text=_t("accessibility.buttons.close", default="Close"), command=self._on_close)
        close_btn.grid(row=2, column=0, pady=(10, 0), sticky=tk.E)

    def _build_dashboard_tab(self):
        """Build the dashboard tab with status overview."""
        # Status summary frame
        summary_frame = ttk.LabelFrame(self.dashboard_frame, text=_t("accessibility.dashboard.status_summary", default="Status Summary"), padding="10")
        summary_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N))

        self.dashboard_frame.columnconfigure(0, weight=1)
        self.dashboard_frame.rowconfigure(1, weight=1)

        # Labels for statistics
        self.total_requests_label = ttk.Label(summary_frame, text=_t("accessibility.dashboard.total_requests", default="Total Requests: {count}", count="0"))
        self.total_requests_label.grid(row=0, column=0, sticky=tk.W, pady=2)

        self.active_accommodations_label = ttk.Label(summary_frame, text=_t("accessibility.dashboard.active_accommodations", default="Active Accommodations: {count}", count="0"))
        self.active_accommodations_label.grid(row=1, column=0, sticky=tk.W, pady=2)

        self.expiring_label = ttk.Label(summary_frame, text=_t("accessibility.dashboard.expiring_soon", default="Expiring Soon: {count}", count="0"), foreground="red")
        self.expiring_label.grid(row=2, column=0, sticky=tk.W, pady=2)

        # Recent requests frame
        requests_frame = ttk.LabelFrame(self.dashboard_frame, text=_t("accessibility.dashboard.recent_requests", default="Recent Requests"), padding="10")
        requests_frame.grid(row=1, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        requests_frame.columnconfigure(0, weight=1)
        requests_frame.rowconfigure(0, weight=1)

        # Requests treeview
        columns = (
            _t("accessibility.table_columns.id", default="ID"),
            _t("accessibility.table_columns.type", default="Type"),
            _t("accessibility.table_columns.status", default="Status"),
            _t("accessibility.table_columns.submitted", default="Submitted")
        )
        self.requests_tree = ttk.Treeview(requests_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.requests_tree.heading(col, text=col)
            self.requests_tree.column(col, width=150)

        self.requests_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar for requests
        scrollbar = ttk.Scrollbar(requests_frame, orient=tk.VERTICAL, command=self.requests_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.requests_tree.configure(yscrollcommand=scrollbar.set)

        # Refresh button
        refresh_btn = ttk.Button(requests_frame, text=_t("accessibility.buttons.refresh", default="Refresh"), command=self._load_dashboard)
        refresh_btn.grid(row=1, column=0, pady=(10, 0), sticky=tk.W)

    def _build_request_tab(self):
        """Build the request submission tab."""
        # Request form
        form_frame = ttk.Frame(self.request_frame, padding="10")
        form_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.request_frame.columnconfigure(0, weight=1)
        self.request_frame.rowconfigure(0, weight=1)

        # Student name
        ttk.Label(form_frame, text=_t("accessibility.labels.full_name", default="Full Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Student email
        ttk.Label(form_frame, text=_t("accessibility.labels.email", default="Email:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(form_frame, width=40)
        self.email_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Accommodation type
        ttk.Label(form_frame, text=_t("accessibility.labels.accommodation_type", default="Accommodation Type:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(
            form_frame,
            textvariable=self.type_var,
            values=self.service.ACCOMMODATION_TYPES,
            state='readonly',
            width=37
        )
        type_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Description
        ttk.Label(form_frame, text=_t("accessibility.labels.description", default="Description:")).grid(row=3, column=0, sticky=(tk.W, tk.N), pady=5)
        self.description_text = scrolledtext.ScrolledText(form_frame, width=40, height=10)
        self.description_text.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)

        form_frame.columnconfigure(1, weight=1)
        form_frame.rowconfigure(3, weight=1)

        # Buttons frame
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("accessibility.buttons.submit_request", default="Submit Request"), command=self._submit_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("accessibility.buttons.clear_form", default="Clear Form"), command=self._clear_request_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("accessibility.buttons.upload_documentation", default="Upload Documentation"), command=self._upload_documentation).pack(side=tk.LEFT, padx=5)

    def _build_messages_tab(self):
        """Build the messages tab."""
        # Split into request selector and message area
        messages_container = ttk.Frame(self.messages_frame, padding="10")
        messages_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.messages_frame.columnconfigure(0, weight=1)
        self.messages_frame.rowconfigure(0, weight=1)
        messages_container.columnconfigure(0, weight=1)
        messages_container.rowconfigure(1, weight=1)

        # Request selector
        selector_frame = ttk.LabelFrame(messages_container, text=_t("accessibility.messages.select_request", default="Select Request"), padding="10")
        selector_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(selector_frame, text=_t("accessibility.labels.request", default="Request:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.message_request_var = tk.StringVar()
        self.message_request_combo = ttk.Combobox(
            selector_frame,
            textvariable=self.message_request_var,
            state='readonly',
            width=50
        )
        self.message_request_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.message_request_combo.bind('<<ComboboxSelected>>', self._load_messages)

        ttk.Button(selector_frame, text=_t("accessibility.buttons.load_messages", default="Load Messages"), command=self._load_messages).grid(row=0, column=2, padx=5)

        selector_frame.columnconfigure(1, weight=1)

        # Messages display
        messages_display_frame = ttk.LabelFrame(messages_container, text=_t("accessibility.messages.message_thread", default="Message Thread"), padding="10")
        messages_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        messages_display_frame.columnconfigure(0, weight=1)
        messages_display_frame.rowconfigure(0, weight=1)

        self.messages_display = scrolledtext.ScrolledText(messages_display_frame, width=80, height=15, state='disabled')
        self.messages_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Send message frame
        send_frame = ttk.LabelFrame(messages_container, text=_t("accessibility.messages.send_message", default="Send Message"), padding="10")
        send_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        send_frame.columnconfigure(0, weight=1)

        self.message_entry = scrolledtext.ScrolledText(send_frame, width=80, height=5)
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(send_frame, text=_t("accessibility.buttons.send_message", default="Send Message"), command=self._send_message).grid(row=1, column=0, sticky=tk.W)

    def _build_accommodations_tab(self):
        """Build the active accommodations tab."""
        acc_container = ttk.Frame(self.accommodations_frame, padding="10")
        acc_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.accommodations_frame.columnconfigure(0, weight=1)
        self.accommodations_frame.rowconfigure(0, weight=1)
        acc_container.columnconfigure(0, weight=1)
        acc_container.rowconfigure(0, weight=1)

        # Accommodations treeview
        columns = (
            _t("accessibility.table_columns.id", default="ID"),
            _t("accessibility.table_columns.type", default="Type"),
            _t("accessibility.table_columns.start_date", default="Start Date"),
            _t("accessibility.table_columns.expiration", default="Expiration"),
            _t("accessibility.table_columns.days_left", default="Days Left")
        )
        self.accommodations_tree = ttk.Treeview(acc_container, columns=columns, show='headings', height=15)

        for col in columns:
            self.accommodations_tree.heading(col, text=col)
            self.accommodations_tree.column(col, width=150)

        self.accommodations_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar
        scrollbar = ttk.Scrollbar(acc_container, orient=tk.VERTICAL, command=self.accommodations_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.accommodations_tree.configure(yscrollcommand=scrollbar.set)

        # Details frame
        details_frame = ttk.LabelFrame(acc_container, text=_t("accessibility.accommodations.accommodation_details", default="Accommodation Details"), padding="10")
        details_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        details_frame.columnconfigure(0, weight=1)

        self.acc_details_text = scrolledtext.ScrolledText(details_frame, width=80, height=8, state='disabled')
        self.acc_details_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Bind selection event
        self.accommodations_tree.bind('<<TreeviewSelect>>', self._on_accommodation_select)

        # Buttons
        btn_frame = ttk.Frame(acc_container)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        ttk.Button(btn_frame, text=_t("accessibility.buttons.refresh", default="Refresh"), command=self._load_accommodations).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("accessibility.buttons.view_faculty_notifications", default="View Faculty Notifications"), command=self._view_faculty_notifications).pack(side=tk.LEFT, padx=5)

    def _build_renewals_tab(self):
        """Build the renewals tab."""
        renewals_container = ttk.Frame(self.renewals_frame, padding="10")
        renewals_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.renewals_frame.columnconfigure(0, weight=1)
        self.renewals_frame.rowconfigure(0, weight=1)
        renewals_container.columnconfigure(0, weight=1)

        # Expiring accommodations section
        expiring_frame = ttk.LabelFrame(renewals_container, text=_t("accessibility.renewals.expiring_accommodations", default="Expiring Accommodations (Next 30 Days)"), padding="10")
        expiring_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        expiring_frame.columnconfigure(0, weight=1)

        columns = (
            _t("accessibility.table_columns.id", default="ID"),
            _t("accessibility.table_columns.type", default="Type"),
            _t("accessibility.table_columns.expiration", default="Expiration"),
            _t("accessibility.table_columns.days_left", default="Days Left")
        )
        self.expiring_tree = ttk.Treeview(expiring_frame, columns=columns, show='headings', height=5)

        for col in columns:
            self.expiring_tree.heading(col, text=col)
            self.expiring_tree.column(col, width=150)

        self.expiring_tree.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Renewal request section
        renewal_request_frame = ttk.LabelFrame(renewals_container, text=_t("accessibility.renewals.request_renewal", default="Request Renewal"), padding="10")
        renewal_request_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        renewal_request_frame.columnconfigure(1, weight=1)

        ttk.Label(renewal_request_frame, text=_t("accessibility.labels.select_accommodation", default="Select Accommodation:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.renewal_acc_var = tk.StringVar()
        self.renewal_acc_combo = ttk.Combobox(
            renewal_request_frame,
            textvariable=self.renewal_acc_var,
            state='readonly',
            width=50
        )
        self.renewal_acc_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        ttk.Label(renewal_request_frame, text=_t("accessibility.labels.notes_optional", default="Notes (optional):")).grid(row=1, column=0, sticky=(tk.W, tk.N), pady=5)
        self.renewal_notes_text = scrolledtext.ScrolledText(renewal_request_frame, width=50, height=4)
        self.renewal_notes_text.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        ttk.Button(renewal_request_frame, text=_t("accessibility.buttons.submit_renewal_request", default="Submit Renewal Request"), command=self._submit_renewal).grid(row=2, column=0, columnspan=2, pady=10)

        # Previous renewal requests
        previous_renewals_frame = ttk.LabelFrame(renewals_container, text=_t("accessibility.renewals.renewal_history", default="Renewal History"), padding="10")
        previous_renewals_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        previous_renewals_frame.columnconfigure(0, weight=1)
        previous_renewals_frame.rowconfigure(0, weight=1)

        renewals_container.rowconfigure(2, weight=1)

        columns = (
            _t("accessibility.table_columns.id", default="ID"),
            _t("accessibility.table_columns.type", default="Type"),
            _t("accessibility.table_columns.requested", default="Requested"),
            _t("accessibility.table_columns.status", default="Status")
        )
        self.renewals_tree = ttk.Treeview(previous_renewals_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.renewals_tree.heading(col, text=col)
            self.renewals_tree.column(col, width=150)

        self.renewals_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar
        scrollbar = ttk.Scrollbar(previous_renewals_frame, orient=tk.VERTICAL, command=self.renewals_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.renewals_tree.configure(yscrollcommand=scrollbar.set)

        # Refresh button
        ttk.Button(previous_renewals_frame, text=_t("accessibility.buttons.refresh", default="Refresh"), command=self._load_renewals).grid(row=1, column=0, pady=(10, 0), sticky=tk.W)

        # Load initial data
        self._load_renewals()

    def _load_dashboard(self):
        """Load dashboard data."""
        # Get statistics
        requests = self.service.get_student_requests(self.student_id)
        active_accs = self.service.get_active_accommodations(self.student_id)
        expiring = self.service.get_expiring_accommodations(self.student_id, days_threshold=30)

        # Update labels
        self.total_requests_label.config(text=_t("accessibility.dashboard.total_requests", default="Total Requests: {count}", count=len(requests)))
        self.active_accommodations_label.config(text=_t("accessibility.dashboard.active_accommodations", default="Active Accommodations: {count}", count=len(active_accs)))
        self.expiring_label.config(text=_t("accessibility.dashboard.expiring_soon", default="Expiring Soon: {count}", count=len(expiring)))

        # Clear and populate requests tree
        for item in self.requests_tree.get_children():
            self.requests_tree.delete(item)

        for req in requests:
            self.requests_tree.insert('', 'end', values=(
                req['request_id'],
                req['accommodation_type'],
                req['status'],
                req['submitted_date'][:10] if req['submitted_date'] else 'N/A'
            ))

    def _clear_request_form(self):
        """Clear the request submission form."""
        self.name_entry.delete(0, tk.END)
        self.email_entry.delete(0, tk.END)
        self.type_var.set('')
        self.description_text.delete('1.0', tk.END)

    def _submit_request(self):
        """Submit a new accommodation request."""
        name = self.name_entry.get().strip()
        email = self.email_entry.get().strip()
        acc_type = self.type_var.get()
        description = self.description_text.get('1.0', tk.END).strip()

        if not all([name, email, acc_type, description]):
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.all_fields_required", default="All fields are required.")
            )
            return

        try:
            request_id = self.service.submit_accommodation_request(
                student_id=self.student_id,
                student_name=name,
                student_email=email,
                accommodation_type=acc_type,
                description=description
            )

            messagebox.showinfo(
                _t("accessibility.dialog_titles.success", default="Success"),
                _t("accessibility.success_messages.request_submitted",
                   default="Accommodation request submitted successfully!\n\nRequest ID: {request_id}\nType: {type}\nStatus: Submitted\n\nPlease upload supporting documentation.",
                   request_id=request_id, type=acc_type)
            )

            self._clear_request_form()
            self._load_dashboard()

        except Exception as e:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.failed_to_submit", default="Failed to submit request: {error}", error=str(e))
            )

    def _upload_documentation(self):
        """Upload documentation for a request."""
        requests = self.service.get_student_requests(self.student_id)

        if not requests:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.no_requests", default="You have no accommodation requests.")
            )
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("accessibility.upload_docs.dialog_title", default="Upload Documentation"))
        dialog.geometry("500x400")

        ttk.Label(dialog, text=_t("accessibility.upload_docs.select_request", default="Select Request:"), font=('Arial', 10, 'bold')).pack(pady=10)

        # List requests
        request_listbox = tk.Listbox(dialog, width=70, height=10)
        request_listbox.pack(pady=10, padx=10)

        for req in requests:
            request_listbox.insert(tk.END, f"ID {req['request_id']}: {req['accommodation_type']} - {req['status']}")

        def upload_file():
            selection = request_listbox.curselection()
            if not selection:
                messagebox.showerror(
                    _t("accessibility.dialog_titles.error", default="Error"),
                    _t("accessibility.error_messages.select_request", default="Please select a request.")
                )
                return

            request_id = requests[selection[0]]['request_id']

            # File selection
            file_path = filedialog.askopenfilename(
                title=_t("accessibility.upload_docs.dialog_title", default="Upload Documentation"),
                filetypes=[
                    (_t("accessibility.upload_docs.file_types.pdf", default="PDF files"), "*.pdf"),
                    (_t("accessibility.upload_docs.file_types.images", default="Image files"), "*.png *.jpg *.jpeg"),
                    (_t("accessibility.upload_docs.file_types.all", default="All files"), "*.*")
                ]
            )

            if not file_path:
                return

            filename = os.path.basename(file_path)

            # Read file
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()

                doc_id = self.service.upload_documentation(
                    request_id=request_id,
                    student_id=self.student_id,
                    filename=filename,
                    file_content=file_content,
                    document_type=_t("accessibility.upload_docs.medical_documentation", default="Medical Documentation")
                )

                messagebox.showinfo(
                    _t("accessibility.dialog_titles.success", default="Success"),
                    _t("accessibility.success_messages.documentation_uploaded",
                       default="Documentation uploaded successfully!\n\nDocument ID: {doc_id}\nFilename: {filename}",
                       doc_id=doc_id, filename=filename)
                )

                dialog.destroy()

            except Exception as e:
                messagebox.showerror(
                    _t("accessibility.dialog_titles.error", default="Error"),
                    _t("accessibility.error_messages.failed_to_upload", default="Failed to upload documentation: {error}", error=str(e))
                )

        ttk.Button(dialog, text=_t("accessibility.buttons.upload_file", default="Upload File"), command=upload_file).pack(pady=10)
        ttk.Button(dialog, text=_t("accessibility.buttons.cancel", default="Cancel"), command=dialog.destroy).pack(pady=5)

    def _load_messages(self, event=None):
        """Load messages for the selected request."""
        # First, populate request combo if empty
        if not self.message_request_combo['values']:
            requests = self.service.get_student_requests(self.student_id)
            if not requests:
                return

            request_options = [f"ID {req['request_id']}: {req['accommodation_type']} - {req['status']}" for req in requests]
            self.message_request_combo['values'] = request_options
            self.message_request_combo.current(0)

        # Get selected request ID
        selected = self.message_request_var.get()
        if not selected:
            return

        request_id = int(selected.split(':')[0].replace('ID ', ''))

        # Load messages
        messages = self.service.get_messages(request_id)

        # Display messages
        self.messages_display.config(state='normal')
        self.messages_display.delete('1.0', tk.END)

        if not messages:
            self.messages_display.insert(tk.END, _t("accessibility.messages.no_messages", default="No messages yet.\n"))
        else:
            for msg in messages:
                sender_label = _t("accessibility.messages.sender_you", default="You") if msg['sender_type'] == 'student' else _t("accessibility.messages.sender_staff", default="Disability Services Staff")
                self.messages_display.insert(tk.END, f"[{msg['sent_date']}] {sender_label}:\n", 'sender')
                self.messages_display.insert(tk.END, f"{msg['message']}\n\n")

                # Mark as read
                if msg['sender_type'] == 'staff' and not msg['is_read']:
                    self.service.mark_message_as_read(msg['message_id'])

        self.messages_display.config(state='disabled')

    def _send_message(self):
        """Send a message to disability services."""
        selected = self.message_request_var.get()
        if not selected:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.select_request_first", default="Please select a request first.")
            )
            return

        request_id = int(selected.split(':')[0].replace('ID ', ''))
        message = self.message_entry.get('1.0', tk.END).strip()

        if not message:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.message_empty", default="Message cannot be empty.")
            )
            return

        try:
            message_id = self.service.send_message(
                request_id=request_id,
                sender_id=self.student_id,
                sender_type='student',
                message=message
            )

            messagebox.showinfo(
                _t("accessibility.dialog_titles.success", default="Success"),
                _t("accessibility.success_messages.message_sent", default="Message sent successfully! (ID: {message_id})", message_id=message_id)
            )
            self.message_entry.delete('1.0', tk.END)
            self._load_messages()

        except Exception as e:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.failed_to_send", default="Failed to send message: {error}", error=str(e))
            )

    def _load_accommodations(self):
        """Load active accommodations."""
        # Clear tree
        for item in self.accommodations_tree.get_children():
            self.accommodations_tree.delete(item)

        # Load accommodations
        accommodations = self.service.get_active_accommodations(self.student_id)

        for acc in accommodations:
            exp_date = datetime.strptime(acc['expiration_date'], '%Y-%m-%d')
            days_left = (exp_date - datetime.now()).days

            # Add color coding for expiring accommodations
            tag = 'expiring' if days_left <= 30 else 'normal'

            self.accommodations_tree.insert('', 'end', values=(
                acc['accommodation_id'],
                acc['accommodation_type'],
                acc['start_date'],
                acc['expiration_date'],
                days_left
            ), tags=(tag,))

        # Configure tags
        self.accommodations_tree.tag_configure('expiring', foreground='red')
        self.accommodations_tree.tag_configure('normal', foreground='black')

    def _on_accommodation_select(self, event):
        """Handle accommodation selection."""
        selection = self.accommodations_tree.selection()
        if not selection:
            return

        item = self.accommodations_tree.item(selection[0])
        acc_id = item['values'][0]

        # Get full accommodation details
        accommodations = self.service.get_active_accommodations(self.student_id)
        acc = next((a for a in accommodations if a['accommodation_id'] == acc_id), None)

        if acc:
            # Display details
            self.acc_details_text.config(state='normal')
            self.acc_details_text.delete('1.0', tk.END)

            self.acc_details_text.insert(tk.END, _t("accessibility.accommodations.accommodation_id", default="Accommodation ID: {id}", id=acc['accommodation_id']) + "\n")
            self.acc_details_text.insert(tk.END, _t("accessibility.accommodations.type", default="Type: {type}", type=acc['accommodation_type']) + "\n")
            self.acc_details_text.insert(tk.END, _t("accessibility.accommodations.start_date", default="Start Date: {date}", date=acc['start_date']) + "\n")
            self.acc_details_text.insert(tk.END, _t("accessibility.accommodations.expiration_date", default="Expiration Date: {date}", date=acc['expiration_date']) + "\n")
            self.acc_details_text.insert(tk.END, _t("accessibility.accommodations.approved_by", default="Approved By: {approver}", approver=acc['approved_by']) + "\n\n")
            self.acc_details_text.insert(tk.END, _t("accessibility.accommodations.description_label", default="Description:\n{description}", description=acc['description']) + "\n")

            self.acc_details_text.config(state='disabled')

    def _view_faculty_notifications(self):
        """View faculty notifications sent."""
        notifications = self.service.get_faculty_notifications(self.student_id)

        if not notifications:
            messagebox.showinfo(
                _t("accessibility.faculty_notifications.dialog_title", default="Faculty Notifications"),
                _t("accessibility.info_messages.no_faculty_notifications", default="No faculty notifications have been sent.")
            )
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("accessibility.faculty_notifications.dialog_title", default="Faculty Notifications"))
        dialog.geometry("700x500")

        ttk.Label(
            dialog,
            text=_t("accessibility.faculty_notifications.total_sent", default="Total Notifications Sent: {count}", count=len(notifications)),
            font=('Arial', 10, 'bold')
        ).pack(pady=10)

        # Treeview
        columns = (
            _t("accessibility.table_columns.id", default="ID"),
            _t("accessibility.table_columns.faculty", default="Faculty"),
            _t("accessibility.table_columns.course", default="Course"),
            _t("accessibility.table_columns.sent_date", default="Sent Date"),
            _t("accessibility.table_columns.acknowledged", default="Acknowledged")
        )
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        tree.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        for notif in notifications:
            tree.insert('', 'end', values=(
                notif['notification_id'],
                notif['faculty_id'],
                notif['course_id'],
                notif['sent_date'][:10],
                _t("accessibility.faculty_notifications.yes", default="Yes") if notif['acknowledged'] else _t("accessibility.faculty_notifications.no", default="No")
            ))

        ttk.Button(dialog, text=_t("accessibility.buttons.close", default="Close"), command=dialog.destroy).pack(pady=10)

    def _load_renewals(self):
        """Load renewal data."""
        # Load expiring accommodations
        for item in self.expiring_tree.get_children():
            self.expiring_tree.delete(item)

        expiring = self.service.get_expiring_accommodations(self.student_id, days_threshold=30)

        for acc in expiring:
            exp_date = datetime.strptime(acc['expiration_date'], '%Y-%m-%d')
            days_left = (exp_date - datetime.now()).days

            self.expiring_tree.insert('', 'end', values=(
                acc['accommodation_id'],
                acc['accommodation_type'],
                acc['expiration_date'],
                days_left
            ))

        # Populate renewal combo
        active_accs = self.service.get_active_accommodations(self.student_id)
        acc_options = [f"ID {acc['accommodation_id']}: {acc['accommodation_type']}" for acc in active_accs]
        self.renewal_acc_combo['values'] = acc_options
        if acc_options:
            self.renewal_acc_combo.current(0)

        # Load renewal history
        for item in self.renewals_tree.get_children():
            self.renewals_tree.delete(item)

        renewals = self.service.get_renewal_requests(self.student_id)

        for renewal in renewals:
            self.renewals_tree.insert('', 'end', values=(
                renewal['renewal_id'],
                renewal['accommodation_type'],
                renewal['renewal_request_date'][:10],
                renewal['status']
            ))

    def _submit_renewal(self):
        """Submit a renewal request."""
        selected = self.renewal_acc_var.get()
        if not selected:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.select_accommodation", default="Please select an accommodation to renew.")
            )
            return

        acc_id = int(selected.split(':')[0].replace('ID ', ''))
        notes = self.renewal_notes_text.get('1.0', tk.END).strip()

        try:
            renewal_id = self.service.request_renewal(
                accommodation_id=acc_id,
                student_id=self.student_id,
                notes=notes if notes else None
            )

            messagebox.showinfo(
                _t("accessibility.dialog_titles.success", default="Success"),
                _t("accessibility.success_messages.renewal_submitted",
                   default="Renewal request submitted successfully!\n\nRenewal ID: {renewal_id}\nStatus: Pending\n\nYou will be notified when your renewal is processed.",
                   renewal_id=renewal_id)
            )

            self.renewal_notes_text.delete('1.0', tk.END)
            self._load_renewals()

        except Exception as e:
            messagebox.showerror(
                _t("accessibility.dialog_titles.error", default="Error"),
                _t("accessibility.error_messages.failed_renewal", default="Failed to submit renewal request: {error}", error=str(e))
            )

    def _on_close(self):
        """Handle window close."""
        self.root.destroy()

    def run(self):
        """Run the GUI main loop (for standalone mode)."""
        if self.is_standalone:
            self.root.mainloop()


def main():
    """Main entry point for the accessibility GUI."""
    app = AccessibilityGUI()
    app.run()


if __name__ == '__main__':
    main()
