"""
Configuration management tab for the Activity Logger GUI.
"""

from .._imports import (
    tk, ttk, messagebox, filedialog,
    json, os,
    Dict, Any,
    LOGGER_AVAILABLE,
    _t,
)

if LOGGER_AVAILABLE:
    from .._imports import create_default_config

from ..theme import LoggerGUITheme


class ConfigurationTab(ttk.Frame):
    """Configuration management tab"""

    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        self.config_vars = {}

        self.setup_ui()

    def setup_ui(self):
        """Setup configuration UI"""
        # Header
        header_frame = ttk.Frame(self, style='AL.Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(header_frame, text=_t("activity_logger.config.title"),
                 style='AL.Title.TLabel').pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT, padx=5)

        ttk.Button(button_frame, text=_t("activity_logger.config.load"),
                  command=self.load_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text=_t("activity_logger.config.save"),
                  command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text=_t("activity_logger.config.apply"),
                  command=self.apply_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text=_t("activity_logger.config.reset"),
                  command=self.reset_config).pack(side=tk.LEFT, padx=2)

        # Configuration notebook
        config_notebook = ttk.Notebook(self, style='AL.TNotebook')
        config_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # General settings tab
        self.setup_general_tab(config_notebook)

        # Security settings tab
        self.setup_security_tab(config_notebook)

        # Output settings tab
        self.setup_output_tab(config_notebook)

        # Cloud settings tab
        self.setup_cloud_tab(config_notebook)

        # Load current configuration
        self.load_current_config()

    def setup_general_tab(self, notebook):
        """Setup general configuration tab"""
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text=_t("activity_logger.config.general"))

        # Create scrollable frame
        canvas = tk.Canvas(general_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(general_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # General settings
        settings = [
            ("Log Directory", "log_dir", "string", "logs"),
            ("Minimum Log Level", "min_log_level", "combo", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
            ("Queue Size", "queue_size", "int", 10000),
            ("Batch Size", "batch_size", "int", 100),
            ("Flush Interval (seconds)", "flush_interval", "int", 5),
            ("Enable PII Detection", "enable_pii_detection", "bool", True),
            ("Encrypt Logs", "encrypt_logs", "bool", False)
        ]

        for i, (label, key, widget_type, default) in enumerate(settings):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def setup_security_tab(self, notebook):
        """Setup security configuration tab"""
        security_frame = ttk.Frame(notebook)
        notebook.add(security_frame, text=_t("activity_logger.config.security"))

        # Create scrollable frame
        canvas = tk.Canvas(security_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(security_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Security settings
        settings = [
            ("Max Failed Attempts", "security.max_failed_attempts", "int", 5),
            ("Lockout Window (minutes)", "security.lockout_window", "int", 15),
            ("Max Requests Per Minute", "security.max_requests_per_minute", "int", 100),
            ("Enable Security Alerts", "security_alerts.webhook_enabled", "bool", False),
            ("Security Webhook URL", "security_alerts.webhook_url", "string", "")
        ]

        for i, (label, key, widget_type, default) in enumerate(settings):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def setup_output_tab(self, notebook):
        """Setup output configuration tab"""
        output_frame = ttk.Frame(notebook)
        notebook.add(output_frame, text=_t("activity_logger.config.output"))

        # Create scrollable frame
        canvas = tk.Canvas(output_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Output formats
        ttk.Label(scrollable_frame, text=_t("activity_logger.config.output_formats"),
                 style='AL.Heading.TLabel').grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        self.config_vars["output_formats.json"] = tk.BooleanVar()
        self.config_vars["output_formats.csv"] = tk.BooleanVar()
        self.config_vars["output_formats.database"] = tk.BooleanVar()

        ttk.Checkbutton(scrollable_frame, text="JSON",
                       variable=self.config_vars["output_formats.json"]).grid(
                           row=1, column=0, sticky=tk.W, padx=20, pady=2)
        ttk.Checkbutton(scrollable_frame, text="CSV",
                       variable=self.config_vars["output_formats.csv"]).grid(
                           row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(scrollable_frame, text="Database",
                       variable=self.config_vars["output_formats.database"]).grid(
                           row=1, column=2, sticky=tk.W, padx=5, pady=2)

        # Rotation settings
        rotation_settings = [
            ("Max File Size (MB)", "rotation.max_file_size_mb", "int", 100),
            ("Retention Days", "rotation.retention_days", "int", 30),
            ("Compress Old Logs", "rotation.compress_old_logs", "bool", True)
        ]

        for i, (label, key, widget_type, default) in enumerate(rotation_settings, start=2):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def setup_cloud_tab(self, notebook):
        """Setup cloud configuration tab"""
        cloud_frame = ttk.Frame(notebook)
        notebook.add(cloud_frame, text=_t("activity_logger.config.cloud"))

        # Create scrollable frame
        canvas = tk.Canvas(cloud_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(cloud_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Cloud services
        ttk.Label(scrollable_frame, text=_t("activity_logger.config.enabled_services"),
                 style='AL.Heading.TLabel').grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        services = ["webhook", "elasticsearch", "splunk", "aws_cloudwatch"]
        for i, service in enumerate(services):
            self.config_vars[f"cloud.enabled_services.{service}"] = tk.BooleanVar()
            ttk.Checkbutton(scrollable_frame, text=service.replace("_", " ").title(),
                           variable=self.config_vars[f"cloud.enabled_services.{service}"]).grid(
                               row=1, column=i, sticky=tk.W, padx=20, pady=2)

        # Cloud settings
        cloud_settings = [
            ("Webhook URL", "cloud.webhook_url", "string", ""),
            ("Elasticsearch URL", "cloud.elasticsearch.url", "string", "http://localhost:9200"),
            ("Elasticsearch Index", "cloud.elasticsearch.index", "string", "activity-logs"),
            ("Elasticsearch Username", "cloud.elasticsearch.username", "string", ""),
            ("Elasticsearch Password", "cloud.elasticsearch.password", "password", "")
        ]

        for i, (label, key, widget_type, default) in enumerate(cloud_settings, start=2):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_config_widget(self, parent, label, key, widget_type, default, row):
        """Create a configuration widget"""
        ttk.Label(parent, text=label + ":", style='AL.Info.TLabel').grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=2)

        if widget_type == "string":
            var = tk.StringVar(value=str(default))
            widget = ttk.Entry(parent, textvariable=var, width=30)
        elif widget_type == "password":
            var = tk.StringVar(value=str(default))
            widget = ttk.Entry(parent, textvariable=var, width=30, show="*")
        elif widget_type == "int":
            var = tk.IntVar(value=int(default))
            widget = ttk.Entry(parent, textvariable=var, width=30)
        elif widget_type == "bool":
            var = tk.BooleanVar(value=bool(default))
            widget = ttk.Checkbutton(parent, variable=var)
        elif widget_type == "combo":
            var = tk.StringVar(value=str(default[0] if isinstance(default, list) else default))
            widget = ttk.Combobox(parent, textvariable=var, values=default if isinstance(default, list) else [default],
                                 state="readonly", width=27)
        else:
            var = tk.StringVar(value=str(default))
            widget = ttk.Entry(parent, textvariable=var, width=30)

        widget.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        self.config_vars[key] = var

    def load_current_config(self):
        """Load current logger configuration"""
        try:
            if LOGGER_AVAILABLE and hasattr(self.main_app, 'logger') and self.main_app.logger:
                config = self.main_app.logger.config
                self.update_config_vars(config)
        except Exception as e:
            print(f"Error loading current config: {e}")

    def update_config_vars(self, config, prefix=""):
        """Update config variables from config dict"""
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self.update_config_vars(value, full_key)
            elif full_key in self.config_vars:
                if isinstance(value, list):
                    # Handle output formats and enabled services
                    if full_key == "output_formats":
                        for format_type in ["json", "csv", "database"]:
                            format_key = f"output_formats.{format_type}"
                            if format_key in self.config_vars:
                                self.config_vars[format_key].set(format_type in value)
                    elif "enabled_services" in full_key:
                        for service in ["webhook", "elasticsearch", "splunk", "aws_cloudwatch"]:
                            service_key = f"{full_key}.{service}"
                            if service_key in self.config_vars:
                                self.config_vars[service_key].set(service in value)
                else:
                    # Handle size conversion for max_file_size
                    if key == "max_file_size" and isinstance(value, int):
                        # Convert bytes to MB
                        value = value // (1024 * 1024)
                        if f"{prefix}.max_file_size_mb" in self.config_vars:
                            self.config_vars[f"{prefix}.max_file_size_mb"].set(value)
                            continue

                    try:
                        self.config_vars[full_key].set(value)
                    except tk.TclError:
                        print(f"Could not set config var {full_key} to {value}")

    def load_config(self):
        """Load configuration from file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Configuration",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("YAML files", "*.yaml"),
                    ("All files", "*.*")
                ]
            )

            if file_path:
                with open(file_path, 'r') as f:
                    if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                        import yaml
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)

                self.update_config_vars(config)
                messagebox.showinfo("Configuration Loaded", f"Configuration loaded from: {file_path}")

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load configuration: {str(e)}")

    def save_config(self):
        """Save current configuration to file"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Save Configuration",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("YAML files", "*.yaml"),
                    ("All files", "*.*")
                ]
            )

            if file_path:
                config = self.build_config_dict()

                with open(file_path, 'w') as f:
                    if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                        import yaml
                        yaml.dump(config, f, indent=2)
                    else:
                        json.dump(config, f, indent=2)

                messagebox.showinfo("Configuration Saved", f"Configuration saved to: {file_path}")

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save configuration: {str(e)}")

    def build_config_dict(self) -> Dict[str, Any]:
        """Build configuration dictionary from current values"""
        config = {}

        # Simple values
        simple_keys = [
            "log_dir", "min_log_level", "queue_size", "batch_size", "flush_interval",
            "enable_pii_detection", "encrypt_logs"
        ]

        for key in simple_keys:
            if key in self.config_vars:
                config[key] = self.config_vars[key].get()

        # Nested values
        config["security"] = {}
        security_keys = [
            ("security.max_failed_attempts", "max_failed_attempts"),
            ("security.lockout_window", "lockout_window"),
            ("security.max_requests_per_minute", "max_requests_per_minute")
        ]

        for var_key, config_key in security_keys:
            if var_key in self.config_vars:
                config["security"][config_key] = self.config_vars[var_key].get()

        # Output formats
        output_formats = []
        for format_type in ["json", "csv", "database"]:
            format_key = f"output_formats.{format_type}"
            if format_key in self.config_vars and self.config_vars[format_key].get():
                output_formats.append(format_type)
        config["output_formats"] = output_formats

        # Rotation settings
        config["rotation"] = {}
        if "rotation.max_file_size_mb" in self.config_vars:
            # Convert MB to bytes
            config["rotation"]["max_file_size"] = self.config_vars["rotation.max_file_size_mb"].get() * 1024 * 1024
        if "rotation.retention_days" in self.config_vars:
            config["rotation"]["retention_days"] = self.config_vars["rotation.retention_days"].get()
        if "rotation.compress_old_logs" in self.config_vars:
            config["rotation"]["compress_old_logs"] = self.config_vars["rotation.compress_old_logs"].get()

        # Cloud settings
        config["cloud"] = {}

        # Enabled services
        enabled_services = []
        for service in ["webhook", "elasticsearch", "splunk", "aws_cloudwatch"]:
            service_key = f"cloud.enabled_services.{service}"
            if service_key in self.config_vars and self.config_vars[service_key].get():
                enabled_services.append(service)
        config["cloud"]["enabled_services"] = enabled_services

        # Cloud URLs and settings
        cloud_settings = [
            ("cloud.webhook_url", "webhook_url"),
            ("cloud.elasticsearch.url", "elasticsearch", "url"),
            ("cloud.elasticsearch.index", "elasticsearch", "index"),
            ("cloud.elasticsearch.username", "elasticsearch", "username"),
            ("cloud.elasticsearch.password", "elasticsearch", "password")
        ]

        for var_key, *config_path in cloud_settings:
            if var_key in self.config_vars:
                value = self.config_vars[var_key].get()
                if value:  # Only set non-empty values
                    if len(config_path) == 1:
                        config["cloud"][config_path[0]] = value
                    else:
                        if config_path[0] not in config["cloud"]:
                            config["cloud"][config_path[0]] = {}
                        config["cloud"][config_path[0]][config_path[1]] = value

        # Security alerts
        config["security_alerts"] = {}
        if "security_alerts.webhook_enabled" in self.config_vars:
            config["security_alerts"]["webhook_enabled"] = self.config_vars["security_alerts.webhook_enabled"].get()
        if "security_alerts.webhook_url" in self.config_vars:
            url = self.config_vars["security_alerts.webhook_url"].get()
            if url:
                config["security_alerts"]["webhook_url"] = url

        return config

    def apply_config(self):
        """Apply configuration changes to logger"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                messagebox.showwarning("Apply Configuration", "Logger not available.")
                return

            config = self.build_config_dict()

            # Update logger configuration
            if hasattr(self.main_app.logger, 'update_config'):
                self.main_app.logger.update_config(config)
                messagebox.showinfo("Configuration Applied", "Configuration changes have been applied.")
            else:
                messagebox.showwarning("Apply Configuration",
                                     "Configuration update not supported in current logger version.")

        except Exception as e:
            messagebox.showerror("Apply Error", f"Failed to apply configuration: {str(e)}")

    def reset_config(self):
        """Reset configuration to defaults"""
        try:
            if messagebox.askyesno("Reset Configuration",
                                 "Are you sure you want to reset all settings to defaults?"):

                # Create default config
                default_config_file = create_default_config("temp_default_config.json")

                with open(default_config_file, 'r') as f:
                    default_config = json.load(f)

                self.update_config_vars(default_config)

                # Clean up temp file
                os.remove(default_config_file)

                messagebox.showinfo("Configuration Reset", "Configuration has been reset to defaults.")

        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset configuration: {str(e)}")
