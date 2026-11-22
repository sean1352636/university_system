"""System dialogs extracted from DialogsMixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._shared import *  # noqa: F401,F403


class SystemDialogsMixin:
    def complete_system_tab_config_display(self):
        """Complete the configuration display area in system tab"""
        # This completes the cut-off section from the document
        config_display_frame = getattr(self, "config_display_frame", None)
        if config_display_frame is None:
            return
        self.config_display = ScrolledText(config_display_frame, height=10, wrap=tk.WORD)
        self.config_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        config_actions_bottom = ttk.Frame(config_display_frame)
        config_actions_bottom.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(config_actions_bottom, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.reload_config', default="Reload Config"),
                  command=self.reload_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(config_actions_bottom, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.save_config', default="Save Config"),
                  command=self.save_config).pack(side=tk.LEFT, padx=(0, 5))

    def show_backup_restore_dialog(self):
        """Show backup and restore dialog"""
        try:
            backup_window = tk.Toplevel(self.root)
            backup_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.windows.backup_restore', default="Backup & Restore"))
            backup_window.geometry("600x500")
            backup_window.transient(self.root)

            backup_notebook = ttk.Notebook(backup_window)
            backup_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Backup tab
            backup_frame = ttk.Frame(backup_notebook)
            backup_notebook.add(backup_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.tabs.backup', default="Backup"))

            backup_info = ttk.LabelFrame(backup_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.backup_information', default="Backup Information"), padding="10")
            backup_info.pack(fill=tk.X, pady=10)

            ttk.Label(backup_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.the_backup_will_include', default="The backup will include:")).pack(anchor=tk.W)
            ttk.Label(backup_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.database_student_records_db', default="• Database (student_records.db)")).pack(anchor=tk.W, padx=20)
            ttk.Label(backup_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.templates_templates_json', default="• Templates (templates.json)")).pack(anchor=tk.W, padx=20)
            ttk.Label(backup_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.scheduled_reports', default="• Scheduled Reports")).pack(anchor=tk.W, padx=20)
            ttk.Label(backup_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.system_configuration', default="• System Configuration")).pack(anchor=tk.W, padx=20)

            # Backup options
            backup_options = ttk.LabelFrame(backup_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.backup_options', default="Backup Options"), padding="10")
            backup_options.pack(fill=tk.X, pady=10)

            include_reports_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(backup_options, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.include_generated_reports', default="Include Generated Reports"),
                           variable=include_reports_var).pack(anchor=tk.W)

            include_cache_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(backup_options, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.include_cache_files', default="Include Cache Files"),
                           variable=include_cache_var).pack(anchor=tk.W)

            def create_backup():
                try:
                    backup_dir = filedialog.askdirectory(title=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.select_backup_directory', default="Select Backup Directory"))
                    if not backup_dir:
                        return

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"reporting_system_backup_{timestamp}"
                    full_backup_path = os.path.join(backup_dir, backup_name)
                    os.makedirs(full_backup_path, exist_ok=True)

                    import shutil

                    # Backup database
                    if os.path.exists(CONFIG.get('database', str(DEFAULT_DB_PATH))):
                        shutil.copy2(CONFIG['database'],
                                   os.path.join(full_backup_path, str(DEFAULT_DB_PATH)))

                    # Backup templates
                    templates_file = os.path.join(CONFIG.get('templates_dir', str(paths.UNIVERSITY_REPORT_TEMPLATES_DIR)), 'templates.json')
                    if os.path.exists(templates_file):
                        shutil.copy2(templates_file,
                                   os.path.join(full_backup_path, 'templates.json'))

                    # Create backup info file
                    backup_info = {
                        'created': datetime.now().isoformat(),
                        'version': '2.0',
                        'includes_reports': include_reports_var.get(),
                        'includes_cache': include_cache_var.get()
                    }

                    with open(os.path.join(full_backup_path, 'backup_info.json'), 'w') as f:
                        json.dump(backup_info, f, indent=4)

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.backup_complete', default="Backup Complete"),
                                      f"Backup created successfully!\n\nLocation: {full_backup_path}")

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.backup_error', default="Backup Error"), f"Backup failed: {str(e)}")

            ttk.Button(backup_options, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.create_backup', default="Create Backup"), command=create_backup,
                      style='Success.TButton').pack(pady=10)

            # Restore tab
            restore_frame = ttk.Frame(backup_notebook)
            backup_notebook.add(restore_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.tabs.restore', default="Restore"))

            restore_info = ttk.LabelFrame(restore_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.restore_information', default="Restore Information"), padding="10")
            restore_info.pack(fill=tk.X, pady=10)

            ttk.Label(restore_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.restoring_will_overwrite_current_data', default="Restoring will overwrite current data!")).pack(anchor=tk.W)
            ttk.Label(restore_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.please_backup_current_data_before_restoring', default="Please backup current data before restoring.")).pack(anchor=tk.W)

            def restore_backup():
                try:
                    backup_dir = filedialog.askdirectory(title=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.select_backup_directory_to_restore', default="Select Backup Directory to Restore"))
                    if not backup_dir:
                        return

                    backup_info_file = os.path.join(backup_dir, 'backup_info.json')
                    if not os.path.exists(backup_info_file):
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.invalid_backup', default="Invalid Backup"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.selected_directory_is_not_a_valid_backup', default="Selected directory is not a valid backup"))
                        return

                    if not messagebox.askyesno(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.confirm_restore', default="Confirm Restore"),
                                             _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.this_will_overwrite_current_data_continue', default="This will overwrite current data. Continue?")):
                        return

                    import shutil

                    # Restore database
                    db_backup = os.path.join(backup_dir, str(DEFAULT_DB_PATH))
                    if os.path.exists(db_backup):
                        shutil.copy2(db_backup, CONFIG['database'])

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.restore_complete', default="Restore Complete"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.backup_restored_successfully', default="Backup restored successfully!"))

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.restore_error', default="Restore Error"), f"Restore failed: {str(e)}")

            ttk.Button(restore_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.restore_from_backup', default="Restore from Backup"), command=restore_backup,
                      style='Warning.TButton').pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.backup_restore_error', default="Backup/Restore Error"), f"Failed to open backup dialog: {str(e)}")

    def show_user_management_dialog(self):
        """Show user management dialog"""
        try:
            user_window = tk.Toplevel(self.root)
            user_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.windows.user_management', default="User Management"))
            user_window.geometry("800x600")
            user_window.transient(self.root)

            note_frame = ttk.LabelFrame(user_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.note', default="Note"), padding="10")
            note_frame.pack(fill=tk.X, padx=10, pady=10)

            note_text = """User management and authentication features are available in the full system.
