from ._common import (
    BACKUP_DIR,
    DB_DIR,
    LOG_DIR,
    UPLOAD_DIR,
    _install_clean_close,
    _t,
    csv,
    datetime,
    filedialog,
    logger,
    messagebox,
    os,
    tk,
    ttk,
)

def show_system_monitoring_dashboard(self):
    """Real-time system monitoring dashboard with CPU, memory, disk, and DB metrics."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools.access_denied"), _t("admin_tools.admin_required"))
        return

    try:
        import psutil
    except ImportError:
        psutil = None

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools.monitoring.title"))
        win.geometry("1000x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools.monitoring.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        # -- Metric cards frame --
        cards_frame = ttk.Frame(win)
        cards_frame.pack(fill=tk.X, padx=10, pady=5)
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)

        card_labels = {}

        def _make_card(parent, col, title, initial="--"):
            frame = ttk.LabelFrame(parent, text=title, padding=10)
            frame.grid(row=0, column=col, padx=5, sticky="nsew")
            val_lbl = ttk.Label(frame, text=initial, font=('Arial', 20, 'bold'))
            val_lbl.pack()
            status_lbl = ttk.Label(frame, text="", font=('Arial', 10))
            status_lbl.pack()
            return val_lbl, status_lbl

        card_labels['cpu'] = _make_card(cards_frame, 0, _t("admin_tools.monitoring.cpu_usage"))
        card_labels['mem'] = _make_card(cards_frame, 1, _t("admin_tools.monitoring.memory_usage"))
        card_labels['disk'] = _make_card(cards_frame, 2, _t("admin_tools.monitoring.disk_usage"))
        card_labels['db'] = _make_card(cards_frame, 3, _t("admin_tools.monitoring.db_status"))

        # -- Notebook with tabs --
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tab 1: System Health
        health_frame = ttk.Frame(nb, padding=10)
        nb.add(health_frame, text=_t("admin_tools.monitoring.system_health"))
        health_text = tk.Text(health_frame, wrap=tk.WORD, height=15, state=tk.DISABLED,
                              fg="#000000", bg="#FFFFFF")
        health_text.pack(fill=tk.BOTH, expand=True)

        # Tab 2: Active Connections / Pool
        pool_frame = ttk.Frame(nb, padding=10)
        nb.add(pool_frame, text=_t("admin_tools.monitoring.active_connections"))
        pool_text = tk.Text(pool_frame, wrap=tk.WORD, height=15, state=tk.DISABLED,
                            fg="#000000", bg="#FFFFFF")
        pool_text.pack(fill=tk.BOTH, expand=True)

        # Status bar
        status_lbl = ttk.Label(win, text=_t("admin_tools.monitoring.auto_refresh"),
                               font=('Arial', 9))
        status_lbl.pack(pady=(0, 5))

        def _color_for_pct(pct):
            if pct < 70:
                return "#2e7d32"  # green
            elif pct < 90:
                return "#f9a825"  # yellow
            return "#c62828"      # red

        def _status_text(pct):
            if pct < 70:
                return _t("admin_tools.monitoring.status_healthy")
            elif pct < 90:
                return _t("admin_tools.monitoring.status_warning")
            return _t("admin_tools.monitoring.status_critical")

        def _refresh():
            if not win.winfo_exists():
                return
            try:
                # CPU / Memory / Disk
                if psutil:
                    cpu = psutil.cpu_percent(interval=0)
                    mem = psutil.virtual_memory().percent
                    disk = psutil.disk_usage('/').percent
                else:
                    cpu = mem = disk = 0.0

                for key, pct in [('cpu', cpu), ('mem', mem), ('disk', disk)]:
                    val_lbl, st_lbl = card_labels[key]
                    val_lbl.config(text=f"{pct:.1f}%", foreground=_color_for_pct(pct))
                    st_lbl.config(text=_status_text(pct), foreground=_color_for_pct(pct))

                # DB test
                db_ok = False
                try:
                    from education_system.post_18.university_system.infrastructure.database.db import get_connection
                    conn = get_connection()
                    conn.execute("SELECT 1")
                    conn.close()
                    db_ok = True
                except Exception:
                    pass

                db_val, db_st = card_labels['db']
                if db_ok:
                    db_val.config(text=_t("admin_tools.monitoring.connected"), foreground="#2e7d32")
                    db_st.config(text=_t("admin_tools.monitoring.status_healthy"), foreground="#2e7d32")
                else:
                    db_val.config(text=_t("admin_tools.monitoring.disconnected"), foreground="#c62828")
                    db_st.config(text=_t("admin_tools.monitoring.status_critical"), foreground="#c62828")

                # Health tab
                lines = []
                if psutil:
                    lines.append(f"CPU Cores: {psutil.cpu_count(logical=True)}")
                    vm = psutil.virtual_memory()
                    lines.append(f"Total RAM: {vm.total / (1024**3):.1f} GB")
                    lines.append(f"Available RAM: {vm.available / (1024**3):.1f} GB")
                    du = psutil.disk_usage('/')
                    lines.append(f"Disk Total: {du.total / (1024**3):.1f} GB")
                    lines.append(f"Disk Free: {du.free / (1024**3):.1f} GB")
                    boot = datetime.fromtimestamp(psutil.boot_time())
                    lines.append(f"{_t('admin_tools.monitoring.uptime')}: {datetime.now() - boot}")
                else:
                    lines.append("psutil not available")

                health_text.config(state=tk.NORMAL)
                health_text.delete("1.0", tk.END)
                health_text.insert("1.0", "\n".join(lines))
                health_text.config(state=tk.DISABLED)

                # Pool tab
                pool_lines = []
                try:
                    from education_system.post_18.university_system.infrastructure.database.pool_metrics import get_pool_metrics
                    pm = get_pool_metrics()
                    stats = pm.get_stats()
                    pool_lines.append(f"=== {_t('admin_tools.monitoring.active_connections')} ===")
                    pool_lines.append(f"{_t('admin_tools.monitoring.pool_size')}: {stats.get('pool_max_size', 'N/A')}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.active')}: {stats.get('active_connections', 'N/A')}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.idle')}: {stats.get('idle_connections', 'N/A')}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.utilization')}: {stats.get('utilization', 0):.1f}%")
                    pool_lines.append("")
                    pool_lines.append("=== Cumulative ===")
                    pool_lines.append(f"{_t('admin_tools.monitoring.total_created')}: {stats.get('total_connections_created', 0)}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.total_closed')}: {stats.get('total_connections_closed', 0)}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.total_errors')}: {stats.get('total_errors', 0)}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.total_timeouts')}: {stats.get('total_timeouts', 0)}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.avg_wait_ms')}: {stats.get('avg_wait_time_ms', 0):.2f}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.peak_active')}: {stats.get('peak_active_connections', 0)}")
                except Exception as exc:
                    pool_lines.append(f"Pool metrics unavailable: {exc}")

                pool_text.config(state=tk.NORMAL)
                pool_text.delete("1.0", tk.END)
                pool_text.insert("1.0", "\n".join(pool_lines))
                pool_text.config(state=tk.DISABLED)

            except Exception as exc:
                logger.error(f"Monitoring refresh error: {exc}")

            if win.winfo_exists():
                win._refresh_id = win.after(10000, _refresh)

        # Cancel auto-refresh on close
        def _on_close():
            if hasattr(win, '_refresh_id'):
                try:
                    win.after_cancel(win._refresh_id)
                except Exception:
                    pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Button bar
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text=_t("admin_tools.refresh"), command=_refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools.close"), command=_on_close).pack(side=tk.RIGHT, padx=5)

        _refresh()

    except Exception as e:
        messagebox.showerror(_t("admin_tools.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 2: Configuration Editor
# ---------------------------------------------------------------------------

def show_query_analyser(self):
    """Performance and query analysis dashboard."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools.access_denied"), _t("admin_tools.admin_required"))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools.query_analyser.title"))
        win.geometry("1100x750")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools.query_analyser.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Get monitor
        monitor = None
        try:
            from education_system.post_18.university_system.infrastructure.database.query_monitor import get_query_monitor
            monitor = get_query_monitor()
        except Exception:
            pass

        # ---- Tab 1: Overview ----
        overview_frame = ttk.Frame(nb, padding=10)
        nb.add(overview_frame, text=_t("admin_tools.query_analyser.overview"))

        stats_grid = ttk.Frame(overview_frame)
        stats_grid.pack(fill=tk.X, pady=10)

        if monitor:
            try:
                stats = monitor.get_stats()
                total = stats.get('total_queries', 0)
                slow = stats.get('slow_queries', 0)
                slow_pct = (slow / total * 100) if total > 0 else 0
                avg_ms = stats.get('avg_duration_ms', 0)
                p95 = monitor.get_percentile(95.0)
            except Exception:
                total = slow = 0
                slow_pct = avg_ms = p95 = 0.0
        else:
            total = slow = 0
            slow_pct = avg_ms = p95 = 0.0

        overview_items = [
            (_t("admin_tools.query_analyser.total_queries"), str(total)),
            (_t("admin_tools.query_analyser.slow_count"), str(slow)),
            (_t("admin_tools.query_analyser.slow_pct"), f"{slow_pct:.1f}%"),
            (_t("admin_tools.query_analyser.avg_time_ms"), f"{avg_ms:.2f}"),
            (_t("admin_tools.query_analyser.p95_time_ms"), f"{p95:.2f}"),
        ]

        for col, (label, value) in enumerate(overview_items):
            f = ttk.LabelFrame(stats_grid, text=label, padding=10)
            f.grid(row=0, column=col, padx=5, sticky="nsew")
            stats_grid.columnconfigure(col, weight=1)
            ttk.Label(f, text=value, font=('Arial', 16, 'bold')).pack()

        # ---- Tab 2: Slow Queries ----
        slow_frame = ttk.Frame(nb, padding=10)
        nb.add(slow_frame, text=_t("admin_tools.query_analyser.slow_queries"))

        slow_cols = ("query", "duration_ms", "timestamp")
        slow_tree = ttk.Treeview(slow_frame, columns=slow_cols, show="headings", height=15)
        slow_tree.heading("query", text=_t("admin_tools.query_analyser.query"))
        slow_tree.heading("duration_ms", text=_t("admin_tools.query_analyser.duration_ms"))
        slow_tree.heading("timestamp", text=_t("admin_tools.query_analyser.timestamp"))
        slow_tree.column("query", width=500)
        slow_tree.column("duration_ms", width=120)
        slow_tree.column("timestamp", width=180)

        slow_scroll = ttk.Scrollbar(slow_frame, orient="vertical", command=slow_tree.yview)
        slow_tree.configure(yscrollcommand=slow_scroll.set)
        slow_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        slow_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        slow_queries_data = []
        if monitor:
            try:
                slow_queries_data = monitor.get_slow_queries(limit=100)
            except Exception:
                pass

        for sq in slow_queries_data:
            q_text = getattr(sq, 'query', str(sq))[:80]
            dur = getattr(sq, 'duration_ms', 0)
            ts = getattr(sq, 'timestamp', '')
            slow_tree.insert('', tk.END, values=(q_text, f"{dur:.2f}", str(ts)))

        def _on_slow_double_click(event):
            sel = slow_tree.selection()
            if not sel:
                return
            idx = slow_tree.index(sel[0])
            if idx < len(slow_queries_data):
                sq = slow_queries_data[idx]
                full_q = getattr(sq, 'query', str(sq))
                detail_win = tk.Toplevel(win)
                detail_win.title(_t("admin_tools.query_analyser.query_details"))
                detail_win.geometry("600x400")
                txt = tk.Text(detail_win, wrap=tk.WORD, fg="#000000", bg="#FFFFFF")
                txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                txt.insert("1.0", full_q)
                txt.config(state=tk.DISABLED)

        slow_tree.bind("<Double-1>", _on_slow_double_click)

        # ---- Tab 3: Query Patterns ----
        patterns_frame = ttk.Frame(nb, padding=10)
        nb.add(patterns_frame, text=_t("admin_tools.query_analyser.query_patterns"))

        pat_cols = ("pattern", "count", "avg_ms", "total_ms", "max_ms")
        pat_tree = ttk.Treeview(patterns_frame, columns=pat_cols, show="headings", height=15)
        pat_tree.heading("pattern", text=_t("admin_tools.query_analyser.pattern"))
        pat_tree.heading("count", text=_t("admin_tools.query_analyser.count"))
        pat_tree.heading("avg_ms", text=_t("admin_tools.query_analyser.avg_duration"))
        pat_tree.heading("total_ms", text=_t("admin_tools.query_analyser.total_duration"))
        pat_tree.heading("max_ms", text=_t("admin_tools.query_analyser.max_duration"))
        pat_tree.column("pattern", width=400)
        pat_tree.column("count", width=80)
        pat_tree.column("avg_ms", width=120)
        pat_tree.column("total_ms", width=120)
        pat_tree.column("max_ms", width=120)

        pat_scroll = ttk.Scrollbar(patterns_frame, orient="vertical", command=pat_tree.yview)
        pat_tree.configure(yscrollcommand=pat_scroll.set)
        pat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        if monitor:
            try:
                patterns = monitor.get_query_stats(top_n=50)
                for p in patterns:
                    pat_text = getattr(p, 'pattern', getattr(p, 'query', str(p)))[:60]
                    cnt = getattr(p, 'count', 0)
                    avg = getattr(p, 'avg_duration_ms', 0)
                    tot = getattr(p, 'total_duration_ms', 0)
                    mx = getattr(p, 'max_duration_ms', 0)
                    pat_tree.insert('', tk.END, values=(pat_text, cnt, f"{avg:.2f}", f"{tot:.1f}", f"{mx:.2f}"))
            except Exception:
                pass

        # ---- Tab 4: Connection Pool ----
        pool_tab = ttk.Frame(nb, padding=10)
        nb.add(pool_tab, text=_t("admin_tools.query_analyser.connection_pool"))

        pool_text = tk.Text(pool_tab, wrap=tk.WORD, height=20, state=tk.DISABLED,
                            fg="#000000", bg="#FFFFFF")
        pool_text.pack(fill=tk.BOTH, expand=True)

        pool_lines = []
        try:
            from education_system.post_18.university_system.infrastructure.database.pool_metrics import get_pool_metrics
            pm = get_pool_metrics()
            stats = pm.get_stats()

            pool_lines.append(f"=== {_t('admin_tools.query_analyser.current_state')} ===")
            pool_lines.append(f"Active: {stats.get('active_connections', 0)}")
            pool_lines.append(f"Idle: {stats.get('idle_connections', 0)}")
            pool_lines.append(f"Utilization: {stats.get('utilization', 0):.1f}%")
            pool_lines.append("")
            pool_lines.append(f"=== {_t('admin_tools.query_analyser.cumulative_stats')} ===")
            pool_lines.append(f"Created: {stats.get('total_connections_created', 0)}")
            pool_lines.append(f"Closed: {stats.get('total_connections_closed', 0)}")
            pool_lines.append(f"Errors: {stats.get('total_errors', 0)}")
            pool_lines.append(f"Timeouts: {stats.get('total_timeouts', 0)}")
            pool_lines.append(f"Avg Wait: {stats.get('avg_wait_time_ms', 0):.2f} ms")
            pool_lines.append(f"Peak Active: {stats.get('peak_active_connections', 0)}")
        except Exception as exc:
            pool_lines.append(f"Pool metrics unavailable: {exc}")

        pool_text.config(state=tk.NORMAL)
        pool_text.insert("1.0", "\n".join(pool_lines))
        pool_text.config(state=tk.DISABLED)

        # ---- Export button ----
        def _export_csv():
            if not slow_queries_data:
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                title=_t("admin_tools.export_csv"))
            if not path:
                return
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Query", "Duration (ms)", "Timestamp", "Rows Affected"])
                    for sq in slow_queries_data:
                        writer.writerow([
                            getattr(sq, 'query', str(sq)),
                            getattr(sq, 'duration_ms', 0),
                            getattr(sq, 'timestamp', ''),
                            getattr(sq, 'rows_affected', 0),
                        ])
                messagebox.showinfo(
                    _t("admin_tools.query_analyser.export_success"),
                    _t("admin_tools.query_analyser.export_success_msg", path=path))
            except Exception as exc:
                messagebox.showerror(_t("admin_tools.error"), str(exc))

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text=_t("admin_tools.export_csv"), command=_export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools.close"), command=win.destroy).pack(side=tk.RIGHT, padx=5)

    except Exception as e:
        messagebox.showerror(_t("admin_tools.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 4: Capacity Planning
# ---------------------------------------------------------------------------

def show_capacity_planning(self):
    """Capacity planning tools: storage analysis, user growth, resource projections."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools.access_denied"), _t("admin_tools.admin_required"))
        return

    try:
        import psutil
    except ImportError:
        psutil = None

    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools.capacity.title"))
        win.geometry("1000x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools.capacity.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ---- Helper: directory size ----
        def _dir_size(path):
            total_size = 0
            file_count = 0
            try:
                for dirpath, _dirnames, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            total_size += os.path.getsize(fp)
                        except OSError:
                            pass
                        file_count += 1
            except Exception:
                pass
            return total_size, file_count

        # ---- Tab 1: Storage Analysis ----
        storage_frame = ttk.Frame(nb, padding=10)
        nb.add(storage_frame, text=_t("admin_tools.capacity.storage_analysis"))

        stor_cols = ("directory", "size_mb", "files", "quota_pct")
        stor_tree = ttk.Treeview(storage_frame, columns=stor_cols, show="headings", height=8)
        stor_tree.heading("directory", text=_t("admin_tools.capacity.directory"))
        stor_tree.heading("size_mb", text=_t("admin_tools.capacity.size_mb"))
        stor_tree.heading("files", text=_t("admin_tools.capacity.files"))
        stor_tree.heading("quota_pct", text=_t("admin_tools.capacity.quota_pct"))
        stor_tree.column("directory", width=250)
        stor_tree.column("size_mb", width=120)
        stor_tree.column("files", width=100)
        stor_tree.column("quota_pct", width=120)
        stor_tree.pack(fill=tk.BOTH, expand=True)

        # Gather storage info
        dirs_to_check = [
            (_t("admin_tools.capacity.database"), DB_DIR),
            (_t("admin_tools.capacity.logs"), LOG_DIR),
            (_t("admin_tools.capacity.uploads"), UPLOAD_DIR),
            (_t("admin_tools.capacity.backups"), BACKUP_DIR),
        ]

        total_all = 0
        if psutil:
            disk_total = psutil.disk_usage('/').total
        else:
            disk_total = 1  # avoid division by zero

        for label, dirpath in dirs_to_check:
            size, count = _dir_size(dirpath)
            size_mb = size / (1024 * 1024)
            pct = (size / disk_total * 100) if disk_total > 0 else 0
            total_all += size
            stor_tree.insert('', tk.END, values=(label, f"{size_mb:.2f}", count, f"{pct:.3f}%"))

        total_mb = total_all / (1024 * 1024)
        total_pct = (total_all / disk_total * 100) if disk_total > 0 else 0
        stor_tree.insert('', tk.END, values=(
            _t("admin_tools.capacity.total_storage"), f"{total_mb:.2f}",
            "", f"{total_pct:.3f}%"))

        # ---- Tab 2: User Growth ----
        growth_frame = ttk.Frame(nb, padding=10)
        nb.add(growth_frame, text=_t("admin_tools.capacity.user_growth"))

        growth_cols = ("month", "new_users", "admin", "staff", "student", "instructor")
        growth_tree = ttk.Treeview(growth_frame, columns=growth_cols, show="headings", height=12)
        growth_tree.heading("month", text=_t("admin_tools.capacity.month"))
        growth_tree.heading("new_users", text=_t("admin_tools.capacity.new_users"))
        growth_tree.heading("admin", text=_t("admin_tools.capacity.admin_count"))
        growth_tree.heading("staff", text=_t("admin_tools.capacity.staff_count"))
        growth_tree.heading("student", text=_t("admin_tools.capacity.student_count"))
        growth_tree.heading("instructor", text=_t("admin_tools.capacity.instructor_count"))
        for c in growth_cols:
            growth_tree.column(c, width=110)
        growth_tree.pack(fill=tk.BOTH, expand=True)

        growth_data = []
        try:
            conn = get_connection()
            # Check if created_at column exists
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [row[1] if isinstance(row, tuple) else row['name'] for row in cursor.fetchall()]

            if 'created_at' in columns:
                rows = conn.execute("""
                    SELECT strftime('%Y-%m', created_at) as month,
                           COUNT(*) as total,
                           SUM(CASE WHEN role='admin' THEN 1 ELSE 0 END) as admins,
                           SUM(CASE WHEN role='staff' THEN 1 ELSE 0 END) as staff,
                           SUM(CASE WHEN role='student' THEN 1 ELSE 0 END) as students,
                           SUM(CASE WHEN role='instructor' THEN 1 ELSE 0 END) as instructors
                    FROM users
                    WHERE created_at IS NOT NULL
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 12
                """).fetchall()
                for r in rows:
                    month = r[0] if isinstance(r, tuple) else r['month']
                    total = r[1] if isinstance(r, tuple) else r['total']
                    admins = r[2] if isinstance(r, tuple) else r['admins']
                    staff = r[3] if isinstance(r, tuple) else r['staff']
                    students = r[4] if isinstance(r, tuple) else r['students']
                    instructors = r[5] if isinstance(r, tuple) else r['instructors']
                    growth_data.append((month, total))
                    growth_tree.insert('', tk.END, values=(
                        month, total, admins, staff, students, instructors))
            else:
                # Fallback: just count totals by role
                rows = conn.execute("""
                    SELECT role, COUNT(*) as cnt FROM users GROUP BY role
                """).fetchall()
                for r in rows:
                    role = r[0] if isinstance(r, tuple) else r['role']
                    cnt = r[1] if isinstance(r, tuple) else r['cnt']
                    growth_tree.insert('', tk.END, values=("(all time)", cnt, "", "", "", ""))
            conn.close()
        except Exception as exc:
            logger.warning(f"User growth query failed: {exc}")

        # Simple linear projection
        if len(growth_data) >= 2:
            recent_counts = [d[1] for d in growth_data[:3]]
            avg_growth = sum(recent_counts) / len(recent_counts)
            proj_label = ttk.Label(growth_frame,
                                   text=f"{_t('admin_tools.capacity.growth_rate')}: ~{avg_growth:.0f} users/month",
                                   font=('Arial', 10, 'italic'))
            proj_label.pack(pady=5)
        else:
            ttk.Label(growth_frame, text=_t("admin_tools.capacity.no_growth_data"),
                      font=('Arial', 10, 'italic')).pack(pady=5)

        # ---- Tab 3: Resource Projections ----
        proj_frame = ttk.Frame(nb, padding=10)
        nb.add(proj_frame, text=_t("admin_tools.capacity.resource_projections"))

        proj_text = tk.Text(proj_frame, wrap=tk.WORD, height=20, state=tk.DISABLED,
                            fg="#000000", bg="#FFFFFF")
        proj_text.pack(fill=tk.BOTH, expand=True)

        proj_lines = [
            f"=== {_t('admin_tools.capacity.resource_projections')} ===",
            "",
        ]

        # Table row counts
        try:
            conn = get_connection()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            proj_lines.append(f"{_t('admin_tools.capacity.table_name'):30s} {_t('admin_tools.capacity.row_count'):>10s}")
            proj_lines.append("-" * 42)
            for t in tables:
                tname = t[0] if isinstance(t, tuple) else t['name']
                try:
                    cnt = conn.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
                    proj_lines.append(f"{tname:30s} {cnt:>10,}")
                except Exception:
                    proj_lines.append(f"{tname:30s} {'N/A':>10s}")
            conn.close()
        except Exception as exc:
            proj_lines.append(f"DB query error: {exc}")

        proj_lines.append("")
        proj_lines.append(f"=== {_t('admin_tools.capacity.recommendations')} ===")

        if psutil:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            if mem.percent > 85:
                proj_lines.append("- WARNING: Memory usage is high, consider adding RAM")
            if disk.percent > 85:
                proj_lines.append("- WARNING: Disk usage is high, consider expanding storage")
            if mem.percent <= 85 and disk.percent <= 85:
                proj_lines.append("- System resources are within normal range")
        else:
            proj_lines.append("- psutil not available for resource analysis")

        proj_text.config(state=tk.NORMAL)
        proj_text.insert("1.0", "\n".join(proj_lines))
        proj_text.config(state=tk.DISABLED)

        # Button bar
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text=_t("admin_tools.close"), command=win.destroy).pack(side=tk.RIGHT, padx=5)

    except Exception as e:
        messagebox.showerror(_t("admin_tools.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 5: Usage / Adoption Reports
# ---------------------------------------------------------------------------
