"""
Cinema Booking System - Inventory Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import DB_FILE

def show_inventory_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.inventory.title"), style="Subtitle.TLabel").pack(pady=10)
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text="+ Add Item", style="Success.TButton", command=self.add_inv_item).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.restock"), style="Primary.TButton", command=self.restock_inv).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Item", "Unit", "Stock", "Min", "Cost", "Status")
    self.inv_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
    for col in columns:
        self.inv_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_name, unit, quantity, minimum_threshold, cost_per_unit FROM inventory ORDER BY item_name")
        for row in cursor.fetchall():
            status = "LOW" if row[3] < row[4] else "OK"
            self.inv_tree.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4], f"\u00a3{row[5]:.2f}" if row[5] else "-", status))
    finally:
        conn.close()
    self.inv_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.inv_tree.yview)
    self.inv_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    # Low stock alerts
    alert = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    alert.pack(fill="x", pady=10)
    tk.Label(alert, text=_t("cinema.inventory.low_stock_alerts"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#dc3545").pack(anchor="w")
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT item_name, quantity, minimum_threshold FROM inventory WHERE quantity < minimum_threshold")
        low = cursor.fetchall()
    finally:
        conn.close()
    if low:
        for item, stock, min_l in low:
            tk.Label(alert, text=f"\u26a0 {item}: {stock} (min: {min_l})", bg="#ffffff", fg="#ffc107").pack(anchor="w")
    else:
        tk.Label(alert, text=_t("cinema.status.all_stocked"), bg="#ffffff", fg="#27ae60").pack(anchor="w")

def add_inv_item(self):
    form = tk.Toplevel(self.root)
    form.title("Add Item")
    form.geometry("400x350")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text="Add Item", font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)
    fields = [("Item:*", "name"), ("Unit:*", "unit"), ("Stock:", "stock"), ("Min Level:", "min"), ("Cost:", "cost")]
    entries = {}
    for i, (label, key) in enumerate(fields):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        e = ttk.Entry(frame, width=25)
        e.grid(row=i+1, column=1, pady=5)
        entries[key] = e
    entries['stock'].insert(0, "100")
    entries['min'].insert(0, "20")
    def save():
        if not entries['name'].get().strip() or not entries['unit'].get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Name and unit required")
            return
        try:
            stock = int(entries['stock'].get() or 0)
            min_l = int(entries['min'].get() or 20)
            cost = float(entries['cost'].get() or 0)
        except (ValueError, TypeError):
            stock, min_l, cost = 0, 20, 0
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO inventory (item_name, unit, quantity, minimum_threshold, cost_per_unit) VALUES (?, ?, ?, ?, ?)",
                          (entries['name'].get(), entries['unit'].get(), stock, min_l, cost))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Item added!")
        form.destroy()
        self.show_inventory_page()
    ttk.Button(frame, text=_t("cinema.buttons.add"), style="Success.TButton", command=save).grid(row=len(fields)+1, column=0, columnspan=2, pady=20)

def restock_inv(self):
    selected = self.inv_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select an item")
        return
    item_id = self.inv_tree.item(selected[0])['values'][0]
    item_name = self.inv_tree.item(selected[0])['values'][1]
    dialog = tk.Toplevel(self.root)
    dialog.title("Restock")
    dialog.geometry("300x150")
    dialog.configure(bg="#ecf0f1")
    dialog.transient(self.root)
    dialog.grab_set()
    frame = ttk.Frame(dialog, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text=f"Restock: {item_name}", bg="#ffffff", fg="#333333").pack()
    qty_e = ttk.Entry(frame, width=20)
    qty_e.pack(pady=10)
    def restock():
        try:
            qty = int(qty_e.get())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), "Invalid qty")
            return
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET quantity = quantity + ?, last_updated = ? WHERE id = ?", (qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), f"Added {qty}")
        dialog.destroy()
        self.show_inventory_page()
    ttk.Button(frame, text=_t("cinema.btn.restock"), style="Success.TButton", command=restock).pack()
