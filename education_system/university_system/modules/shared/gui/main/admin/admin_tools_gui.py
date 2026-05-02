# Admin tools GUI - 14 admin-only features
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
import json
import csv
from datetime import datetime, timedelta
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.university_system.core.paths import (
    PROJECT_ROOT, DATA_DIR, CONFIG_DIR, DB_DIR, LOG_DIR, EMAIL_CONFIG_FILE,
    SAVED_REPORTS_FILE, API_SERVER_CONFIG_FILE, LICENSES_FILE, DR_CONFIG_FILE,
    SCHEDULED_REPORTS_FILE, EMAIL_TEMPLATE_MAPPING_FILE,
    UPLOAD_DIR, BACKUP_DIR, EMAIL_TEMPLATES_DIR,
)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_json(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default if default is not None else {}


def _save_json(path, data):
    _ensure_dir(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Feature 1: System Monitoring Dashboard
# ---------------------------------------------------------------------------

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
                    from education_system.university_system.infrastructure.database.db import get_connection
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
                    from education_system.university_system.infrastructure.database.pool_metrics import get_pool_metrics
                    pm = get_pool_metrics()
                    stats = pm.get_stats()
                    pool_lines.append(f"=== {_t('admin_tools.monitoring.active_connections')} ===")
                    pool_lines.append(f"{_t('admin_tools.monitoring.pool_size')}: {stats.get('pool_max_size', 'N/A')}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.active')}: {stats.get('active_connections', 'N/A')}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.idle')}: {stats.get('idle_connections', 'N/A')}")
                    pool_lines.append(f"{_t('admin_tools.monitoring.utilization')}: {stats.get('utilization', 0):.1f}%")
                    pool_lines.append("")
                    pool_lines.append(f"=== Cumulative ===")
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
            from education_system.university_system.infrastructure.database.query_monitor import get_query_monitor
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
            from education_system.university_system.infrastructure.database.pool_metrics import get_pool_metrics
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
        from education_system.university_system.infrastructure.database.db import get_connection

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

def show_usage_adoption_reports(self):
    """System usage and adoption reports with heatmap and module usage stats."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools.access_denied"), _t("admin_tools.admin_required"))
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools.usage.title"))
        win.geometry("1100x750")
        win.transient(self.root)

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
    """Custom report builder with SQL query generation, preview, and export."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("admin_tools_v2.report_builder.title"))
        win.geometry("1100x750")
        win.transient(self.root)

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

def show_data_retention_manager(self):
    """Data retention policy editor with archive status and purge scheduler."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.university_system.infrastructure.database.data_backup.config import DEFAULT_CONFIG as backup_config
        from education_system.university_system.infrastructure.database.data_backup.metadata import metadata_manager
        from education_system.university_system.infrastructure.database.data_backup.retention import cleanup_old_backups

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

def show_department_isolation(self):
    """Department isolation view with data scope and access matrix."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

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
                from education_system.university_system.infrastructure.database.db import get_connection
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
                from education_system.university_system.infrastructure.database.data_backup.config import DEFAULT_CONFIG
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
            from education_system.university_system.infrastructure.database.data_backup.config import DEFAULT_CONFIG as bkp_cfg
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

def show_license_management(self):
    """License and subscription management with seat usage tracking."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("admin_tools_v2.access_denied"), _t("admin_tools_v2.admin_required"))
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

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
        from education_system.university_system.infrastructure.database.data_backup.metadata import metadata_manager

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
