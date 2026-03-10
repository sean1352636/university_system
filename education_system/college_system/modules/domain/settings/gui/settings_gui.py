"""Settings GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.settings.services.settings_service import SettingsService


class SettingsFrame(tk.Frame):
    """Settings management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SettingsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Settings",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- User Preferences tab ---
        user_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(user_tab, text="User Preferences")

        tk.Label(user_tab, text="Theme:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky="w", pady=8)
        self._theme_var = tk.StringVar(value="light")
        ttk.Combobox(user_tab, textvariable=self._theme_var,
                     values=["light", "dark"], state="readonly",
                     width=12).grid(row=0, column=1, sticky="w", pady=8)

        tk.Label(user_tab, text="Notifications:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=1, column=0, sticky="w", pady=8)
        self._notif_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(user_tab, text="Enabled",
                        variable=self._notif_var).grid(
            row=1, column=1, sticky="w", pady=8)

        tk.Label(user_tab, text="Language:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=2, column=0, sticky="w", pady=8)
        self._lang_var = tk.StringVar(value="en")
        ttk.Combobox(user_tab, textvariable=self._lang_var,
                     values=["en"], state="readonly",
                     width=12).grid(row=2, column=1, sticky="w", pady=8)

        tk.Label(user_tab, text="Items per page:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=3, column=0, sticky="w", pady=8)
        self._ipp_var = tk.StringVar(value="25")
        ttk.Combobox(user_tab, textvariable=self._ipp_var,
                     values=["25", "50", "100"], state="readonly",
                     width=8).grid(row=3, column=1, sticky="w", pady=8)

        ttk.Button(user_tab, text="Save Preferences",
                   command=self._save_user_settings).grid(
            row=4, column=1, sticky="w", pady=20)

        # --- System Settings tab (admin only) ---
        self._system_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(self._system_tab, text="System Settings")

        tk.Label(self._system_tab, text="College Name:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky="w", pady=8)
        self._college_name_var = tk.StringVar()
        ttk.Entry(self._system_tab, textvariable=self._college_name_var,
                  width=30).grid(row=0, column=1, sticky="w", pady=8)

        tk.Label(self._system_tab, text="Academic Year:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=1, column=0, sticky="w", pady=8)
        self._academic_year_var = tk.StringVar()
        ttk.Entry(self._system_tab, textvariable=self._academic_year_var,
                  width=15).grid(row=1, column=1, sticky="w", pady=8)

        tk.Label(self._system_tab, text="Default Capacity:", bg="#ecf0f1",
                 font=("Helvetica", 10)).grid(row=2, column=0, sticky="w", pady=8)
        self._capacity_var = tk.StringVar()
        ttk.Entry(self._system_tab, textvariable=self._capacity_var,
                  width=8).grid(row=2, column=1, sticky="w", pady=8)

        ttk.Button(self._system_tab, text="Save System Settings",
                   command=self._save_system_settings).grid(
            row=3, column=1, sticky="w", pady=20)

    def refresh(self):
        self._apply_permissions()
        self._load_user_settings()
        if self._get_role() == "admin":
            self._load_system_settings()

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _get_role(self) -> str:
        if self._auth and self._auth.current_user:
            return self._auth.current_user.get("role", "student")
        return "student"

    def _apply_permissions(self):
        is_admin = self._get_role() == "admin"
        try:
            self._nb.tab(self._system_tab,
                         state="normal" if is_admin else "hidden")
        except Exception:
            pass

    def _load_user_settings(self):
        user_id = self._get_user_id()
        try:
            settings = self._svc.get_all_user_settings(user_id)
            self._theme_var.set(settings.get("theme", "light"))
            self._notif_var.set(settings.get("notifications_enabled", "true") == "true")
            self._lang_var.set(settings.get("language", "en"))
            self._ipp_var.set(settings.get("items_per_page", "25"))
        except Exception:
            pass

    def _save_user_settings(self):
        user_id = self._get_user_id()
        try:
            self._svc.set_user_setting(user_id, "theme", self._theme_var.get())
            self._svc.set_user_setting(user_id, "notifications_enabled",
                                       "true" if self._notif_var.get() else "false")
            self._svc.set_user_setting(user_id, "language", self._lang_var.get())
            self._svc.set_user_setting(user_id, "items_per_page", self._ipp_var.get())
            messagebox.showinfo("Success", "Preferences saved.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_system_settings(self):
        try:
            settings = self._svc.get_all_system_settings()
            self._college_name_var.set(settings.get("college_name", ""))
            self._academic_year_var.set(settings.get("academic_year", ""))
            self._capacity_var.set(settings.get("default_capacity", ""))
        except Exception:
            pass

    def _save_system_settings(self):
        user_id = self._get_user_id()
        try:
            name = self._college_name_var.get().strip()
            if name:
                self._svc.set_system_setting("college_name", name, user_id)
            year = self._academic_year_var.get().strip()
            if year:
                self._svc.set_system_setting("academic_year", year, user_id)
            cap = self._capacity_var.get().strip()
            if cap:
                self._svc.set_system_setting("default_capacity", cap, user_id)
            messagebox.showinfo("Success", "System settings saved.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
