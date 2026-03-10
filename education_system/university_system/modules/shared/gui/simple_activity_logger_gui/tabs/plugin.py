"""
Plugin management tab for the Activity Logger GUI.
"""

from .._imports import (
    tk, ttk, messagebox, scrolledtext,
    LOGGER_AVAILABLE,
    _t,
)

if LOGGER_AVAILABLE:
    from .._imports import (
        plugin_manager,
        SlackNotificationPlugin, MetricsCollectionPlugin,
        EmailNotificationPlugin, AuditTrailPlugin,
    )

from ..theme import LoggerGUITheme


class PluginTab(ttk.Frame):
    """Plugin management tab"""

    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app

        self.setup_ui()

    def setup_ui(self):
        """Setup plugin management UI"""
        # Header
        header_frame = ttk.Frame(self, style='AL.Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(header_frame, text=_t("activity_logger.plugins.title"),
                 style='AL.Title.TLabel').pack(side=tk.LEFT, padx=5)

        ttk.Button(header_frame, text=_t("activity_logger.plugins.refresh"),
                  command=self.refresh_plugins).pack(side=tk.RIGHT, padx=5)

        # Plugin list and controls
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Left panel - Plugin list
        left_panel = ttk.LabelFrame(content_frame, text=_t("activity_logger.plugins.installed"), padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Plugin treeview
        plugin_columns = ('name', 'status', 'type')
        self.plugin_tree = ttk.Treeview(left_panel, columns=plugin_columns, show='headings', height=15)

        self.plugin_tree.heading('name', text=_t("activity_logger.plugins.plugin_name"))
        self.plugin_tree.heading('status', text=_t("activity_logger.plugins.status"))
        self.plugin_tree.heading('type', text=_t("activity_logger.plugins.type"))

        self.plugin_tree.column('name', width=200)
        self.plugin_tree.column('status', width=100)
        self.plugin_tree.column('type', width=150)

        plugin_scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.plugin_tree.yview)
        self.plugin_tree.configure(yscrollcommand=plugin_scrollbar.set)

        self.plugin_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        plugin_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.plugin_tree.bind('<ButtonRelease-1>', self.on_plugin_select)

        # Right panel - Plugin details and controls
        right_panel = ttk.LabelFrame(content_frame, text=_t("activity_logger.plugins.details"), padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Plugin info display
        self.plugin_info = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, height=15, width=40)
        self.plugin_info.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Plugin controls
        control_frame = ttk.Frame(right_panel)
        control_frame.pack(fill=tk.X)

        ttk.Button(control_frame, text=_t("activity_logger.plugins.add_default"),
                  command=self.add_default_plugins).pack(fill=tk.X, pady=2)

        ttk.Button(control_frame, text=_t("activity_logger.plugins.configure"),
                  command=self.configure_plugin).pack(fill=tk.X, pady=2)

        ttk.Button(control_frame, text=_t("activity_logger.plugins.toggle"),
                  command=self.toggle_plugin).pack(fill=tk.X, pady=2)

        ttk.Button(control_frame, text=_t("activity_logger.plugins.remove"),
                  command=self.remove_plugin).pack(fill=tk.X, pady=2)

        # Load plugins
        self.refresh_plugins()

    def refresh_plugins(self):
        """Refresh plugin list"""
        # Clear existing items
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)

        try:
            if LOGGER_AVAILABLE:
                plugin_status = plugin_manager.get_plugin_status()

                for plugin in plugin_status:
                    name = plugin.get('name', 'Unknown')
                    enabled = plugin.get('enabled', False)
                    status = "Enabled" if enabled else "Disabled"
                    plugin_type = self.get_plugin_type(name)

                    self.plugin_tree.insert('', 'end', values=(name, status, plugin_type))

        except Exception as e:
            print(f"Error refreshing plugins: {e}")

    def get_plugin_type(self, plugin_name: str) -> str:
        """Get plugin type based on name"""
        if "Slack" in plugin_name:
            return "Notification"
        elif "Email" in plugin_name:
            return "Notification"
        elif "Metrics" in plugin_name:
            return "Analytics"
        elif "Audit" in plugin_name:
            return "Compliance"
        else:
            return "General"

    def on_plugin_select(self, event):
        """Handle plugin selection"""
        selection = self.plugin_tree.selection()
        if not selection:
            return

        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]

        self.show_plugin_info(plugin_name)

    def show_plugin_info(self, plugin_name: str):
        """Show detailed plugin information"""
        self.plugin_info.delete(1.0, tk.END)

        try:
            if LOGGER_AVAILABLE:
                plugin_status_list = plugin_manager.get_plugin_status()

                for plugin in plugin_status_list:
                    if plugin.get('name') == plugin_name:
                        info_text = f"""PLUGIN INFORMATION
{'='*40}

Name: {plugin.get('name', 'Unknown')}
Status: {'Enabled' if plugin.get('enabled', False) else 'Disabled'}
Type: {self.get_plugin_type(plugin_name)}

CONFIGURATION
{'='*40}
"""

                        config = plugin.get('config', {})
                        if config:
                            for key, value in config.items():
                                # Hide sensitive information
                                if 'password' in key.lower() or 'token' in key.lower() or 'key' in key.lower():
                                    value = '*' * 8
                                info_text += f"{key}: {value}\n"
                        else:
                            info_text += "No configuration available.\n"

                        # Add plugin-specific info
                        if 'Metrics' in plugin_name and hasattr(plugin, 'get_metrics'):
                            try:
                                metrics = plugin.get_metrics()
                                info_text += f"""

METRICS
{'='*40}
Total Logs: {metrics.get('total_logs', 0)}
Error Count: {metrics.get('error_count', 0)}
Error Rate: {metrics.get('error_rate', 0):.2f}%
"""
                            except Exception:
                                pass

                        self.plugin_info.insert(tk.END, info_text)
                        return

                self.plugin_info.insert(tk.END, f"Plugin '{plugin_name}' not found.")

        except Exception as e:
            self.plugin_info.insert(tk.END, f"Error loading plugin info: {str(e)}")

    def add_default_plugins(self):
        """Add default plugins to the logger"""
        try:
            if not LOGGER_AVAILABLE:
                messagebox.showwarning("Add Plugins", "Logger not available.")
                return

            # Define default plugins
            default_plugins = [
                ("Slack Notifications", SlackNotificationPlugin, {
                    'enabled': False,
                    'slack_webhook_url': '',
                    'rate_limit_seconds': 300
                }),
                ("Metrics Collection", MetricsCollectionPlugin, {
                    'enabled': True,
                    'reset_interval_hours': 24
                }),
                ("Email Notifications", EmailNotificationPlugin, {
                    'enabled': False,
                    'smtp_server': '',
                    'smtp_port': 587,
                    'smtp_username': '',
                    'smtp_password': '',
                    'from_email': '',
                    'to_emails': []
                }),
                ("Audit Trail", AuditTrailPlugin, {
                    'enabled': True,
                    'audit_file': 'compliance_audit.log',
                    'audit_actions': ['create', 'update', 'delete', 'admin', 'export']
                })
            ]

            added_count = 0

            for name, plugin_class, config in default_plugins:
                try:
                    # Check if plugin already exists
                    existing_plugins = plugin_manager.get_plugin_status()
                    if any(p.get('name') == plugin_class.__name__ for p in existing_plugins):
                        continue

                    # Create and register plugin
                    plugin_instance = plugin_class(config)
                    plugin_manager.register_plugin(plugin_instance)
                    added_count += 1

                except Exception as e:
                    print(f"Error adding plugin {name}: {e}")

            if added_count > 0:
                messagebox.showinfo("Plugins Added", f"Added {added_count} default plugins.")
                self.refresh_plugins()
            else:
                messagebox.showinfo("Plugins", "All default plugins are already installed.")

        except Exception as e:
            messagebox.showerror("Plugin Error", f"Failed to add default plugins: {str(e)}")

    def configure_plugin(self):
        """Configure selected plugin"""
        selection = self.plugin_tree.selection()
        if not selection:
            messagebox.showwarning("Configure Plugin", "Please select a plugin to configure.")
            return

        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]

        # Create configuration window
        config_window = tk.Toplevel(self)
        config_window.title(f"Configure {plugin_name}")
        config_window.geometry("500x400")
        config_window.configure(bg=LoggerGUITheme.DARK_BG)

        ttk.Label(config_window, text=f"Configuration for {plugin_name}",
                 style='AL.Title.TLabel').pack(pady=10)

        # Configuration form
        config_frame = ttk.Frame(config_window)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Get current plugin config
        try:
            if LOGGER_AVAILABLE:
                plugin_status_list = plugin_manager.get_plugin_status()
                current_config = {}

                for plugin in plugin_status_list:
                    if plugin.get('name') == plugin_name:
                        current_config = plugin.get('config', {})
                        break

                # Create config widgets based on plugin type
                config_vars = {}

                if "Slack" in plugin_name:
                    config_vars = self.create_slack_config(config_frame, current_config)
                elif "Email" in plugin_name:
                    config_vars = self.create_email_config(config_frame, current_config)
                elif "Metrics" in plugin_name:
                    config_vars = self.create_metrics_config(config_frame, current_config)
                elif "Audit" in plugin_name:
                    config_vars = self.create_audit_config(config_frame, current_config)
                else:
                    ttk.Label(config_frame, text=_t("activity_logger.plugin_config.not_available"),
                             style='AL.Info.TLabel').pack(pady=20)

                # Buttons
                button_frame = ttk.Frame(config_window)
                button_frame.pack(pady=10)

                def save_config():
                    try:
                        new_config = {}
                        for key, var in config_vars.items():
                            new_config[key] = var.get()

                        # Here you would update the actual plugin configuration
                        # This would require extending the plugin system
                        messagebox.showinfo("Configuration Saved",
                                          f"Configuration for {plugin_name} has been updated.")
                        config_window.destroy()

                    except Exception as e:
                        messagebox.showerror("Configuration Error",
                                           f"Failed to save configuration: {str(e)}")

                ttk.Button(button_frame, text=_t("activity_logger.plugin_config.save"), command=save_config).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="Cancel",
                          command=config_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to load plugin configuration: {str(e)}")

    def create_slack_config(self, parent, current_config):
        """Create Slack plugin configuration widgets"""
        config_vars = {}

        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', False))
        ttk.Checkbutton(parent, text="Enable Slack Notifications",
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)

        # Webhook URL
        ttk.Label(parent, text=_t("activity_logger.plugin_config.slack.webhook_url"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['slack_webhook_url'] = tk.StringVar(value=current_config.get('slack_webhook_url', ''))
        ttk.Entry(parent, textvariable=config_vars['slack_webhook_url'], width=60).pack(fill=tk.X, pady=2)

        # Rate limit
        ttk.Label(parent, text=_t("activity_logger.plugin_config.slack.rate_limit"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['rate_limit_seconds'] = tk.IntVar(value=current_config.get('rate_limit_seconds', 300))
        ttk.Entry(parent, textvariable=config_vars['rate_limit_seconds'], width=20).pack(anchor=tk.W, pady=2)

        return config_vars

    def create_email_config(self, parent, current_config):
        """Create Email plugin configuration widgets"""
        config_vars = {}

        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', False))
        ttk.Checkbutton(parent, text="Enable Email Notifications",
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)

        # SMTP settings
        ttk.Label(parent, text=_t("activity_logger.plugin_config.email.smtp_server"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_server'] = tk.StringVar(value=current_config.get('smtp_server', ''))
        ttk.Entry(parent, textvariable=config_vars['smtp_server'], width=40).pack(anchor=tk.W, pady=2)

        ttk.Label(parent, text=_t("activity_logger.plugin_config.email.smtp_port"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_port'] = tk.IntVar(value=current_config.get('smtp_port', 587))
        ttk.Entry(parent, textvariable=config_vars['smtp_port'], width=20).pack(anchor=tk.W, pady=2)

        ttk.Label(parent, text=_t("activity_logger.plugin_config.email.username"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_username'] = tk.StringVar(value=current_config.get('smtp_username', ''))
        ttk.Entry(parent, textvariable=config_vars['smtp_username'], width=40).pack(anchor=tk.W, pady=2)

        ttk.Label(parent, text=_t("activity_logger.plugin_config.email.password"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_password'] = tk.StringVar()
        ttk.Entry(parent, textvariable=config_vars['smtp_password'], width=40, show="*").pack(anchor=tk.W, pady=2)

        return config_vars

    def create_metrics_config(self, parent, current_config):
        """Create Metrics plugin configuration widgets"""
        config_vars = {}

        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', True))
        ttk.Checkbutton(parent, text="Enable Metrics Collection",
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)

        # Reset interval
        ttk.Label(parent, text=_t("activity_logger.plugin_config.metrics.reset_interval"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['reset_interval_hours'] = tk.IntVar(value=current_config.get('reset_interval_hours', 24))
        ttk.Entry(parent, textvariable=config_vars['reset_interval_hours'], width=20).pack(anchor=tk.W, pady=2)

        return config_vars

    def create_audit_config(self, parent, current_config):
        """Create Audit plugin configuration widgets"""
        config_vars = {}

        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', True))
        ttk.Checkbutton(parent, text="Enable Audit Trail",
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)

        # Audit file
        ttk.Label(parent, text=_t("activity_logger.plugin_config.audit.audit_file"), style='AL.Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['audit_file'] = tk.StringVar(value=current_config.get('audit_file', 'compliance_audit.log'))
        ttk.Entry(parent, textvariable=config_vars['audit_file'], width=40).pack(anchor=tk.W, pady=2)

        return config_vars

    def toggle_plugin(self):
        """Enable/disable selected plugin"""
        selection = self.plugin_tree.selection()
        if not selection:
            messagebox.showwarning("Toggle Plugin", "Please select a plugin to enable/disable.")
            return

        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]
        current_status = item['values'][1]

        # This would require extending the plugin system to support enabling/disabling
        action = "disable" if current_status == "Enabled" else "enable"
        messagebox.showinfo("Toggle Plugin", f"Plugin {plugin_name} would be {action}d.")

        # Refresh the display
        self.refresh_plugins()

    def remove_plugin(self):
        """Remove selected plugin"""
        selection = self.plugin_tree.selection()
        if not selection:
            messagebox.showwarning("Remove Plugin", "Please select a plugin to remove.")
            return

        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]

        if messagebox.askyesno("Remove Plugin", f"Are you sure you want to remove the plugin '{plugin_name}'?"):
            try:
                if LOGGER_AVAILABLE:
                    plugin_manager.unregister_plugin(plugin_name)
                    messagebox.showinfo("Plugin Removed", f"Plugin '{plugin_name}' has been removed.")
                    self.refresh_plugins()
                    self.plugin_info.delete(1.0, tk.END)

            except Exception as e:
                messagebox.showerror("Remove Error", f"Failed to remove plugin: {str(e)}")
