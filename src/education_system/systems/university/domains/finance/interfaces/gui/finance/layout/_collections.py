"""Collections management mixin for LayoutManager."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collections import (
    list_cases,
    open_case,
)
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collection_case_actions import (
    resolve_case,
    send_case_notice,
    student_contact,
)


class CollectionsMixin:
    """Collections: create case, send notice, resolve, refresh."""

    def create_collections_tab(self):
        """Create collections management tab"""
        collections_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['collections'] = collections_frame

        # Title
        title_label = tk.Label(collections_frame, text=_("finance_gui.collections_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(collections_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.collections_tab.create_case"), command=self._create_collection_case,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.collections_tab.send_notice"), command=self._send_collection_notice,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.collections_tab.resolve_case"), command=self._resolve_collection_case,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_collections,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Collections table
        table_frame = tk.Frame(collections_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('case_id', 'student_id', 'total_debt', 'case_status', 'assigned_date',
                   'amount_collected', 'resolution_date')
        self.collections_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.collections_tree.heading(col, text=col.replace('_', ' ').title())
            self.collections_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.collections_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.collections_tree.xview)
        self.collections_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.collections_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_collections)

    def _load_students_for_dropdown(self):
        """Load students from DB for dropdown selection."""
        students = []
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id, first_name, last_name
                FROM students
                ORDER BY last_name, first_name
            ''')
            for row in cursor.fetchall():
                sid = row[0]
                name = f"{row[1]} {row[2]}"
                students.append((sid, f"{sid} - {name}"))
            conn.close()
        except Exception as e:
            print(f"Error loading students: {e}")
        return students

    def _create_collection_case(self):
        """Create a new collection case"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.collections.title"))
        dialog.geometry("550x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.collections.title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        # Student dropdown
        tk.Label(form_frame, text=_("finance_gui.common_labels.student_id")).grid(row=0, column=0, sticky='w', pady=5)

        students = self._load_students_for_dropdown()
        student_display_values = [s[1] for s in students]
        student_id_map = {s[1]: s[0] for s in students}

        student_combo = ttk.Combobox(form_frame, values=student_display_values, width=35, state='readonly')
        student_combo.grid(row=0, column=1, pady=5)
        if student_display_values:
            student_combo.current(0)

        tk.Label(form_frame, text=_("finance_gui.collections.total_debt")).grid(row=1, column=0, sticky='w', pady=5)
        debt_entry = tk.Entry(form_frame, width=30)
        debt_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.common_labels.notes")).grid(row=2, column=0, sticky='w', pady=5)
        notes_entry = tk.Entry(form_frame, width=30)
        notes_entry.grid(row=2, column=1, pady=5)

        def save_case():
            try:
                selected = student_combo.get()
                if not selected:
                    messagebox.showwarning(_("finance_gui.messages.warning"), _t('gui.finance.finance.layout.collections.dialogs.please_select_a_student', default="Please select a student."))
                    return
                student_id = student_id_map.get(selected, selected)

                debt_str = debt_entry.get().strip()
                if not debt_str:
                    messagebox.showwarning(_("finance_gui.messages.warning"), _t('gui.finance.finance.layout.collections.dialogs.please_enter_a_debt_amount', default="Please enter a debt amount."))
                    return
                try:
                    total_debt = float(debt_str)
                except ValueError:
                    messagebox.showerror(_("finance_gui.messages.error"), _t('gui.finance.finance.layout.collections.dialogs.please_enter_a_valid_number_for_the_debt_amount', default="Please enter a valid number for the debt amount."))
                    return
                notes = notes_entry.get()

                # Shared with the Finance CLI: validates the student and refuses
                # a second open case for them.
                open_case(student_id, total_debt, notes)

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.collections_tab.case_created"))
                dialog.destroy()
                self._refresh_collections()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_create_case", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.common_buttons.save"), command=save_case, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.common_buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _get_student_email(self, student_id):
        """Look up student email and name from DB."""
        return student_contact(student_id)

    def _send_email_to_student(self, student_email, subject, body):
        """Send an email to a student via the university email system."""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email
            return send_email(recipient_email=student_email, subject=subject, body=body)
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def _send_collection_notice(self):
        """Send collection notice for selected case"""
        selection = self.collections_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.collections_tab.no_selection"), _("finance_gui.collections_tab.select_collection_case"))
            return

        case_values = self.collections_tree.item(selection[0])['values']
        case_id = case_values[0]
        student_id = case_values[1]
        try:
            total_debt = float(case_values[2])
        except (ValueError, TypeError):
            total_debt = 0.0

        student_name, student_email = self._get_student_email(student_id)

        # Create notice dialog — compact size with fixed button bar at bottom
        notice_dialog = tk.Toplevel(self.root)
        notice_dialog.title(_("finance_gui.collections_tab.send_notice_title", case_id=case_id))
        notice_dialog.geometry("650x550")
        notice_dialog.transient(self.root)
        notice_dialog.grab_set()

        # Fixed button bar at the BOTTOM (packed first so it stays visible)
        btn_frame = ttk.Frame(notice_dialog)
        btn_frame.pack(side='bottom', fill='x', padx=10, pady=8)

        # Scrollable content area
        main_container = tk.Frame(notice_dialog)
        main_container.pack(fill='both', expand=True)

        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Case info frame
        info_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.case_information"), padding=10)
        info_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Label(info_frame, text=f"{_('finance_gui.collections.case_id')}: {case_id}").pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.collections.student_id')}: {student_id}").pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.collections.total_debt')}: \u00a3{total_debt:.2f}", font=('Arial', 10, 'bold')).pack(anchor='w')

        if student_name:
            ttk.Label(info_frame, text=f"Student: {student_name}").pack(anchor='w')
            ttk.Label(info_frame, text=f"Email: {student_email or 'N/A'}").pack(anchor='w')
        else:
            ttk.Label(info_frame, text=_("finance_gui.collections.student_details_not_found"), foreground='red').pack(anchor='w')

        # Notice type frame — horizontal layout to save space
        type_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.notice_type"), padding=10)
        type_frame.pack(fill='x', padx=10, pady=5)

        notice_type_var = tk.StringVar(value=_t('gui.finance.finance.layout.collections.values.first_notice', default="first_notice"))
        notice_types = [
            ("first_notice", _("finance_gui.collections_tab.notice_types.first_notice")),
            ("second_notice", _("finance_gui.collections_tab.notice_types.second_notice")),
            ("final_notice", _("finance_gui.collections_tab.notice_types.final_notice")),
            ("legal_notice", _("finance_gui.collections_tab.notice_types.legal_notice")),
            ("payment_demand", _("finance_gui.collections_tab.notice_types.payment_demand"))
        ]

        for value, text in notice_types:
            ttk.Radiobutton(type_frame, text=text, variable=notice_type_var, value=value).pack(anchor='w', pady=1)

        # Message frame
        message_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.message"), padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=5)

        ttk.Label(message_frame, text=_("finance_gui.collections.subject")).pack(anchor='w')
        subject_var = tk.StringVar(value=_("finance_gui.collections_tab.notice_subject_default"))
        ttk.Entry(message_frame, textvariable=subject_var, font=('Arial', 10)).pack(fill='x', pady=(0, 5))

        ttk.Label(message_frame, text=_("finance_gui.collections_tab.message_body_label")).pack(anchor='w')
        message_text = tk.Text(message_frame, height=6, font=('Arial', 9), wrap='word')
        message_text.pack(fill='both', expand=True)

        # Default message template — pass total_debt as float so i18n {total_debt:.2f} works
        default_message = _("finance_gui.collections_tab.default_message", total_debt=total_debt)
        message_text.insert('1.0', default_message)

        def send_notice():
            """Send the collection notice"""
            try:
                if not student_email:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.email_not_found"))
                    return

                notice_type = notice_type_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning(_("finance_gui.messages.warning"), _("finance_gui.collections_tab.missing_subject_message"))
                    return

                # Get authentication for audit trail
                from education_system.systems.university.infrastructure.shared_context import get_auth
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Shared with the Finance CLI: builds the HTML notice, emails it,
                # records it in collection_notices (when present) and on the case.
                try:
                    send_case_notice(case_id, notice_type, subject, message, sent_by=username)
                except RuntimeError:
                    messagebox.showwarning(_("finance_gui.collections_tab.email_failed"),
                                         _("finance_gui.collections_tab.email_failed_message", email=student_email))
                    return

                messagebox.showinfo(_("finance_gui.messages.success"),
                                  _("finance_gui.collections_tab.notice_sent", email=student_email, notice_type=notice_type.replace('_', ' ').title()))
                notice_dialog.destroy()
                self._refresh_collections()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_send_notice", error=str(e)))
                import traceback
                traceback.print_exc()

        # Button bar (packed at bottom of dialog, always visible)
        ttk.Button(btn_frame, text=_("finance_gui.collections_tab.send_notice_btn"), command=send_notice).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=notice_dialog.destroy).pack(side='left', padx=5)

    def _resolve_collection_case(self):
        """Resolve selected collection case and email the student the outcome"""
        selection = self.collections_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.collections_tab.no_selection"), _("finance_gui.collections_tab.select_case_to_resolve"))
            return

        case_values = self.collections_tree.item(selection[0])['values']
        case_id = case_values[0]
        student_id = case_values[1]
        try:
            total_debt = float(case_values[2])
        except (ValueError, TypeError):
            total_debt = 0.0

        student_name, student_email = self._get_student_email(student_id)

        resolve_dialog = tk.Toplevel(self.root)
        resolve_dialog.title(_("finance_gui.collections_tab.resolve_case_title"))
        resolve_dialog.geometry("450x320")
        resolve_dialog.transient(self.root)
        resolve_dialog.grab_set()

        # Case info
        info_frame = ttk.LabelFrame(resolve_dialog, text=_t('gui.finance.finance.layout.collections.labels.case_details', default="Case Details"), padding=10)
        info_frame.pack(fill='x', padx=15, pady=(10, 5))

        ttk.Label(info_frame, text=f"Case: {case_id} | Student: {student_id}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Total Debt: \u00a3{total_debt:.2f}", font=('Arial', 10, 'bold')).pack(anchor='w')
        if student_name:
            ttk.Label(info_frame, text=f"Name: {student_name} | Email: {student_email or 'N/A'}").pack(anchor='w')

        # Amount collected
        amount_frame = ttk.Frame(resolve_dialog)
        amount_frame.pack(fill='x', padx=15, pady=5)

        ttk.Label(amount_frame, text=_("finance_gui.collections_tab.enter_amount_collected"),
                 font=('Arial', 10)).pack(anchor='w')
        amount_entry = ttk.Entry(amount_frame, width=20, font=('Arial', 11))
        amount_entry.pack(anchor='w', pady=5)
        amount_entry.focus_set()

        # Email notification checkbox
        send_email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(resolve_dialog, text=_t('gui.finance.finance.layout.collections.buttons.email_resolution_notice_to_student', default="Email resolution notice to student"),
                       variable=send_email_var).pack(padx=15, anchor='w', pady=5)

        def do_resolve():
            amount_str = amount_entry.get().strip()
            if not amount_str:
                messagebox.showwarning(_("finance_gui.messages.warning"), _t('gui.finance.finance.layout.collections.dialogs.please_enter_an_amount', default="Please enter an amount."))
                return
            try:
                amount_collected = float(amount_str)
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _t('gui.finance.finance.layout.collections.dialogs.please_enter_a_valid_number', default="Please enter a valid number."))
                return

            try:
                # Shared with the Finance CLI: records the amount, stamps the
                # resolution date and emails the student the outcome.
                resolve_case(case_id, amount_collected, notify=bool(send_email_var.get()))

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.collections_tab.case_resolved"))
                resolve_dialog.destroy()
                self._refresh_collections()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_resolve_case", error=str(e)))

        btn_frame = ttk.Frame(resolve_dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text=_t('gui.finance.finance.layout.collections.buttons.resolve_save', default="Resolve & Save"), command=do_resolve).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.common_buttons.cancel"), command=resolve_dialog.destroy).pack(side='left', padx=5)

        amount_entry.bind('<Return>', lambda e: do_resolve())

    def _refresh_collections(self):
        """Refresh collections list"""
        try:
            # Clear existing items
            for item in self.collections_tree.get_children():
                self.collections_tree.delete(item)

            for case in list_cases(limit=500):
                values = [
                    case['case_id'], case['student_id'],
                    f"{float(case['total_debt'] or 0):.2f}",
                    case['case_status'], case['assigned_date'],
                    f"{float(case['amount_collected'] or 0):.2f}",
                    case['resolution_date'],
                ]
                self.collections_tree.insert('', 'end', values=values)
        except Exception as e:
            print(f"Error refreshing collections: {e}")
