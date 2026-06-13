from ._common import (
    API_SERVER_CONFIG_FILE,
    CONFIG_DIR,
    EMAIL_CONFIG_FILE,
    _install_clean_close,
    _t,
    json,
    messagebox,
    os,
    tk,
    ttk,
)

def show_configuration_editor(self):
    """GUI editor for email and API server configuration with validation."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools.access_denied"), _t("admin_tools.admin_required"))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools.config_editor.title"))
        win.geometry("900x650")
        win.transient(self.root)

        ttk.Label(win, text=_t("admin_tools.config_editor.header"),
                  font=('Arial', 16, 'bold')).pack(pady=(10, 5))

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        email_cfg_path = EMAIL_CONFIG_FILE
        api_cfg_path = API_SERVER_CONFIG_FILE

        # ---- helpers ----
        def _load_json(path):
            # First-run scenario: the config file hasn't been written yet.
            # Open the editor with blank fields rather than failing — saving
            # later creates the file.
            if not os.path.exists(path):
                return {}
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as exc:
                messagebox.showerror(_t("admin_tools.error"),
                                     _t("admin_tools.config_editor.load_error", error=str(exc)))
                return {}

        def _save_json(path, data):
            # Ensure parent directory exists (first-run case)
            parent = os.path.dirname(str(path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            # Backup existing file before overwrite
            if os.path.exists(path):
                bak = str(path) + ".bak"
                try:
                    import shutil
                    shutil.copy2(path, bak)
                except Exception:
                    pass
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)

        # ---- Tab 1: Email Config ----
        email_frame = ttk.Frame(nb, padding=10)
        nb.add(email_frame, text=_t("admin_tools.config_editor.email_config"))

        email_vars = {}
        email_data = _load_json(email_cfg_path)

        email_fields = [
            ("smtp_server", "admin_tools.config_editor.smtp_server", "entry"),
            ("smtp_port", "admin_tools.config_editor.smtp_port", "spinbox"),
            ("sender_email", "admin_tools.config_editor.sender_email", "entry"),
            ("sender_name", "admin_tools.config_editor.sender_name", "entry"),
            ("use_tls", "admin_tools.config_editor.use_tls", "check"),
            ("use_authentication", "admin_tools.config_editor.use_auth", "check"),
            ("smtp_username", "admin_tools.config_editor.smtp_username", "entry"),
            ("max_retries", "admin_tools.config_editor.max_retries", "spinbox"),
            ("send_delay", "admin_tools.config_editor.send_delay", "entry"),
            ("log_level", "admin_tools.config_editor.log_level", "combo"),
            ("attachment_size_limit", "admin_tools.config_editor.attachment_limit", "entry"),
            ("database_only_mode", "admin_tools.config_editor.db_only_mode", "check"),
            ("email_signature", "admin_tools.config_editor.email_signature", "entry"),
            ("max_threads", "admin_tools.config_editor.max_threads", "spinbox"),
        ]

        canvas_e = tk.Canvas(email_frame, highlightthickness=0)
        scrollbar_e = ttk.Scrollbar(email_frame, orient="vertical", command=canvas_e.yview)
        scroll_frame_e = ttk.Frame(canvas_e)
        scroll_frame_e.bind("<Configure>", lambda e: canvas_e.configure(scrollregion=canvas_e.bbox("all")))
        canvas_e.create_window((0, 0), window=scroll_frame_e, anchor="nw")
        canvas_e.configure(yscrollcommand=scrollbar_e.set)
        canvas_e.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_e.pack(side=tk.RIGHT, fill=tk.Y)

        for row_idx, (key, label_key, wtype) in enumerate(email_fields):
            ttk.Label(scroll_frame_e, text=_t(label_key)).grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=3)
            val = email_data.get(key, "")
            if wtype == "check":
                var = tk.BooleanVar(value=bool(val))
                ttk.Checkbutton(scroll_frame_e, variable=var).grid(row=row_idx, column=1, sticky=tk.W, padx=5)
            elif wtype == "spinbox":
                var = tk.StringVar(value=str(val))
                ttk.Spinbox(scroll_frame_e, from_=0, to=99999, textvariable=var, width=10).grid(
                    row=row_idx, column=1, sticky=tk.W, padx=5)
            elif wtype == "combo":
                var = tk.StringVar(value=str(val))
                ttk.Combobox(scroll_frame_e, textvariable=var,
                             values=["DEBUG", "INFO", "WARNING", "ERROR"], width=12).grid(
                    row=row_idx, column=1, sticky=tk.W, padx=5)
            else:
                var = tk.StringVar(value=str(val))
                ttk.Entry(scroll_frame_e, textvariable=var, width=40).grid(
                    row=row_idx, column=1, sticky=tk.W, padx=5)
            email_vars[key] = (var, wtype)

        # ---- Tab 2: API Server Config ----
        api_frame = ttk.Frame(nb, padding=10)
        nb.add(api_frame, text=_t("admin_tools.config_editor.api_config"))

        api_vars = {}
        api_data = _load_json(api_cfg_path)

        api_fields = [
            ("host", "admin_tools.config_editor.api_host", "entry"),
            ("port", "admin_tools.config_editor.api_port", "spinbox"),
            ("debug", "admin_tools.config_editor.api_debug", "check"),
            ("ssl_enabled", "admin_tools.config_editor.api_ssl", "check"),
        ]

        for row_idx, (key, label_key, wtype) in enumerate(api_fields):
            ttk.Label(api_frame, text=_t(label_key)).grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=3)
            val = api_data.get(key, "")
            if wtype == "check":
                var = tk.BooleanVar(value=bool(val))
                ttk.Checkbutton(api_frame, variable=var).grid(row=row_idx, column=1, sticky=tk.W, padx=5)
            elif wtype == "spinbox":
                var = tk.StringVar(value=str(val))
                ttk.Spinbox(api_frame, from_=1, to=65535, textvariable=var, width=10).grid(
                    row=row_idx, column=1, sticky=tk.W, padx=5)
            else:
                var = tk.StringVar(value=str(val))
                ttk.Entry(api_frame, textvariable=var, width=40).grid(
                    row=row_idx, column=1, sticky=tk.W, padx=5)
            api_vars[key] = (var, wtype)

        # Rate limiting fields (nested)
        rl = api_data.get("rate_limiting", {})
        sep_row = len(api_fields)
        ttk.Separator(api_frame, orient="horizontal").grid(row=sep_row, column=0, columnspan=2, sticky="ew", pady=5)

        ttk.Label(api_frame, text=_t("admin_tools.config_editor.rate_limit_enabled")).grid(
            row=sep_row + 1, column=0, sticky=tk.W, padx=5, pady=3)
        rl_enabled_var = tk.BooleanVar(value=rl.get("enabled", True))
        ttk.Checkbutton(api_frame, variable=rl_enabled_var).grid(row=sep_row + 1, column=1, sticky=tk.W, padx=5)

        ttk.Label(api_frame, text=_t("admin_tools.config_editor.rate_limit_rpm")).grid(
            row=sep_row + 2, column=0, sticky=tk.W, padx=5, pady=3)
        rl_rpm_var = tk.StringVar(value=str(rl.get("requests_per_minute", 100)))
        ttk.Spinbox(api_frame, from_=1, to=10000, textvariable=rl_rpm_var, width=10).grid(
            row=sep_row + 2, column=1, sticky=tk.W, padx=5)

        # JWT fields (nested)
        jwt = api_data.get("jwt", {})
        ttk.Separator(api_frame, orient="horizontal").grid(row=sep_row + 3, column=0, columnspan=2, sticky="ew", pady=5)

        ttk.Label(api_frame, text=_t("admin_tools.config_editor.jwt_algorithm")).grid(
            row=sep_row + 4, column=0, sticky=tk.W, padx=5, pady=3)
        jwt_alg_var = tk.StringVar(value=jwt.get("algorithm", "HS256"))
        ttk.Combobox(api_frame, textvariable=jwt_alg_var,
                     values=["HS256", "HS384", "HS512"], width=12).grid(
            row=sep_row + 4, column=1, sticky=tk.W, padx=5)

        ttk.Label(api_frame, text=_t("admin_tools.config_editor.jwt_access_expires")).grid(
            row=sep_row + 5, column=0, sticky=tk.W, padx=5, pady=3)
        jwt_access_var = tk.StringVar(value=str(jwt.get("access_token_expires_minutes", 30)))
        ttk.Spinbox(api_frame, from_=1, to=1440, textvariable=jwt_access_var, width=10).grid(
            row=sep_row + 5, column=1, sticky=tk.W, padx=5)

        ttk.Label(api_frame, text=_t("admin_tools.config_editor.jwt_refresh_expires")).grid(
            row=sep_row + 6, column=0, sticky=tk.W, padx=5, pady=3)
        jwt_refresh_var = tk.StringVar(value=str(jwt.get("refresh_token_expires_days", 7)))
        ttk.Spinbox(api_frame, from_=1, to=365, textvariable=jwt_refresh_var, width=10).grid(
            row=sep_row + 6, column=1, sticky=tk.W, padx=5)

        # ---- Tab 3: System Settings (read-only summary) ----
        sys_frame = ttk.Frame(nb, padding=10)
        nb.add(sys_frame, text=_t("admin_tools.config_editor.system_settings"))
        sys_text = tk.Text(sys_frame, wrap=tk.WORD, height=20, state=tk.DISABLED,
                           fg="#000000", bg="#FFFFFF")
        sys_text.pack(fill=tk.BOTH, expand=True)

        sys_lines = [
            "System Settings (read-only overview)",
            "=" * 40,
            f"Email config: {email_cfg_path}",
            f"API config:   {api_cfg_path}",
            f"Config dir:   {CONFIG_DIR}",
        ]
        sys_text.config(state=tk.NORMAL)
        sys_text.insert("1.0", "\n".join(sys_lines))
        sys_text.config(state=tk.DISABLED)

        # ---- Save / Reload buttons ----
        def _collect_email():
            result = dict(email_data)  # preserve keys we don't edit
            for key, (var, wtype) in email_vars.items():
                if wtype == "check":
                    result[key] = var.get()
                elif wtype == "spinbox":
                    try:
                        result[key] = int(var.get())
                    except ValueError:
                        result[key] = var.get()
                else:
                    val = var.get()
                    # try to preserve numeric types
                    try:
                        result[key] = int(val)
                    except ValueError:
                        try:
                            result[key] = float(val)
                        except ValueError:
                            result[key] = val
            return result

        def _collect_api():
            result = dict(api_data)
            for key, (var, wtype) in api_vars.items():
                if wtype == "check":
                    result[key] = var.get()
                elif wtype == "spinbox":
                    try:
                        result[key] = int(var.get())
                    except ValueError:
                        result[key] = var.get()
                else:
                    result[key] = var.get()
            # nested objects
            result.setdefault("rate_limiting", {})
            result["rate_limiting"]["enabled"] = rl_enabled_var.get()
            try:
                result["rate_limiting"]["requests_per_minute"] = int(rl_rpm_var.get())
            except ValueError:
                pass
            result.setdefault("jwt", {})
            result["jwt"]["algorithm"] = jwt_alg_var.get()
            try:
                result["jwt"]["access_token_expires_minutes"] = int(jwt_access_var.get())
            except ValueError:
                pass
            try:
                result["jwt"]["refresh_token_expires_days"] = int(jwt_refresh_var.get())
            except ValueError:
                pass
            return result

        def _save():
            current_tab = nb.index(nb.select())
            try:
                if current_tab == 0:
                    data = _collect_email()
                    # validate
                    try:
                        from education_system.university_system.infrastructure.validation.config_validators import validate_email_config
                        vr = validate_email_config(data)
                        if not vr.is_valid:
                            messagebox.showerror(
                                _t("admin_tools.config_editor.validation_failed"),
                                _t("admin_tools.config_editor.validation_errors",
                                   errors="\n".join(vr.errors)))
                            return
                    except ImportError:
                        pass  # validator not available, save anyway
                    _save_json(email_cfg_path, data)
                elif current_tab == 1:
                    data = _collect_api()
                    try:
                        from education_system.university_system.infrastructure.validation.config_validators import validate_api_config
                        vr = validate_api_config(data)
                        if not vr.is_valid:
                            messagebox.showerror(
                                _t("admin_tools.config_editor.validation_failed"),
                                _t("admin_tools.config_editor.validation_errors",
                                   errors="\n".join(vr.errors)))
                            return
                    except ImportError:
                        pass
                    _save_json(api_cfg_path, data)
                else:
                    return  # system settings tab is read-only

                messagebox.showinfo(
                    _t("admin_tools.config_editor.save_success"),
                    _t("admin_tools.config_editor.save_success_msg"))
            except Exception as exc:
                messagebox.showerror(_t("admin_tools.config_editor.save_failed"), str(exc))

        def _reload():
            win.destroy()
            show_configuration_editor(self)

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text=_t("admin_tools.config_editor.save"), command=_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools.config_editor.reload"), command=_reload).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admin_tools.close"), command=win.destroy).pack(side=tk.RIGHT, padx=5)

    except Exception as e:
        messagebox.showerror(_t("admin_tools.error"), str(e))


# ---------------------------------------------------------------------------
# Feature 3: Query Analyser
# ---------------------------------------------------------------------------
