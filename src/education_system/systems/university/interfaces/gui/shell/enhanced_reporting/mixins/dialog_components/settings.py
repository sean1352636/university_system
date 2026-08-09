"""Settings dialogs extracted from DialogsMixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._shared import *  # noqa: F401,F403


class SettingsDialogsMixin:
    def show_directory_settings(self):
        """Show directory settings dialog"""
        try:
            dir_window = tk.Toplevel(self.root)
            dir_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.windows.directory_settings', default="Directory Settings"))
            dir_window.geometry("500x400")
            dir_window.transient(self.root)

            settings_frame = ttk.LabelFrame(dir_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.directory_configuration', default="Directory Configuration"), padding="10")
            settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            settings_frame.columnconfigure(1, weight=1)

            # Reports directory
            ttk.Label(settings_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.reports_directory', default="Reports Directory:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            reports_dir_var = tk.StringVar(value=CONFIG.get('reports_dir', 'reports'))
            ttk.Entry(settings_frame, textvariable=reports_dir_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            def browse_reports_dir():
                directory = filedialog.askdirectory(title=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.select_reports_directory', default="Select Reports Directory"))
                if directory:
                    reports_dir_var.set(directory)

            ttk.Button(settings_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.browse', default="Browse"), command=browse_reports_dir).grid(row=0, column=2, padx=(5, 0), pady=5)

            # Templates directory
            ttk.Label(settings_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.templates_directory', default="Templates Directory:")).grid(row=1, column=0, sticky=tk.W, pady=5)
            templates_dir_var = tk.StringVar(value=CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)))
            ttk.Entry(settings_frame, textvariable=templates_dir_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            def browse_templates_dir():
                directory = filedialog.askdirectory(title=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.select_templates_directory', default="Select Templates Directory"))
                if directory:
                    templates_dir_var.set(directory)

            ttk.Button(settings_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.browse', default="Browse"), command=browse_templates_dir).grid(row=1, column=2, padx=(5, 0), pady=5)

            # Create directories option
            create_dirs_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(settings_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.create_directories_if_they_don_t_exist', default="Create directories if they don't exist"),
                           variable=create_dirs_var).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10)

            # Button frame
            button_frame = ttk.Frame(dir_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_directory_settings():
                try:
                    new_dirs = {
                        'reports_dir': reports_dir_var.get(),
                        'templates_dir': templates_dir_var.get()
                    }

                    if create_dirs_var.get():
                        for dir_path in new_dirs.values():
                            os.makedirs(dir_path, exist_ok=True)

                    CONFIG.update(new_dirs)

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.directory_settings_saved_successfully', default="Directory settings saved successfully!"))
                    dir_window.destroy()
                    self.check_system_status()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.save_error', default="Save Error"), f"Failed to save directory settings: {str(e)}")

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.save', default="Save"), command=save_directory_settings).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.cancel', default="Cancel"), command=dir_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.directory_settings_error', default="Directory Settings Error"), f"Failed to open directory settings: {str(e)}")

    def show_theme_settings(self):
        """Show theme and appearance settings"""
        try:
            theme_window = tk.Toplevel(self.root)
            theme_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.windows.theme_appearance_settings', default="Theme & Appearance Settings"))
            theme_window.geometry("450x350")
            theme_window.transient(self.root)

            theme_frame = ttk.LabelFrame(theme_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.appearance_settings', default="Appearance Settings"), padding="10")
            theme_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Theme selection
            ttk.Label(theme_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.theme', default="Theme:")).pack(anchor=tk.W, pady=5)
            theme_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.values.default', default="default"))
            theme_combo = ttk.Combobox(theme_frame, textvariable=theme_var,
                                      values=["default", "dark", "light", "modern"], state="readonly")
            theme_combo.pack(fill=tk.X, pady=(0, 10))

            # Font settings
            ttk.Label(theme_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.font_family', default="Font Family:")).pack(anchor=tk.W, pady=5)
            font_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.values.arial', default="Arial"))
            font_combo = ttk.Combobox(theme_frame, textvariable=font_var,
                                     values=["Arial", "Helvetica", "Times New Roman", "Calibri"],
                                     state="readonly")
            font_combo.pack(fill=tk.X, pady=(0, 10))

            # Font size
            ttk.Label(theme_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.font_size', default="Font Size:")).pack(anchor=tk.W, pady=5)
            font_size_var = tk.StringVar(value="10")
            font_size_spin = ttk.Spinbox(theme_frame, from_=8, to=16, textvariable=font_size_var)
            font_size_spin.pack(fill=tk.X, pady=(0, 10))

            # Preview
            preview_frame = ttk.LabelFrame(theme_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.preview', default="Preview"), padding="10")
            preview_frame.pack(fill=tk.X, pady=10)

            preview_label = ttk.Label(preview_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.sample_text_with_current_settings', default="Sample text with current settings"))
            preview_label.pack()

            def update_preview():
                try:
                    font_family = font_var.get()
                    font_size = int(font_size_var.get())
                    preview_label.config(font=(font_family, font_size))
                except Exception as e:
                    logger.debug(f"Failed to configure preview label font: {e}")

            theme_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())
            font_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())

            # Button frame
            button_frame = ttk.Frame(theme_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def apply_theme():
                try:
                    theme_settings = {
                        'theme': theme_var.get(),
                        'font_family': font_var.get(),
                        'font_size': int(font_size_var.get())
                    }

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.theme_applied', default="Theme Applied"),
                                      f"Theme settings would be applied:\n\nTheme: {theme_settings['theme']}\nFont: {theme_settings['font_family']} {theme_settings['font_size']}pt")
                    theme_window.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.theme_error', default="Theme Error"), f"Failed to apply theme: {str(e)}")

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.apply', default="Apply"), command=apply_theme).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.cancel', default="Cancel"), command=theme_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.theme_settings_error', default="Theme Settings Error"), f"Failed to open theme settings: {str(e)}")

    def show_system_config_editor(self):
        """Show system configuration editor window"""
        try:
            config_window = tk.Toplevel(self.root)
            config_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.windows.system_configuration_editor', default="System Configuration Editor"))
            config_window.geometry("700x600")
            config_window.transient(self.root)

            # Create notebook for different config sections
            config_notebook = ttk.Notebook(config_window)
            config_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # General config tab
            general_frame = ttk.Frame(config_notebook)
            config_notebook.add(general_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.tabs.general', default="General"))

            # Database config
            ttk.Label(general_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.database_path', default="Database Path:")).pack(anchor=tk.W, pady=5)
            db_path_var = tk.StringVar(value=CONFIG.get('database', str(DEFAULT_DB_PATH)))
            ttk.Entry(general_frame, textvariable=db_path_var, width=60).pack(fill=tk.X, pady=(0, 10))

            # Reports directory
            ttk.Label(general_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.reports_directory', default="Reports Directory:")).pack(anchor=tk.W, pady=5)
            reports_dir_var = tk.StringVar(value=CONFIG.get('reports_dir', 'reports'))
            ttk.Entry(general_frame, textvariable=reports_dir_var, width=60).pack(fill=tk.X, pady=(0, 10))

            # Cache config tab
            cache_frame = ttk.Frame(config_notebook)
            config_notebook.add(cache_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.tabs.cache', default="Cache"))

            ttk.Label(cache_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.cache_expiry_hours', default="Cache Expiry (hours):")).pack(anchor=tk.W, pady=5)
            cache_expiry_var = tk.StringVar(value=str(CONFIG.get('cache_expiry_hours', 24)))
            ttk.Entry(cache_frame, textvariable=cache_expiry_var).pack(fill=tk.X, pady=(0, 10))

            ttk.Label(cache_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.max_cache_size_mb', default="Max Cache Size (MB):")).pack(anchor=tk.W, pady=5)
            max_cache_var = tk.StringVar(value=str(CONFIG.get('max_cache_size_mb', 500)))
            ttk.Entry(cache_frame, textvariable=max_cache_var).pack(fill=tk.X, pady=(0, 10))

            # Security config tab
            security_frame = ttk.Frame(config_notebook)
            config_notebook.add(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.tabs.security', default="Security"))

            ttk.Label(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.session_timeout_seconds', default="Session Timeout (seconds):")).pack(anchor=tk.W, pady=5)
            session_timeout_var = tk.StringVar(value="3600")
            ttk.Entry(security_frame, textvariable=session_timeout_var).pack(fill=tk.X, pady=(0, 10))

            require_auth_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.require_authentication', default="Require Authentication"), variable=require_auth_var).pack(anchor=tk.W, pady=5)

            # Button frame
            button_frame = ttk.Frame(config_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_config():
                try:
                    new_config = {
                        'database': db_path_var.get(),
                        'reports_dir': reports_dir_var.get(),
                        'cache_expiry_hours': int(cache_expiry_var.get()),
                        'max_cache_size_mb': int(max_cache_var.get())
                    }

                    CONFIG.update(new_config)
                    if ENHANCED_AVAILABLE:
                        SystemConfig.save_config(new_config)

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.configuration_saved_successfully', default="Configuration saved successfully!"))
                    config_window.destroy()
                    self.check_system_status()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.save_error', default="Save Error"), f"Failed to save configuration: {str(e)}")

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.save', default="Save"), command=save_config).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.cancel', default="Cancel"), command=config_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.config_error', default="Config Error"), f"Failed to open configuration editor: {str(e)}")

    def show_email_settings_dialog(self):
        """Show email configuration dialog"""
        try:
            email_window = tk.Toplevel(self.root)
            email_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.windows.email_settings', default="Email Settings"))
            email_window.geometry("500x400")
            email_window.transient(self.root)

            # Email configuration form
            config_frame = ttk.LabelFrame(email_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.smtp_configuration', default="SMTP Configuration"), padding="10")
            config_frame.pack(fill=tk.X, padx=10, pady=10)
            config_frame.columnconfigure(1, weight=1)

            # SMTP Server
            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.smtp_server', default="SMTP Server:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            smtp_server_var = tk.StringVar(value=CONFIG.get('email', {}).get('smtp_server', 'smtp.gmail.com'))
            ttk.Entry(config_frame, textvariable=smtp_server_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # SMTP Port
            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.smtp_port', default="SMTP Port:")).grid(row=1, column=0, sticky=tk.W, pady=5)
            smtp_port_var = tk.StringVar(value=str(CONFIG.get('email', {}).get('smtp_port', 587)))
            ttk.Entry(config_frame, textvariable=smtp_port_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # From Address
            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.from_address', default="From Address:")).grid(row=2, column=0, sticky=tk.W, pady=5)
            from_address_var = tk.StringVar(value=CONFIG.get('email', {}).get('from_address', ''))
            ttk.Entry(config_frame, textvariable=from_address_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Username
            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.username', default="Username:")).grid(row=3, column=0, sticky=tk.W, pady=5)
            username_var = tk.StringVar(value=CONFIG.get('email', {}).get('username', ''))
            ttk.Entry(config_frame, textvariable=username_var).grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Password
            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.password', default="Password:")).grid(row=4, column=0, sticky=tk.W, pady=5)
            password_var = tk.StringVar()
            ttk.Entry(config_frame, textvariable=password_var, show='*').grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Use TLS
            use_tls_var = tk.BooleanVar(value=CONFIG.get('email', {}).get('use_tls', True))
            ttk.Checkbutton(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.use_tls', default="Use TLS"), variable=use_tls_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)

            # Enable email
            email_enabled_var = tk.BooleanVar(value=CONFIG.get('email', {}).get('enabled', False))
            ttk.Checkbutton(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.enable_email_notifications', default="Enable Email Notifications"), variable=email_enabled_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)

            # Test email section
            test_frame = ttk.LabelFrame(email_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.test_email', default="Test Email"), padding="10")
            test_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(test_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.test_email_address', default="Test Email Address:")).pack(anchor=tk.W)
            test_email_var = tk.StringVar()
            ttk.Entry(test_frame, textvariable=test_email_var, width=40).pack(fill=tk.X, pady=(0, 10))

            def send_test_email():
                try:
                    from education_system.systems.university.infrastructure.email.email_service import send_email

                    test_email = test_email_var.get().strip()
                    if not test_email or '@' not in test_email:
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.invalid_email', default="Invalid Email"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.please_enter_a_valid_email_address', default="Please enter a valid email address"))
                        return

                    # Use temporary config for test
                    test_config = {
                        'smtp_server': smtp_server_var.get(),
                        'smtp_port': int(smtp_port_var.get()),
                        'from_address': from_address_var.get(),
                        'username': username_var.get(),
                        'password': password_var.get(),
                        'use_tls': use_tls_var.get()
                    }

                    body = """This is a test email from the University Reporting System.

