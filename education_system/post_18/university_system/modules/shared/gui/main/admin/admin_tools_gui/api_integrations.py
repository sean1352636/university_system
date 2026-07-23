from ._common import (
    API_SERVER_CONFIG_FILE,
    EMAIL_CONFIG_FILE,
    LOG_DIR,
    PROJECT_ROOT,
    _install_clean_close,
    _load_json,
    _t,
    datetime,
    json,
    logger,
    messagebox,
    os,
    tk,
    ttk,
)

def show_api_documentation(self):
    """API documentation browser with endpoint listing, config view, and test tool."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.api_docs.title"))
        win.geometry("1100x750")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.api_docs.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        api_config_path = str(API_SERVER_CONFIG_FILE)
        api_config = _load_json(api_config_path)

        # --- Tab 1: Endpoints ---
        ep_frame = ttk.Frame(notebook, padding=10)
        notebook.add(ep_frame, text=_t("admin_tools_v2.api_docs.tab_endpoints"))

        ep_tree = ttk.Treeview(ep_frame,
                               columns=('endpoint', 'method', 'description', 'source'),
                               show='headings')
        for c, w in [('endpoint', 300), ('method', 80), ('description', 350), ('source', 200)]:
            ep_tree.heading(c, text=c.title())
            ep_tree.column(c, width=w)
        ep_scroll = ttk.Scrollbar(ep_frame, orient=tk.VERTICAL, command=ep_tree.yview)
        ep_tree.configure(yscrollcommand=ep_scroll.set)
        ep_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        ep_tree.pack(fill=tk.BOTH, expand=True)

        # Load from config endpoints
        endpoints = api_config.get('endpoints', [])
        for ep in endpoints:
            path = ep.get('path', ep.get('url', ''))
            method = ep.get('method', ep.get('methods', 'GET'))
            if isinstance(method, list):
                method = ', '.join(method)
            desc = ep.get('description', ep.get('name', ''))
            ep_tree.insert('', tk.END, values=(path, method, desc, _t("admin_tools_v2.api_docs.config_file")))

        # Scan route files
        routes_dir = os.path.join(PROJECT_ROOT, 'api', 'routes')
        if os.path.isdir(routes_dir):
            for fname in sorted(os.listdir(routes_dir)):
                if fname.endswith('.py') and fname != '__init__.py':
                    module_name = fname.replace('.py', '')
                    ep_tree.insert('', tk.END, values=(
                        f'/api/{module_name}/*', 'GET/POST', f'Route module: {module_name}',
                        _t("admin_tools_v2.api_docs.route_files")))

        # --- Tab 2: Server Config ---
        cfg_frame = ttk.Frame(notebook, padding=10)
        notebook.add(cfg_frame, text=_t("admin_tools_v2.api_docs.tab_config"))

        config_fields = [
            (_t("admin_tools_v2.api_docs.host"), api_config.get('host', 'N/A')),
            (_t("admin_tools_v2.api_docs.port"), str(api_config.get('port', 'N/A'))),
            (_t("admin_tools_v2.api_docs.debug"), str(api_config.get('debug', False))),
            (_t("admin_tools_v2.api_docs.ssl"), str(api_config.get('ssl_enabled', False))),
            (_t("admin_tools_v2.api_docs.auth_method"), api_config.get('authentication', {}).get('method', 'N/A')),
            (_t("admin_tools_v2.api_docs.rate_limiting"),
             str(api_config.get('rate_limiting', {}).get('enabled', False))),
            (_t("admin_tools_v2.api_docs.requests_per_min"),
             str(api_config.get('rate_limiting', {}).get('requests_per_minute', 'N/A'))),
            (_t("admin_tools_v2.api_docs.jwt_algorithm"),
             api_config.get('jwt', {}).get('algorithm', 'N/A')),
            (_t("admin_tools_v2.api_docs.jwt_access_exp"),
             str(api_config.get('jwt', {}).get('access_token_expires_minutes', 'N/A'))),
            (_t("admin_tools_v2.api_docs.jwt_refresh_exp"),
             str(api_config.get('jwt', {}).get('refresh_token_expires_days', 'N/A'))),
            (_t("admin_tools_v2.api_docs.started_at"), api_config.get('started_at', 'N/A')),
        ]

        for i, (label, value) in enumerate(config_fields):
            ttk.Label(cfg_frame, text=label, font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='w', padx=(10, 20), pady=3)
            ttk.Label(cfg_frame, text=value).grid(row=i, column=1, sticky='w', pady=3)

        # --- Tab 3: Test Endpoint ---
        test_frame = ttk.Frame(notebook, padding=10)
        notebook.add(test_frame, text=_t("admin_tools_v2.api_docs.tab_test"))

        url_frame = ttk.Frame(test_frame)
        url_frame.pack(fill=tk.X, pady=5)
        method_var = tk.StringVar(value='GET')
        ttk.Combobox(url_frame, textvariable=method_var,
                     values=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
                     width=8, state='readonly').pack(side=tk.LEFT, padx=5)
        ttk.Label(url_frame, text=_t("admin_tools_v2.api_docs.url")).pack(side=tk.LEFT)
        url_var = tk.StringVar(value=f"http://{api_config.get('host', 'localhost')}:{api_config.get('port', 5000)}/api/status")
        ttk.Entry(url_frame, textvariable=url_var, width=60).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Label(test_frame, text=_t("admin_tools_v2.api_docs.request_body")).pack(anchor='w', padx=5)
        body_text = tk.Text(test_frame, height=5, width=80)
        body_text.pack(fill=tk.X, padx=5, pady=5)

        resp_label = ttk.Label(test_frame, text=_t("admin_tools_v2.api_docs.response"))
        resp_label.pack(anchor='w', padx=5)
        resp_text = tk.Text(test_frame, height=15, state=tk.DISABLED)
        resp_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def send_request():
            import urllib.request
            import urllib.error
            url = url_var.get().strip()
            method = method_var.get()
            body = body_text.get('1.0', tk.END).strip() or None

            resp_text.config(state=tk.NORMAL)
            resp_text.delete('1.0', tk.END)

            try:
                data = body.encode('utf-8') if body else None
                req = urllib.request.Request(url, data=data, method=method)
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=10) as response:
                    status = response.status
                    result = response.read().decode('utf-8')
                    resp_text.insert(tk.END, f"{_t('admin_tools_v2.api_docs.status_code')}: {status}\n\n")
                    try:
                        formatted = json.dumps(json.loads(result), indent=2)
                        resp_text.insert(tk.END, formatted)
                    except (json.JSONDecodeError, ValueError):
                        resp_text.insert(tk.END, result)
            except Exception as e:
                resp_text.insert(tk.END, _t("admin_tools_v2.api_docs.request_error").format(error=str(e)))
            resp_text.config(state=tk.DISABLED)

        ttk.Button(test_frame, text=_t("admin_tools_v2.api_docs.send"), command=send_request).pack(pady=5)

    except Exception as e:
        logger.exception("Error in API Documentation Browser")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 8: Notification Template Manager
# ---------------------------------------------------------------------------

def show_integration_status_dashboard(self):
    """Integration status dashboard with connection monitoring and sync log."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.integration.title"))
        win.geometry("1100x700")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools_v2.integration.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        auto_refresh_id = [None]

        # --- Tab 1: Connection Status ---
        status_frame = ttk.Frame(notebook, padding=10)
        notebook.add(status_frame, text=_t("admin_tools_v2.integration.tab_status"))

        cards_frame = ttk.Frame(status_frame)
        cards_frame.pack(fill=tk.X, pady=10)
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)

        status_labels = {}

        def make_status_card(parent, col, title, key):
            frame = ttk.LabelFrame(parent, text=title, padding=10)
            frame.grid(row=0, column=col, padx=5, sticky='nsew')
            status_lbl = ttk.Label(frame, text=_t("admin_tools_v2.integration.unknown"),
                                   font=('Arial', 14, 'bold'))
            status_lbl.pack()
            time_lbl = ttk.Label(frame, text='')
            time_lbl.pack()
            status_labels[key] = (status_lbl, time_lbl)

        make_status_card(cards_frame, 0, _t("admin_tools_v2.integration.database"), 'db')
        make_status_card(cards_frame, 1, _t("admin_tools_v2.integration.api_server"), 'api')
        make_status_card(cards_frame, 2, _t("admin_tools_v2.integration.email_smtp"), 'email')
        make_status_card(cards_frame, 3, _t("admin_tools_v2.integration.backup_system"), 'backup')

        ttk.Label(status_frame, text=_t("admin_tools_v2.integration.auto_refresh")).pack(pady=5)

        def check_statuses():
            now = datetime.now().strftime('%H:%M:%S')

            # Database
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                conn.execute("SELECT 1")
                conn.close()
                status_labels['db'][0].config(text=_t("admin_tools_v2.integration.connected"),
                                               foreground='green')
            except Exception:
                status_labels['db'][0].config(text=_t("admin_tools_v2.integration.disconnected"),
                                               foreground='red')
            status_labels['db'][1].config(text=f"{_t('admin_tools_v2.integration.last_check')}: {now}")

            # API Server
            api_config_path = str(API_SERVER_CONFIG_FILE)
            api_cfg = _load_json(api_config_path)
            if api_cfg.get('host'):
                try:
                    import urllib.request
                    url = f"http://{api_cfg.get('host', 'localhost')}:{api_cfg.get('port', 5000)}/api/status"
                    urllib.request.urlopen(url, timeout=3)
                    status_labels['api'][0].config(text=_t("admin_tools_v2.integration.connected"),
                                                    foreground='green')
                except Exception:
                    status_labels['api'][0].config(text=_t("admin_tools_v2.integration.disconnected"),
                                                    foreground='orange')
            else:
                status_labels['api'][0].config(text=_t("admin_tools_v2.integration.disconnected"),
                                                foreground='gray')
            status_labels['api'][1].config(text=f"{_t('admin_tools_v2.integration.last_check')}: {now}")

            # Email
            email_path = str(EMAIL_CONFIG_FILE)
            email_cfg = _load_json(email_path)
            if email_cfg.get('smtp_server'):
                status_labels['email'][0].config(
                    text=_t("admin_tools_v2.integration.connected") if email_cfg.get('smtp_server') else _t("admin_tools_v2.integration.disconnected"),
                    foreground='green' if email_cfg.get('smtp_server') else 'red')
            else:
                status_labels['email'][0].config(text=_t("admin_tools_v2.integration.disconnected"),
                                                  foreground='gray')
            status_labels['email'][1].config(text=f"{_t('admin_tools_v2.integration.last_check')}: {now}")

            # Backup
            try:
                from education_system.post_18.university_system.infrastructure.database.data_backup.config import DEFAULT_CONFIG
                if DEFAULT_CONFIG.get('auto_backup_enabled', False):
                    status_labels['backup'][0].config(text=_t("admin_tools_v2.integration.connected"),
                                                       foreground='green')
                else:
                    status_labels['backup'][0].config(text=_t("admin_tools_v2.integration.disconnected"),
                                                       foreground='orange')
            except Exception:
                status_labels['backup'][0].config(text=_t("admin_tools_v2.integration.disconnected"),
                                                   foreground='red')
            status_labels['backup'][1].config(text=f"{_t('admin_tools_v2.integration.last_check')}: {now}")

            # Schedule next refresh
            if win.winfo_exists():
                auto_refresh_id[0] = win.after(30000, check_statuses)

        check_statuses()

        # --- Tab 2: Sync Log ---
        sync_frame = ttk.Frame(notebook, padding=10)
        notebook.add(sync_frame, text=_t("admin_tools_v2.integration.tab_sync"))

        sync_tree = ttk.Treeview(sync_frame,
                                 columns=('timestamp', 'event', 'details'), show='headings')
        for c, w in [('timestamp', 180), ('event', 200), ('details', 500)]:
            sync_tree.heading(c, text=c.title())
            sync_tree.column(c, width=w)
        sync_scroll = ttk.Scrollbar(sync_frame, orient=tk.VERTICAL, command=sync_tree.yview)
        sync_tree.configure(yscrollcommand=sync_scroll.set)
        sync_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        sync_tree.pack(fill=tk.BOTH, expand=True)

        # Load activity log for integration events
        log_path = str(LOG_DIR / 'app.log')
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-200:]
                keywords = ['backup', 'api', 'email', 'smtp', 'sync', 'integration', 'database', 'connection']
                for line in reversed(lines):
                    line = line.strip()
                    if any(kw in line.lower() for kw in keywords):
                        parts = line.split(' - ', 2)
                        ts = parts[0] if len(parts) > 0 else ''
                        event = parts[1] if len(parts) > 1 else ''
                        details = parts[2] if len(parts) > 2 else line
                        sync_tree.insert('', tk.END, values=(ts, event, details))
            except Exception:
                pass

        if not sync_tree.get_children():
            ttk.Label(sync_frame, text=_t("admin_tools_v2.integration.no_sync_log")).pack(pady=20)

        # --- Tab 3: Alert Configuration ---
        alert_frame = ttk.Frame(notebook, padding=10)
        notebook.add(alert_frame, text=_t("admin_tools_v2.integration.tab_alerts"))

        ttk.Label(alert_frame, text=_t("admin_tools_v2.integration.webhook_urls"),
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)

        try:
            from education_system.post_18.university_system.infrastructure.database.data_backup.config import DEFAULT_CONFIG as bkp_cfg
            slack = bkp_cfg.get('slack_webhook', '')
            discord = bkp_cfg.get('discord_webhook', '')
        except Exception:
            slack = discord = ''

        wh_frame = ttk.Frame(alert_frame)
        wh_frame.pack(fill=tk.X, pady=5)
        ttk.Label(wh_frame, text=_t("admin_tools_v2.integration.slack_webhook"), width=20).pack(side=tk.LEFT)
        ttk.Label(wh_frame, text=slack if slack else '(not configured)').pack(side=tk.LEFT, padx=5)
        wh_frame2 = ttk.Frame(alert_frame)
        wh_frame2.pack(fill=tk.X, pady=5)
        ttk.Label(wh_frame2, text=_t("admin_tools_v2.integration.discord_webhook"), width=20).pack(side=tk.LEFT)
        ttk.Label(wh_frame2, text=discord if discord else '(not configured)').pack(side=tk.LEFT, padx=5)

        ttk.Separator(alert_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(alert_frame, text=_t("admin_tools_v2.integration.alert_types"),
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=5)

        for alert_key in ['alert_backup_fail', 'alert_db_error', 'alert_api_down', 'alert_email_fail']:
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(alert_frame, text=_t(f"admin_tools_v2.integration.{alert_key}"),
                            variable=var).pack(anchor='w', padx=10, pady=2)

        def _on_close():
            if auto_refresh_id[0]:
                win.after_cancel(auto_refresh_id[0])
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    except Exception as e:
        logger.exception("Error in Integration Status Dashboard")
        messagebox.showerror(_t("admin_tools_v2.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 13: License / Subscription Management
# ---------------------------------------------------------------------------
