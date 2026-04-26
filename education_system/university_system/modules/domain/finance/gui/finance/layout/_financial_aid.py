"""Financial aid management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _

try:
    from education_system.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui import FinancialAidGUI
    FINANCIAL_AID_GUI_AVAILABLE = True
except ImportError:
    FINANCIAL_AID_GUI_AVAILABLE = False
    FinancialAidGUI = None


class FinancialAidMixin:
    """Financial aid tab — embeds the Financial Aid & Scholarships GUI inline."""

    def create_aid_tab(self):
        """Create financial aid tab; embed lazily on first show."""
        aid_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['aid'] = aid_frame
        self._aid_gui_instance = None

        if not (FINANCIAL_AID_GUI_AVAILABLE and FinancialAidGUI):
            tk.Label(
                aid_frame,
                text=_("finance_gui.aid_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger'],
            ).pack(pady=10)
            return

        aid_frame.bind('<Map>', self._on_aid_tab_shown, add='+')

    def _on_aid_tab_shown(self, _event):
        if getattr(self, '_aid_gui_instance', None) is not None:
            return
        aid_frame = self.tab_frames.get('aid')
        if aid_frame is None:
            return
        try:
            host = ttk.Frame(aid_frame)
            host.pack(fill='both', expand=True)
            auth = getattr(self.gui, 'auth', None) or getattr(self, 'auth', None)
            self._aid_gui_instance = FinancialAidGUI(auth_instance=auth, parent=host)
            self._aid_gui_instance.create_embedded_interface()
        except Exception as e:
            tk.Label(
                aid_frame,
                text=str(e),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger'],
                justify='left',
            ).pack(padx=20, pady=20, anchor='nw')

    def _award_financial_aid(self):
        """Award financial aid to a student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.aid_tab.award_dialog_title"))
        dialog.geometry("500x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.aid_tab.award_dialog_title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.student_id_label")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.aid_type_label")).grid(row=1, column=0, sticky='w', pady=5)
        aid_type_var = tk.StringVar()
        aid_type_combo = ttk.Combobox(form_frame, textvariable=aid_type_var, state='readonly', width=27)
        aid_type_combo.grid(row=1, column=1, pady=5)

        # Load aid types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT aid_type_id, aid_name FROM financial_aid_types WHERE is_active = 1")
            aid_types = cursor.fetchall()
            conn.close()
            aid_type_combo['values'] = [f"{at[0]} - {at[1]}" for at in aid_types]
        except Exception as e:
            print(f"Error loading aid types: {e}")

        tk.Label(form_frame, text=_("finance_gui.aid_tab.awarded_amount_label")).grid(row=2, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.status_label")).grid(row=3, column=0, sticky='w', pady=5)
        status_var = tk.StringVar(value="pending")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                   values=['pending', 'approved', 'disbursed', 'completed', 'cancelled'],
                                   state='readonly', width=27)
        status_combo.grid(row=3, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.notes_label")).grid(row=4, column=0, sticky='w', pady=5)
        notes_entry = tk.Entry(form_frame, width=30)
        notes_entry.grid(row=4, column=1, pady=5)

        def save_aid():
            try:
                student_id = student_id_entry.get()
                aid_type_str = aid_type_var.get()
                aid_type_id = int(aid_type_str.split(' - ')[0])
                awarded_amount = float(amount_entry.get())
                status = status_var.get()
                notes = notes_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO student_financial_aid
                    (student_id, aid_type_id, awarded_amount, disbursed_amount, remaining_amount,
                     status, application_date, notes, created_at, updated_at)
                    VALUES (?, ?, ?, 0, ?, ?, date('now'), ?, datetime('now'), datetime('now'))
                ''', (student_id, aid_type_id, awarded_amount, awarded_amount, status, notes))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.aid_tab.aid_awarded"))
                dialog.destroy()
                self._refresh_financial_aid()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.aid_tab.failed_award_aid", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_aid, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _disburse_aid(self):
        """Disburse funds for selected aid"""
        selection = self.aid_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.aid_tab.no_selection"), _("finance_gui.aid_tab.select_aid_record"))
            return

        amount = simpledialog.askfloat(_("finance_gui.aid_tab.disburse_aid_title"), _("finance_gui.aid_tab.enter_disbursement_amount"))
        if amount is None:
            return

        try:
            aid_id = self.aid_tree.item(selection[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE student_financial_aid
                SET disbursed_amount = disbursed_amount + ?,
                    remaining_amount = remaining_amount - ?,
                    status = 'disbursed',
                    updated_at = datetime('now')
                WHERE aid_id = ?
            ''', (amount, amount, aid_id))
            conn.commit()
            conn.close()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.aid_tab.aid_disbursed"))
            self._refresh_financial_aid()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.aid_tab.failed_disburse_aid", error=str(e)))

    def _cancel_aid(self):
        """Cancel selected financial aid"""
        selection = self.aid_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.aid_tab.no_selection"), _("finance_gui.aid_tab.select_aid_to_cancel"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.aid_tab.confirm_cancel")):
            try:
                aid_id = self.aid_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE student_financial_aid
                    SET status = 'cancelled', updated_at = datetime('now')
                    WHERE aid_id = ?
                ''', (aid_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.aid_tab.aid_cancelled"))
                self._refresh_financial_aid()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.aid_tab.failed_cancel_aid", error=str(e)))

    def _refresh_financial_aid(self):
        """Refresh financial aid list"""
        try:
            # Clear existing items
            for item in self.aid_tree.get_children():
                self.aid_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sfa.aid_id, sfa.student_id, fat.aid_name, sfa.awarded_amount,
                       sfa.disbursed_amount, sfa.remaining_amount, sfa.status, sfa.application_date
                FROM student_financial_aid sfa
                LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                ORDER BY sfa.created_at DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.aid_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing financial aid: {e}")
