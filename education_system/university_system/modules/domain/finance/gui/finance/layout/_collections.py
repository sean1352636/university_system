"""Collections management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _


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

    def _create_collection_case(self):
        """Create a new collection case"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.collections.title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.collections.title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.common_labels.student_id")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.collections.total_debt")).grid(row=1, column=0, sticky='w', pady=5)
        debt_entry = tk.Entry(form_frame, width=30)
        debt_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.common_labels.notes")).grid(row=2, column=0, sticky='w', pady=5)
        notes_entry = tk.Entry(form_frame, width=30)
        notes_entry.grid(row=2, column=1, pady=5)

        def save_case():
            try:
                student_id = student_id_entry.get()
                total_debt = float(debt_entry.get())
                notes = notes_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO collection_cases
                    (student_id, total_debt, case_status, assigned_date, amount_collected,
                     notes, created_at, updated_at)
                    VALUES (?, ?, 'new', date('now'), 0, ?, datetime('now'), datetime('now'))
                ''', (student_id, total_debt, notes))

                conn.commit()
                conn.close()

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

    def _send_collection_notice(self):
        """Send collection notice for selected case"""
        selection = self.collections_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.collections_tab.no_selection"), _("finance_gui.collections_tab.select_collection_case"))
            return

        case_values = self.collections_tree.item(selection[0])['values']
        case_id = case_values[0]
        student_id = case_values[1]
        total_debt = case_values[2]

        # Create notice dialog
        notice_dialog = tk.Toplevel(self.root)
        notice_dialog.title(_("finance_gui.collections_tab.send_notice_title", case_id=case_id))
        notice_dialog.geometry("750x700")
        notice_dialog.transient(self.root)
        notice_dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(notice_dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Case info frame
        info_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.case_information"), padding=15)
        info_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(info_frame, text=f"{_('finance_gui.collections.case_id')}: {case_id}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.collections.student_id')}: {student_id}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.collections.total_debt')}: \u00a3{total_debt:.2f}", font=('Arial', 10, 'bold')).pack(anchor='w')

        # Get student info
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT first_name, last_name, email_address FROM students
                WHERE student_id = ?
            ''', (student_id,))
            student = cursor.fetchone()

            if student:
                student_name = f"{student[0]} {student[1]}"
                student_email = student[2]
                ttk.Label(info_frame, text=f"Student: {student_name}", font=('Arial', 10)).pack(anchor='w')
                ttk.Label(info_frame, text=f"Email: {student_email}", font=('Arial', 10)).pack(anchor='w')
            else:
                student_email = None
                ttk.Label(info_frame, text=_("finance_gui.collections.student_details_not_found"), font=('Arial', 10), foreground='red').pack(anchor='w')

            conn.close()
        except Exception as e:
            student_email = None
            ttk.Label(info_frame, text=f"Error loading student: {e}", font=('Arial', 9), foreground='red').pack(anchor='w')

        # Notice type frame
        type_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.notice_type"), padding=15)
        type_frame.pack(fill='x', padx=10, pady=10)

        notice_type_var = tk.StringVar(value="first_notice")
        notice_types = [
            ("first_notice", _("finance_gui.collections_tab.notice_types.first_notice")),
            ("second_notice", _("finance_gui.collections_tab.notice_types.second_notice")),
            ("final_notice", _("finance_gui.collections_tab.notice_types.final_notice")),
            ("legal_notice", _("finance_gui.collections_tab.notice_types.legal_notice")),
            ("payment_demand", _("finance_gui.collections_tab.notice_types.payment_demand"))
        ]

        for value, text in notice_types:
            ttk.Radiobutton(type_frame, text=text, variable=notice_type_var, value=value).pack(anchor='w', pady=2)

        # Message frame
        message_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.message"), padding=15)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(message_frame, text=_("finance_gui.collections.subject")).pack(anchor='w')
        subject_var = tk.StringVar(value=_("finance_gui.collections_tab.notice_subject_default"))
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, font=('Arial', 11))
        subject_entry.pack(fill='x', pady=(0, 10))

        ttk.Label(message_frame, text=_("finance_gui.collections_tab.message_body_label")).pack(anchor='w')
        message_text = tk.Text(message_frame, height=10, font=('Arial', 10), wrap='word')
        message_text.pack(fill='both', expand=True)

        # Default message template
        default_message = _("finance_gui.collections_tab.default_message", **{"total_debt:.2f": f"{total_debt:.2f}"})
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
                from education_system.university_system.infrastructure.shared_context import get_auth
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Send email using email service
                from education_system.university_system.infrastructure.email.email_service import send_email

                html_message = f"""
                <html>
                <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #d9534f;">{_("finance_gui.email_template.collection_notice_title")}</h2>
                <p><strong>{_("finance_gui.email_template.case_id_label")}</strong> {case_id}</p>
                <p><strong>{_("finance_gui.email_template.outstanding_amount_label")}</strong> \u00a3{total_debt:.2f}</p>
                <hr>
                <div style="white-space: pre-wrap;">{message}</div>
                <hr>
                <p style="font-size: 12px; color: #666;">
                {_("finance_gui.email_template.footer")}
                </p>
                </div>
                </body>
                </html>
                """

                # Send email
                success = send_email(
                    recipient_email=student_email,
                    subject=subject,
                    body=html_message
                )

                if success:
                    # Log the notice in database
                    conn = get_connection()
                    cursor = conn.cursor()

                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Check if collection_notices table exists
                    cursor.execute('''
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='collection_notices'
                    ''')

                    if cursor.fetchone():
                        cursor.execute('''
                            INSERT INTO collection_notices
                            (case_id, student_id, notice_type, subject, message, sent_by, sent_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (case_id, student_id, notice_type, subject, message, username, now))
                        conn.commit()

                    # Update case with last notice date
                    cursor.execute('''
                        UPDATE collection_cases
                        SET last_contact_date = ?, updated_at = ?
                        WHERE case_id = ?
                    ''', (now, now, case_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("finance_gui.messages.success"),
                                      _("finance_gui.collections_tab.notice_sent", email=student_email, notice_type=notice_type.replace('_', ' ').title()))
                    notice_dialog.destroy()
                    self._refresh_collections()
                else:
                    messagebox.showwarning(_("finance_gui.collections_tab.email_failed"),
                                         _("finance_gui.collections_tab.email_failed_message", email=student_email))

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_send_notice", error=str(e)))
                import traceback
                traceback.print_exc()

        # Buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=_("finance_gui.collections_tab.send_notice_btn"), command=send_notice).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=notice_dialog.destroy).pack(side='left', padx=5)

    def _resolve_collection_case(self):
        """Resolve selected collection case"""
        selection = self.collections_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.collections_tab.no_selection"), _("finance_gui.collections_tab.select_case_to_resolve"))
            return

        amount_collected = simpledialog.askfloat(_("finance_gui.collections_tab.resolve_case_title"), _("finance_gui.collections_tab.enter_amount_collected"))
        if amount_collected is None:
            return

        try:
            case_id = self.collections_tree.item(selection[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE collection_cases
                SET case_status = 'resolved', amount_collected = ?,
                    resolution_date = date('now'), updated_at = datetime('now')
                WHERE case_id = ?
            ''', (amount_collected, case_id))
            conn.commit()
            conn.close()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.collections_tab.case_resolved"))
            self._refresh_collections()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_resolve_case", error=str(e)))

    def _refresh_collections(self):
        """Refresh collections list"""
        try:
            # Clear existing items
            for item in self.collections_tree.get_children():
                self.collections_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT case_id, student_id, total_debt, case_status, assigned_date,
                       amount_collected, resolution_date
                FROM collection_cases
                ORDER BY created_at DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.collections_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing collections: {e}")
