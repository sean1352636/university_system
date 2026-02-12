"""
Cinema Booking System - Promo Code Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

def show_promo_management(self):
    """Display promo code management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.promo.title"),
             style="Subtitle.TLabel").pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)

    ttk.Button(btn_frame, text=_t("cinema.promo.add_promo_btn"), style="Success.TButton",
              command=self.show_add_promo_form).pack(side="left", padx=5)

    # Promo codes list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Code", "Type", "Value", "Min Purchase", "Uses", "Max Uses", "Valid Until", "Status")
    self.promo_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        self.promo_tree.heading(col, text=col)
        self.promo_tree.column(col, width=100)
    self.promo_tree.column("ID", width=50)

    self.refresh_promo_list()

    self.promo_tree.pack(fill="both", expand=True, side="left")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.promo_tree.yview)
    self.promo_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.buttons.edit_selected"), style="Secondary.TButton",
              command=self.edit_selected_promo).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.deactivate_selected"), style="Danger.TButton",
              command=self.deactivate_selected_promo).pack(side="left", padx=5)

def refresh_promo_list(self):
    """Refresh promo codes list."""
    for item in self.promo_tree.get_children():
        self.promo_tree.delete(item)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM promo_codes ORDER BY id DESC")

    for row in cursor.fetchall():
        value_display = f"{row[3]}%" if row[2] == 'percentage' else f"\u00a3{row[3]:.2f}"
        self.promo_tree.insert("", "end", values=(
            row[0], row[1], row[2].title(), value_display,
            f"\u00a3{row[4]:.2f}", row[6], row[5] or "\u221e", row[8] or "No limit", row[9].upper()
        ))
    conn.close()

def show_add_promo_form(self):
    """Show form to add promo code."""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Promo Code")
    form_window.geometry("450x400")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=_t("cinema.promo.new_promo"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    # Code
    tk.Label(fields_frame, text=_t("cinema.promo.code_label"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    code_entry = ttk.Entry(fields_frame, width=35)
    code_entry.grid(row=1, column=1, pady=5)

    # Type
    tk.Label(fields_frame, text=_t("cinema.promo.type_label"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    type_var = tk.StringVar(value="percentage")
    type_combo = ttk.Combobox(fields_frame, textvariable=type_var, width=32,
                              values=["percentage", "fixed"])
    type_combo.grid(row=2, column=1, pady=5)

    # Value
    tk.Label(fields_frame, text=_t("cinema.promo.value_label"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    value_entry = ttk.Entry(fields_frame, width=35)
    value_entry.grid(row=3, column=1, pady=5)

    # Min purchase
    tk.Label(fields_frame, text=_t("cinema.promo.min_purchase_label"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    min_entry = ttk.Entry(fields_frame, width=35)
    min_entry.insert(0, "0")
    min_entry.grid(row=4, column=1, pady=5)

    # Max uses
    tk.Label(fields_frame, text=_t("cinema.promo.max_uses_label"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    max_entry = ttk.Entry(fields_frame, width=35)
    max_entry.grid(row=5, column=1, pady=5)

    # Valid until
    tk.Label(fields_frame, text=_t("cinema.promo.valid_until_label"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="w", pady=5)
    valid_entry = ttk.Entry(fields_frame, width=35)
    valid_entry.insert(0, (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
    valid_entry.grid(row=6, column=1, pady=5)

    def save_promo():
        code = code_entry.get().strip().upper()
        if not code:
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.enter_code"))
            return

        try:
            value = float(value_entry.get())
            min_purchase = float(min_entry.get() or 0)
            max_uses = int(max_entry.get()) if max_entry.get() else None
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.errors.invalid_values"))
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO promo_codes (code, discount_type, discount_value, min_purchase, max_uses, valid_until)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (code, type_var.get(), value, min_purchase, max_uses, valid_entry.get()))
            conn.commit()
            messagebox.showinfo(_t("cinema.common.success"), "Promo code created!")
            form_window.destroy()
            self.refresh_promo_list()
        except sqlite3.IntegrityError:
            messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.code_exists"))
        finally:
            conn.close()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.buttons.save"), style="Success.TButton", command=save_promo).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton", command=form_window.destroy).pack(side="left", padx=5)

def edit_selected_promo(self):
    """Edit selected promo code."""
    selected = self.promo_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_promo"))
        return
    # Similar to add form but pre-filled - simplified for brevity
    messagebox.showinfo(_t("cinema.common.info"), _t("cinema.messages.info.edit_note"))

def deactivate_selected_promo(self):
    """Deactivate selected promo code."""
    selected = self.promo_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_promo"))
        return

    promo_id = self.promo_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE promo_codes SET status = 'inactive' WHERE id = ?", (promo_id,))
    conn.commit()
    conn.close()

    messagebox.showinfo(_t("cinema.common.success"), "Promo code deactivated")
    self.refresh_promo_list()
