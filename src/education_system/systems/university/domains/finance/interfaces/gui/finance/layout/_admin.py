"""Admin/system management mixin for LayoutManager.

The queries and writes live in ``domain/core/finance_admin`` and are shared
with the Finance CLI (``interfaces/cli/admin``); this mixin only draws the
tab and its dialogs.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from education_system.systems.university.domains.finance.domain.core import finance_admin as _admin
from education_system.systems.university.infrastructure.i18n import get_text as _


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

    def _set_admin_text(self, text):
        self.admin_status_text.delete('1.0', tk.END)
        self.admin_status_text.insert('1.0', text)

    def _backup_database(self):
        """Backup the database"""
        try:
            backup_path = _admin.backup_database()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.backup_success", path=str(backup_path)))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.backup_failed", error=str(e)))

    def _show_db_stats(self):
        """Show database statistics"""
        try:
            stats_text = "Database Statistics\n"
            stats_text += "=" * 70 + "\n\n"

            for table, count in _admin.database_statistics():
                if count is None:
                    stats_text += f"{table:30s}: Table not found\n"
                else:
                    stats_text += f"{table:30s}: {count:>10,} records\n"

            self._set_admin_text(stats_text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.db_stats_failed", error=str(e)))

    def _cleanup_old_data(self):
        """Cleanup old data (with confirmation)"""
        if not messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.admin_tab.cleanup_confirm")):
            return

        try:
            deleted = _admin.cleanup_old_data()
            messagebox.showinfo(_("finance_gui.messages.success"),
                              _("finance_gui.admin_tab.cleanup_success", payments=deleted['payments'], late_fees=deleted['late_fees']))
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
                _admin.create_fee_type(
                    name_entry.get(),
                    description_entry.get(),
                    year_entry.get(),
                    is_recurring_var.get(),
                )
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
            text = _("finance_gui.admin_tab.fee_types_title") + "\n"
            text += "=" * 70 + "\n\n"

            for ft in _admin.list_fee_types():
                text += f"{_('finance_gui.admin_tab.id_label', id=ft['fee_type_id'])}\n"
                text += f"{_('finance_gui.admin_tab.name_label', name=ft['fee_name'])}\n"
                text += f"{_('finance_gui.admin_tab.description_value', description=ft['description'])}\n"
                text += f"{_('finance_gui.admin_tab.academic_year_value', year=ft['academic_year'])}\n"
                recurring_value = _("finance_gui.admin_tab.recurring_yes") if ft['is_recurring'] else _("finance_gui.admin_tab.recurring_no")
                text += f"{_('finance_gui.admin_tab.recurring_label', value=recurring_value)}\n"
                text += "-" * 70 + "\n"

            self._set_admin_text(text)
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
        category_var = tk.StringVar(value=_t('gui.finance.finance.layout.admin.values.grant', default="grant"))
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                     values=list(_admin.AID_CATEGORIES),
                                     state='readonly', width=27)
        category_combo.grid(row=3, column=1, pady=5)

        def save_aid_type():
            try:
                name = name_entry.get().strip()
                if not name:
                    messagebox.showwarning(_("finance_gui.messages.warning"), _t('gui.finance.finance.layout.admin.dialogs.aid_type_name_is_required', default="Aid type name is required."))
                    return
                max_amount_str = max_amount_entry.get().strip()
                max_amount = float(max_amount_str) if max_amount_str else 0.0

                _admin.create_aid_type(name, description_entry.get().strip(), max_amount, category_var.get())

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
            text = _("finance_gui.admin_tab.aid_types_title") + "\n"
            text += "=" * 70 + "\n\n"

            for at in _admin.list_aid_types():
                text += f"{_('finance_gui.admin_tab.id_label', id=at['aid_type_id'])}\n"
                text += f"{_('finance_gui.admin_tab.name_label', name=at['aid_name'])}\n"
                text += f"{_('finance_gui.admin_tab.description_value', description=at['description'])}\n"
                text += f"{_('finance_gui.admin_tab.max_amount_value', amount=at['max_amount'])}\n"
                text += f"{_('finance_gui.admin_tab.category_value', category=at['aid_category'])}\n"
                active_value = _("finance_gui.admin_tab.active_yes") if at['is_active'] else _("finance_gui.admin_tab.active_no")
                text += f"{_('finance_gui.admin_tab.active_label', value=active_value)}\n"
                text += "-" * 70 + "\n"

            self._set_admin_text(text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.view_aid_types_failed", error=str(e)))

    def _refresh_admin_status(self):
        """Refresh admin status display"""
        try:
            self._set_admin_text(_admin.system_status_text())
        except Exception as e:
            self._set_admin_text(f"Error loading system status: {e}")
