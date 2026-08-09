"""Methods _load_integrity_cases through _clear_audit_filters."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsManager:
    def _load_integrity_cases(self):
        """Load integrity cases into treeview with current filters"""
        for item in self.integrity_tree.get_children():
            self.integrity_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, student_id, assignment_id, case_type, status, created_at, outcome
                FROM integrity_cases WHERE 1=1
            '''
            params = []

            status_filter = self.integrity_status_var.get()
            if status_filter != 'all':
                query += ' AND status = ?'
                params.append(status_filter)

            type_filter = self.integrity_type_var.get()
            if type_filter != 'all':
                query += ' AND case_type = ?'
                params.append(type_filter)

            query += ' ORDER BY created_at DESC LIMIT 100'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                self.integrity_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Failed to load integrity cases: {e}")

    def _on_integrity_case_double_click(self):
        """Handle double-click on integrity case"""
        selection = self.integrity_tree.selection()
        if selection:
            values = self.integrity_tree.item(selection[0], 'values')
            if values:
                self.review_integrity_case(values[0])

    def create_integrity_case(self):
        """Form to create new integrity case"""
        if not self._check_permission('manage_integrity'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.you_do_not_have_permission_to_create_integrity_cases', default="You do not have permission to create integrity cases."))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.windows.new_academic_integrity_case', default="New Academic Integrity Case"))
        dialog.geometry("550x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.new_integrity_case', default="New Integrity Case"), style='Title.TLabel').pack(anchor='w', pady=(0, 15))

        # Student ID
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.student_id', default="Student ID:")).pack(anchor='w', pady=(5, 2))
        student_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=student_var, width=40).pack(anchor='w')

        # Assignment ID
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.assignment_id_optional', default="Assignment ID (optional):")).pack(anchor='w', pady=(10, 2))
        assignment_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=assignment_var, width=40).pack(anchor='w')

        # Case type
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.case_type', default="Case Type:")).pack(anchor='w', pady=(10, 2))
        type_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.values.plagiarism', default='plagiarism'))
        ttk.Combobox(main_frame, textvariable=type_var,
                     values=['plagiarism', 'cheating', 'collusion', 'other'],
                     state='readonly', width=37).pack(anchor='w')

        # Description
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.description', default="Description:")).pack(anchor='w', pady=(10, 2))
        desc_text = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        desc_text.pack(anchor='w')

        # Evidence path
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.evidence_file_optional', default="Evidence File (optional):")).pack(anchor='w', pady=(10, 2))
        evidence_frame = ttk.Frame(main_frame)
        evidence_frame.pack(anchor='w', fill='x')
        evidence_var = tk.StringVar()
        ttk.Entry(evidence_frame, textvariable=evidence_var, width=35).pack(side='left')

        def browse_evidence():
            path = filedialog.askopenfilename(title=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.select_evidence_file', default="Select Evidence File"))
            if path:
                evidence_var.set(path)

        ttk.Button(evidence_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.browse', default="Browse"), command=browse_evidence).pack(side='left', padx=5)

        def save_case():
            student_id = student_var.get().strip()
            if not student_id:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.student_id_is_required', default="Student ID is required."), parent=dialog)
                return

            description = desc_text.get('1.0', 'end').strip()
            if not description:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.description_is_required', default="Description is required."), parent=dialog)
                return

            assignment_id = assignment_var.get().strip() or None
            if assignment_id:
                try:
                    assignment_id = int(assignment_id)
                except ValueError:
                    messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.assignment_id_must_be_a_number', default="Assignment ID must be a number."), parent=dialog)
                    return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                current_user = getattr(self.auth, 'current_user', {})
                created_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

                cursor.execute('''
                    INSERT INTO integrity_cases
                    (student_id, assignment_id, case_type, description, evidence_path, status, created_by)
                    VALUES (?, ?, ?, ?, ?, 'open', ?)
                ''', (student_id, assignment_id, type_var.get(), description,
                      evidence_var.get().strip() or None, created_by))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.integrity_case_created', default="Integrity case created."), parent=dialog)
                dialog.destroy()
                self.show_integrity_cases()

            except Exception as e:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Failed to create case: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.save_case', default="Save Case"), command=save_case).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def review_integrity_case(self, case_id):
        """Review/update an integrity case"""
        if not self._check_permission('manage_integrity'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.you_do_not_have_permission_to_review_integrity_cases', default="You do not have permission to review integrity cases."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM integrity_cases WHERE id = ?', (case_id,))
            case = cursor.fetchone()
            col_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not case:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Case {case_id} not found.")
                return

            case_data = dict(zip(col_names, case))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Failed to load case: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Integrity Case #{case_id}")
        dialog.geometry("550x650")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Case #{case_id}", style='Title.TLabel').pack(anchor='w', pady=(0, 15))

        # Info display
        info_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.case_details', default="Case Details"), padding=10)
        info_frame.pack(fill='x', pady=(0, 15))

        details = [
            ("Student ID", case_data.get('student_id', '')),
            ("Assignment ID", case_data.get('assignment_id', 'N/A')),
            ("Type", case_data.get('case_type', '')),
            ("Created By", case_data.get('created_by', '')),
            ("Created At", case_data.get('created_at', '')),
        ]
        for label, value in details:
            row = ttk.Frame(info_frame)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=f"{label}:", width=15, anchor='w').pack(side='left')
            ttk.Label(row, text=str(value)).pack(side='left')

        # Description (read-only)
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.description', default="Description:")).pack(anchor='w', pady=(5, 2))
        desc_text = scrolledtext.ScrolledText(main_frame, width=55, height=5)
        desc_text.pack(anchor='w')
        desc_text.insert('1.0', case_data.get('description', ''))
        desc_text.configure(state='disabled')

        # Evidence path
        evidence = case_data.get('evidence_path', '')
        if evidence:
            ttk.Label(main_frame, text=f"Evidence: {evidence}").pack(anchor='w', pady=(5, 0))

        # Editable fields
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.status', default="Status:")).pack(anchor='w', pady=(15, 2))
        status_var = tk.StringVar(value=case_data.get('status', 'open'))
        ttk.Combobox(main_frame, textvariable=status_var,
                     values=['open', 'investigating', 'resolved', 'dismissed'],
                     state='readonly', width=37).pack(anchor='w')

        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.outcome', default="Outcome:")).pack(anchor='w', pady=(10, 2))
        outcome_var = tk.StringVar(value=case_data.get('outcome', '') or '')
        ttk.Entry(main_frame, textvariable=outcome_var, width=40).pack(anchor='w')

        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.penalty', default="Penalty:")).pack(anchor='w', pady=(10, 2))
        penalty_var = tk.StringVar(value=case_data.get('penalty', '') or '')
        ttk.Entry(main_frame, textvariable=penalty_var, width=40).pack(anchor='w')

        def update_case():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                resolved_at = None
                if status_var.get() in ('resolved', 'dismissed') and case_data.get('status') not in ('resolved', 'dismissed'):
                    resolved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE integrity_cases
                    SET status = ?, outcome = ?, penalty = ?, resolved_at = COALESCE(?, resolved_at)
                    WHERE id = ?
                ''', (status_var.get(), outcome_var.get().strip() or None,
                      penalty_var.get().strip() or None, resolved_at, case_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.case_updated', default="Case updated."), parent=dialog)
                dialog.destroy()
                self.show_integrity_cases()

            except Exception as e:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Failed to update case: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.update_case', default="Update Case"), command=update_case).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.close', default="Close"), command=dialog.destroy).pack(side='left', padx=5)

    def show_grade_audit_log(self):
        """View grade change audit trail with filters"""
        if not self._check_permission('view_audit_log'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.you_do_not_have_permission_to_view_the_audit_log', default="You do not have permission to view the audit log."))
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.grade_change_audit_log', default="Grade Change Audit Log"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filters
        filter_frame = ttk.LabelFrame(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.filters', default="Filters"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.student_id', default="Student ID:")).pack(side='left', padx=(0, 5))
        self.audit_student_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_student_var, width=15).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.assignment_id', default="Assignment ID:")).pack(side='left', padx=(15, 5))
        self.audit_assignment_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_assignment_var, width=10).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.changed_by', default="Changed By:")).pack(side='left', padx=(15, 5))
        self.audit_changed_by_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_changed_by_var, width=15).pack(side='left', padx=5)

        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.search', default="Search"), command=self._load_audit_log).pack(side='left', padx=15)
        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.clear', default="Clear"), command=self._clear_audit_filters).pack(side='left', padx=5)

        # Audit log treeview
        log_frame = ttk.Frame(content)
        log_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Submission', 'Student', 'Assignment', 'Old Grade', 'New Grade', 'Changed By', 'Reason', 'Date')
        self.audit_tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=16)

        col_widths = {'ID': 40, 'Submission': 80, 'Student': 90, 'Assignment': 80,
                      'Old Grade': 75, 'New Grade': 75, 'Changed By': 100, 'Reason': 160, 'Date': 140}
        for col in columns:
            self.audit_tree.heading(col, text=col)
            self.audit_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=scrollbar.set)
        self.audit_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self._load_audit_log()

    def _load_audit_log(self):
        """Load audit log entries with current filters"""
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, submission_id, student_id, assignment_id,
                       old_grade, new_grade, changed_by, reason, changed_at
                FROM grade_audit_log WHERE 1=1
            '''
            params = []

            student_filter = self.audit_student_var.get().strip()
            if student_filter:
                query += ' AND student_id = ?'
                params.append(student_filter)

            assignment_filter = self.audit_assignment_var.get().strip()
            if assignment_filter:
                query += ' AND assignment_id = ?'
                params.append(assignment_filter)

            changed_by_filter = self.audit_changed_by_var.get().strip()
            if changed_by_filter:
                query += ' AND changed_by LIKE ?'
                params.append(f'%{changed_by_filter}%')

            query += ' ORDER BY changed_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                self.audit_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Failed to load audit log: {e}")

    def _clear_audit_filters(self):
        """Clear audit log filters and reload"""
        self.audit_student_var.set('')
        self.audit_assignment_var.set('')
        self.audit_changed_by_var.set('')
        self._load_audit_log()
