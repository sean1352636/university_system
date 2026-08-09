"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EcoSuppliersDialog:
    """Dialog for managing eco-friendly suppliers."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.windows.eco_suppliers_directory', default="Eco Suppliers Directory"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_suppliers()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.eco_friendly_supplier_directory', default="Eco-Friendly Supplier Directory"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Add supplier form
        form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.add_new_supplier', default="Add New Supplier"))
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.name', default="Name:")).pack(side='left')
        self.name_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.name_var, width=30).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.category', default="Category:")).pack(side='left', padx=(10, 0))
        self.cat_var = tk.StringVar()
        ttk.Combobox(row1, textvariable=self.cat_var, width=20,
                      values=["Catering", "Venues", "Equipment", "Transport",
                              "Printing", "Energy", "Other"]).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.rating_1_5', default="Rating (1-5):")).pack(side='left', padx=(10, 0))
        self.rating_var = tk.StringVar(value="4")
        ttk.Entry(row1, textvariable=self.rating_var, width=5).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.contact_email', default="Contact Email:")).pack(side='left')
        self.email_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.email_var, width=30).pack(side='left', padx=5)

        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.certifications', default="Certifications:")).pack(side='left', padx=(10, 0))
        self.certs_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.certs_var, width=30).pack(side='left', padx=5)

        row3 = ttk.Frame(form_frame)
        row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.description', default="Description:")).pack(side='left')
        self.desc_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.desc_var, width=60).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.buttons.add_supplier', default="Add Supplier"), command=self.add_supplier).pack(side='right', padx=5)

        # Supplier list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.labels.registered_suppliers', default="Registered Suppliers"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Category', 'Certifications', 'Email', 'Rating', 'Added')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110)
        self.tree.column('ID', width=40)
        self.tree.column('Name', width=160)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.buttons.refresh', default="Refresh"), command=self.load_suppliers).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.buttons.delete_selected', default="Delete Selected"), command=self.delete_supplier).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def load_suppliers(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT supplier_id, name, category, certifications,
                       contact_email, rating, added_date
                FROM eco_suppliers ORDER BY name
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['supplier_id'], r['name'], r['category'] or '',
                    r['certifications'] or '', r['contact_email'] or '',
                    f"{r['rating']:.1f}" if r['rating'] else '',
                    r['added_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading suppliers: {e}")

    def add_supplier(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.please_enter_a_supplier_name', default="Please enter a supplier name."))
            return
        try:
            rating = float(self.rating_var.get() or 0)
            rating = max(0, min(5, rating))
        except ValueError:
            rating = 0

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO eco_suppliers
                    (name, category, certifications, description,
                     contact_email, rating, added_by, added_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                self.cat_var.get().strip() or 'Other',
                self.certs_var.get().strip(),
                self.desc_var.get().strip(),
                self.email_var.get().strip(),
                rating,
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.success', default="Success"), f"Supplier '{name}' added.")
            self.name_var.set('')
            self.cat_var.set('')
            self.certs_var.set('')
            self.desc_var.set('')
            self.email_var.set('')
            self.rating_var.set('4')
            self.load_suppliers()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.error', default="Error"), f"Failed to add supplier: {e}")

    def delete_supplier(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.selection', default="Selection"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.please_select_a_supplier_to_delete', default="Please select a supplier to delete."))
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.confirm', default="Confirm"), f"Delete supplier '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM eco_suppliers WHERE supplier_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_suppliers()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.ecosuppliersdialog.dialogs.error', default="Error"), f"Failed to delete: {e}")
