from ._common import (
    SAVED_REPORTS_FILE,
    SCHEDULED_REPORTS_FILE,
    _install_clean_close,
    _load_json,
    _save_json,
    _t,
    csv,
    datetime,
    filedialog,
    logger,
    messagebox,
    tk,
    timedelta,
    ttk,
)

def show_usage_adoption_reports(self):
    """System usage and adoption reports.

    Renders inside the main GUI's content notebook when a workspace is
    available (via ``open_in_workspace``); falls back to a Toplevel
    otherwise. Same pattern as Student Records (8.117.38).
    """
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools.access_denied"), _t("admin_tools.admin_required"))
        return

    title = _t("admin_tools.usage.title")
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: _build_usage_adoption_reports(self, host))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(title)
        win.geometry("1100x750")
        win.transient(self.root)
        _build_usage_adoption_reports(self, win)
    except Exception as e:
        messagebox.showerror(_t("admin_tools.error"), str(e))


def _build_usage_adoption_reports(self, win):
    """Build the Usage / Adoption Reports UI inside *win* (Toplevel or
    workspace tab Frame)."""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection

        ttk.Label(win, text=_t("admin_tools.usage.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        # Date range selector
        range_frame = ttk.Frame(win)
        range_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(range_frame, text=_t("admin_tools.usage.date_range")).pack(side=tk.LEFT, padx=5)
        range_var = tk.StringVar(value="30")
        range_combo = ttk.Combobox(range_frame, textvariable=range_var,
                                   values=["7", "30", "90"], width=5, state="readonly")
        range_combo.pack(side=tk.LEFT, padx=5)

        # Map display text
        range_labels = {"7": _t("admin_tools.usage.last_7_days"),
                        "30": _t("admin_tools.usage.last_30_days"),
                        "90": _t("admin_tools.usage.last_90_days")}
        range_display = ttk.Label(range_frame, text=range_labels.get("30", ""))
        range_display.pack(side=tk.LEFT, padx=5)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tab frames
        mod_frame = ttk.Frame(nb, padding=10)
        nb.add(mod_frame, text=_t("admin_tools.usage.module_usage"))

        heat_frame = ttk.Frame(nb, padding=10)
        nb.add(heat_frame, text=_t("admin_tools.usage.activity_heatmap"))

        user_frame = ttk.Frame(nb, padding=10)
        nb.add(user_frame, text=_t("admin_tools.usage.user_activity"))

        # Module usage tree
        mod_cols = ("action", "count", "percentage")
        mod_tree = ttk.Treeview(mod_frame, columns=mod_cols, show="headings", height=18)
        mod_tree.heading("action", text=_t("admin_tools.usage.action"))
        mod_tree.heading("count", text=_t("admin_tools.usage.action_count"))
        mod_tree.heading("percentage", text=_t("admin_tools.usage.percentage"))
        mod_tree.column("action", width=400)
        mod_tree.column("count", width=120)
        mod_tree.column("percentage", width=120)
        mod_scroll = ttk.Scrollbar(mod_frame, orient="vertical", command=mod_tree.yview)
        mod_tree.configure(yscrollcommand=mod_scroll.set)
        mod_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mod_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Heatmap text widget
        heat_text = tk.Text(heat_frame, wrap=tk.NONE, font=('Courier', 10),
                            fg="#000000", bg="#FFFFFF")
        heat_hscroll = ttk.Scrollbar(heat_frame, orient="horizontal", command=heat_text.xview)
        heat_text.configure(xscrollcommand=heat_hscroll.set)
        heat_text.pack(fill=tk.BOTH, expand=True)
        heat_hscroll.pack(fill=tk.X)

        # Color tags for heatmap
        heat_text.tag_configure("low", background="#e8f5e9", foreground="#000000")
        heat_text.tag_configure("medium", background="#fff9c4", foreground="#000000")
        heat_text.tag_configure("high", background="#ffcc80", foreground="#000000")
        heat_text.tag_configure("very_high", background="#ef9a9a", foreground="#000000")
        heat_text.tag_configure("header", font=('Courier', 10, 'bold'))

        # User activity tree
        usr_cols = ("username", "total_actions", "first_active", "last_active")
        usr_tree = ttk.Treeview(user_frame, columns=usr_cols, show="headings", height=18)
        usr_tree.heading("username", text=_t("admin_tools.usage.username"))
        usr_tree.heading("total_actions", text=_t("admin_tools.usage.total_actions"))
        usr_tree.heading("first_active", text=_t("admin_tools.usage.first_active"))
        usr_tree.heading("last_active", text=_t("admin_tools.usage.last_active"))
        usr_tree.column("username", width=200)
        usr_tree.column("total_actions", width=120)
        usr_tree.column("first_active", width=180)
        usr_tree.column("last_active", width=180)
        usr_scroll = ttk.Scrollbar(user_frame, orient="vertical", command=usr_tree.yview)
        usr_tree.configure(yscrollcommand=usr_scroll.set)
        usr_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        usr_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _load_data():
            days = int(range_var.get())
            range_display.config(text=range_labels.get(range_var.get(), ""))
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

            # Clear existing data
            for item in mod_tree.get_children():
                mod_tree.delete(item)
            for item in usr_tree.get_children():
                usr_tree.delete(item)

            try:
                conn = get_connection()

                # Check if activity_log table exists
                tables = [r[0] if isinstance(r, tuple) else r['name']
                          for r in conn.execute(
                              "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                if 'activity_log' not in tables:
                    heat_text.config(state=tk.NORMAL)
                    heat_text.delete("1.0", tk.END)
                    heat_text.insert("1.0", _t("admin_tools.usage.no_activity_data"))
                    heat_text.config(state=tk.DISABLED)
                    conn.close()
                    return

                # Detect columns
                cols_info = conn.execute("PRAGMA table_info(activity_log)").fetchall()
                col_names = [r[1] if isinstance(r, tuple) else r['name'] for r in cols_info]

                action_col = 'action' if 'action' in col_names else 'activity_type' if 'activity_type' in col_names else None
                ts_col = 'timestamp' if 'timestamp' in col_names else 'created_at' if 'created_at' in col_names else None
                user_col = 'username' if 'username' in col_names else 'user_id' if 'user_id' in col_names else None

                if not action_col or not ts_col:
                    heat_text.config(state=tk.NORMAL)
                    heat_text.delete("1.0", tk.END)
                    heat_text.insert("1.0", _t("admin_tools.usage.no_activity_data"))
                    heat_text.config(state=tk.DISABLED)
                    conn.close()
                    return

                # Module usage
                rows = conn.execute(f"""
                    SELECT {action_col}, COUNT(*) as cnt
                    FROM activity_log
                    WHERE {ts_col} >= ?
                    GROUP BY {action_col}
                    ORDER BY cnt DESC
                """, (cutoff,)).fetchall()

                total_actions = sum(r[1] if isinstance(r, tuple) else r['cnt'] for r in rows) if rows else 0

                for r in rows:
                    action = r[0] if isinstance(r, tuple) else r[action_col]
                    cnt = r[1] if isinstance(r, tuple) else r['cnt']
                    pct = (cnt / total_actions * 100) if total_actions > 0 else 0
                    mod_tree.insert('', tk.END, values=(action or "unknown", cnt, f"{pct:.1f}%"))

                # Heatmap: day x hour
                heatmap_rows = conn.execute(f"""
                    SELECT CAST(strftime('%w', {ts_col}) AS INTEGER) as dow,
                           CAST(strftime('%H', {ts_col}) AS INTEGER) as hour,
                           COUNT(*) as cnt
                    FROM activity_log
                    WHERE {ts_col} >= ?
                    GROUP BY dow, hour
                """, (cutoff,)).fetchall()

                # Build grid
                grid = [[0]*24 for _ in range(7)]
                max_val = 1
                for r in heatmap_rows:
                    dow = r[0] if isinstance(r, tuple) else r['dow']
                    hr = r[1] if isinstance(r, tuple) else r['hour']
                    cnt = r[2] if isinstance(r, tuple) else r['cnt']
                    if dow is not None and hr is not None:
                        grid[dow][hr] = cnt
                        if cnt > max_val:
                            max_val = cnt

                day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

                heat_text.config(state=tk.NORMAL)
                heat_text.delete("1.0", tk.END)
                heat_text.insert(tk.END, _t("admin_tools.usage.heatmap_header") + "\n\n", "header")

                # Header row
                header_line = "     " + "".join(f"{h:>5}" for h in range(24)) + "\n"
                heat_text.insert(tk.END, header_line, "header")

                for d in range(7):
                    heat_text.insert(tk.END, f"{day_names[d]:>4} ")
                    for h in range(24):
                        val = grid[d][h]
                        cell = f"{val:>5}"
                        if val == 0:
                            tag = "low"
                        elif val < max_val * 0.33:
                            tag = "low"
                        elif val < max_val * 0.66:
                            tag = "medium"
                        elif val < max_val * 0.9:
                            tag = "high"
                        else:
                            tag = "very_high"
                        heat_text.insert(tk.END, cell, tag)
                    heat_text.insert(tk.END, "\n")

                heat_text.insert(tk.END, "\nLegend: ")
                for tag, lbl_key in [("low", "admin_tools.usage.low_activity"),
                                     ("medium", "admin_tools.usage.medium_activity"),
                                     ("high", "admin_tools.usage.high_activity"),
                                     ("very_high", "admin_tools.usage.very_high_activity")]:
                    heat_text.insert(tk.END, f"  {_t(lbl_key)}  ", tag)

                heat_text.config(state=tk.DISABLED)

                # User activity
                if user_col:
                    user_rows = conn.execute(f"""
                        SELECT {user_col}, COUNT(*) as cnt,
                               MIN({ts_col}) as first_active,
                               MAX({ts_col}) as last_active
                        FROM activity_log
                        WHERE {ts_col} >= ?
                        GROUP BY {user_col}
                        ORDER BY cnt DESC
                        LIMIT 50
                    """, (cutoff,)).fetchall()

                    for r in user_rows:
                        uname = r[0] if isinstance(r, tuple) else r[user_col]
                        cnt = r[1] if isinstance(r, tuple) else r['cnt']
                        first = r[2] if isinstance(r, tuple) else r['first_active']
                        last = r[3] if isinstance(r, tuple) else r['last_active']
                        usr_tree.insert('', tk.END, values=(uname or "unknown", cnt, first or "", last or ""))

                conn.close()

            except Exception as exc:
                logger.error(f"Usage report error: {exc}")
                heat_text.config(state=tk.NORMAL)
                heat_text.delete("1.0", tk.END)
                heat_text.insert("1.0", f"Error loading data: {exc}")
                heat_text.config(state=tk.DISABLED)

        range_combo.bind("<<ComboboxSelected>>", lambda e: _load_data())

        # Button bar
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text=_t("admin_tools.refresh"), command=_load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools.close"), command=win.destroy).pack(side=tk.RIGHT, padx=5)

        _load_data()

    except Exception as e:
        messagebox.showerror(_t("admin_tools.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 6: Custom Report Builder
# ---------------------------------------------------------------------------

def show_custom_report_builder(self):
    """Custom report builder with SQL query generation, preview, and export.

    Renders inside the main GUI's content notebook when a workspace is
    available; falls back to a Toplevel otherwise.
    """
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    title = _t("admin_tools_v2.report_builder.title")
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: _build_custom_report_builder(self, host))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(title)
        win.geometry("1100x750")
        win.transient(self.root)
        _build_custom_report_builder(self, win)
    except Exception as e:
        logger.exception("Error in Custom Report Builder")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


def _build_custom_report_builder(self, win):
    """Build the Custom Report Builder UI inside *win* (Toplevel or
    workspace tab Frame)."""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection

        ttk.Label(win, text=_t("admin_tools_v2.report_builder.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Tab 1: Build Report ---
        build_frame = ttk.Frame(notebook, padding=10)
        notebook.add(build_frame, text=_t("admin_tools_v2.report_builder.tab_build"))

        top_frame = ttk.Frame(build_frame)
        top_frame.pack(fill=tk.X, pady=5)

        # Table selector
        ttk.Label(top_frame, text=_t("admin_tools_v2.report_builder.data_source")).pack(side=tk.LEFT)
        table_var = tk.StringVar()
        table_combo = ttk.Combobox(top_frame, textvariable=table_var, state='readonly', width=30)
        table_combo.pack(side=tk.LEFT, padx=5)

        # Load tables from sqlite_master
        tables = []
        try:
            conn = get_connection()
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row['name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
            conn.close()
        except Exception:
            pass
        table_combo['values'] = tables

        # Columns frame
        col_frame = ttk.LabelFrame(build_frame, text=_t("admin_tools_v2.report_builder.columns"), padding=5)
        col_frame.pack(fill=tk.X, pady=5)

        col_vars = {}
        col_inner = ttk.Frame(col_frame)
        col_inner.pack(fill=tk.X)

        def on_table_change(*_args):
            for w in col_inner.winfo_children():
                w.destroy()
            col_vars.clear()
            table = table_var.get()
            if not table:
                return
            try:
                conn = get_connection()
                cursor = conn.execute(f"PRAGMA table_info({table})")
                cols = cursor.fetchall()
                conn.close()
                for i, c in enumerate(cols):
                    cname = c['name'] if isinstance(c, dict) else c[1]
                    var = tk.BooleanVar(value=True)
                    col_vars[cname] = var
                    ttk.Checkbutton(col_inner, text=cname, variable=var).grid(
                        row=i // 6, column=i % 6, sticky='w', padx=5)
            except Exception:
                pass

        table_var.trace_add('write', on_table_change)

        # Filters
        filter_frame = ttk.LabelFrame(build_frame, text=_t("admin_tools_v2.report_builder.filters"), padding=5)
        filter_frame.pack(fill=tk.X, pady=5)
        filter_rows = []

        def add_filter_row():
            row_frame = ttk.Frame(filter_frame)
            row_frame.pack(fill=tk.X, pady=2)
            col_e = ttk.Entry(row_frame, width=20)
            col_e.pack(side=tk.LEFT, padx=2)
            op_var = tk.StringVar(value='=')
            op_combo = ttk.Combobox(row_frame, textvariable=op_var, values=['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'IN'], width=8, state='readonly')
            op_combo.pack(side=tk.LEFT, padx=2)
            val_e = ttk.Entry(row_frame, width=25)
            val_e.pack(side=tk.LEFT, padx=2)
            ttk.Button(row_frame, text=_t("admin_tools_v2.report_builder.remove_filter"),
                       command=lambda: (filter_rows.remove((col_e, op_var, val_e, row_frame)), row_frame.destroy())).pack(side=tk.LEFT, padx=2)
            filter_rows.append((col_e, op_var, val_e, row_frame))

        ttk.Button(filter_frame, text=_t("admin_tools_v2.report_builder.add_filter"),
                   command=add_filter_row).pack(anchor='w')

        # Sort & Limit
        sort_frame = ttk.Frame(build_frame)
        sort_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sort_frame, text=_t("admin_tools_v2.report_builder.sort_by")).pack(side=tk.LEFT)
        sort_var = tk.StringVar()
        sort_entry = ttk.Entry(sort_frame, textvariable=sort_var, width=20)
        sort_entry.pack(side=tk.LEFT, padx=5)
        order_var = tk.StringVar(value='ASC')
        ttk.Combobox(sort_frame, textvariable=order_var,
                     values=['ASC', 'DESC'], width=8, state='readonly').pack(side=tk.LEFT, padx=5)
        ttk.Label(sort_frame, text=_t("admin_tools_v2.report_builder.limit")).pack(side=tk.LEFT, padx=(20, 0))
        limit_var = tk.StringVar(value='100')
        ttk.Entry(sort_frame, textvariable=limit_var, width=8).pack(side=tk.LEFT, padx=5)

        # Results
        result_frame = ttk.Frame(build_frame)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        result_tree = ttk.Treeview(result_frame, show='headings')
        result_scroll_y = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=result_tree.yview)
        result_scroll_x = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL, command=result_tree.xview)
        result_tree.configure(yscrollcommand=result_scroll_y.set, xscrollcommand=result_scroll_x.set)
        result_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        result_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        result_tree.pack(fill=tk.BOTH, expand=True)

        status_var = tk.StringVar()
        ttk.Label(build_frame, textvariable=status_var).pack(anchor='w')

        last_query_data = {'columns': [], 'rows': []}

        def _get_valid_columns(table_name):
            """Get the set of valid column names for a table."""
            valid = set()
            try:
                conn = get_connection()
                cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
                valid = {row['name'] if isinstance(row, dict) else row[1] for row in cursor.fetchall()}
                conn.close()
            except Exception:
                pass
            return valid

        ALLOWED_OPS = {'=', '!=', '>', '<', '>=', '<=', 'LIKE', 'IN'}
        ALLOWED_ORDERS = {'ASC', 'DESC'}

        def run_preview():
            table = table_var.get()
            if not table or table not in tables:
                messagebox.showwarning(_t("admin_tools_v2.error"), _t("admin_tools_v2.report_builder.invalid_table"))
                return
            selected_cols = [c for c, v in col_vars.items() if v.get()]
            if not selected_cols:
                messagebox.showwarning(_t("admin_tools_v2.error"), _t("admin_tools_v2.report_builder.no_columns"))
                return

            # Validate column names against actual table schema
            valid_columns = _get_valid_columns(table)
            selected_cols = [c for c in selected_cols if c in valid_columns]
            if not selected_cols:
                messagebox.showwarning(_t("admin_tools_v2.error"), _t("admin_tools_v2.report_builder.no_columns"))
                return

            col_str = ', '.join(f'[{c}]' for c in selected_cols)
            query = f"SELECT {col_str} FROM [{table}]"
            params = []

            # Build WHERE — validate filter column names and operators
            wheres = []
            for col_e, op_var_f, val_e, _ in filter_rows:
                col_name = col_e.get().strip()
                op = op_var_f.get()
                val = val_e.get().strip()
                if col_name and val and col_name in valid_columns and op in ALLOWED_OPS:
                    wheres.append(f"[{col_name}] {op} ?")
                    params.append(val)
            if wheres:
                query += " WHERE " + " AND ".join(wheres)

            # Validate sort column against table schema
            sort = sort_var.get().strip()
            if sort and sort in valid_columns:
                order = order_var.get().upper()
                if order not in ALLOWED_ORDERS:
                    order = 'ASC'
                query += f" ORDER BY [{sort}] {order}"

            try:
                lim = int(limit_var.get())
                query += f" LIMIT {lim}"
            except ValueError:
                pass

            try:
                conn = get_connection()
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                # Update treeview
                result_tree.delete(*result_tree.get_children())
                result_tree['columns'] = selected_cols
                for c in selected_cols:
                    result_tree.heading(c, text=c)
                    result_tree.column(c, width=120)

                row_data = []
                for row in rows:
                    vals = [row[c] if isinstance(row, dict) else row[i] for i, c in enumerate(selected_cols)]
                    result_tree.insert('', tk.END, values=vals)
                    row_data.append(vals)

                last_query_data['columns'] = selected_cols
                last_query_data['rows'] = row_data
                status_var.set(_t("admin_tools_v2.report_builder.rows_found").format(count=len(rows)))
            except Exception as e:
                messagebox.showerror(_t("admin_tools_v2.error"),
                                     _t("admin_tools_v2.report_builder.query_error").format(error=str(e)))

        def export_csv_report():
            if not last_query_data['columns']:
                return
            path = filedialog.asksaveasfilename(defaultextension='.csv',
                                                  filetypes=[('CSV', '*.csv')])
            if not path:
                return
            try:
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(last_query_data['columns'])
                    writer.writerows(last_query_data['rows'])
                messagebox.showinfo(_t("admin_tools_v2.success"),
                                    _t("admin_tools_v2.report_builder.exported").format(path=path))
            except Exception as e:
                messagebox.showerror(_t("admin_tools_v2.error"),
                                     _t("admin_tools_v2.report_builder.export_error").format(error=str(e)))

        def save_report():
            name = save_name_var.get().strip()
            if not name:
                return
            report = {
                'name': name,
                'table': table_var.get(),
                'columns': [c for c, v in col_vars.items() if v.get()],
                'filters': [(ce.get(), ov.get(), ve.get()) for ce, ov, ve, _ in filter_rows],
                'sort': sort_var.get(),
                'order': order_var.get(),
                'limit': limit_var.get(),
                'saved_at': datetime.now().isoformat()
            }
            saved_path = str(SAVED_REPORTS_FILE)
            reports = _load_json(saved_path, [])
            reports.append(report)
            _save_json(saved_path, reports)
            messagebox.showinfo(_t("admin_tools_v2.success"), _t("admin_tools_v2.report_builder.saved"))
            load_saved_reports()

        btn_frame = ttk.Frame(build_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text=_t("admin_tools_v2.report_builder.preview"), command=run_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools_v2.report_builder.export"), command=export_csv_report).pack(side=tk.LEFT, padx=5)
        save_name_var = tk.StringVar()
        ttk.Entry(btn_frame, textvariable=save_name_var, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools_v2.report_builder.save_report"), command=save_report).pack(side=tk.LEFT, padx=5)

        # --- Tab 2: Saved Reports ---
        saved_frame = ttk.Frame(notebook, padding=10)
        notebook.add(saved_frame, text=_t("admin_tools_v2.report_builder.tab_saved"))

        saved_tree = ttk.Treeview(saved_frame, columns=('name', 'table', 'columns', 'saved_at'), show='headings')
        for c, w in [('name', 200), ('table', 120), ('columns', 300), ('saved_at', 180)]:
            saved_tree.heading(c, text=c.replace('_', ' ').title())
            saved_tree.column(c, width=w)
        saved_tree.pack(fill=tk.BOTH, expand=True)

        def load_saved_reports():
            saved_tree.delete(*saved_tree.get_children())
            saved_path = str(SAVED_REPORTS_FILE)
            reports = _load_json(saved_path, [])
            if not reports:
                return
            for r in reports:
                saved_tree.insert('', tk.END, values=(
                    r.get('name', ''), r.get('table', ''),
                    ', '.join(r.get('columns', [])), r.get('saved_at', '')))

        def load_selected_report():
            sel = saved_tree.selection()
            if not sel:
                return
            idx = saved_tree.index(sel[0])
            saved_path = str(SAVED_REPORTS_FILE)
            reports = _load_json(saved_path, [])
            if idx < len(reports):
                r = reports[idx]
                table_var.set(r.get('table', ''))
                on_table_change()
                win.after(100, lambda: _apply_saved(r))

        def _apply_saved(r):
            for cname, var in col_vars.items():
                var.set(cname in r.get('columns', []))
            sort_var.set(r.get('sort', ''))
            order_var.set(r.get('order', 'ASC'))
            limit_var.set(r.get('limit', '100'))
            notebook.select(0)

        def delete_selected_report():
            sel = saved_tree.selection()
            if not sel:
                return
            idx = saved_tree.index(sel[0])
            saved_path = str(SAVED_REPORTS_FILE)
            reports = _load_json(saved_path, [])
            if idx < len(reports):
                reports.pop(idx)
                _save_json(saved_path, reports)
                load_saved_reports()

        saved_btn_frame = ttk.Frame(saved_frame)
        saved_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(saved_btn_frame, text=_t("admin_tools_v2.report_builder.load"), command=load_selected_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(saved_btn_frame, text=_t("admin_tools_v2.delete"), command=delete_selected_report).pack(side=tk.LEFT, padx=5)

        load_saved_reports()

        # --- Tab 3: Scheduled Reports ---
        sched_frame = ttk.Frame(notebook, padding=10)
        notebook.add(sched_frame, text=_t("admin_tools_v2.report_builder.tab_scheduled"))

        sched_tree = ttk.Treeview(sched_frame, columns=('name', 'frequency', 'next_run', 'format'), show='headings')
        for c, w in [('name', 250), ('frequency', 120), ('next_run', 200), ('format', 100)]:
            sched_tree.heading(c, text=c.replace('_', ' ').title())
            sched_tree.column(c, width=w)
        sched_tree.pack(fill=tk.BOTH, expand=True)

        sched_path = str(SCHEDULED_REPORTS_FILE)
        scheduled = _load_json(sched_path, [])
        if scheduled:
            for s in scheduled:
                sched_tree.insert('', tk.END, values=(
                    s.get('name', ''), s.get('frequency', ''),
                    s.get('next_run', ''), s.get('format', '')))
        else:
            ttk.Label(sched_frame, text=_t("admin_tools_v2.report_builder.no_scheduled")).pack(pady=20)

    except Exception as e:
        logger.exception("Error in Custom Report Builder")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 7: API Documentation Browser
# ---------------------------------------------------------------------------
