"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class GreenInitiativesDialog:
    """Main dialog for green initiatives and sustainability"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.windows.green_initiatives', default="Green Initiatives"))
        self.dialog.geometry("1000x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_initiatives()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.green_initiatives_sustainability', default="Green Initiatives & Sustainability"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Top button bar for sub-dialogs
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill='x', pady=(0, 10))

        buttons = [
            ("Carbon Tracking", self.carbon_tracking),
            ("Waste Reduction", self.waste_reduction),
            ("Green Transport", self.green_transport),
            ("Env. Reports", self.environmental_reports),
            ("Eco Suppliers", self.eco_suppliers),
            ("Certifications", self.green_certifications),
            ("Offset Programs", self.offset_programs),
        ]
        for text, cmd in buttons:
            ttk.Button(nav_frame, text=text, command=cmd).pack(side='left', padx=3)

        # -- New initiative form --
        form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.create_new_initiative', default="Create New Initiative"))
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.title', default="Title:")).pack(side='left')
        self.title_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.title_var, width=40).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.category', default="Category:")).pack(side='left', padx=(10, 0))
        self.category_var = tk.StringVar()
        cat_combo = ttk.Combobox(row1, textvariable=self.category_var, width=20,
                                  values=["Carbon Reduction", "Waste Management",
                                          "Transport", "Energy", "Biodiversity", "Other"])
        cat_combo.pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.description', default="Description:")).pack(side='left')
        self.desc_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.desc_var, width=70).pack(side='left', padx=5, fill='x', expand=True)

        row3 = ttk.Frame(form_frame)
        row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.target_date_yyyy_mm_dd', default="Target Date (YYYY-MM-DD):")).pack(side='left')
        self.target_date_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.target_date_var, width=15).pack(side='left', padx=5)

        ttk.Label(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.carbon_target_kg_co2', default="Carbon Target (kg CO2):")).pack(side='left', padx=(10, 0))
        self.carbon_target_var = tk.StringVar(value="0")
        ttk.Entry(row3, textvariable=self.carbon_target_var, width=10).pack(side='left', padx=5)

        ttk.Button(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.buttons.save_initiative', default="Save Initiative"), command=self.save_initiative).pack(side='right', padx=5)

        # -- Initiatives list --
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.labels.current_initiatives', default="Current Initiatives"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Title', 'Category', 'Status', 'Target Date', 'Carbon Target', 'Created')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.column('ID', width=40)
        self.tree.column('Title', width=200)
        self.tree.column('Category', width=130)
        self.tree.column('Status', width=80)
        self.tree.column('Target Date', width=100)
        self.tree.column('Carbon Target', width=100)
        self.tree.column('Created', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.buttons.refresh', default="Refresh"), command=self.load_initiatives).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.buttons.delete_selected', default="Delete Selected"), command=self.delete_initiative).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def load_initiatives(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT initiative_id, title, category, status, target_date,
                       carbon_target, created_date
                FROM green_initiatives ORDER BY created_date DESC
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['initiative_id'], r['title'], r['category'] or '',
                    r['status'], r['target_date'] or '', r['carbon_target'] or 0,
                    r['created_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading initiatives: {e}")

    def save_initiative(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.please_enter_a_title', default="Please enter a title."))
            return
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO green_initiatives
                    (title, description, category, status, created_by, created_date,
                     target_date, carbon_target)
                VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
            ''', (
                title,
                self.desc_var.get().strip(),
                self.category_var.get().strip() or 'Other',
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                self.target_date_var.get().strip() or None,
                float(self.carbon_target_var.get() or 0),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.success', default="Success"), f"Initiative '{title}' created.")
            self.title_var.set('')
            self.desc_var.set('')
            self.category_var.set('')
            self.target_date_var.set('')
            self.carbon_target_var.set('0')
            self.load_initiatives()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.error', default="Error"), f"Failed to save initiative: {e}")

    def delete_initiative(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.selection', default="Selection"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.please_select_an_initiative_to_delete', default="Please select an initiative to delete."))
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.confirm', default="Confirm"), f"Delete initiative '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM green_initiatives WHERE initiative_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_initiatives()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greeninitiativesdialog.dialogs.error', default="Error"), f"Failed to delete: {e}")

    # --- Sub-dialog launchers ---

    def carbon_tracking(self):
        dialog = CarbonTrackingDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def sustainable_events(self):
        dialog = SustainableEventsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def waste_reduction(self):
        dialog = WasteReductionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def green_transport(self):
        dialog = GreenTransportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def environmental_reports(self):
        dialog = EnvironmentalReportsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def eco_suppliers(self):
        dialog = EcoSuppliersDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def green_certifications(self):
        dialog = GreenCertificationsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def offset_programs(self):
        dialog = OffsetProgramsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
