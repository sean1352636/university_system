"""Scholarships management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _

try:
    from education_system.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui import launch_financial_aid_gui
    FINANCIAL_AID_GUI_AVAILABLE = True
except ImportError:
    FINANCIAL_AID_GUI_AVAILABLE = False
    launch_financial_aid_gui = None


class ScholarshipsMixin:
    """Scholarships: create, award, deactivate, refresh."""

    def create_scholarships_tab(self):
        """Create scholarships management tab - Redirects to Financial Aid GUI"""
        scholarships_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['scholarships'] = scholarships_frame

        # Title
        title_label = tk.Label(
            scholarships_frame,
            text=_("finance_gui.tabs.scholarships.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            scholarships_frame,
            text=_("finance_gui.tabs.scholarships.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555',
            justify='center'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        if FINANCIAL_AID_GUI_AVAILABLE and launch_financial_aid_gui:
            launch_btn = tk.Button(
                scholarships_frame,
                text=_("finance_gui.buttons.open_financial_aid"),
                command=lambda: launch_financial_aid_gui(self.root, self.gui.auth),
                font=('Arial', 12, 'bold'),
                bg=self.colors['success'],
                fg='white',
                padx=30,
                pady=15
            )
            launch_btn.pack(pady=10)
        else:
            error_label = tk.Label(
                scholarships_frame,
                text=_("finance_gui.messages.financial_aid_unavailable"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger']
            )
            error_label.pack(pady=10)

        # Info text
        info_text = ScrolledText(scholarships_frame, height=15, width=80, font=('Arial', 10), wrap='word')
        info_text.pack(padx=20, pady=20, fill='both', expand=True)

        info_content = _("finance_gui.scholarships_info.info_content")
        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')

    def _create_scholarship(self):
        """Create a new scholarship"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.create_scholarship"))
        dialog.geometry("500x500")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.create_scholarship"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.scholarship_name")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = tk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.description")).grid(row=1, column=0, sticky='w', pady=5)
        description_entry = tk.Entry(form_frame, width=30)
        description_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.amount")).grid(row=2, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.academic_year")).grid(row=3, column=0, sticky='w', pady=5)
        year_entry = tk.Entry(form_frame, width=30)
        year_entry.insert(0, "2024-2025")
        year_entry.grid(row=3, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.criteria")).grid(row=4, column=0, sticky='w', pady=5)
        criteria_entry = tk.Entry(form_frame, width=30)
        criteria_entry.grid(row=4, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.deadline")).grid(row=5, column=0, sticky='w', pady=5)
        deadline_entry = tk.Entry(form_frame, width=30)
        deadline_entry.grid(row=5, column=1, pady=5)

        def save_scholarship():
            try:
                name = name_entry.get()
                description = description_entry.get()
                amount = float(amount_entry.get())
                academic_year = year_entry.get()
                criteria = criteria_entry.get()
                deadline = deadline_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO scholarships
                    (scholarship_name, description, amount, academic_year, criteria, deadline,
                     is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                ''', (name, description, amount, academic_year, criteria, deadline))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.scholarship_created"))
                dialog.destroy()
                self._refresh_scholarships()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_create_scholarship", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_scholarship, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _award_scholarship(self):
        """Award scholarship to a student"""
        selection = self.scholarships_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_scholarship_first"))
            return

        scholarship_id = self.scholarships_tree.item(selection[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.award_scholarship"))
        dialog.geometry("400x250")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.award_scholarship_to_student"), font=('Arial', 12, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10)

        tk.Label(form_frame, text=_("finance_gui.labels.student_id")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.award_amount")).grid(row=1, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=1, column=1, pady=5)

        def save_award():
            try:
                student_id = student_id_entry.get()
                amount = float(amount_entry.get())

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO student_scholarships
                    (student_id, scholarship_id, amount, status, awarded_date, created_at)
                    VALUES (?, ?, ?, 'active', date('now'), datetime('now'))
                ''', (student_id, scholarship_id, amount))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.scholarship_awarded"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_award_scholarship", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.award"), command=save_award, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _deactivate_scholarship(self):
        """Deactivate selected scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_scholarship_deactivate"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.messages.confirm_deactivate_scholarship")):
            try:
                scholarship_id = self.scholarships_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE scholarships SET is_active = 0 WHERE scholarship_id = ?", (scholarship_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.scholarship_deactivated"))
                self._refresh_scholarships()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_deactivate_scholarship", error=str(e)))

    def _refresh_scholarships(self):
        """Refresh scholarships list"""
        try:
            # Clear existing items
            for item in self.scholarships_tree.get_children():
                self.scholarships_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT scholarship_id, scholarship_name, amount, academic_year, deadline, is_active
                FROM scholarships
                ORDER BY created_at DESC
            ''')

            for row in cursor.fetchall():
                self.scholarships_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing scholarships: {e}")
