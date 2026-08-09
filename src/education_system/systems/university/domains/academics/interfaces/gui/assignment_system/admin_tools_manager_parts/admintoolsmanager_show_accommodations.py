"""Methods show_accommodations through _edit_selected_ta_permissions."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsManager:
    def show_accommodations(self):
        """Manage student accessibility accommodations"""
        if not self._check_permission('manage_accommodations'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.you_do_not_have_permission_to_manage_accommodations', default="You do not have permission to manage accommodations."))
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.student_accommodations', default="Student Accommodations"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.add_accommodation', default="Add Accommodation"), command=lambda: self.add_accommodation(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.refresh', default="Refresh"), command=self.show_accommodations).pack(side='left', padx=5)

        # Filter
        filter_frame = ttk.LabelFrame(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.filters', default="Filters"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.student_id', default="Student ID:")).pack(side='left', padx=(0, 5))
        self.accom_student_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.accom_student_var, width=15).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.active_only', default="Active Only:")).pack(side='left', padx=(15, 5))
        self.accom_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, variable=self.accom_active_var).pack(side='left', padx=5)

        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.search', default="Search"), command=self._load_accommodations).pack(side='left', padx=15)

        # Accommodations treeview
        accom_frame = ttk.Frame(content)
        accom_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Student', 'Type', 'Details', 'Time Mult.', 'Active', 'Approved By', 'Expires')
        self.accom_tree = ttk.Treeview(accom_frame, columns=columns, show='headings', height=14)

        col_widths = {'ID': 40, 'Student': 90, 'Type': 110, 'Details': 180,
                      'Time Mult.': 75, 'Active': 55, 'Approved By': 100, 'Expires': 100}
        for col in columns:
            self.accom_tree.heading(col, text=col)
            self.accom_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(accom_frame, orient='vertical', command=self.accom_tree.yview)
        self.accom_tree.configure(yscrollcommand=scrollbar.set)
        self.accom_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Double-click to edit
        self.accom_tree.bind('<Double-1>', lambda e: self._on_accommodation_double_click())

        # Bottom buttons
        bottom_frame = ttk.Frame(content)
        bottom_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(bottom_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.deactivate_selected', default="Deactivate Selected"), command=self._deactivate_accommodation).pack(side='left', padx=5)

        self._load_accommodations()

    def _load_accommodations(self):
        """Load accommodations into treeview"""
        for item in self.accom_tree.get_children():
            self.accom_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, student_id, accommodation_type, details, time_multiplier,
                       is_active, approved_by, expires_at
                FROM student_accommodations WHERE 1=1
            '''
            params = []

            student_filter = self.accom_student_var.get().strip()
            if student_filter:
                query += ' AND student_id = ?'
                params.append(student_filter)

            if self.accom_active_var.get():
                query += ' AND is_active = 1'

            query += ' ORDER BY created_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                display_row = list(row)
                display_row[5] = 'Yes' if display_row[5] else 'No'
                self.accom_tree.insert('', 'end', values=display_row)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), f"Failed to load accommodations: {e}")

    def _on_accommodation_double_click(self):
        """Handle double-click on accommodation row"""
        selection = self.accom_tree.selection()
        if selection:
            values = self.accom_tree.item(selection[0], 'values')
            if values:
                self.add_accommodation(values[1])

    def _deactivate_accommodation(self):
        """Deactivate the selected accommodation"""
        selection = self.accom_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.no_accommodation_selected', default="No accommodation selected."))
            return

        values = self.accom_tree.item(selection[0], 'values')
        accom_id = values[0]

        if not messagebox.askyesno(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.confirm', default="Confirm"), f"Deactivate accommodation #{accom_id}?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('UPDATE student_accommodations SET is_active = 0 WHERE id = ?', (accom_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.accommodation_deactivated', default="Accommodation deactivated."))
            self._load_accommodations()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), f"Failed to deactivate: {e}")

    def add_accommodation(self, student_id):
        """Add accommodation for a student"""
        if not self._check_permission('manage_accommodations'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.you_do_not_have_permission_to_manage_accommodations', default="You do not have permission to manage accommodations."))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.windows.add_student_accommodation', default="Add Student Accommodation"))
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.add_accommodation', default="Add Accommodation"), style='Title.TLabel').pack(anchor='w', pady=(0, 15))

        # Student ID
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.student_id', default="Student ID:")).pack(anchor='w', pady=(5, 2))
        student_var = tk.StringVar(value=student_id or '')
        ttk.Entry(main_frame, textvariable=student_var, width=40).pack(anchor='w')

        # Accommodation type
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.accommodation_type', default="Accommodation Type:")).pack(anchor='w', pady=(10, 2))
        type_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.values.extended_time', default='extended_time'))
        ttk.Combobox(main_frame, textvariable=type_var,
                     values=['extended_time', 'alt_format', 'screen_reader', 'large_text', 'other'],
                     state='readonly', width=37).pack(anchor='w')

        # Details
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.details', default="Details:")).pack(anchor='w', pady=(10, 2))
        details_text = scrolledtext.ScrolledText(main_frame, width=50, height=5)
        details_text.pack(anchor='w')

        # Time multiplier
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.time_multiplier_e_g_1_5_for_50_extra', default="Time Multiplier (e.g. 1.5 for 50% extra):")).pack(anchor='w', pady=(10, 2))
        multiplier_var = tk.StringVar(value='1.0')
        ttk.Entry(main_frame, textvariable=multiplier_var, width=10).pack(anchor='w')

        # Expires at
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.expires_yyyy_mm_dd_leave_blank_for_no_expiry', default="Expires (YYYY-MM-DD, leave blank for no expiry):")).pack(anchor='w', pady=(10, 2))
        expires_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=expires_var, width=20).pack(anchor='w')

        def save_accommodation():
            sid = student_var.get().strip()
            if not sid:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.student_id_is_required', default="Student ID is required."), parent=dialog)
                return

            try:
                time_mult = float(multiplier_var.get().strip())
            except ValueError:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.time_multiplier_must_be_a_number', default="Time multiplier must be a number."), parent=dialog)
                return

            expires = expires_var.get().strip() or None
            if expires:
                try:
                    datetime.strptime(expires, '%Y-%m-%d')
                except ValueError:
                    messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.expiry_date_must_be_yyyy_mm_dd', default="Expiry date must be YYYY-MM-DD."), parent=dialog)
                    return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                current_user = getattr(self.auth, 'current_user', {})
                approved_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

                cursor.execute('''
                    INSERT INTO student_accommodations
                    (student_id, accommodation_type, details, time_multiplier, is_active, approved_by, expires_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                ''', (sid, type_var.get(), details_text.get('1.0', 'end').strip(),
                      time_mult, approved_by, expires))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.accommodation_added', default="Accommodation added."), parent=dialog)
                dialog.destroy()
                self.show_accommodations()

            except Exception as e:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), f"Failed to add accommodation: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.save', default="Save"), command=save_accommodation).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def show_ta_management(self):
        """Unified TA/co-instructor management with assignments, permissions, and evaluation"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.you_do_not_have_permission_to_manage_ta_assignments', default="You do not have permission to manage TA assignments."))
            return

        self._ensure_ta_evaluation_table()

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.teaching_assistant_management', default="Teaching Assistant Management"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Tabbed notebook for TA features
        notebook = ttk.Notebook(content)
        notebook.pack(fill='both', expand=True)

        # ── Tab 1: TA Assignments ──
        assign_frame = ttk.Frame(notebook)
        notebook.add(assign_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.tabs.ta_assignments', default="TA Assignments"))
        self._build_ta_assignments_tab(assign_frame)

        # ── Tab 2: Permissions ──
        perm_frame = ttk.Frame(notebook)
        notebook.add(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.tabs.permissions', default="Permissions"))
        self._build_ta_permissions_tab(perm_frame)

        # ── Tab 3: Performance Evaluation ──
        eval_frame = ttk.Frame(notebook)
        notebook.add(eval_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.tabs.performance_evaluation', default="Performance Evaluation"))
        self._build_ta_evaluation_tab(eval_frame)

    def _ensure_ta_evaluation_table(self):
        """Ensure ta_evaluations table exists"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ta_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ta_id TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    evaluation_period TEXT,
                    hours_logged REAL DEFAULT 0,
                    avg_grading_turnaround_days REAL DEFAULT 0,
                    submissions_graded INTEGER DEFAULT 0,
                    feedback_score REAL,
                    evaluator_id TEXT,
                    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _build_ta_assignments_tab(self, parent):
        """Build the TA assignments management tab"""
        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.assign_ta', default="Assign TA"), command=lambda: self.assign_ta(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.view_workload', default="View Workload"), command=self._view_ta_workload).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.refresh', default="Refresh"), command=self._load_ta_assignments).pack(side='right', padx=5)

        # Filter bar
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=10, pady=(0, 5))

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.module', default="Module:")).pack(side='left', padx=(0, 5))
        self.ta_module_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.ta_module_var, width=15).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.role', default="Role:")).pack(side='left', padx=(15, 5))
        self.ta_role_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.values.all', default='all'))
        ttk.Combobox(filter_frame, textvariable=self.ta_role_var,
                     values=['all', 'ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=15).pack(side='left', padx=5)

        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.search', default="Search"), command=self._load_ta_assignments).pack(side='left', padx=15)
        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.clear', default="Clear"), command=self._clear_ta_filter).pack(side='left', padx=5)

        # TA assignments treeview
        ta_frame = ttk.Frame(parent)
        ta_frame.pack(fill='both', expand=True, padx=10)

        columns = ('ID', 'User', 'Section', 'Module', 'Role', 'Hours/Wk',
                   'Grade', 'Create', 'Analytics', 'Assigned By', 'Date')
        self.ta_tree = ttk.Treeview(ta_frame, columns=columns, show='headings', height=12)

        col_widths = {'ID': 35, 'User': 80, 'Section': 70, 'Module': 75, 'Role': 85,
                      'Hours/Wk': 65, 'Grade': 45, 'Create': 50, 'Analytics': 60,
                      'Assigned By': 90, 'Date': 110}
        for col in columns:
            self.ta_tree.heading(col, text=col)
            self.ta_tree.column(col, width=col_widths.get(col, 70))

        scrollbar = ttk.Scrollbar(ta_frame, orient='vertical', command=self.ta_tree.yview)
        self.ta_tree.configure(yscrollcommand=scrollbar.set)
        self.ta_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.ta_tree.bind('<Double-1>', lambda e: self._on_ta_double_click())

        # Bottom buttons
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Button(bottom_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.edit_permissions', default="Edit Permissions"), command=self._edit_selected_ta_permissions).pack(side='left', padx=5)
        ttk.Button(bottom_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.remove_assignment', default="Remove Assignment"), command=self._remove_ta_assignment).pack(side='left', padx=5)

        self._load_ta_assignments()

    def _clear_ta_filter(self):
        """Clear TA filter and reload"""
        self.ta_module_var.set('')
        self.ta_role_var.set('all')
        self._load_ta_assignments()

    def _load_ta_assignments(self):
        """Load TA assignments into treeview"""
        for item in self.ta_tree.get_children():
            self.ta_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, user_id, section_id, module_code, role,
                       COALESCE(hours_per_week, 0),
                       can_grade, can_create_assignments, can_view_analytics,
                       assigned_by, assigned_at
                FROM ta_assignments WHERE 1=1
            '''
            params = []

            module_filter = self.ta_module_var.get().strip()
            if module_filter:
                query += ' AND module_code LIKE ?'
                params.append(f'%{module_filter}%')

            role_filter = self.ta_role_var.get()
            if role_filter != 'all':
                query += ' AND role = ?'
                params.append(role_filter)

            query += ' ORDER BY assigned_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                display_row = list(row)
                display_row[6] = 'Yes' if display_row[6] else 'No'
                display_row[7] = 'Yes' if display_row[7] else 'No'
                display_row[8] = 'Yes' if display_row[8] else 'No'
                self.ta_tree.insert('', 'end', values=display_row)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), f"Failed to load TA assignments: {e}")

    def _on_ta_double_click(self):
        """Handle double-click on TA assignment"""
        selection = self.ta_tree.selection()
        if selection:
            values = self.ta_tree.item(selection[0], 'values')
            if values:
                self.configure_ta_permissions(values[0])

    def _edit_selected_ta_permissions(self):
        """Edit permissions for selected TA"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.no_ta_assignment_selected', default="No TA assignment selected."))
            return
        values = self.ta_tree.item(selection[0], 'values')
        if values:
            self.configure_ta_permissions(values[0])
