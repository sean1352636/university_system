"""Methods _remove_ta_assignment through _send_ta_email."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsManager:
    def _remove_ta_assignment(self):
        """Remove the selected TA assignment with email notification"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.no_ta_assignment_selected', default="No TA assignment selected."))
            return

        values = self.ta_tree.item(selection[0], 'values')
        ta_id = values[0]
        user_id = values[1]
        module_code = values[3]

        if not messagebox.askyesno(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.confirm', default="Confirm"),
                f"Remove TA assignment #{ta_id}?\n\nUser: {user_id}\nModule: {module_code}"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ta_assignments WHERE id = ?', (ta_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.ta_assignment_removed', default="TA assignment removed."))
            self._send_ta_email(user_id, module_code, '', 0, 'removed')
            self._load_ta_assignments()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"Failed to remove assignment: {e}")

    def _view_ta_workload(self):
        """Show workload details for the selected TA"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.select_a_ta_to_view_workload', default="Select a TA to view workload."))
            return

        values = self.ta_tree.item(selection[0], 'values')
        user_id = values[1]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, section_id, module_code, role,
                       COALESCE(hours_per_week, 0) as hours, assigned_at
                FROM ta_assignments WHERE user_id = ?
            ''', (user_id,))
            assignments = cursor.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"Failed to load workload: {e}")
            return

        total_hours = sum(a[4] for a in assignments)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"TA Workload - {user_id}")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)

        summary_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.workload_summary', default="Workload Summary"), padding=10)
        summary_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(summary_frame, text=f"User: {user_id}", font=('Arial', 11)).pack(anchor='w')
        ttk.Label(summary_frame, text=f"Active Assignments: {len(assignments)}", font=('Arial', 11)).pack(anchor='w')
        ttk.Label(summary_frame, text=f"Total Hours/Week: {total_hours}", font=('Arial', 11)).pack(anchor='w')

        if total_hours > 20:
            ttk.Label(summary_frame,
                      text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.warning_exceeds_20_hours_week_across_ta_assignments', default="WARNING: Exceeds 20 hours/week across TA assignments."),
                      foreground='red', font=('Arial', 10, 'bold')).pack(anchor='w', pady=(5, 0))

        if assignments:
            detail_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.assignment_details', default="Assignment Details"), padding=5)
            detail_frame.pack(fill='both', expand=True)

            columns = ('Module', 'Role', 'Hours/Wk', 'Section', 'Assigned')
            detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=8)
            for col in columns:
                detail_tree.heading(col, text=col)
                detail_tree.column(col, width=110)

            for a in assignments:
                detail_tree.insert('', 'end', values=(a[2], a[3], a[4], a[1] or 'N/A', a[5] or ''))

            detail_tree.pack(fill='both', expand=True)

        ttk.Button(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.close', default="Close"), command=dialog.destroy).pack(pady=(10, 0))

    def assign_ta(self, section_id):
        """Assign TA with student/module dropdowns, roles, hours, and permissions"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.you_do_not_have_permission_to_assign_tas', default="You do not have permission to assign TAs."))
            return

        # Fetch students for dropdown
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name")
            students = cursor.fetchall()
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"Failed to load data: {e}")
            return

        student_map = {}
        student_values = []
        for s in students:
            display = f"{s[0]} - {s[1]} {s[2]}"
            student_values.append(display)
            student_map[display] = s[0]

        module_map = {}
        module_values = []
        for m in modules:
            display = f"{m[0]} - {m[1]}"
            module_values.append(display)
            module_map[display] = m[0]

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.windows.assign_teaching_assistant', default="Assign Teaching Assistant"))
        dialog.geometry("480x550")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.assign_ta_co_instructor', default="Assign TA / Co-Instructor"), font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 10))

        # Student dropdown
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.student', default="Student:")).pack(anchor='w', pady=(5, 2))
        student_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=student_var, values=student_values,
                     state='readonly', width=45).pack(anchor='w')

        # Module dropdown
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.module', default="Module:")).pack(anchor='w', pady=(10, 2))
        module_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=module_var, values=module_values,
                     state='readonly', width=45).pack(anchor='w')

        # Section ID
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.section_id_optional', default="Section ID (optional):")).pack(anchor='w', pady=(10, 2))
        section_var = tk.StringVar(value=section_id or '')
        ttk.Entry(main_frame, textvariable=section_var, width=35).pack(anchor='w')

        # Role
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.role', default="Role:")).pack(anchor='w', pady=(10, 2))
        role_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.values.ta', default='ta'))
        ttk.Combobox(main_frame, textvariable=role_var,
                     values=['ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=25).pack(anchor='w')

        # Hours per week
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.hours_week', default="Hours/Week:")).pack(anchor='w', pady=(10, 2))
        hours_var = tk.StringVar(value='10')
        ttk.Entry(main_frame, textvariable=hours_var, width=10).pack(anchor='w')

        # Permissions
        perm_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.permissions', default="Permissions"), padding=10)
        perm_frame.pack(fill='x', pady=(15, 0))

        can_grade_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.can_grade_submissions', default="Can Grade Submissions"), variable=can_grade_var).pack(anchor='w', pady=2)
        can_create_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.can_create_assignments', default="Can Create Assignments"), variable=can_create_var).pack(anchor='w', pady=2)
        can_analytics_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.can_view_analytics', default="Can View Analytics"), variable=can_analytics_var).pack(anchor='w', pady=2)

        def save_assignment():
            student_selection = student_var.get().strip()
            module_selection = module_var.get().strip()

            if not student_selection:
                messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.validation', default="Validation"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.please_select_a_student', default="Please select a student."), parent=dialog)
                return
            if not module_selection:
                messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.validation', default="Validation"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.please_select_a_module', default="Please select a module."), parent=dialog)
                return

            uid = student_map.get(student_selection, '')
            mc = module_map.get(module_selection, '')
            sid = section_var.get().strip() or None

            try:
                hours = float(hours_var.get())
                if hours <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.validation', default="Validation"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.hours_week_must_be_a_positive_number', default="Hours/Week must be a positive number."), parent=dialog)
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                current_user = getattr(self.auth, 'current_user', {})
                assigned_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

                cursor.execute('''
                    INSERT INTO ta_assignments
                    (user_id, section_id, module_code, role, hours_per_week,
                     can_grade, can_create_assignments, can_view_analytics, assigned_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (uid, sid, mc, role_var.get(), hours,
                      int(can_grade_var.get()), int(can_create_var.get()),
                      int(can_analytics_var.get()), assigned_by))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.success', default="Success"), f"TA assigned: {uid} to {mc}", parent=dialog)
                dialog.destroy()
                self._send_ta_email(uid, mc, role_var.get(), hours, 'assigned')
                self._load_ta_assignments()

            except sqlite3.IntegrityError:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.duplicate', default="Duplicate"), f"This student is already a TA for module '{mc}'.", parent=dialog)
            except Exception as e:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"Failed to create assignment: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.assign', default="Assign"), command=save_assignment).pack(side='left', padx=10)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=10)

    def configure_ta_permissions(self, ta_id):
        """Configure TA role and permissions"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.you_do_not_have_permission_to_manage_ta_permissions', default="You do not have permission to manage TA permissions."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ta_assignments WHERE id = ?', (ta_id,))
            ta = cursor.fetchone()
            col_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not ta:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"TA assignment #{ta_id} not found.")
                return

            ta_data = dict(zip(col_names, ta))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"Failed to load TA assignment: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Configure Permissions - TA #{ta_id}")
        dialog.geometry("480x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"TA Permissions - #{ta_id}", font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 15))

        # Info display
        info_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.assignment_details', default="Assignment Details"), padding=10)
        info_frame.pack(fill='x', pady=(0, 15))

        for label, value in [("User", ta_data.get('user_id', '')),
                             ("Section", ta_data.get('section_id', 'N/A')),
                             ("Module", ta_data.get('module_code', 'N/A'))]:
            row = ttk.Frame(info_frame)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=f"{label}:", width=12, anchor='w').pack(side='left')
            ttk.Label(row, text=str(value)).pack(side='left')

        # Role
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.role', default="Role:")).pack(anchor='w', pady=(10, 2))
        role_var = tk.StringVar(value=ta_data.get('role', 'ta'))
        ttk.Combobox(main_frame, textvariable=role_var,
                     values=['ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=25).pack(anchor='w')

        # Hours
        ttk.Label(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.hours_week', default="Hours/Week:")).pack(anchor='w', pady=(10, 2))
        hours_var = tk.StringVar(value=str(ta_data.get('hours_per_week', 0) or 0))
        ttk.Entry(main_frame, textvariable=hours_var, width=10).pack(anchor='w')

        # Permissions
        perm_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.labels.permissions', default="Permissions"), padding=10)
        perm_frame.pack(fill='x', pady=(15, 0))

        can_grade_var = tk.BooleanVar(value=bool(ta_data.get('can_grade', 0)))
        ttk.Checkbutton(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.can_grade_submissions', default="Can Grade Submissions"), variable=can_grade_var).pack(anchor='w', pady=2)

        can_create_var = tk.BooleanVar(value=bool(ta_data.get('can_create_assignments', 0)))
        ttk.Checkbutton(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.can_create_assignments', default="Can Create Assignments"), variable=can_create_var).pack(anchor='w', pady=2)

        can_analytics_var = tk.BooleanVar(value=bool(ta_data.get('can_view_analytics', 0)))
        ttk.Checkbutton(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.can_view_analytics', default="Can View Analytics"), variable=can_analytics_var).pack(anchor='w', pady=2)

        def update_permissions():
            try:
                hours = float(hours_var.get()) if hours_var.get().strip() else 0
            except ValueError:
                messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.validation', default="Validation"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.hours_must_be_a_number', default="Hours must be a number."), parent=dialog)
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ta_assignments
                    SET role = ?, hours_per_week = ?, can_grade = ?,
                        can_create_assignments = ?, can_view_analytics = ?
                    WHERE id = ?
                ''', (role_var.get(), hours, int(can_grade_var.get()),
                      int(can_create_var.get()), int(can_analytics_var.get()), ta_id))
                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.permissions_updated', default="Permissions updated."), parent=dialog)
                dialog.destroy()
                self._load_ta_assignments()

            except Exception as e:
                messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.dialogs.error', default="Error"), f"Failed to update permissions: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.save', default="Save"), command=update_permissions).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_remove_ta_assignment.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def _send_ta_email(self, student_id, module_code, role_type, hours_per_week, action):
        """Email student about TA assignment or removal"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT first_name, last_name, email FROM students WHERE student_id = ?", (student_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT first_name, last_name, email FROM users WHERE username = ?", (student_id,))
                row = cursor.fetchone()
            conn.close()

            if not row or not row[2]:
                return

            name = f"{row[0]} {row[1]}"
            email = row[2]

            if action == 'assigned':
                subject = f"TA Assignment: {module_code}"
                body = (f"Dear {name},\n\nYou have been assigned as a Teaching Assistant:\n\n"
                        f"Module: {module_code}\nRole: {role_type}\nHours per Week: {hours_per_week}\n\n"
                        f"Please contact the module instructor for further details.\n\n"
                        f"Best regards,\nAcademic Administration")
            elif action == 'removed':
                subject = f"TA Assignment Removed: {module_code}"
                body = (f"Dear {name},\n\nYour Teaching Assistant assignment has been removed:\n\n"
                        f"Module: {module_code}\n\nIf you believe this is an error, please contact "
                        f"the module instructor.\n\nBest regards,\nAcademic Administration")
            else:
                return

            send_email(recipient_email=email, subject=subject, body=body)
        except Exception:
            pass
