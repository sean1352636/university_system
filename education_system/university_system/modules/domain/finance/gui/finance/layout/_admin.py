"""Admin/system management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _


class AdminMixin:
    """Admin tab: database management, fee/aid types, system status."""

    def create_admin_tab(self):
        """Create admin/system management tab"""
        admin_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['admin'] = admin_frame

        # Title
        title_label = tk.Label(admin_frame, text=_("finance_gui.admin_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Main container with sections
        main_container = tk.Frame(admin_frame, bg='white')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Database Management Section
        db_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.database_management"),
                                   font=('Arial', 12, 'bold'), bg='white')
        db_section.pack(fill='x', padx=10, pady=10)

        db_buttons = tk.Frame(db_section, bg='white')
        db_buttons.pack(fill='x', padx=10, pady=10)

        tk.Button(db_buttons, text=_("finance_gui.admin_tab.backup_database"), command=self._backup_database,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(db_buttons, text=_("finance_gui.admin_tab.database_statistics"), command=self._show_db_stats,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(db_buttons, text=_("finance_gui.admin_tab.cleanup_old_data"), command=self._cleanup_old_data,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # Fee Type Management Section
        fee_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.fee_type_management"),
                                    font=('Arial', 12, 'bold'), bg='white')
        fee_section.pack(fill='x', padx=10, pady=10)

        fee_buttons = tk.Frame(fee_section, bg='white')
        fee_buttons.pack(fill='x', padx=10, pady=10)

        tk.Button(fee_buttons, text=_("finance_gui.admin_tab.create_fee_type_btn"), command=self._create_fee_type,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(fee_buttons, text=_("finance_gui.admin_tab.view_fee_types_btn"), command=self._view_fee_types,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # Aid Type Management Section
        aid_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.aid_type_management"),
                                    font=('Arial', 12, 'bold'), bg='white')
        aid_section.pack(fill='x', padx=10, pady=10)

        aid_buttons = tk.Frame(aid_section, bg='white')
        aid_buttons.pack(fill='x', padx=10, pady=10)

        tk.Button(aid_buttons, text=_("finance_gui.admin_tab.create_aid_type_btn"), command=self._create_aid_type,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(aid_buttons, text=_("finance_gui.admin_tab.view_aid_types_btn"), command=self._view_aid_types,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # System Status Section
        status_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.system_status"),
                                      font=('Arial', 12, 'bold'), bg='white')
        status_section.pack(fill='both', expand=True, padx=10, pady=10)

        self.admin_status_text = ScrolledText(status_section, height=15, width=80, wrap=tk.WORD)
        self.admin_status_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Refresh button for status
        tk.Button(status_section, text=_("finance_gui.admin_tab.refresh_status"), command=self._refresh_admin_status,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8).pack(pady=10)

        # Load initial status
        self.root.after(100, self._refresh_admin_status)

    def _backup_database(self):
        """Backup the database"""
        try:
            import shutil
            from pathlib import Path
            from education_system.university_system.modules.shared.constants import paths

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = paths.BACKUP_DIR
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / f"student_records_backup_{timestamp}.db"

            shutil.copy2(paths.DEFAULT_DB_PATH, backup_path)
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.backup_success", path=str(backup_path)))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.backup_failed", error=str(e)))

    def _show_db_stats(self):
        """Show database statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            stats_text = "Database Statistics\n"
            stats_text += "=" * 70 + "\n\n"

            tables = ['students', 'student_fees', 'payments', 'scholarships',
                     'student_scholarships', 'collection_cases', 'student_financial_aid',
                     'late_fees', 'exchange_rates']

            for table in tables:
                try:
                    from education_system.university_system.core.sql_safety import validate_table_name
                    validated_table = validate_table_name(table, conn=conn)
                    cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                    count = cursor.fetchone()[0]
                    stats_text += f"{table:30s}: {count:>10,} records\n"
                except Exception:
                    stats_text += f"{table:30s}: Table not found\n"

            conn.close()

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', stats_text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.db_stats_failed", error=str(e)))

    def _cleanup_old_data(self):
        """Cleanup old data (with confirmation)"""
        if not messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.admin_tab.cleanup_confirm")):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Delete old payment records
            cursor.execute('''
                DELETE FROM payments
                WHERE created_at < date('now', '-7 years')
            ''')
            deleted_payments = cursor.rowcount

            # Delete old late fees
            cursor.execute('''
                DELETE FROM late_fees
                WHERE created_at < date('now', '-7 years')
            ''')
            deleted_late_fees = cursor.rowcount

            conn.commit()
            conn.close()

            messagebox.showinfo(_("finance_gui.messages.success"),
                              _("finance_gui.admin_tab.cleanup_success", payments=deleted_payments, late_fees=deleted_late_fees))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.cleanup_failed", error=str(e)))

    def _create_fee_type(self):
        """Create a new fee type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.admin_tab.create_fee_type_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.admin_tab.create_fee_type_title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.fee_name_label")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = tk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.description_label")).grid(row=1, column=0, sticky='w', pady=5)
        description_entry = tk.Entry(form_frame, width=30)
        description_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.academic_year_label")).grid(row=2, column=0, sticky='w', pady=5)
        year_entry = tk.Entry(form_frame, width=30)
        year_entry.insert(0, "2024-2025")
        year_entry.grid(row=2, column=1, pady=5)

        is_recurring_var = tk.BooleanVar()
        tk.Checkbutton(form_frame, text=_("finance_gui.admin_tab.is_recurring_label"), variable=is_recurring_var).grid(row=3, column=1, sticky='w', pady=5)

        def save_fee_type():
            try:
                name = name_entry.get()
                description = description_entry.get()
                academic_year = year_entry.get()
                is_recurring = is_recurring_var.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO fee_types
                    (fee_name, description, academic_year, is_recurring, created_at, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ''', (name, description, academic_year, 1 if is_recurring else 0))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.fee_type_created"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.fee_type_failed", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_fee_type, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _view_fee_types(self):
        """View all fee types"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fee_type_id, fee_name, description, academic_year, is_recurring
                FROM fee_types
                ORDER BY fee_type_id
            ''')

            fee_types = cursor.fetchall()
            conn.close()

            text = _("finance_gui.admin_tab.fee_types_title") + "\n"
            text += "=" * 70 + "\n\n"

            for ft in fee_types:
                text += f"{_('finance_gui.admin_tab.id_label', id=ft[0])}\n"
                text += f"{_('finance_gui.admin_tab.name_label', name=ft[1])}\n"
                text += f"{_('finance_gui.admin_tab.description_value', description=ft[2])}\n"
                text += f"{_('finance_gui.admin_tab.academic_year_value', year=ft[3])}\n"
                recurring_value = _("finance_gui.admin_tab.recurring_yes") if ft[4] else _("finance_gui.admin_tab.recurring_no")
                text += f"{_('finance_gui.admin_tab.recurring_label', value=recurring_value)}\n"
                text += "-" * 70 + "\n"

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.view_fee_types_failed", error=str(e)))

    def _create_aid_type(self):
        """Create a new financial aid type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.admin_tab.create_aid_type_title"))
        dialog.geometry("500x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.admin_tab.create_aid_type_heading"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.aid_type_name_label")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = tk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.description_label")).grid(row=1, column=0, sticky='w', pady=5)
        description_entry = tk.Entry(form_frame, width=30)
        description_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.max_amount_label")).grid(row=2, column=0, sticky='w', pady=5)
        max_amount_entry = tk.Entry(form_frame, width=30)
        max_amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.category_label")).grid(row=3, column=0, sticky='w', pady=5)
        category_var = tk.StringVar(value="grant")
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                     values=['grant', 'loan', 'scholarship', 'work_study'],
                                     state='readonly', width=27)
        category_combo.grid(row=3, column=1, pady=5)

        def save_aid_type():
            try:
                name = name_entry.get()
                description = description_entry.get()
                max_amount = float(max_amount_entry.get())
                category = category_var.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO financial_aid_types
                    (aid_name, description, max_amount, aid_category, is_active,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                ''', (name, description, max_amount, category))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.aid_type_created"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.aid_type_failed", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_aid_type, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _view_aid_types(self):
        """View all financial aid types"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT aid_type_id, aid_name, description, max_amount, aid_category, is_active
                FROM financial_aid_types
                ORDER BY aid_type_id
            ''')

            aid_types = cursor.fetchall()
            conn.close()

            text = _("finance_gui.admin_tab.aid_types_title") + "\n"
            text += "=" * 70 + "\n\n"

            for at in aid_types:
                text += f"{_('finance_gui.admin_tab.id_label', id=at[0])}\n"
                text += f"{_('finance_gui.admin_tab.name_label', name=at[1])}\n"
                text += f"{_('finance_gui.admin_tab.description_value', description=at[2])}\n"
                text += f"{_('finance_gui.admin_tab.max_amount_value', amount=at[3])}\n"
                text += f"{_('finance_gui.admin_tab.category_value', category=at[4])}\n"
                active_value = _("finance_gui.admin_tab.active_yes") if at[5] else _("finance_gui.admin_tab.active_no")
                text += f"{_('finance_gui.admin_tab.active_label', value=active_value)}\n"
                text += "-" * 70 + "\n"

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.view_aid_types_failed", error=str(e)))

    def _refresh_admin_status(self):
        """Refresh admin status display"""
        try:
            status_text = f"System Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_text += "=" * 70 + "\n\n"

            conn = get_connection()
            cursor = conn.cursor()

            # Database info
            status_text += "DATABASE STATUS\n"
            status_text += "-" * 70 + "\n"

            # Count records
            cursor.execute("SELECT COUNT(*) FROM students")
            student_count = cursor.fetchone()[0]
            status_text += f"Total Students: {student_count:,}\n"

            cursor.execute("SELECT COUNT(*) FROM student_fees WHERE status = 'unpaid'")
            unpaid_fees = cursor.fetchone()[0]
            status_text += f"Unpaid Fees: {unpaid_fees:,}\n"

            cursor.execute("SELECT COUNT(*) FROM payments")
            payment_count = cursor.fetchone()[0]
            status_text += f"Total Payments: {payment_count:,}\n"

            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0]
            status_text += f"Total Revenue: \u00a3{total_revenue:,.2f}\n\n"

            # Recent activity
            status_text += "RECENT ACTIVITY (Last 7 Days)\n"
            status_text += "-" * 70 + "\n"

            cursor.execute('''
                SELECT COUNT(*) FROM payments
                WHERE created_at >= date('now', '-7 days')
            ''')
            recent_payments = cursor.fetchone()[0]
            status_text += f"New Payments: {recent_payments}\n"

            cursor.execute('''
                SELECT COUNT(*) FROM student_fees
                WHERE created_at >= date('now', '-7 days')
            ''')
            recent_fees = cursor.fetchone()[0]
            status_text += f"New Fees Assigned: {recent_fees}\n"

            cursor.execute('''
                SELECT COUNT(*) FROM collection_cases
                WHERE created_at >= date('now', '-7 days')
            ''')
            recent_collections = cursor.fetchone()[0]
            status_text += f"New Collection Cases: {recent_collections}\n\n"

            status_text += "System is operational and running normally.\n"
            status_text += "Last updated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn.close()

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', status_text)

        except Exception as e:
            error_text = f"Error loading system status: {e}"
            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', error_text)
