from ._common import (
    EMAIL_TEMPLATE_MAPPING_FILE,
    EMAIL_TEMPLATES_DIR,
    _install_clean_close,
    _load_json,
    _save_json,
    _t,
    datetime,
    logger,
    messagebox,
    os,
    tk,
    ttk,
)

def show_notification_template_manager(self):
    """Notification template browser, editor, and creator."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.templates.title"))
        win.geometry("1100x750")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.templates.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        mapping_path = str(EMAIL_TEMPLATE_MAPPING_FILE)
        templates_dir = str(EMAIL_TEMPLATES_DIR)
        mapping = _load_json(mapping_path, {})

        # --- Tab 1: Browse Templates ---
        browse_frame = ttk.Frame(notebook, padding=10)
        notebook.add(browse_frame, text=_t("admin_tools_v2.templates.tab_browse"))

        filter_frame = ttk.Frame(browse_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(filter_frame, text=_t("admin_tools_v2.search")).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        cat_filter_var = tk.StringVar(value='All')
        categories = set()
        for path in mapping.values():
            parts = path.split('/')
            if len(parts) > 1:
                categories.add(parts[0])
        cat_combo = ttk.Combobox(filter_frame, textvariable=cat_filter_var,
                                 values=['All'] + sorted(categories), state='readonly', width=20)
        cat_combo.pack(side=tk.LEFT, padx=5)

        tmpl_tree = ttk.Treeview(browse_frame,
                                 columns=('name', 'category', 'path'), show='headings')
        for c, w in [('name', 300), ('category', 150), ('path', 400)]:
            tmpl_tree.heading(c, text=c.title())
            tmpl_tree.column(c, width=w)
        tmpl_scroll = ttk.Scrollbar(browse_frame, orient=tk.VERTICAL, command=tmpl_tree.yview)
        tmpl_tree.configure(yscrollcommand=tmpl_scroll.set)
        tmpl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tmpl_tree.pack(fill=tk.BOTH, expand=True)

        def refresh_template_list(*_args):
            tmpl_tree.delete(*tmpl_tree.get_children())
            search_term = search_var.get().lower()
            cat = cat_filter_var.get()
            for name, path in sorted(mapping.items()):
                parts = path.split('/')
                category = parts[0] if len(parts) > 1 else 'general'
                if cat != 'All' and category != cat:
                    continue
                if search_term and search_term not in name.lower() and search_term not in category.lower():
                    continue
                tmpl_tree.insert('', tk.END, values=(name, category, path))

        search_var.trace_add('write', refresh_template_list)
        cat_filter_var.trace_add('write', refresh_template_list)
        refresh_template_list()

        # --- Tab 2: Edit Template ---
        edit_frame = ttk.Frame(notebook, padding=10)
        notebook.add(edit_frame, text=_t("admin_tools_v2.templates.tab_edit"))

        edit_info = ttk.Label(edit_frame, text=_t("admin_tools_v2.templates.select_template"))
        edit_info.pack(anchor='w', pady=5)

        subj_var = tk.StringVar()
        ttk.Label(edit_frame, text=_t("admin_tools_v2.templates.subject")).pack(anchor='w')
        ttk.Entry(edit_frame, textvariable=subj_var, width=80).pack(fill=tk.X, pady=2)

        ttk.Label(edit_frame, text=_t("admin_tools_v2.templates.body")).pack(anchor='w')
        body_edit = tk.Text(edit_frame, height=20)
        body_edit.pack(fill=tk.BOTH, expand=True, pady=2)

        current_template_path = [None]

        def load_template_for_edit(*_args):
            sel = tmpl_tree.selection()
            if not sel:
                return
            vals = tmpl_tree.item(sel[0], 'values')
            rel_path = vals[2]
            full_path = os.path.join(templates_dir, rel_path)
            try:
                tdata = _load_json(full_path, {})
                subj_var.set(tdata.get('subject', ''))
                body_edit.delete('1.0', tk.END)
                body_edit.insert('1.0', tdata.get('body', tdata.get('html_body', '')))
                current_template_path[0] = full_path
                edit_info.config(text=f"Editing: {vals[0]}")
                notebook.select(1)
            except Exception as e:
                messagebox.showerror(_t("admin_tools_v2.error"),
                                     _t("admin_tools_v2.templates.template_load_error").format(error=str(e)))

        tmpl_tree.bind('<Double-1>', load_template_for_edit)

        def save_template():
            if not current_template_path[0]:
                return
            try:
                # Create backup
                bak_path = current_template_path[0] + '.bak'
                if os.path.exists(current_template_path[0]):
                    import shutil
                    shutil.copy2(current_template_path[0], bak_path)

                tdata = _load_json(current_template_path[0], {})
                tdata['subject'] = subj_var.get()
                tdata['body'] = body_edit.get('1.0', tk.END).strip()
                _save_json(current_template_path[0], tdata)
                messagebox.showinfo(_t("admin_tools_v2.success"),
                                    _t("admin_tools_v2.templates.template_saved"))
            except Exception as e:
                messagebox.showerror(_t("admin_tools_v2.error"),
                                     _t("admin_tools_v2.templates.template_save_error").format(error=str(e)))

        ttk.Button(edit_frame, text=_t("admin_tools_v2.templates.save_template"),
                   command=save_template).pack(pady=5)

        # --- Tab 3: Create Template ---
        create_frame = ttk.Frame(notebook, padding=10)
        notebook.add(create_frame, text=_t("admin_tools_v2.templates.tab_create"))

        new_name_var = tk.StringVar()
        new_cat_var = tk.StringVar(value='general')
        new_subj_var = tk.StringVar()

        for lbl, var in [(_t("admin_tools_v2.templates.new_name"), new_name_var),
                         (_t("admin_tools_v2.templates.new_category"), new_cat_var),
                         (_t("admin_tools_v2.templates.subject"), new_subj_var)]:
            ttk.Label(create_frame, text=lbl).pack(anchor='w', pady=(5, 0))
            ttk.Entry(create_frame, textvariable=var, width=60).pack(fill=tk.X, pady=2)

        ttk.Label(create_frame, text=_t("admin_tools_v2.templates.body")).pack(anchor='w', pady=(5, 0))
        new_body = tk.Text(create_frame, height=15)
        new_body.pack(fill=tk.BOTH, expand=True, pady=2)

        def create_template():
            name = new_name_var.get().strip()
            cat = new_cat_var.get().strip() or 'general'
            if not name:
                return
            if not name.endswith('.json'):
                name += '.json'
            if name in mapping:
                messagebox.showwarning(_t("admin_tools_v2.error"),
                                       _t("admin_tools_v2.templates.file_exists"))
                return
            rel_path = f"{cat}/{name}"
            full_path = os.path.join(templates_dir, rel_path)
            tdata = {
                'subject': new_subj_var.get(),
                'body': new_body.get('1.0', tk.END).strip(),
                'created_at': datetime.now().isoformat()
            }
            _save_json(full_path, tdata)
            mapping[name] = rel_path
            _save_json(mapping_path, mapping)
            refresh_template_list()
            messagebox.showinfo(_t("admin_tools_v2.success"),
                                _t("admin_tools_v2.templates.template_created"))

        ttk.Button(create_frame, text=_t("admin_tools_v2.templates.create_template"),
                   command=create_template).pack(pady=10)

    except Exception as e:
        logger.exception("Error in Notification Template Manager")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 9: Data Retention Policy Manager
# ---------------------------------------------------------------------------
