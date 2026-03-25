"""Settings-related standalone functions for the enhanced reporting GUI.

Note: These functions accept ``self`` as a first argument even though
they are module-level functions.  They were originally written to be
called on a GUI instance and are preserved here with the same
signature for backward compatibility.
"""

from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    tk, ttk, filedialog, messagebox,
    os, logging, paths,
    CONFIG, ENHANCED_AVAILABLE, SystemConfig,
    _t, logger,
)


def show_directory_settings(self):
    """Show directory settings dialog"""
    try:
        dir_window = tk.Toplevel(self.root)
        dir_window.title(_t("enhanced_reporting.dialogs.directory_settings"))
        dir_window.geometry("500x400")
        dir_window.transient(self.root)

        settings_frame = ttk.LabelFrame(dir_window, text=_t("enhanced_reporting.labels.directory_configuration"), padding="10")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        settings_frame.columnconfigure(1, weight=1)

        # Reports directory
        ttk.Label(settings_frame, text=_t("enhanced_reporting.labels.reports_directory")).grid(row=0, column=0, sticky=tk.W, pady=5)
        reports_dir_var = tk.StringVar(value=CONFIG.get('reports_dir', 'reports'))
        reports_entry = ttk.Entry(settings_frame, textvariable=reports_dir_var)
        reports_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        def browse_reports_dir():
            directory = filedialog.askdirectory(title=_t("enhanced_reporting.dialogs.select_reports_directory"))
            if directory:
                reports_dir_var.set(directory)

        ttk.Button(settings_frame, text=_t("enhanced_reporting.buttons.browse"), command=browse_reports_dir).grid(row=0, column=2, padx=(5, 0), pady=5)

        # Templates directory
        ttk.Label(settings_frame, text=_t("enhanced_reporting.labels.templates_directory")).grid(row=1, column=0, sticky=tk.W, pady=5)
        templates_dir_var = tk.StringVar(value=CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)))
        templates_entry = ttk.Entry(settings_frame, textvariable=templates_dir_var)
        templates_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        def browse_templates_dir():
            directory = filedialog.askdirectory(title=_t("enhanced_reporting.dialogs.select_templates_directory"))
            if directory:
                templates_dir_var.set(directory)

        ttk.Button(settings_frame, text=_t("enhanced_reporting.buttons.browse"), command=browse_templates_dir).grid(row=1, column=2, padx=(5, 0), pady=5)

        # Cache directory
        ttk.Label(settings_frame, text=_t("enhanced_reporting.labels.cache_directory")).grid(row=2, column=0, sticky=tk.W, pady=5)
        cache_dir_var = tk.StringVar(value=CONFIG.get('cache_dir', 'cache'))
        cache_entry = ttk.Entry(settings_frame, textvariable=cache_dir_var)
        cache_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        def browse_cache_dir():
            directory = filedialog.askdirectory(title=_t("enhanced_reporting.dialogs.select_cache_directory"))
            if directory:
                cache_dir_var.set(directory)

        ttk.Button(settings_frame, text=_t("enhanced_reporting.buttons.browse"), command=browse_cache_dir).grid(row=2, column=2, padx=(5, 0), pady=5)

        # Create directories option
        create_dirs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text=_t("enhanced_reporting.labels.create_directories_if_missing"),
                       variable=create_dirs_var).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=10)

        # Button frame
        button_frame = ttk.Frame(dir_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def save_directory_settings():
            try:
                new_dirs = {
                    'reports_dir': reports_dir_var.get(),
                    'templates_dir': templates_dir_var.get(),
                    'cache_dir': cache_dir_var.get()
                }

                # Create directories if requested
                if create_dirs_var.get():
                    for dir_path in new_dirs.values():
                        os.makedirs(dir_path, exist_ok=True)

                CONFIG.update(new_dirs)

                if ENHANCED_AVAILABLE:
                    full_config = SystemConfig.load_config()
                    full_config.update(new_dirs)
                    SystemConfig.save_config(full_config)

                messagebox.showinfo(_t("enhanced_reporting.messages.success"), _t("enhanced_reporting.messages.directory_settings_saved"))
                dir_window.destroy()
                self.check_system_status()

            except Exception as e:
                messagebox.showerror(_t("enhanced_reporting.messages.save_error"), _t("enhanced_reporting.messages.failed_save_directory_settings", error=str(e)))

        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.save"), command=save_directory_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.cancel"), command=dir_window.destroy).pack(side=tk.RIGHT)

    except Exception as e:
        messagebox.showerror(_t("enhanced_reporting.messages.directory_settings_error"), _t("enhanced_reporting.messages.failed_open_directory_settings", error=str(e)))

