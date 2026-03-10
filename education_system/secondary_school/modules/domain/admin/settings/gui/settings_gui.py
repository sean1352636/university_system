"""Settings GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.admin.settings.services.settings_service import (
    SettingsService, CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class SettingsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SettingsService(db_path)
        self._svc.seed_defaults()
        self._entries = {}
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Settings", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Save All", command=self._on_save).pack(side="left", padx=4)
        tk.Label(toolbar, text="Category:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._cat_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._cat_var,
                     values=["All"] + list(CATEGORIES), state="readonly", width=14).pack(side="left")
        self._cat_var.trace_add("write", lambda *_: self._load())

        # Scrollable settings area
        canvas_frame = tk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self._settings_frame = tk.Frame(canvas, bg="white")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=self._settings_frame, anchor="nw")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure("all", width=event.width)
        self._settings_frame.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(
            canvas.find_withtag("all")[0], width=e.width) if canvas.find_withtag("all") else None)

        self._canvas = canvas
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        for w in self._settings_frame.winfo_children():
            w.destroy()
        self._entries.clear()
        cat = self._cat_var.get()
        try:
            settings = self._svc.list_settings(category=cat if cat != "All" else None)
            current_cat = None
            for s in settings:
                if s["category"] != current_cat:
                    current_cat = s["category"]
                    tk.Label(self._settings_frame, text=current_cat.upper(),
                             font=("Helvetica", 10, "bold"), bg="white",
                             fg=HEADER_BG).pack(anchor="w", padx=15, pady=(12, 4))
                    ttk.Separator(self._settings_frame, orient="horizontal").pack(fill="x", padx=15)

                row = tk.Frame(self._settings_frame, bg="white")
                row.pack(fill="x", padx=15, pady=3)
                desc = s.get("description") or s["key"]
                tk.Label(row, text=desc, font=("Helvetica", 9), bg="white",
                         width=35, anchor="w").pack(side="left")
                var = tk.StringVar(value=s["value"] or "")
                ttk.Entry(row, textvariable=var, width=35).pack(side="left", padx=10)
                self._entries[s["key"]] = var

                if s.get("updated_by"):
                    tk.Label(row, text=f"({s['updated_by']})", font=("Helvetica", 8),
                             bg="white", fg="#95a5a6").pack(side="left")

            self._status_var.set(f"{len(settings)} setting(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_save(self):
        updated_by = self._auth.get("username") if self._auth else None
        count = 0
        for key, var in self._entries.items():
            try:
                self._svc.set(key, var.get(), updated_by)
                count += 1
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save {key}: {e}")
                return
        self._status_var.set(f"Saved {count} setting(s)")
        messagebox.showinfo("Success", f"All {count} settings saved.")