If you receive this email, your email settings are configured correctly!

System Configuration:
- SMTP Server: {smtp_server}
- SMTP Port: {smtp_port}
- From Address: {from_address}
- TLS Enabled: {use_tls}

Thank you for using our system.
""".format(**test_config)

                    success = send_email(
                        recipient_email=test_email,
                        subject='Test Email from University Reporting System',
                        body=body
                    )

                    if success:
                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.test_email_sent', default="Test Email Sent"), f"Test email successfully sent to {test_email}!")
                    else:
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.test_failed', default="Test Failed"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.test_email_failed_to_send', default="Test email failed to send"))

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.test_failed', default="Test Failed"), f"Test email failed: {str(e)}")

            ttk.Button(test_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.send_test_email', default="Send Test Email"), command=send_test_email).pack()

            # Button frame
            button_frame = ttk.Frame(email_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_email_settings():
                try:
                    email_config = {
                        'enabled': email_enabled_var.get(),
                        'smtp_server': smtp_server_var.get(),
                        'smtp_port': int(smtp_port_var.get()),
                        'from_address': from_address_var.get(),
                        'username': username_var.get(),
                        'use_tls': use_tls_var.get()
                    }

                    CONFIG['email'] = email_config

                    if ENHANCED_AVAILABLE:
                        full_config = SystemConfig.load_config()
                        full_config['email'] = email_config
                        SystemConfig.save_config(full_config)

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.email_settings_saved_successfully', default="Email settings saved successfully!"))
                    email_window.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.save_error', default="Save Error"), f"Failed to save email settings: {str(e)}")

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.save', default="Save"), command=save_email_settings).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.cancel', default="Cancel"), command=email_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.email_settings_error', default="Email Settings Error"), f"Failed to open email settings: {str(e)}")

    def show_advanced_settings(self):
        """Show advanced settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.windows.advanced_settings', default="Advanced Settings"))
        settings_window.geometry("500x400")
        settings_window.transient(self.root)

        # Create notebook for different setting categories
        settings_notebook = ttk.Notebook(settings_window)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load existing settings
        default_settings = {
            'cache_expiry_hours': 24,
            'max_cache_size_mb': 500,
            'session_timeout_seconds': 3600,
            'require_2fa': False,
            'enable_caching': True,
            'max_concurrent_reports': 5
        }

        try:
            config_file = paths.DATA_DIR / 'reporting_settings.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    loaded_settings = json.load(f)
                    default_settings.update(loaded_settings)
        except Exception as e:
            logging.warning(f"Could not load settings: {e}")

        # General settings
        general_frame = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(general_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.tabs.general', default="General"))

        ttk.Label(general_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.cache_expiry_hours_variant_2', default="Cache expiry (hours):")).pack(anchor=tk.W, pady=5)
        cache_expiry = tk.StringVar(value=str(default_settings['cache_expiry_hours']))
        ttk.Entry(general_frame, textvariable=cache_expiry).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(general_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.max_cache_size_mb_variant_2', default="Max cache size (MB):")).pack(anchor=tk.W, pady=5)
        cache_size = tk.StringVar(value=str(default_settings['max_cache_size_mb']))
        ttk.Entry(general_frame, textvariable=cache_size).pack(fill=tk.X, pady=(0, 10))

        # Security settings
        security_frame = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.tabs.security', default="Security"))

        ttk.Label(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.session_timeout_seconds_variant_2', default="Session timeout (seconds):")).pack(anchor=tk.W, pady=5)
        session_timeout = tk.StringVar(value=str(default_settings['session_timeout_seconds']))
        ttk.Entry(security_frame, textvariable=session_timeout).pack(fill=tk.X, pady=(0, 10))

        require_2fa = tk.BooleanVar(value=default_settings['require_2fa'])
        ttk.Checkbutton(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.require_2fa', default="Require 2FA"), variable=require_2fa).pack(anchor=tk.W, pady=5)

        # Performance settings
        performance_frame = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(performance_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.tabs.performance', default="Performance"))

        enable_caching = tk.BooleanVar(value=default_settings['enable_caching'])
        ttk.Checkbutton(performance_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.enable_caching', default="Enable caching"), variable=enable_caching).pack(anchor=tk.W, pady=5)

        ttk.Label(performance_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.labels.max_concurrent_reports', default="Max concurrent reports:")).pack(anchor=tk.W, pady=5)
        max_reports = tk.StringVar(value=str(default_settings['max_concurrent_reports']))
        ttk.Entry(performance_frame, textvariable=max_reports).pack(fill=tk.X, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def save_settings():
            try:
                # Prepare settings dictionary
                settings = {
                    'cache_expiry_hours': int(cache_expiry.get()),
                    'max_cache_size_mb': int(cache_size.get()),
                    'session_timeout_seconds': int(session_timeout.get()),
                    'require_2fa': require_2fa.get(),
                    'enable_caching': enable_caching.get(),
                    'max_concurrent_reports': int(max_reports.get())
                }

                # Save to config file
                config_file = paths.DATA_DIR / 'reporting_settings.json'
                with open(config_file, 'w') as f:
                    json.dump(settings, f, indent=4)

                messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.settings_saved_successfully', default="Settings saved successfully!"))
                settings_window.destroy()
            except ValueError:
                messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.invalid_input', default="Invalid Input"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.please_enter_valid_numeric_values_for_all_fields', default="Please enter valid numeric values for all fields."))
            except Exception as e:
                messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.dialogs.error', default="Error"), f"Failed to save settings: {str(e)}")

        ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.save', default="Save"), command=save_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.settings.buttons.cancel', default="Cancel"), command=settings_window.destroy).pack(side=tk.RIGHT)

    def show_settings(self):
        """Show general settings"""
        self.show_advanced_settings()