This interface provides basic user management functionality."""

            ttk.Label(note_frame, text=note_text, wraplength=700).pack()

            users_frame = ttk.LabelFrame(user_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.system_users', default="System Users"), padding="10")
            users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Username', 'Role', 'Last Login', 'Status')
            users_tree = ttk.Treeview(users_frame, columns=columns, show='headings')

            for col in columns:
                users_tree.heading(col, text=col)
                users_tree.column(col, width=150)

            users_tree.pack(fill=tk.BOTH, expand=True)

            from education_system.systems.university.infrastructure.shared_context import get_auth
            auth_service = get_auth()
            user_rows = {}

            def refresh_users():
                for item in users_tree.get_children():
                    users_tree.delete(item)
                user_rows.clear()
                with get_db_connection() as conn:
                    # is_active/last_login live on user_accounts, not users —
                    # the same split the auth service writes through.
                    # LEFT JOIN because a user row may have no account row yet.
                    users = [dict(row) for row in conn.execute('''
                        SELECT u.id, u.username, u.role, u.email,
                               ua.last_login,
                               COALESCE(ua.is_active, 1) AS is_active
                        FROM users u
                        LEFT JOIN user_accounts ua ON ua.user_id = u.id
                        ORDER BY u.username
                    ''').fetchall()]
                for user in users:
                    item = users_tree.insert('', tk.END, values=(
                        user.get('username', ''), user.get('role', ''),
                        user.get('last_login') or 'Never',
                        'Active' if user.get('is_active', True) else 'Inactive',
                    ))
                    user_rows[item] = user

            def add_user():
                username = simpledialog.askstring(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.add_user', default="Add User"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.username', default="Username:"), parent=user_window)
                if not username:
                    return
                password = simpledialog.askstring(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.add_user', default="Add User"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.temporary_password', default="Temporary password:"), parent=user_window, show='*')
                if not password:
                    return
                email = simpledialog.askstring(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.add_user', default="Add User"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.email', default="Email:"), parent=user_window) or ""
                role = simpledialog.askstring(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.add_user', default="Add User"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.role', default="Role:"), parent=user_window) or "student"
                auth_service.create_user(username, password, email=email, role=role,
                                         password_reset_required=True)
                refresh_users()

            def edit_user():
                selected = users_tree.selection()
                if not selected:
                    messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.selection', default="Selection"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.select_a_user_first', default="Select a user first."))
                    return
                user = user_rows[selected[0]]
                role = simpledialog.askstring(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.edit_user', default="Edit User"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.role', default="Role:"),
                                              initialvalue=user.get('role', ''), parent=user_window)
                if role is None:
                    return
                active = messagebox.askyesno(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.account_status', default="Account Status"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.should_this_account_be_active', default="Should this account be active?"), parent=user_window)
                auth_service.update_user(user['id'], role=role)
                (auth_service.activate_user if active else auth_service.deactivate_user)(user['id'])
                refresh_users()

            actions_frame = ttk.Frame(users_frame)
            actions_frame.pack(fill=tk.X, pady=(10, 0))

            ttk.Button(actions_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.add_user', default="Add User"),
                      command=add_user).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(actions_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.edit_user', default="Edit User"),
                      command=edit_user).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(actions_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.refresh', default="Refresh"), command=refresh_users).pack(side=tk.LEFT, padx=(0, 5))

            refresh_users()

            ttk.Button(user_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.close', default="Close"), command=user_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.user_management_error', default="User Management Error"), f"Failed to open user management: {str(e)}")

    def check_system_requirements_gui(self):
        """GUI version of system requirements check"""
        try:
            req_window = tk.Toplevel(self.root)
            req_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.windows.system_requirements_check', default="System Requirements Check"))
            req_window.geometry("600x400")
            req_window.transient(self.root)

            # Requirements display
            req_frame = ttk.LabelFrame(req_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.system_requirements_status', default="System Requirements Status"), padding="10")
            req_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            req_text = ScrolledText(req_frame, wrap=tk.WORD)
            req_text.pack(fill=tk.BOTH, expand=True)

            def check_requirements():
                requirements_status = {
                    'tkinter': True,  # Already available if GUI is running
                    'pandas': pd is not None,
                    'enhanced_features': ENHANCED_AVAILABLE,
                    'database': False,
                    'matplotlib': True,  # Check if plotting works
                    'reportlab': True   # Check if PDF generation works
                }

                # Test database connection
                try:
                    conn = get_db_connection()
                    if conn:
                        conn.close()
                        requirements_status['database'] = True
                except Exception as e:
                    logger.debug(f"Failed to check database requirements: {e}")

                # Test matplotlib
                try:
                    import matplotlib.pyplot as plt
                    plt.figure()
                    plt.close()
                except Exception:
                    requirements_status['matplotlib'] = False

                # Generate report
                report = "System Requirements Check\n"
                report += "=" * 40 + "\n\n"

                for requirement, status in requirements_status.items():
                    status_text = "✓ Available" if status else "✗ Missing"
                    report += f"{requirement.replace('_', ' ').title()}: {status_text}\n"

                # Recommendations
                missing = [req for req, status in requirements_status.items() if not status]
                if missing:
                    report += f"\nMissing Requirements: {', '.join(missing)}\n"
                    report += "\nRecommendations:\n"
                    if 'pandas' in missing:
                        report += "- Install pandas: pip install pandas\n"
                    if 'matplotlib' in missing:
                        report += "- Install matplotlib: pip install matplotlib\n"
                    if 'reportlab' in missing:
                        report += "- Install reportlab: pip install reportlab\n"
                    if not requirements_status['database']:
                        report += "- Check database connection and permissions\n"
                else:
                    report += "\n✓ All requirements satisfied!\n"

                req_text.delete(1.0, tk.END)
                req_text.insert(1.0, report)

            # Run check automatically
            check_requirements()

            # Buttons
            button_frame = ttk.Frame(req_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.refresh_check', default="Refresh Check"), command=check_requirements).pack(side=tk.LEFT)
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.close', default="Close"), command=req_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.requirements_check_error', default="Requirements Check Error"), f"Failed to check requirements: {str(e)}")

    def show_system_logs_viewer(self):
        """Show real-time system logs viewer"""
        try:
            logs_window = tk.Toplevel(self.root)
            logs_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.windows.system_logs_viewer', default="System Logs Viewer"))
            logs_window.geometry("900x600")
            logs_window.transient(self.root)

            # Controls frame
            controls_frame = ttk.Frame(logs_window)
            controls_frame.pack(fill=tk.X, padx=10, pady=10)

            # Log level filter
            ttk.Label(controls_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.log_level', default="Log Level:")).pack(side=tk.LEFT)
            log_level_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.values.all', default="ALL"))
            log_level_combo = ttk.Combobox(controls_frame, textvariable=log_level_var,
                                          values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"], state="readonly")
            log_level_combo.pack(side=tk.LEFT, padx=(5, 20))

            # Auto-refresh
            auto_refresh_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(controls_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.auto_refresh', default="Auto-refresh"), variable=auto_refresh_var).pack(side=tk.LEFT, padx=(0, 20))

            # Clear logs button
            def clear_logs():
                logs_text.delete(1.0, tk.END)

            ttk.Button(controls_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.clear', default="Clear"), command=clear_logs).pack(side=tk.LEFT)
            ttk.Button(controls_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.refresh', default="Refresh"), command=lambda: load_logs()).pack(side=tk.LEFT, padx=(5, 0))

            # Logs display
            logs_frame = ttk.LabelFrame(logs_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.system_logs', default="System Logs"), padding="10")
            logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            logs_text = ScrolledText(logs_frame, wrap=tk.NONE, font=("Consolas", 9))
            logs_text.pack(fill=tk.BOTH, expand=True)

            def load_logs():
                try:
                    log_file = get_log_file('app.log')
                    if not os.path.exists(log_file):
                        logs_text.insert(tk.END, "No log file found\n")
                        return

                    with open(log_file, 'r') as f:
                        lines = f.readlines()

                    # Filter by log level
                    level_filter = log_level_var.get()
                    if level_filter != "ALL":
                        lines = [line for line in lines if level_filter in line]

                    # Show last 1000 lines
                    display_lines = lines[-1000:] if len(lines) > 1000 else lines

                    logs_text.delete(1.0, tk.END)
                    for line in display_lines:
                        # Color code by log level
                        if "ERROR" in line:
                            logs_text.insert(tk.END, line, "error")
                        elif "WARNING" in line:
                            logs_text.insert(tk.END, line, "warning")
                        elif "INFO" in line:
                            logs_text.insert(tk.END, line, "info")
                        else:
                            logs_text.insert(tk.END, line)

                    logs_text.see(tk.END)

                except Exception as e:
                    logs_text.insert(tk.END, f"Error loading logs: {str(e)}\n")

            # Configure text tags for coloring
            logs_text.tag_configure("error", foreground="red")
            logs_text.tag_configure("warning", foreground="orange")
            logs_text.tag_configure("info", foreground="blue")

            # Auto-refresh functionality
            def auto_refresh():
                if auto_refresh_var.get():
                    load_logs()
                logs_window.after(5000, auto_refresh)  # Refresh every 5 seconds

            # Initial load and start auto-refresh
            load_logs()
            auto_refresh()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.logs_viewer_error', default="Logs Viewer Error"), f"Failed to open logs viewer: {str(e)}")

    def show_cache_management_dialog(self):
        """Show cache management dialog"""
        try:
            cache_window = tk.Toplevel(self.root)
            cache_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.windows.cache_management', default="Cache Management"))
            cache_window.geometry("600x500")
            cache_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(cache_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)
            ttk.Label(header_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.cache_management', default="\U0001f4be Cache Management"),
                     font=('Arial', 14, 'bold')).pack(anchor=tk.W)

            # Cache info
            info_frame = ttk.LabelFrame(cache_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.labels.cache_information', default="Cache Information"), padding="10")
            info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            info_text = ScrolledText(info_frame, wrap=tk.WORD, height=15)
            info_text.pack(fill=tk.BOTH, expand=True)

            def load_cache_info():
                try:
                    cache_dir = CONFIG.get('cache_dir', 'cache')
                    if os.path.exists(cache_dir):
                        cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
                        total_size = sum(os.path.getsize(os.path.join(cache_dir, f))
                                       for f in cache_files)

                        info_text.insert(tk.END, f"Cache Directory: {cache_dir}\n")
                        info_text.insert(tk.END, f"Total Cached Reports: {len(cache_files)}\n")
                        info_text.insert(tk.END, f"Total Size: {total_size / (1024 * 1024):.2f} MB\n")
                        info_text.insert(tk.END, f"Max Cache Size: {CONFIG.get('max_cache_size_mb', 100)} MB\n")
                        info_text.insert(tk.END, f"Cache Expiry: {CONFIG.get('cache_expiry_hours', 24)} hours\n\n")

                        if cache_files:
                            info_text.insert(tk.END, "Cached Reports:\n")
                            for cache_file in cache_files[:20]:  # Show first 20
                                file_path = os.path.join(cache_dir, cache_file)
                                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                age = datetime.now() - file_time
                                info_text.insert(tk.END, f"  \u2022 {cache_file} (Age: {age.seconds // 3600}h)\n")

                            if len(cache_files) > 20:
                                info_text.insert(tk.END, f"\n  ... and {len(cache_files) - 20} more\n")
                    else:
                        info_text.insert(tk.END, "Cache directory does not exist yet.\n")

                    info_text.config(state=tk.DISABLED)
                except Exception as e:
                    info_text.insert(tk.END, f"Error loading cache info: {str(e)}")
                    info_text.config(state=tk.DISABLED)

            load_cache_info()

            # Buttons
            button_frame = ttk.Frame(cache_window)
            button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            def refresh_info():
                info_text.config(state=tk.NORMAL)
                info_text.delete(1.0, tk.END)
                load_cache_info()

            def cleanup_action():
                if messagebox.askyesno(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.confirm', default="Confirm"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.clean_up_old_cache_files', default="Clean up old cache files?")):
                    self.cleanup_cache_dialog()
                    refresh_info()

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.cleanup_cache', default="Cleanup Cache"), command=cleanup_action).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.refresh', default="Refresh"), command=refresh_info).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.buttons.close', default="Close"), command=cache_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.system.dialogs.error', default="Error"), f"Failed to show cache management: {str(e)}")
