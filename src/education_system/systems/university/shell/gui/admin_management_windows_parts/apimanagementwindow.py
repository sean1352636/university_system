"""Extracted class implementation."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ApiManagementWindow:
    """Comprehensive API Management Interface"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.api.title"))
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.api.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Create notebook for different API sections
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # API Keys Tab
        keys_frame = ttk.Frame(notebook)
        notebook.add(keys_frame, text=_("admin_windows.api.tabs.api_keys"))
        self.create_api_keys_tab(keys_frame)

        # Endpoints Tab
        endpoints_frame = ttk.Frame(notebook)
        notebook.add(endpoints_frame, text=_("admin_windows.api.tabs.endpoints"))
        self.create_endpoints_tab(endpoints_frame)

        # Usage Analytics Tab
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text=_("admin_windows.api.tabs.analytics"))
        self.create_analytics_tab(analytics_frame)

        # Security Tab
        security_frame = ttk.Frame(notebook)
        notebook.add(security_frame, text=_("admin_windows.api.tabs.security"))
        self.create_security_tab(security_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def create_api_keys_tab(self, parent):
        """Create API keys management tab"""
        # API keys list
        keys_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.keys.active_keys"), padding="15")
        keys_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Keys treeview
        columns = ('Key ID', 'Name', 'Type', 'Created', 'Last Used', 'Status', 'Requests')
        column_names = [
            _("admin_windows.api.keys.columns.key_id"),
            _("admin_windows.api.keys.columns.name"),
            _("admin_windows.api.keys.columns.type"),
            _("admin_windows.api.keys.columns.created"),
            _("admin_windows.api.keys.columns.last_used"),
            _("admin_windows.api.keys.columns.status"),
            _("admin_windows.api.keys.columns.requests")
        ]
        self.keys_tree = ttk.Treeview(keys_frame, columns=columns, show='headings', height=12)

        for col, name in zip(columns, column_names):
            self.keys_tree.heading(col, text=name)
            self.keys_tree.column(col, width=120)

        self.keys_tree.pack(fill='both', expand=True, pady=(0, 15))

        # Real keys from the platform API-key store (auth.db, PBKDF2-hashed;
        # the raw key is shown once at creation and never stored).
        self.keys_note_var = tk.StringVar(value="")
        ttk.Label(keys_frame, textvariable=self.keys_note_var, foreground='#555555',
                  wraplength=800, justify='left').pack(fill='x', pady=(0, 10))
        self.load_api_keys()

        # Controls
        controls_frame = ttk.Frame(keys_frame)
        controls_frame.pack(fill='x')

        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.generate"),
                  command=self.generate_api_key).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.revoke"),
                  command=self.revoke_api_key).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.view_details"),
                  command=self.view_key_details).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.export"),
                  command=self.export_keys).pack(side='left')

    def create_endpoints_tab(self, parent):
        """Create API endpoints tab"""
        # Endpoints list
        endpoints_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.endpoints.available"), padding="15")
        endpoints_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Endpoints treeview
        columns = ('Method', 'Endpoint', 'Description', 'Auth Required', 'Rate Limit', 'Status')
        column_names = [
            _("admin_windows.api.endpoints.columns.method"),
            _("admin_windows.api.endpoints.columns.endpoint"),
            _("admin_windows.api.endpoints.columns.description"),
            _("admin_windows.api.endpoints.columns.auth_required"),
            _("admin_windows.api.endpoints.columns.rate_limit"),
            _("admin_windows.api.endpoints.columns.status")
        ]
        self.endpoints_tree = ttk.Treeview(endpoints_frame, columns=columns, show='headings', height=15)

        for col, name in zip(columns, column_names):
            self.endpoints_tree.heading(col, text=name)
            self.endpoints_tree.column(col, width=150)

        self.endpoints_tree.pack(fill='both', expand=True, pady=(0, 15))

        # The university routes the unified API mounts, read from a Flask
        # url_map built without serving (see infrastructure/api_admin_info).
        # Building it imports every route module, so it runs off the UI thread.
        self.endpoints_status_var = tk.StringVar(value="Loading the mounted university routes...")
        ttk.Label(endpoints_frame, textvariable=self.endpoints_status_var, foreground='#555555',
                  wraplength=800, justify='left').pack(fill='x', pady=(0, 10))
        self._routes = {}
        self._load_routes_async()

        # Endpoint controls
        endpoint_controls = ttk.Frame(endpoints_frame)
        endpoint_controls.pack(fill='x')

        ttk.Button(endpoint_controls, text=_("admin_windows.api.endpoints.buttons.test"),
                  command=self.test_endpoint).pack(side='left', padx=(0, 10))
        ttk.Button(endpoint_controls, text=_("admin_windows.api.endpoints.buttons.view_docs"),
                  command=self.view_endpoint_docs).pack(side='left', padx=(0, 10))
        ttk.Button(endpoint_controls, text=_("admin_windows.api.endpoints.buttons.configure_rate"),
                  command=self.configure_rate_limits).pack(side='left')

    def create_analytics_tab(self, parent):
        """Create API analytics tab"""
        # Analytics display
        analytics_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.analytics.usage"), padding="15")
        analytics_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Stats summary
        stats_frame = ttk.Frame(analytics_frame)
        stats_frame.pack(fill='x', pady=(0, 15))

        stats, report = self._analytics_report()
        stats_data = [
            (_("admin_windows.api.analytics.total_requests"), stats["total"]),
            (_("admin_windows.api.analytics.active_keys"), stats["active_keys"]),
            (_("admin_windows.api.analytics.error_rate"), stats["error_rate"]),
            (_("admin_windows.api.analytics.avg_response"), stats["avg"]),
        ]

        for i, (label, value) in enumerate(stats_data):
            stat_frame = ttk.LabelFrame(stats_frame, text=label, padding="10")
            stat_frame.grid(row=0, column=i, padx=5, sticky='ew')
            ttk.Label(stat_frame, text=value, font=('Arial', 14, 'bold')).pack()
            stats_frame.grid_columnconfigure(i, weight=1)

        # Analytics text display
        analytics_text = scrolledtext.ScrolledText(analytics_frame, height=20, wrap='word')
        analytics_text.pack(fill='both', expand=True)
        analytics_text.insert('1.0', report)
        analytics_text.config(state='disabled')

    def create_security_tab(self, parent):
        """Create API security tab"""
        # Security settings
        security_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.security.config"), padding="15")
        security_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Security options
        options_frame = ttk.Frame(security_frame)
        options_frame.pack(fill='x', pady=(0, 15))

        # Rate limiting
        rate_frame = ttk.LabelFrame(options_frame, text=_("admin_windows.api.security.rate_limiting"), padding="10")
        rate_frame.pack(fill='x', pady=(0, 10))

        from education_system.systems.university.infrastructure.api_admin_info import security_settings
        cfg = security_settings()
        ttk.Label(rate_frame, text=_("admin_windows.api.security.global_rate_limit")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        rate_var = tk.StringVar(value=f"{cfg['rate_limit']} per user+IP")
        ttk.Entry(rate_frame, textvariable=rate_var, width=24, state='readonly').grid(row=0, column=1, sticky='w')
        ttk.Label(rate_frame, text="Set with API_DEFAULT_RATE_LIMIT; routes may add a tighter @limit.",
                  foreground='#555555').grid(row=0, column=2, sticky='w', padx=(10, 0))

        # Authentication - shows what the API actually accepts; not editable here.
        auth_frame = ttk.LabelFrame(options_frame, text=_("admin_windows.api.security.authentication"), padding="10")
        auth_frame.pack(fill='x', pady=(0, 10))

        accepted = {
            _("admin_windows.api.security.auth_api_key"): True,   # store exists; routes opt in
            _("admin_windows.api.security.auth_oauth"): False,
            _("admin_windows.api.security.auth_jwt"): True,
            _("admin_windows.api.security.auth_basic"): False,
        }
        for i, (method, on) in enumerate(accepted.items()):
            var = tk.BooleanVar(value=on)
            ttk.Checkbutton(auth_frame, text=method, variable=var, state='disabled').grid(row=0, column=i, sticky='w', padx=10)

        # Security settings and events
        log_frame = ttk.LabelFrame(security_frame, text=_("admin_windows.api.security.event_log"), padding="10")
        log_frame.pack(fill='both', expand=True)

        security_log = scrolledtext.ScrolledText(log_frame, height=15, wrap='word')
        security_log.pack(fill='both', expand=True)
        security_log.insert('1.0', self._security_report(cfg))
        security_log.config(state='disabled')

    # ── API keys (platform store) ─────────────────────────────────────────
    def _key_manager(self):
        from education_system import paths
        from education_system.platform.delivery.api.security.api_keys import APIKeyManager
        return APIKeyManager(str(paths.PLATFORM_AUTH_DB))

    def load_api_keys(self):
        """List the keys actually issued, newest first."""
        for item in self.keys_tree.get_children():
            self.keys_tree.delete(item)
        self._keys = {}
        note = ("A key is accepted only by API endpoints that opt in with "
                "api_key_required / api_key_or_token (X-API-Key header); people "
                "sign in to the API with JWT tokens instead. ")
        try:
            keys = self._key_manager().list_keys()
        except Exception as exc:
            self.keys_note_var.set(note + f"The key store could not be opened: {exc}")
            return
        for key in keys:
            self._keys[str(key["id"])] = key
            systems = ", ".join(key.get("systems") or []) or "all systems"
            status = (_("admin_windows.api.keys.status.active") if key["active"]
                      else "Revoked")
            self.keys_tree.insert('', 'end', iid=str(key["id"]), values=(
                f"{key['prefix']}...", key["label"], systems,
                (key.get("created_at") or "")[:16].replace("T", " "),
                (key.get("last_used_at") or "never")[:16].replace("T", " "),
                status,
                "not tracked",
            ))
        active = sum(1 for k in keys if k["active"])
        if keys:
            self.keys_note_var.set(note + f"{len(keys)} key(s) issued, {active} active.")
        else:
            self.keys_note_var.set(note + "No API keys have been issued yet.")

    def _selected_key(self, warn_key):
        selection = self.keys_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _(warn_key),
                                   parent=self.window)
            return None
        return getattr(self, "_keys", {}).get(selection[0])

    def generate_api_key(self):
        """Issue a new API key through the platform key store; show it once."""
        from tkinter import simpledialog
        label = simpledialog.askstring(_("admin_windows.api.messages.key_generated_title"),
                                       "Name for this key (who or what will use it):",
                                       parent=self.window)
        if not label or not label.strip():
            return
        days = simpledialog.askinteger(_("admin_windows.api.messages.key_generated_title"),
                                       "Expire after how many days? (leave blank for no expiry)",
                                       parent=self.window, minvalue=1, maxvalue=3650)
        try:
            raw_key = self._key_manager().create_key(
                label.strip(), systems=["university"], expires_in_days=days)
        except Exception as exc:
            messagebox.showerror(_("admin_windows.api.messages.key_generated_title"),
                                 f"The key was not created: {exc}", parent=self.window)
            return
        try:
            from education_system.systems.university.infrastructure.utils.activity_logger import log_activity
            log_activity("api_key_create", "api", details=f"API key issued: {label.strip()}")
        except Exception:
            pass
        self._show_key_once(raw_key, label.strip())
        self.load_api_keys()

    def _show_key_once(self, raw_key, label):
        win = tk.Toplevel(self.window)
        win.title(_("admin_windows.api.messages.key_generated_title"))
        win.transient(self.window)
        win.grab_set()
        ttk.Label(win, text=f"API key for '{label}'", font=('Arial', 12, 'bold')).pack(padx=15, pady=(15, 5))
        ttk.Label(win, text="Copy it now - it is stored only as a hash and cannot be shown again.",
                  foreground='#a33').pack(padx=15)
        value = tk.StringVar(value=raw_key)
        entry = ttk.Entry(win, textvariable=value, width=60, state='readonly')
        entry.pack(padx=15, pady=10)

        def copy():
            win.clipboard_clear()
            win.clipboard_append(raw_key)

        buttons = ttk.Frame(win)
        buttons.pack(pady=(0, 15))
        ttk.Button(buttons, text="Copy", command=copy).pack(side='left', padx=5)
        ttk.Button(buttons, text=_("common.close"), command=win.destroy).pack(side='left', padx=5)

    def revoke_api_key(self):
        """Revoke the selected key in the platform store."""
        key = self._selected_key("admin_windows.api.messages.select_key_revoke")
        if not key:
            return
        if not key["active"]:
            messagebox.showinfo(_("admin_windows.api.messages.key_revoked_title"),
                                "That key is already revoked.", parent=self.window)
            return
        key_label = f"{key['prefix']}... ({key['label']})"
        if not messagebox.askyesno(_("admin_windows.api.messages.confirm_revoke_title"),
                                   _("admin_windows.api.messages.confirm_revoke_body", key_id=key_label),
                                   parent=self.window):
            return
        try:
            ok = self._key_manager().revoke_key(int(key["id"]))
        except Exception as exc:
            messagebox.showerror(_("admin_windows.api.messages.key_revoked_title"),
                                 f"The key was not revoked: {exc}", parent=self.window)
            return
        if ok:
            try:
                from education_system.systems.university.infrastructure.utils.activity_logger import log_activity
                log_activity("api_key_revoke", "api", details=f"API key revoked: {key_label}")
            except Exception:
                pass
            messagebox.showinfo(_("admin_windows.api.messages.key_revoked_title"),
                                _("admin_windows.api.messages.key_revoked_body", key_id=key_label),
                                parent=self.window)
        self.load_api_keys()

    def view_key_details(self):
        """Show the stored details of the selected key (never the key itself)."""
        key = self._selected_key("admin_windows.api.messages.select_key_details")
        if not key:
            return
        details = "\n".join((
            f"Key ID: {key['id']}",
            f"Prefix: {key['prefix']}...",
            f"Name: {key['label']}",
            f"Systems: {', '.join(key.get('systems') or []) or 'all systems'}",
            f"Rate limit: {key.get('rate_limit') or 'default'}",
            f"Created: {key.get('created_at') or '-'}",
            f"Last used: {key.get('last_used_at') or 'never'}",
            f"Status: {'Active' if key['active'] else 'Revoked'}",
            "Requests: not tracked per key",
        ))
        messagebox.showinfo(_("admin_windows.api.messages.key_details_title"), details,
                            parent=self.window)

    def export_keys(self):
        """Export the key list (prefixes and metadata only - no secrets)."""
        keys = list(getattr(self, "_keys", {}).values())
        if not keys:
            messagebox.showinfo(_("admin_windows.api.messages.export_keys_title"),
                                "There are no API keys to export.", parent=self.window)
            return
        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_("admin_windows.api.messages.export_keys_title"),
            defaultextension=".json",
            filetypes=[(_("admin_windows.filetypes.json"), "*.json"), (_("admin_windows.filetypes.all"), "*.*")]
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as handle:
                json.dump(keys, handle, indent=2, default=str)
        except OSError as exc:
            messagebox.showerror(_("admin_windows.api.messages.export_keys_title"),
                                 f"Could not write {filename}: {exc}", parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.messages.export_complete"),
                            _("admin_windows.api.messages.keys_exported", filename=filename),
                            parent=self.window)

    # ── Endpoints ─────────────────────────────────────────────────────────
    def _load_routes_async(self):
        from education_system.systems.university.infrastructure.api_admin_info import university_routes
        state = {}

        def work():
            try:
                state["result"] = university_routes()
            except Exception as exc:
                state["error"] = str(exc)

        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            try:
                if worker.is_alive():
                    self.window.after(250, poll)
                    return
                self._fill_routes(state)
            except tk.TclError:
                pass  # window closed while loading

        self.window.after(250, poll)

    def _fill_routes(self, state):
        for item in self.endpoints_tree.get_children():
            self.endpoints_tree.delete(item)
        if "error" in state:
            self.endpoints_status_var.set(f"The route list could not be built: {state['error']}")
            return
        result = state["result"]
        self._routes = {}
        for i, route in enumerate(result["routes"]):
            iid = str(i)
            self._routes[iid] = route
            self.endpoints_tree.insert('', 'end', iid=iid, values=(
                ", ".join(route["methods"]), route["rule"],
                route["description"] or "-",
                route["auth"] if route["auth"] != "none found" else _("common.no"),
                route["rate_limit"], "Mounted"))
        unauth = sum(1 for r in result["routes"] if r["auth"] == "none found")
        status = (f"{len(result['routes'])} routes from {result['blueprints']} university "
                  f"blueprint(s), as mounted under /api/v1/university. "
                  f"{unauth} have no auth decorator detected.")
        if result.get("error"):
            status += f" Load problem: {result['error']}"
        self.endpoints_status_var.set(status)

    def _selected_route(self, warn_key):
        selection = self.endpoints_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _(warn_key),
                                   parent=self.window)
            return None
        return getattr(self, "_routes", {}).get(selection[0])

    def test_endpoint(self):
        """Call the selected route on a running API server (GET only, no token)."""
        route = self._selected_route("admin_windows.api.messages.select_endpoint_test")
        if not route:
            return
        if "GET" not in route["methods"] or route["takes_object_id"]:
            messagebox.showinfo(_("admin_windows.api.messages.endpoint_test_title"),
                                "Only GET routes without path parameters can be tested from here, "
                                "so nothing is created or changed.", parent=self.window)
            return
        from education_system.systems.university.infrastructure.api_admin_info import security_settings
        import urllib.request
        import urllib.error
        cfg = security_settings()
        host = "127.0.0.1" if cfg["host"] in ("0.0.0.0", "::") else cfg["host"]
        url = f"http://{host}:{cfg['port']}{route['rule']}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # nosec B310 - local API URL
                status, note = resp.status, "reachable"
        except urllib.error.HTTPError as exc:
            status = exc.code
            note = "reachable - authentication required" if exc.code == 401 else "reachable"
        except (urllib.error.URLError, OSError) as exc:
            messagebox.showwarning(_("admin_windows.api.messages.endpoint_test_title"),
                                   f"No API server answered at {url}.\n{exc}\n\n"
                                   "Start it with: python -m education_system --university --api",
                                   parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.api.messages.endpoint_test_title"),
                            f"GET {url}\nHTTP {status} ({note})", parent=self.window)

    def view_endpoint_docs(self):
        """Show the selected route's own documentation."""
        route = self._selected_route("admin_windows.api.messages.select_endpoint_test")
        if not route:
            return
        body = (f"{', '.join(route['methods'])} {route['rule']}\n\n"
                f"Handler: {route['module']} ({route['endpoint']})\n"
                f"Auth: {route['auth']}\nRate limit: {route['rate_limit']}\n\n"
                f"{route['docstring'] or 'This handler has no docstring.'}\n\n"
                "Full OpenAPI docs: /api/v1/docs on the running server.")
        messagebox.showinfo(_("admin_windows.api.messages.docs_title"), body, parent=self.window)

    def configure_rate_limits(self):
        """Explain where rate limits come from (they are code and environment, not data)."""
        from education_system.systems.university.infrastructure.api_admin_info import security_settings
        cfg = security_settings()
        messagebox.showinfo(
            _("admin_windows.api.messages.rate_config_title"),
            f"Global limit: {cfg['rate_limit']} per user+IP (API_DEFAULT_RATE_LIMIT; 'off' disables).\n"
            "Health and metrics endpoints are exempt.\n\n"
            "Tighter per-route limits are set in code with @limiter.limit(...) and are shown in "
            "the Rate Limit column. Change the environment variable and restart the API server "
            "to alter the global limit.",
            parent=self.window)

    # ── Analytics / security text ─────────────────────────────────────────
    def _analytics_report(self):
        from education_system.systems.university.infrastructure.api_admin_info import request_log_stats
        try:
            active = sum(1 for k in self._key_manager().list_keys() if k["active"])
        except Exception:
            active = "-"
        try:
            st = request_log_stats()
        except Exception as exc:
            return ({"total": "-", "active_keys": active, "error_rate": "-", "avg": "-"},
                    f"The request log could not be read: {exc}\n")
        if not st["total"]:
            return ({"total": "0", "active_keys": active, "error_rate": "-", "avg": "-"},
                    "API USAGE\n=========\nNo API requests are recorded.\n\n"
                    "The API's request middleware writes one line per request to the university "
                    "application logs; none were found there. Per-request counters otherwise "
                    "live only in the running server's memory (/metrics).\n")
        lines = ["API USAGE (from the request lines in the university application logs)",
                 "=" * 68,
                 f"Recorded from {st['first']} to {st['last']}",
                 f"- Total requests: {st['total']:,} (last 24 hours: {st['last_24h']:,})",
                 f"- University API (/api/v1/university): {st['university_total']:,}",
                 f"- Client errors (4xx): {st['errors_4xx']:,}; server errors (5xx): {st['errors_5xx']:,}",
                 "", "STATUS CODES:"]
        lines += [f"- {code}: {n:,}" for code, n in st["statuses"].items()]
        lines += ["", "RESPONSE TIME:",
                  f"- Average {st['avg_ms']:.0f} ms, median {st['median_ms']} ms, "
                  f"95th percentile {st['p95_ms']} ms, slowest {st['max_ms']} ms",
                  "", "MOST REQUESTED (all paths):"]
        lines += [f"{i}. {k} - {n:,}" for i, (k, n) in enumerate(st["top_endpoints"], 1)]
        if st["top_university"]:
            lines += ["", "MOST REQUESTED UNIVERSITY ROUTES:"]
            lines += [f"{i}. {k} - {n:,}" for i, (k, n) in enumerate(st["top_university"], 1)]
        lines += ["", "REQUESTS BY HOUR OF DAY:"]
        lines += [f"- {h}:00  {n:,}" for h, n in st["by_hour"].items()]
        lines += ["", "Per-key request counts are not recorded."]
        stats = {"total": f"{st['total']:,}", "active_keys": active,
                 "error_rate": f"{st['error_rate']:.2f}%", "avg": f"{st['avg_ms']:.0f}ms"}
        return stats, "\n".join(lines) + "\n"

    def _security_report(self, cfg):
        yes = lambda b: "set" if b else "NOT SET"  # noqa: E731
        lines = [
            "API SECURITY SETTINGS (as this process's environment resolves them;",
            "a server started with other variables will differ)",
            "=" * 66,
            f"- Environment: {cfg['app_env']}{' (development defaults allowed)' if cfg['dev_mode'] else ''}",
            f"- Global rate limit: {cfg['rate_limit']} per user+IP",
            f"- CORS origins: {cfg['cors']}",
            f"- JWT access token lifetime: {cfg['jwt_access_hours']} hour(s) (JWT_EXPIRY_HOURS)",
            f"- JWT refresh token lifetime: {cfg['jwt_refresh_days']} day(s) (JWT_REFRESH_DAYS)",
            f"- JWT_SECRET_KEY: {yes(cfg['jwt_secret_set'])}",
            f"- API_SECRET_KEY: {yes(cfg['api_secret_set'])}",
            f"- API_KEY_PEPPER: {yes(cfg['api_key_pepper_set'])}",
            f"- Max request body: {cfg['max_content_mb']:.0f} MB",
            f"- Debug mode: {'ON' if cfg['debug'] else 'off'}",
            f"- Listens on: {cfg['host']}:{cfg['port']}",
            "- Accepted credentials: JWT bearer tokens; API keys (X-API-Key) only on routes "
            "that opt in",
            "",
            "RECENT AUTHENTICATION WARNINGS (audit stores):",
        ]
        try:
            from education_system.systems.university.infrastructure.api_admin_info import recent_security_events
            events = recent_security_events()
        except Exception as exc:
            events = []
            lines.append(f"- could not read the audit stores: {exc}")
        if events:
            lines += [f"{e['timestamp']}  {e['user']}  {e['action']}  ({e['source']})" for e in events]
        elif len(lines) and not lines[-1].startswith("- could not"):
            lines.append("- none recorded")
        return "\n".join(lines) + "\n"
