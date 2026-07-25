from ._common import (
    PROJECT_ROOT,
    _install_clean_close,
    _t,
    logger,
    messagebox,
    os,
    tk,
    ttk,
)

def show_data_retention_manager(self):
    """Data retention policy editor with archive status and purge scheduler."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.systems.university.infrastructure.database.data_backup.config import DEFAULT_CONFIG as backup_config
        from education_system.systems.university.infrastructure.database.data_backup.metadata import metadata_manager
        from education_system.systems.university.infrastructure.database.data_backup.retention import cleanup_old_backups

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.retention.title"))
        win.geometry("1000x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.retention.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        retention = backup_config.get('retention_policy', {})

        # --- Tab 1: Retention Policies ---
        pol_frame = ttk.Frame(notebook, padding=10)
        notebook.add(pol_frame, text=_t("admin_tools_v2.retention.tab_policies"))

        spin_vars = {}
        for key, label_key, default in [
            ('daily_keep', 'daily_keep', 7),
            ('weekly_keep', 'weekly_keep', 4),
            ('monthly_keep', 'monthly_keep', 12),
            ('yearly_keep', 'yearly_keep', 5),
        ]:
            row = ttk.Frame(pol_frame)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=_t(f"admin_tools_v2.retention.{label_key}"), width=30).pack(side=tk.LEFT)
            var = tk.IntVar(value=retention.get(key, default))
            spin_vars[key] = var
            ttk.Spinbox(row, from_=0, to=365, textvariable=var, width=10).pack(side=tk.LEFT, padx=10)

        # Activity log retention
        row = ttk.Frame(pol_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("admin_tools_v2.retention.activity_log_days"), width=30).pack(side=tk.LEFT)
        log_days_var = tk.IntVar(value=90)
        spin_vars['activity_log_days'] = log_days_var
        ttk.Spinbox(row, from_=1, to=3650, textvariable=log_days_var, width=10).pack(side=tk.LEFT, padx=10)

        def save_policies():
            backup_config['retention_policy'] = {
                'daily_keep': spin_vars['daily_keep'].get(),
                'weekly_keep': spin_vars['weekly_keep'].get(),
                'monthly_keep': spin_vars['monthly_keep'].get(),
                'yearly_keep': spin_vars['yearly_keep'].get(),
            }
            messagebox.showinfo(_t("admin_tools_v2.success"),
                                _t("admin_tools_v2.retention.policies_saved"))

        ttk.Button(pol_frame, text=_t("admin_tools_v2.retention.save_policies"),
                   command=save_policies).pack(pady=10)

        # --- Tab 2: Archive Status ---
        arch_frame = ttk.Frame(notebook, padding=10)
        notebook.add(arch_frame, text=_t("admin_tools_v2.retention.tab_archive"))

        arch_tree = ttk.Treeview(arch_frame,
                                 columns=('filename', 'date', 'size', 'type', 'status'),
                                 show='headings')
        for c, w in [('filename', 300), ('date', 150), ('size', 100), ('type', 100), ('status', 100)]:
            arch_tree.heading(c, text=c.title())
            arch_tree.column(c, width=w)
        arch_scroll = ttk.Scrollbar(arch_frame, orient=tk.VERTICAL, command=arch_tree.yview)
        arch_tree.configure(yscrollcommand=arch_scroll.set)
        arch_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        arch_tree.pack(fill=tk.BOTH, expand=True)

        def load_backups():
            arch_tree.delete(*arch_tree.get_children())
            try:
                backups = metadata_manager.get_backups()
                if not backups:
                    return
                for b in backups:
                    fname = b.get('filename', os.path.basename(b.get('path', '')))
                    date = b.get('timestamp', b.get('date', ''))
                    size = b.get('size', 'N/A')
                    if isinstance(size, (int, float)):
                        size = f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"
                    btype = b.get('backup_type', b.get('type', 'full'))
                    status = b.get('status', 'completed')
                    arch_tree.insert('', tk.END, values=(fname, date, size, btype, status))
            except Exception:
                pass

        load_backups()

        def do_cleanup():
            try:
                cleanup_old_backups()
                load_backups()
                messagebox.showinfo(_t("admin_tools_v2.success"),
                                    _t("admin_tools_v2.retention.cleanup_done").format(removed='N/A'))
            except Exception as e:
                messagebox.showerror(_t("admin_tools_v2.error"),
                                     _t("admin_tools_v2.retention.cleanup_error").format(error=str(e)))

        ttk.Button(arch_frame, text=_t("admin_tools_v2.retention.cleanup_now"),
                   command=do_cleanup).pack(pady=5)

        # --- Tab 3: Purge Scheduler ---
        purge_frame = ttk.Frame(notebook, padding=10)
        notebook.add(purge_frame, text=_t("admin_tools_v2.retention.tab_purge"))

        info_fields = [
            (_t("admin_tools_v2.retention.backup_frequency"), backup_config.get('backup_frequency', 'daily')),
            (_t("admin_tools_v2.retention.scheduled_time"), backup_config.get('scheduled_backup_time', '02:00')),
            (_t("admin_tools_v2.retention.auto_cleanup"),
             'Enabled' if backup_config.get('auto_backup_enabled', True) else 'Disabled'),
        ]
        for label, value in info_fields:
            row = ttk.Frame(purge_frame)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, font=('Arial', 10, 'bold'), width=25).pack(side=tk.LEFT)
            ttk.Label(row, text=str(value)).pack(side=tk.LEFT)

        ttk.Separator(purge_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        gdpr_text = tk.Text(purge_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        gdpr_text.pack(fill=tk.X, padx=10, pady=5)
        gdpr_text.config(state=tk.NORMAL)
        gdpr_text.insert('1.0', _t("admin_tools_v2.retention.gdpr_notice"))
        gdpr_text.config(state=tk.DISABLED)

    except Exception as e:
        logger.exception("Error in Data Retention Manager")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 10: System Changelog / Release Notes
# ---------------------------------------------------------------------------

def show_system_changelog(self):
    """System changelog viewer with parsed release notes and search."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        # Search order: repo root (two levels above PROJECT_ROOT), then
        # one level up (education_system/), then PROJECT_ROOT itself.
        # The canonical location is the repo root.
        candidates = [
            os.path.abspath(os.path.join(PROJECT_ROOT, '..', '..', 'CHANGELOG.md')),
            os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'CHANGELOG.md')),
            os.path.abspath(os.path.join(PROJECT_ROOT, 'CHANGELOG.md')),
        ]
        changelog_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

        changelog_content = ''
        if os.path.exists(changelog_path):
            with open(changelog_path, 'r', encoding='utf-8') as f:
                changelog_content = f.read()

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.changelog.title"))
        win.geometry("900x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.changelog.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Tab 1: Release Notes (parsed) ---
        rel_frame = ttk.Frame(notebook, padding=10)
        notebook.add(rel_frame, text=_t("admin_tools_v2.changelog.tab_releases"))

        # Parse versions from changelog
        import re
        version_pattern = re.compile(r'^## \[([^\]]+)\]\s*-\s*(.+)$', re.MULTILINE)
        matches = list(version_pattern.finditer(changelog_content))

        canvas = tk.Canvas(rel_frame)
        scrollbar = ttk.Scrollbar(rel_frame, orient=tk.VERTICAL, command=canvas.yview)
        scroll_inner = ttk.Frame(canvas)
        scroll_inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_inner, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)

        for i, match in enumerate(matches[:5]):
            version = match.group(1)
            date = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog_content)
            section_text = changelog_content[start:end].strip()

            lf = ttk.LabelFrame(scroll_inner, text=f"v{version}  —  {date}", padding=10)
            lf.pack(fill=tk.X, padx=5, pady=5)

            text_widget = tk.Text(lf, wrap=tk.WORD, height=min(15, max(4, section_text.count('\n') + 1)))
            text_widget.insert('1.0', section_text)
            text_widget.config(state=tk.DISABLED)
            text_widget.pack(fill=tk.X)

        if not matches:
            ttk.Label(scroll_inner, text=_t("admin_tools_v2.changelog.no_changelog")).pack(pady=20)

        # --- Tab 2: Full Changelog ---
        full_frame = ttk.Frame(notebook, padding=10)
        notebook.add(full_frame, text=_t("admin_tools_v2.changelog.tab_full"))

        search_frame = ttk.Frame(full_frame)
        search_frame.pack(fill=tk.X, pady=5)
        search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=search_var, width=40).pack(side=tk.LEFT, padx=5)
        match_lbl = ttk.Label(search_frame, text='')
        match_lbl.pack(side=tk.LEFT, padx=10)

        full_text = tk.Text(full_frame, wrap=tk.WORD, state=tk.DISABLED)
        full_scroll = ttk.Scrollbar(full_frame, orient=tk.VERTICAL, command=full_text.yview)
        full_text.configure(yscrollcommand=full_scroll.set)
        full_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        full_text.pack(fill=tk.BOTH, expand=True)

        full_text.config(state=tk.NORMAL)
        full_text.insert('1.0', changelog_content if changelog_content else _t("admin_tools_v2.changelog.no_changelog"))
        full_text.config(state=tk.DISABLED)

        full_text.tag_configure('highlight', background='yellow')

        def do_search(*_args):
            full_text.tag_remove('highlight', '1.0', tk.END)
            term = search_var.get().strip()
            if not term:
                match_lbl.config(text='')
                return
            count = 0
            start = '1.0'
            while True:
                pos = full_text.search(term, start, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(term)}c"
                full_text.tag_add('highlight', pos, end_pos)
                start = end_pos
                count += 1
            if count:
                match_lbl.config(text=_t("admin_tools_v2.changelog.matches_found").format(count=count))
            else:
                match_lbl.config(text=_t("admin_tools_v2.changelog.no_matches"))

        ttk.Button(search_frame, text=_t("admin_tools_v2.changelog.search"), command=do_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text=_t("admin_tools_v2.changelog.clear_search"),
                   command=lambda: (search_var.set(''), full_text.tag_remove('highlight', '1.0', tk.END), match_lbl.config(text=''))).pack(side=tk.LEFT)

    except Exception as e:
        logger.exception("Error in System Changelog")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 11: Multi-Tenancy / Department Isolation
# ---------------------------------------------------------------------------
