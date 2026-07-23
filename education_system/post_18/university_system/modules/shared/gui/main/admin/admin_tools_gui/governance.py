from ._common import (
    DR_CONFIG_FILE,
    LICENSES_FILE,
    _install_clean_close,
    _load_json,
    _save_json,
    _t,
    datetime,
    logger,
    messagebox,
    os,
    timedelta,
    tk,
    ttk,
)

def show_department_isolation(self):
    """Department isolation view with data scope and access matrix."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.department.title"))
        win.geometry("1000x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.department.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Tab 1: Departments ---
        dept_frame = ttk.Frame(notebook, padding=10)
        notebook.add(dept_frame, text=_t("admin_tools_v2.department.tab_departments"))

        dept_tree = ttk.Treeview(dept_frame,
                                 columns=('department', 'students', 'users'),
                                 show='headings')
        for c, w in [('department', 300), ('students', 150), ('users', 150)]:
            dept_tree.heading(c, text=c.title())
            dept_tree.column(c, width=w)
        dept_tree.pack(fill=tk.BOTH, expand=True)

        try:
            conn = get_connection()
            # Get departments from courses in students
            cursor = conn.execute("""
                SELECT course, COUNT(*) as cnt
                FROM students
                WHERE course IS NOT NULL AND course != ''
                GROUP BY course ORDER BY cnt DESC
            """)
            depts = cursor.fetchall()

            # Get user role counts
            role_cursor = conn.execute("SELECT role, COUNT(*) as cnt FROM users GROUP BY role")
            role_counts = {r['role'] if isinstance(r, dict) else r[0]: r['cnt'] if isinstance(r, dict) else r[1]
                          for r in role_cursor.fetchall()}
            conn.close()

            total_users = sum(role_counts.values())
            for d in depts:
                dept_name = d['course'] if isinstance(d, dict) else d[0]
                student_cnt = d['cnt'] if isinstance(d, dict) else d[1]
                dept_tree.insert('', tk.END, values=(dept_name, student_cnt, total_users))
        except Exception:
            pass

        # --- Tab 2: Data Scope ---
        scope_frame = ttk.Frame(notebook, padding=10)
        notebook.add(scope_frame, text=_t("admin_tools_v2.department.tab_scope"))

        ttk.Label(scope_frame, text=_t("admin_tools_v2.department.scope_header"),
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)

        scope_tree = ttk.Treeview(scope_frame,
                                  columns=('department', 'students', 'modules'),
                                  show='headings')
        for c, w in [('department', 300), ('students', 150), ('modules', 150)]:
            scope_tree.heading(c, text=c.title())
            scope_tree.column(c, width=w)
        scope_tree.pack(fill=tk.BOTH, expand=True)

        try:
            conn = get_connection()
            # Student counts per department
            cursor = conn.execute("""
                SELECT course, COUNT(*) as student_count
                FROM students
                WHERE course IS NOT NULL AND course != ''
                GROUP BY course ORDER BY course
            """)
            dept_students = cursor.fetchall()

            # Module counts (try modules table)
            module_counts = {}
            try:
                mcursor = conn.execute("""
                    SELECT department, COUNT(*) as cnt
                    FROM modules
                    WHERE department IS NOT NULL
                    GROUP BY department
                """)
                module_counts = {r['department'] if isinstance(r, dict) else r[0]: r['cnt'] if isinstance(r, dict) else r[1]
                                for r in mcursor.fetchall()}
            except Exception:
                pass

            conn.close()

            for d in dept_students:
                dept_name = d['course'] if isinstance(d, dict) else d[0]
                s_cnt = d['student_count'] if isinstance(d, dict) else d[1]
                m_cnt = module_counts.get(dept_name, 0)
                scope_tree.insert('', tk.END, values=(dept_name, s_cnt, m_cnt))
        except Exception:
            pass

        # --- Tab 3: Access Matrix ---
        matrix_frame = ttk.Frame(notebook, padding=10)
        notebook.add(matrix_frame, text=_t("admin_tools_v2.department.tab_matrix"))

        matrix_text = tk.Text(matrix_frame, wrap=tk.NONE, font=('Courier', 10), state=tk.DISABLED)
        mx_scroll = ttk.Scrollbar(matrix_frame, orient=tk.VERTICAL, command=matrix_text.yview)
        mh_scroll = ttk.Scrollbar(matrix_frame, orient=tk.HORIZONTAL, command=matrix_text.xview)
        matrix_text.configure(yscrollcommand=mx_scroll.set, xscrollcommand=mh_scroll.set)
        mx_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        mh_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        matrix_text.pack(fill=tk.BOTH, expand=True)

        # Build access matrix from role definitions
        roles = ['admin', 'staff', 'instructor', 'student']
        features = [
            'Student Records', 'Grade Tracking', 'Course Management',
            'Finance', 'User Management', 'System Admin', 'Library',
            'Attendance', 'Reports', 'Backup', 'Audit Log',
            'Health Portal', 'Housing', 'Assignments', 'Plagiarism Check',
        ]
        # Define access based on get_visible_buttons_for_role logic
        access_map = {
            'admin': {f: 'Y' for f in features},
            'staff': {f: 'Y' for f in features if f not in ['User Management', 'System Admin', 'Backup', 'Audit Log']},
            'instructor': {f: 'Y' for f in ['Student Records', 'Grade Tracking', 'Course Management',
                                              'Library', 'Attendance', 'Assignments', 'Plagiarism Check']},
            'student': {f: 'Y' for f in ['Student Records', 'Library', 'Health Portal',
                                          'Housing', 'Assignments']},
        }

        matrix_text.config(state=tk.NORMAL)
        header = f"{'Feature':<25}" + ''.join(f"{r:<15}" for r in roles)
        matrix_text.insert(tk.END, header + '\n')
        matrix_text.insert(tk.END, '=' * len(header) + '\n')
        for feat in features:
            line = f"{feat:<25}"
            for role in roles:
                val = access_map.get(role, {}).get(feat, '-')
                line += f"{val:<15}"
            matrix_text.insert(tk.END, line + '\n')
        matrix_text.config(state=tk.DISABLED)

    except Exception as e:
        logger.exception("Error in Department Isolation")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 12: Integration Status Dashboard
# ---------------------------------------------------------------------------

def show_license_management(self):
    """License and subscription management with seat usage tracking."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        licenses_path = str(LICENSES_FILE)
        if not os.path.exists(licenses_path):
            default_licenses = [{
                "name": "University Management System",
                "type": "MIT",
                "seats": "Unlimited",
                "expiry": None,
                "status": "Active"
            }]
            _save_json(licenses_path, default_licenses)

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.license.title"))
        win.geometry("1000x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.license.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Tab 1: Licenses ---
        lic_frame = ttk.Frame(notebook, padding=10)
        notebook.add(lic_frame, text=_t("admin_tools_v2.license.tab_licenses"))

        lic_tree = ttk.Treeview(lic_frame,
                                columns=('name', 'type', 'seats', 'expiry', 'status'),
                                show='headings')
        for c, w in [('name', 300), ('type', 100), ('seats', 100), ('expiry', 150), ('status', 100)]:
            lic_tree.heading(c, text=c.title())
            lic_tree.column(c, width=w)
        lic_tree.pack(fill=tk.BOTH, expand=True)

        def load_licenses():
            lic_tree.delete(*lic_tree.get_children())
            licenses = _load_json(licenses_path, [])
            for lic in licenses:
                expiry = lic.get('expiry') or _t("admin_tools_v2.license.unlimited")
                lic_tree.insert('', tk.END, values=(
                    lic.get('name', ''), lic.get('type', ''),
                    lic.get('seats', ''), expiry,
                    lic.get('status', 'Active')))

        load_licenses()

        def add_license():
            dlg = tk.Toplevel(win)
            dlg.title(_t("admin_tools_v2.license.add_license"))
            dlg.geometry("400x300")
            dlg.transient(win)

            vars_dict = {}
            for field in ['name', 'type', 'seats', 'expiry', 'status']:
                ttk.Label(dlg, text=field.title()).pack(anchor='w', padx=10, pady=(5, 0))
                var = tk.StringVar(value='Active' if field == 'status' else '')
                ttk.Entry(dlg, textvariable=var, width=40).pack(padx=10)
                vars_dict[field] = var

            def save():
                licenses = _load_json(licenses_path, [])
                new_lic = {f: v.get() for f, v in vars_dict.items()}
                if not new_lic.get('expiry'):
                    new_lic['expiry'] = None
                licenses.append(new_lic)
                _save_json(licenses_path, licenses)
                load_licenses()
                dlg.destroy()

            ttk.Button(dlg, text=_t("admin_tools_v2.save"), command=save).pack(pady=10)

        def edit_license():
            sel = lic_tree.selection()
            if not sel:
                return
            idx = lic_tree.index(sel[0])
            licenses = _load_json(licenses_path, [])
            if idx >= len(licenses):
                return
            lic = licenses[idx]

            dlg = tk.Toplevel(win)
            dlg.title(_t("admin_tools_v2.license.edit_license"))
            dlg.geometry("400x300")
            dlg.transient(win)

            vars_dict = {}
            for field in ['name', 'type', 'seats', 'expiry', 'status']:
                ttk.Label(dlg, text=field.title()).pack(anchor='w', padx=10, pady=(5, 0))
                var = tk.StringVar(value=str(lic.get(field, '') or ''))
                ttk.Entry(dlg, textvariable=var, width=40).pack(padx=10)
                vars_dict[field] = var

            def save():
                updated = {f: v.get() for f, v in vars_dict.items()}
                if not updated.get('expiry'):
                    updated['expiry'] = None
                licenses[idx] = updated
                _save_json(licenses_path, licenses)
                load_licenses()
                dlg.destroy()

            ttk.Button(dlg, text=_t("admin_tools_v2.save"), command=save).pack(pady=10)

        def delete_license():
            sel = lic_tree.selection()
            if not sel:
                return
            if not messagebox.askyesno(_t("admin_tools_v2.confirm"), _t("admin_tools_v2.confirm_delete")):
                return
            idx = lic_tree.index(sel[0])
            licenses = _load_json(licenses_path, [])
            if idx < len(licenses):
                licenses.pop(idx)
                _save_json(licenses_path, licenses)
                load_licenses()

        lic_btn_frame = ttk.Frame(lic_frame)
        lic_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(lic_btn_frame, text=_t("admin_tools_v2.license.add_license"), command=add_license).pack(side=tk.LEFT, padx=5)
        ttk.Button(lic_btn_frame, text=_t("admin_tools_v2.license.edit_license"), command=edit_license).pack(side=tk.LEFT, padx=5)
        ttk.Button(lic_btn_frame, text=_t("admin_tools_v2.license.delete_license"), command=delete_license).pack(side=tk.LEFT, padx=5)

        # --- Tab 2: Seat Usage ---
        seat_frame = ttk.Frame(notebook, padding=10)
        notebook.add(seat_frame, text=_t("admin_tools_v2.license.tab_seats"))

        ttk.Label(seat_frame, text=_t("admin_tools_v2.license.bar_label"),
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=10)

        role_counts = {}
        try:
            conn = get_connection()
            cursor = conn.execute("SELECT role, COUNT(*) as cnt FROM users GROUP BY role ORDER BY cnt DESC")
            role_counts = {r['role'] if isinstance(r, dict) else r[0]: r['cnt'] if isinstance(r, dict) else r[1]
                          for r in cursor.fetchall()}
            conn.close()
        except Exception:
            pass

        colors = {'admin': '#e74c3c', 'staff': '#3498db', 'instructor': '#2ecc71',
                  'student': '#f39c12', 'parent': '#9b59b6'}
        total = max(sum(role_counts.values()), 1)

        for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
            row = ttk.Frame(seat_frame)
            row.pack(fill=tk.X, pady=3, padx=10)
            ttk.Label(row, text=f"{role}", width=15).pack(side=tk.LEFT)
            ttk.Label(row, text=f"{count}", width=8).pack(side=tk.LEFT)
            # Simple bar using a label with background
            bar_frame = tk.Frame(row, height=20, bg=colors.get(role, '#95a5a6'))
            bar_width = max(int(400 * count / total), 10)
            bar_frame.pack(side=tk.LEFT, padx=5)
            bar_frame.config(width=bar_width)
            bar_frame.pack_propagate(False)

        # --- Tab 3: Renewals ---
        renew_frame = ttk.Frame(notebook, padding=10)
        notebook.add(renew_frame, text=_t("admin_tools_v2.license.tab_renewals"))

        ttk.Label(renew_frame, text=_t("admin_tools_v2.license.expiring_soon"),
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=10)

        renew_tree = ttk.Treeview(renew_frame,
                                  columns=('name', 'type', 'expiry', 'status'),
                                  show='headings')
        for c, w in [('name', 300), ('type', 100), ('expiry', 150), ('status', 100)]:
            renew_tree.heading(c, text=c.title())
            renew_tree.column(c, width=w)
        renew_tree.pack(fill=tk.BOTH, expand=True)

        licenses = _load_json(licenses_path, [])
        now = datetime.now()
        threshold = now + timedelta(days=90)
        has_renewals = False
        for lic in licenses:
            exp = lic.get('expiry')
            if exp:
                try:
                    exp_date = datetime.fromisoformat(exp)
                    if exp_date <= threshold:
                        renew_tree.insert('', tk.END, values=(
                            lic.get('name', ''), lic.get('type', ''),
                            exp, lic.get('status', '')))
                        has_renewals = True
                except (ValueError, TypeError):
                    pass

        if not has_renewals:
            ttk.Label(renew_frame, text=_t("admin_tools_v2.license.no_renewals")).pack(pady=20)

    except Exception as e:
        logger.exception("Error in License Management")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 14: Disaster Recovery Plan / Runbook
# ---------------------------------------------------------------------------

def show_disaster_recovery_plan(self):
    """Disaster recovery plan editor, backup verification, and recovery runbook."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.post_18.university_system.infrastructure.database.data_backup.metadata import metadata_manager

        dr_config_path = str(DR_CONFIG_FILE)
        if not os.path.exists(dr_config_path):
            _save_json(dr_config_path, {
                "rto_hours": 4,
                "rpo_hours": 1,
                "dba_contact": "",
                "admin_contact": ""
            })

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.disaster_recovery.title"))
        win.geometry("1000x750")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.disaster_recovery.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        dr_config = _load_json(dr_config_path, {})

        # --- Tab 1: DR Plan ---
        plan_frame = ttk.Frame(notebook, padding=10)
        notebook.add(plan_frame, text=_t("admin_tools_v2.disaster_recovery.tab_plan"))

        plan_vars = {}
        for key, label_key, default in [
            ('rto_hours', 'rto_hours', 4),
            ('rpo_hours', 'rpo_hours', 1),
        ]:
            row = ttk.Frame(plan_frame)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=_t(f"admin_tools_v2.disaster_recovery.{label_key}"), width=35).pack(side=tk.LEFT)
            var = tk.IntVar(value=dr_config.get(key, default))
            plan_vars[key] = var
            ttk.Spinbox(row, from_=0, to=168, textvariable=var, width=10).pack(side=tk.LEFT, padx=10)

        for key, label_key in [('dba_contact', 'dba_contact'), ('admin_contact', 'admin_contact')]:
            row = ttk.Frame(plan_frame)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=_t(f"admin_tools_v2.disaster_recovery.{label_key}"), width=35).pack(side=tk.LEFT)
            var = tk.StringVar(value=dr_config.get(key, ''))
            plan_vars[key] = var
            ttk.Entry(row, textvariable=var, width=40).pack(side=tk.LEFT, padx=10)

        ttk.Separator(plan_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Backup summary
        summary_lf = ttk.LabelFrame(plan_frame, text=_t("admin_tools_v2.disaster_recovery.backup_summary"), padding=10)
        summary_lf.pack(fill=tk.X, padx=5, pady=5)

        try:
            backups = metadata_manager.get_backups()
            total = len(backups) if backups else 0
            latest = ''
            if backups:
                latest = backups[0].get('timestamp', backups[0].get('date', 'N/A'))
        except Exception:
            total = 0
            latest = 'N/A'

        ttk.Label(summary_lf, text=f"{_t('admin_tools_v2.disaster_recovery.total_backups')}: {total}").pack(anchor='w')
        ttk.Label(summary_lf, text=f"{_t('admin_tools_v2.disaster_recovery.latest_backup')}: {latest}").pack(anchor='w')

        def save_dr_plan():
            config = {
                'rto_hours': plan_vars['rto_hours'].get(),
                'rpo_hours': plan_vars['rpo_hours'].get(),
                'dba_contact': plan_vars['dba_contact'].get(),
                'admin_contact': plan_vars['admin_contact'].get(),
            }
            _save_json(dr_config_path, config)
            messagebox.showinfo(_t("admin_tools_v2.success"),
                                _t("admin_tools_v2.disaster_recovery.plan_saved"))

        ttk.Button(plan_frame, text=_t("admin_tools_v2.disaster_recovery.save_plan"),
                   command=save_dr_plan).pack(pady=10)

        # --- Tab 2: Backup Verification ---
        verify_frame = ttk.Frame(notebook, padding=10)
        notebook.add(verify_frame, text=_t("admin_tools_v2.disaster_recovery.tab_verify"))

        verify_tree = ttk.Treeview(verify_frame,
                                   columns=('filename', 'date', 'size', 'verified'),
                                   show='headings')
        for c, w in [('filename', 300), ('date', 150), ('size', 120), ('verified', 200)]:
            verify_tree.heading(c, text=c.title())
            verify_tree.column(c, width=w)
        verify_scroll = ttk.Scrollbar(verify_frame, orient=tk.VERTICAL, command=verify_tree.yview)
        verify_tree.configure(yscrollcommand=verify_scroll.set)
        verify_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        verify_tree.pack(fill=tk.BOTH, expand=True)

        backup_items = []
        try:
            backups = metadata_manager.get_backups()
            if backups:
                for b in backups:
                    path = b.get('path', '')
                    fname = b.get('filename', os.path.basename(path))
                    date = b.get('timestamp', b.get('date', ''))
                    size = b.get('size', '')
                    if isinstance(size, (int, float)):
                        size_str = f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"
                    else:
                        size_str = str(size)
                    iid = verify_tree.insert('', tk.END, values=(fname, date, size_str, ''))
                    backup_items.append((iid, path, size))
        except Exception:
            pass

        def verify_selected():
            sel = verify_tree.selection()
            items_to_check = [(iid, p, s) for iid, p, s in backup_items if iid in sel] if sel else backup_items
            ok = fail = 0
            for iid, path, expected_size in items_to_check:
                if path and os.path.exists(path):
                    actual_size = os.path.getsize(path)
                    if isinstance(expected_size, (int, float)):
                        size_str = f"{actual_size / 1024:.1f} KB" if actual_size < 1048576 else f"{actual_size / 1048576:.1f} MB"
                    else:
                        size_str = str(actual_size)
                    verify_tree.set(iid, 'verified',
                                    _t("admin_tools_v2.disaster_recovery.verified_ok").format(size=size_str))
                    ok += 1
                else:
                    verify_tree.set(iid, 'verified', _t("admin_tools_v2.disaster_recovery.verified_fail"))
                    fail += 1
            messagebox.showinfo(_t("admin_tools_v2.success"),
                                _t("admin_tools_v2.disaster_recovery.verification_done").format(ok=ok, fail=fail))

        verify_btn_frame = ttk.Frame(verify_frame)
        verify_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(verify_btn_frame, text=_t("admin_tools_v2.disaster_recovery.verify"),
                   command=verify_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(verify_btn_frame, text=_t("admin_tools_v2.disaster_recovery.verify_all"),
                   command=lambda: (verify_tree.selection_remove(*verify_tree.selection()), verify_selected())).pack(side=tk.LEFT, padx=5)

        # --- Tab 3: Recovery Procedures ---
        proc_frame = ttk.Frame(notebook, padding=10)
        notebook.add(proc_frame, text=_t("admin_tools_v2.disaster_recovery.tab_procedures"))

        ttk.Label(proc_frame, text=_t("admin_tools_v2.disaster_recovery.runbook_title"),
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)

        runbook_text = tk.Text(proc_frame, wrap=tk.WORD, font=('Courier', 10), state=tk.DISABLED)
        rb_scroll = ttk.Scrollbar(proc_frame, orient=tk.VERTICAL, command=runbook_text.yview)
        runbook_text.configure(yscrollcommand=rb_scroll.set)
        rb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        runbook_text.pack(fill=tk.BOTH, expand=True)

        runbook_text.config(state=tk.NORMAL)
        runbook_text.insert('1.0', _t("admin_tools_v2.disaster_recovery.runbook_text"))
        runbook_text.config(state=tk.DISABLED)

    except Exception as e:
        logger.exception("Error in Disaster Recovery Plan")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))
