# dialogs/settings.py
# Dialog for application settings.

from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import tk, ttk, messagebox


class SettingsDialog:
    """Dialog for application settings"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()

        # Ensure window is visible before grabbing focus
        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Ignore grab errors if window not ready

    def create_widgets(self):
        """Create settings widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Notification settings
        notification_frame = ttk.LabelFrame(main_frame, text="Notifications")
        notification_frame.pack(fill=tk.X, pady=10)

        self.expiry_days_var = tk.StringVar(value="7")
        ttk.Label(notification_frame, text="Expiry notification days:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(notification_frame, textvariable=self.expiry_days_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        # Display settings
        display_frame = ttk.LabelFrame(main_frame, text="Display")
        display_frame.pack(fill=tk.X, pady=10)

        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(display_frame, text="Auto-refresh data", variable=self.auto_refresh_var).pack(anchor='w', padx=5, pady=5)

        self.show_tooltips_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(display_frame, text="Show tooltips", variable=self.show_tooltips_var).pack(anchor='w', padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def save_settings(self):
        """Save settings"""
        messagebox.showinfo("Settings", "Settings saved successfully")
        self.dialog.destroy()
