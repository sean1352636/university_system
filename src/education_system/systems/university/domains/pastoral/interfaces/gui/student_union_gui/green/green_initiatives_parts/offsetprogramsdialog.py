"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class OffsetProgramsDialog:
    """Dialog for managing carbon offset programs."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.windows.carbon_offset_programs', default="Carbon Offset Programs"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_offsets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.carbon_offset_programs', default="Carbon Offset Programs"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Summary
        self.summary_label = ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.loading_summary', default="Loading summary..."),
                                        font=('Arial', 11))
        self.summary_label.pack(pady=(0, 10))

        # Add offset form
        form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.register_offset_purchase', default="Register Offset Purchase"))
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.program_name', default="Program Name:")).pack(side='left')
        self.prog_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.prog_var, width=30).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.offset_kg_co2', default="Offset (kg CO2):")).pack(side='left', padx=(10, 0))
        self.offset_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.offset_var, width=10).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.cost', default="Cost:")).pack(side='left', padx=(10, 0))
        self.cost_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.cost_var, width=10).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.description', default="Description:")).pack(side='left')
        self.desc_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.desc_var, width=55).pack(side='left', padx=5, fill='x', expand=True)

        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.status', default="Status:")).pack(side='left', padx=(10, 0))
        self.status_var = tk.StringVar(value=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.values.purchased', default="purchased"))
        ttk.Combobox(row2, textvariable=self.status_var, width=12,
                      values=["pending", "purchased", "verified", "retired"],
                      state='readonly').pack(side='left', padx=5)

        ttk.Button(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.buttons.save', default="Save"), command=self.save_offset).pack(side='right', padx=5)

        # Offsets list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.labels.offset_records', default="Offset Records"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Program', 'Description', 'Offset (kg)', 'Cost', 'Status', 'Date')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110)
        self.tree.column('ID', width=40)
        self.tree.column('Program', width=160)
        self.tree.column('Description', width=180)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.buttons.refresh', default="Refresh"), command=self.load_offsets).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.buttons.delete_selected', default="Delete Selected"), command=self.delete_offset).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def load_offsets(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT offset_id, program_name, description, offset_kg,
                       cost, status, purchase_date
                FROM carbon_offsets ORDER BY purchase_date DESC
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['offset_id'], r['program_name'], r['description'] or '',
                    f"{r['offset_kg']:.1f}", f"{r['cost']:.2f}",
                    r['status'], r['purchase_date'] or ''
                ))

            # Update summary
            cursor.execute('''
                SELECT COALESCE(SUM(offset_kg), 0) as total_offset,
                       COALESCE(SUM(cost), 0) as total_cost,
                       COUNT(*) as cnt
                FROM carbon_offsets
            ''')
            s = cursor.fetchone()
            self.summary_label.config(
                text=f"Total offset programs: {s['cnt']}  |  "
                     f"Total CO2 offset: {s['total_offset']:,.1f} kg  |  "
                     f"Total invested: {s['total_cost']:,.2f}")
            conn.close()
        except Exception as e:
            logger.error(f"Error loading offsets: {e}")
            self.summary_label.config(text=f"Error loading data: {e}")

    def save_offset(self):
        prog = self.prog_var.get().strip()
        if not prog:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.please_enter_a_program_name', default="Please enter a program name."))
            return
        try:
            offset_kg = float(self.offset_var.get() or 0)
            cost = float(self.cost_var.get() or 0)
        except ValueError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.please_enter_valid_numbers', default="Please enter valid numbers."))
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO carbon_offsets
                    (program_name, description, offset_kg, cost, status,
                     purchased_by, purchase_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                prog,
                self.desc_var.get().strip(),
                offset_kg,
                cost,
                self.status_var.get(),
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.success', default="Success"),
                                f"Offset record saved: {offset_kg:.1f} kg CO2 via '{prog}'.")
            self.prog_var.set('')
            self.desc_var.set('')
            self.offset_var.set('0')
            self.cost_var.set('0')
            self.load_offsets()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.error', default="Error"), f"Failed to save: {e}")

    def delete_offset(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.selection', default="Selection"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.please_select_an_offset_record_to_delete', default="Please select an offset record to delete."))
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.confirm', default="Confirm"), f"Delete offset record '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM carbon_offsets WHERE offset_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_offsets()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.offsetprogramsdialog.dialogs.error', default="Error"), f"Failed to delete: {e}")
