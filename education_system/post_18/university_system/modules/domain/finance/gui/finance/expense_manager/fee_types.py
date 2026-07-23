"""Fee type CRUD and fees tab UI"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from education_system.post_18.university_system.core.i18n import get_text as _

from education_system.post_18.university_system.infrastructure.database.db import get_connection


class FeeTypesMixin:
    """Fee type management methods"""

    def create_fees_tab(self):
        """Create fees management tab"""
        fees_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['fees'] = fees_frame

        # Create fees interface
        main_container = tk.PanedWindow(fees_frame, orient='horizontal')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Left panel - Fee Types
        left_panel = tk.Frame(main_container, bg='white', relief='sunken', bd=2)
        main_container.add(left_panel, minsize=300)

        tk.Label(left_panel, text=_("expense_manager.labels.fee_types"), font=('Arial', 14, 'bold'), bg='white').pack(pady=10)

        # Fee types listbox
        self.fee_types_listbox = tk.Listbox(left_panel, font=('Arial', 9))
        self.fee_types_listbox.pack(fill='both', expand=True, padx=10, pady=5)
        self.fee_types_listbox.bind('<Double-1>', self.edit_fee_type)

        # Fee type buttons
        fee_btn_frame = tk.Frame(left_panel, bg='white')
        fee_btn_frame.pack(fill='x', padx=10, pady=5)

        tk.Button(fee_btn_frame, text=_("expense_manager.buttons.add_fee_type"), command=self.add_fee_type,
                 bg=self.colors['success'], fg='white').pack(side='left', padx=2)
        tk.Button(fee_btn_frame, text=_("expense_manager.buttons.edit"), command=self.edit_fee_type,
                 bg=self.colors['warning'], fg='white').pack(side='left', padx=2)
        tk.Button(fee_btn_frame, text=_("expense_manager.buttons.delete"), command=self.delete_fee_type,
                 bg=self.colors['danger'], fg='white').pack(side='left', padx=2)

        # Right panel - Student Fees
        right_panel = tk.Frame(main_container, bg='white', relief='sunken', bd=2)
        main_container.add(right_panel, minsize=400)

        tk.Label(right_panel, text=_("expense_manager.labels.student_fees"), font=('Arial', 14, 'bold'), bg='white').pack(pady=10)

        # Student fees toolbar
        fees_toolbar = tk.Frame(right_panel, bg='white')
        fees_toolbar.pack(fill='x', padx=10, pady=5)

        tk.Button(fees_toolbar, text=_("expense_manager.buttons.assign_fee"), command=self.assign_fee_to_student,
                 bg=self.colors['secondary'], fg='white').pack(side='left', padx=2)
        tk.Button(fees_toolbar, text=_("expense_manager.buttons.bulk_assign"), command=self.bulk_assign_fees,
                 bg=self.colors['warning'], fg='white').pack(side='left', padx=2)
        tk.Button(fees_toolbar, text=_("expense_manager.buttons.late_fees"), command=self.calculate_late_fees,
                 bg=self.colors['danger'], fg='white').pack(side='left', padx=2)

        # Student fees table
        self.create_student_fees_table(right_panel)

        # Load fees data
        self.refresh_fees()

    def create_student_fees_table(self, parent):
        """Create student fees table"""
        table_frame = tk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('fee_id', 'student_id', 'fee_type', 'amount', 'due_date', 'status')
        self.student_fees_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

        for col in columns:
            self.student_fees_tree.heading(col, text=col.replace('_', ' ').title())
            self.student_fees_tree.column(col, width=100)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.student_fees_tree.yview)
        self.student_fees_tree.configure(yscrollcommand=v_scroll.set)

        self.student_fees_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')

    def refresh_fees(self):
        """Refresh fees data"""
        def refresh_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get fee types
                cursor.execute("SELECT fee_type_id, fee_name, description FROM fee_types")
                fee_types = cursor.fetchall()

                # Get student fees
                cursor.execute('''
                SELECT sf.student_fee_id, sf.student_id, ft.fee_name, sf.amount, sf.due_date, sf.status
                FROM student_fees sf
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                ORDER BY sf.due_date DESC
                LIMIT 100
                ''')

                student_fees = cursor.fetchall()
                conn.close()

                # Update UI
                self.root.after(0, lambda: self.update_fees_data(fee_types, student_fees))

            except Exception as e:
                print(f"Error refreshing fees: {e}")

        refresh_thread()

    def update_fees_data(self, fee_types, student_fees):
        """Update fees data in UI"""
        # Update fee types listbox
        self.fee_types_listbox.delete(0, tk.END)
        for fee_type_id, name, description in fee_types:
            self.fee_types_listbox.insert(tk.END, f"{name} - {description}")

        # Update student fees table
        for item in self.student_fees_tree.get_children():
            self.student_fees_tree.delete(item)

        for fee in student_fees:
            self.student_fees_tree.insert('', 'end', values=fee)

    def add_fee_type(self):
        """Add new fee type"""
        # Simple fee type dialog using built-in dialogs
        fee_name = simpledialog.askstring(_("expense_manager.dialogs.add_fee_type_title"), _("expense_manager.dialogs.enter_fee_name"))
        if fee_name:
            amount = simpledialog.askfloat(_("expense_manager.dialogs.add_fee_type_title"), _("expense_manager.dialogs.enter_fee_amount"))
            if amount:
                description = simpledialog.askstring(_("expense_manager.dialogs.add_fee_type_title"), _("expense_manager.dialogs.enter_description"), initialvalue="")
                try:
                    # Here you would save the fee type to database
                    messagebox.showinfo(_("common.success"), _("expense_manager.messages.fee_type_added", name=fee_name))
                    self.refresh_fees()
                except Exception as e:
                    messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_add_fee_type", error=e))

    def edit_fee_type(self, event=None):
        """Edit selected fee type"""
        selection = self.fee_types_listbox.curselection()
        if not selection:
            messagebox.showwarning(_("common.no_selection"), _("expense_manager.errors.no_selection"))
            return

        fee_index = selection[0]
        # Get fee type ID and show edit dialog
        messagebox.showinfo(_("expense_manager.dialogs.add_fee_type_title"), _("expense_manager.messages.edit_fee_type_info", index=fee_index))

    def delete_fee_type(self):
        """Delete selected fee type"""
        selection = self.fee_types_listbox.curselection()
        if not selection:
            messagebox.showwarning(_("common.no_selection"), _("expense_manager.errors.no_selection_delete"))
            return

        if messagebox.askyesno(_("common.confirm_delete"), _("expense_manager.dialogs.confirm_delete")):
            # Implement delete logic
            self.refresh_fees()