def show_theme_settings(self):
    """Show theme and appearance settings"""
    try:
        theme_window = tk.Toplevel(self.root)
        theme_window.title(_t("enhanced_reporting.dialogs.theme_settings"))
        theme_window.geometry("450x350")
        theme_window.transient(self.root)

        theme_frame = ttk.LabelFrame(theme_window, text=_t("enhanced_reporting.labels.appearance_settings"), padding="10")
        theme_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Theme selection
        ttk.Label(theme_frame, text=_t("enhanced_reporting.labels.theme")).pack(anchor=tk.W, pady=5)
        theme_var = tk.StringVar(value="default")
        theme_combo = ttk.Combobox(theme_frame, textvariable=theme_var,
                                  values=["default", "dark", "light", "modern"], state="readonly")
        theme_combo.pack(fill=tk.X, pady=(0, 10))

        # Font settings
        ttk.Label(theme_frame, text=_t("enhanced_reporting.labels.font_family")).pack(anchor=tk.W, pady=5)
        font_var = tk.StringVar(value="Arial")
        font_combo = ttk.Combobox(theme_frame, textvariable=font_var,
                                 values=["Arial", "Helvetica", "Times New Roman", "Calibri", "Segoe UI"],
                                 state="readonly")
        font_combo.pack(fill=tk.X, pady=(0, 10))

        # Font size
        ttk.Label(theme_frame, text=_t("enhanced_reporting.labels.font_size")).pack(anchor=tk.W, pady=5)
        font_size_var = tk.StringVar(value="10")
        font_size_spin = ttk.Spinbox(theme_frame, from_=8, to=16, textvariable=font_size_var)
        font_size_spin.pack(fill=tk.X, pady=(0, 10))

        # UI density
        ttk.Label(theme_frame, text=_t("enhanced_reporting.labels.ui_density")).pack(anchor=tk.W, pady=5)
        density_var = tk.StringVar(value="normal")
        density_combo = ttk.Combobox(theme_frame, textvariable=density_var,
                                    values=["compact", "normal", "spacious"], state="readonly")
        density_combo.pack(fill=tk.X, pady=(0, 10))

        # Preview frame
        preview_frame = ttk.LabelFrame(theme_frame, text=_t("enhanced_reporting.labels.preview"), padding="10")
        preview_frame.pack(fill=tk.X, pady=10)

        preview_label = ttk.Label(preview_frame, text=_t("enhanced_reporting.labels.sample_text"))
        preview_label.pack()

        def update_preview():
            try:
                font_family = font_var.get()
                font_size = int(font_size_var.get())
                preview_label.config(font=(font_family, font_size))
            except Exception as e:
                logger.debug(f"Failed to configure preview label font: {e}")

        # Bind preview updates
        theme_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())
        font_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())
        font_size_spin.bind('<KeyRelease>', lambda e: update_preview())

        # Button frame
        button_frame = ttk.Frame(theme_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def apply_theme():
            try:
                theme_settings = {
                    'theme': theme_var.get(),
                    'font_family': font_var.get(),
                    'font_size': int(font_size_var.get()),
                    'ui_density': density_var.get()
                }

                # Apply theme (this would require theme system implementation)
                messagebox.showinfo(_t("enhanced_reporting.messages.theme_applied"),
                                  f"{_t('enhanced_reporting.messages.theme_settings_applied')}\n\n{_t('enhanced_reporting.labels.theme')}: {theme_settings['theme']}\n{_t('enhanced_reporting.labels.font')}: {theme_settings['font_family']} {theme_settings['font_size']}pt\n{_t('enhanced_reporting.labels.density')}: {theme_settings['ui_density']}")

                theme_window.destroy()

            except Exception as e:
                messagebox.showerror(_t("enhanced_reporting.messages.theme_error"), _t("enhanced_reporting.messages.failed_apply_theme", error=str(e)))

        def reset_theme():
            theme_var.set("default")
            font_var.set("Arial")
            font_size_var.set("10")
            density_var.set("normal")
            update_preview()

        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.apply"), command=apply_theme).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.reset"), command=reset_theme).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.cancel"), command=theme_window.destroy).pack(side=tk.RIGHT)

    except Exception as e:
        messagebox.showerror(_t("enhanced_reporting.messages.theme_settings_error"), _t("enhanced_reporting.messages.failed_open_theme_settings", error=str(e)))

def validate_email_settings(self, settings):
    """Validate email configuration settings"""
    try:
        required_fields = ['smtp_server', 'smtp_port', 'from_address']

        for field in required_fields:
            if not settings.get(field):
                return False, f"Missing required field: {field}"

        # Validate port is numeric
        try:
            port = int(settings['smtp_port'])
            if port < 1 or port > 65535:
                return False, "SMTP port must be between 1 and 65535"
        except ValueError:
            return False, "SMTP port must be a valid number"

        # Validate email format
        email = settings['from_address']
        if '@' not in email or '.' not in email.split('@')[1]:
            return False, "Invalid from_address email format"

        return True, "Valid"

    except Exception as e:
        return False, f"Validation error: {str(e)}"
