"""Data export dialog."""
import tkinter as tk
from tkinter import ttk, messagebox


class ExportDialog:
    def __init__(self, parent):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Data")
        self.dialog.geometry("300x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Export Type:").grid(row=0, column=0, sticky="w", pady=5)
        self.export_var = tk.StringVar()
        export_combo = ttk.Combobox(main_frame, textvariable=self.export_var,
                                   values=["permits", "vehicles", "violations", "lots"],
                                   state="readonly")
        export_combo.grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Format:").grid(row=1, column=0, sticky="w", pady=5)
        self.format_var = tk.StringVar()
        format_combo = ttk.Combobox(main_frame, textvariable=self.format_var,
                                   values=["csv", "excel", "pdf", "txt"],
                                   state="readonly")
        format_combo.grid(row=1, column=1, sticky="ew", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Export", command=self.export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def export(self):
        if not self.export_var.get() or not self.format_var.get():
            messagebox.showerror("Error", "Please select both export type and format")
            return

        self.result = (self.export_var.get(), self.format_var.get())
        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()
