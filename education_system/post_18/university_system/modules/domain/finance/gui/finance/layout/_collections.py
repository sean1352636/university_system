"""Collections management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import get_text as _


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
                    messagebox.showwarning(_("finance_gui.messages.warning"), "Please select a student.")
                    return
                student_id = student_id_map.get(selected, selected)

                debt_str = debt_entry.get().strip()
                if not debt_str:
                    messagebox.showwarning(_("finance_gui.messages.warning"), "Please enter a debt amount.")
                    return
                total_debt = float(debt_str)
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
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), "Please enter a valid number for the debt amount.")
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
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT first_name, last_name, email_address FROM students
                WHERE student_id = ?
            ''', (student_id,))
            student = cursor.fetchone()
            conn.close()
            if student:
                return f"{student[0]} {student[1]}", student[2]
        except Exception:
            pass
        return None, None

    def _send_email_to_student(self, student_email, subject, body):
        """Send an email to a student via the university email system."""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email
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

        notice_type_var = tk.StringVar(value="first_notice")
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
                from education_system.post_18.university_system.infrastructure.shared_context import get_auth
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Build HTML email
                html_message = (
                    '<html><body>'
                    '<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">'
                    f'<h2 style="color: #d9534f;">{_("finance_gui.email_template.collection_notice_title")}</h2>'
                    f'<p><strong>{_("finance_gui.email_template.case_id_label")}</strong> {case_id}</p>'
                    f'<p><strong>{_("finance_gui.email_template.outstanding_amount_label")}</strong> \u00a3{total_debt:.2f}</p>'
                    '<hr>'
                    f'<div style="white-space: pre-wrap;">{message}</div>'
                    '<hr>'
                    f'<p style="font-size: 12px; color: #666;">{_("finance_gui.email_template.footer")}</p>'
                    '</div></body></html>'
                )

                success = self._send_email_to_student(student_email, subject, html_message)

                if success is not False:
                    # Log the notice in database
                    conn = get_connection()
                    cursor = conn.cursor()
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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

                    cursor.execute('''
                        UPDATE collection_cases
                        SET notes = COALESCE(notes, '') || ? , updated_at = ?
                        WHERE case_id = ?
                    ''', (f'\nNotice sent: {notice_type} on {now}', now, case_id))
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
        info_frame = ttk.LabelFrame(resolve_dialog, text="Case Details", padding=10)
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
        ttk.Checkbutton(resolve_dialog, text="Email resolution notice to student",
                       variable=send_email_var).pack(padx=15, anchor='w', pady=5)

        def do_resolve():
            amount_str = amount_entry.get().strip()
            if not amount_str:
                messagebox.showwarning(_("finance_gui.messages.warning"), "Please enter an amount.")
                return
            try:
                amount_collected = float(amount_str)
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), "Please enter a valid number.")
                return

            try:
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

                # Email the student the outcome
                if send_email_var.get() and student_email:
                    display_name = student_name or student_id
                    remaining = total_debt - amount_collected
                    if remaining <= 0:
                        status_text = "Your account balance has been fully settled."
                    else:
                        status_text = f"Remaining balance: \u00a3{remaining:.2f}. Please contact the finance department for any queries."

                    email_body = (
                        f"Dear {display_name},\n\n"
                        f"This is to inform you that collection case #{case_id} has been resolved.\n\n"
                        f"Original Debt: \u00a3{total_debt:.2f}\n"
                        f"Amount Collected: \u00a3{amount_collected:.2f}\n"
                        f"{status_text}\n\n"
                        f"If you have any questions, please contact the Finance Department.\n\n"
                        f"Best regards,\nFinance Department"
                    )
                    self._send_email_to_student(student_email, f"Collection Case #{case_id} - Resolved", email_body)

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.collections_tab.case_resolved"))
                resolve_dialog.destroy()
                self._refresh_collections()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_resolve_case", error=str(e)))

        btn_frame = ttk.Frame(resolve_dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Resolve & Save", command=do_resolve).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.common_buttons.cancel"), command=resolve_dialog.destroy).pack(side='left', padx=5)

        amount_entry.bind('<Return>', lambda e: do_resolve())

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
                # Format monetary values for display
                values = list(row)
                # total_debt (index 2) and amount_collected (index 5)
                try:
                    values[2] = f"{float(values[2]):.2f}" if values[2] is not None else "0.00"
                except (ValueError, TypeError):
                    values[2] = "0.00"
                try:
                    values[5] = f"{float(values[5]):.2f}" if values[5] is not None else "0.00"
                except (ValueError, TypeError):
                    values[5] = "0.00"
                self.collections_tree.insert('', 'end', values=values)

            conn.close()
        except Exception as e:
            print(f"Error refreshing collections: {e}")
