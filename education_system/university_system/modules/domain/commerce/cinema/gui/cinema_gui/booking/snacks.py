"""
Cinema Booking System - Snacks Ordering

Functions for displaying the snacks ordering page during booking,
updating snack totals, showing standalone snacks menu, and creating
standalone snack orders.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
import random
import string

# i18n support
try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE
from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import SNACKS_MENU, SNACK_DIETARY, SNACK_COMBOS

def show_snacks_page(self, screening, movie):
    """Display snacks ordering page."""
    if not self.selected_seats:
        messagebox.showwarning(_t("cinema.common.warning", default="Warning"), _t("cinema.messages.warnings.select_seat", default="Please select at least one seat"))
        return

    self.clear_content()
    self.selected_snacks = {}

    subtotal = sum(price for _, price in self.ticket_types.values())

    ttk.Label(self.content_frame, text=_t("cinema.booking.add_snacks"),
             style="Subtitle.TLabel").pack(pady=10)

    # Booking summary
    summary_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    summary_frame.pack(fill="x", pady=10)

    tk.Label(summary_frame, text=f"Movie: {movie[1]}", font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    tk.Label(summary_frame, text=f"Date/Time: {screening[3]}",
            bg="#ffffff", fg="#333333").pack(anchor="w")
    tk.Label(summary_frame, text=f"Tickets: {len(self.selected_seats)} | Subtotal: £{subtotal:.2f}",
            bg="#ffffff", fg="#27ae60").pack(anchor="w")

    # Snacks grid
    snacks_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    snacks_frame.pack(fill="x", pady=10)

    tk.Label(snacks_frame, text=_t("cinema.snacks.snacks_beverages"), font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#333333").pack(anchor="w", pady=(0, 10))

    self.snack_vars = {}
    snack_grid = ttk.Frame(snacks_frame, style="Card.TFrame")
    snack_grid.pack(fill="x")

    for i, (item, price) in enumerate(SNACKS_MENU.items()):
        row = i // 2
        col = i % 2

        item_frame = ttk.Frame(snack_grid, style="Card.TFrame")
        item_frame.grid(row=row, column=col, padx=10, pady=5, sticky="w")

        tk.Label(item_frame, text=f"{item} - £{price:.2f}",
                bg="#ffffff", fg="#333333").pack(side="left")

        var = tk.IntVar(value=0)
        self.snack_vars[item] = var

        spinbox = ttk.Spinbox(item_frame, from_=0, to=10, width=5, textvariable=var,
                              command=lambda: self.update_snacks_total())
        spinbox.pack(side="left", padx=10)

    # Snacks total
    self.snacks_total_label = tk.Label(snacks_frame, text=_t("cinema.labels.snacks_total_zero"),
                                       font=("Helvetica", 11), bg="#ffffff", fg="#27ae60")
    self.snacks_total_label.pack(anchor="w", pady=10)

    # Navigation buttons
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(pady=10)

    ttk.Button(btn_frame, text="← " + _t("cinema.booking.back_to_seats"), style="Secondary.TButton",
              command=lambda: self.show_seat_selection(screening[0], movie)).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.snacks.skip"), style="Secondary.TButton",
              command=lambda: self.show_payment_page(screening, movie)).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.booking.continue_to_payment_arrow"), style="Primary.TButton",
              command=lambda: self.show_payment_page(screening, movie)).pack(side="left", padx=5)

def update_snacks_total(self):
    """Update snacks total display."""
    total = 0
    for item, var in self.snack_vars.items():
        qty = var.get()
        if qty > 0:
            self.selected_snacks[item] = qty
            total += SNACKS_MENU[item] * qty
        elif item in self.selected_snacks:
            del self.selected_snacks[item]

    self.snacks_total_label.config(text=f"Snacks Total: £{total:.2f}")

def show_snacks_only_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.snacks.title"), style="Subtitle.TLabel").pack(pady=10)
    menu_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    menu_frame.pack(fill="x", pady=10)
    tk.Label(menu_frame, text=_t("cinema.menu.title"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    for item, price in SNACKS_MENU.items():
        dietary = SNACK_DIETARY.get(item, [])
        dietary_str = f" ({', '.join(dietary)})" if dietary else ""
        tk.Label(menu_frame, text=f"{item}: £{price:.2f}{dietary_str}", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
    tk.Label(menu_frame, text=_t("cinema.labels.combo_deals"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#27ae60").pack(anchor="w", pady=(10, 0))
    for combo, info in SNACK_COMBOS.items():
        tk.Label(menu_frame, text=f"{combo}: £{info['price']:.2f} (Save £{info['savings']:.2f})", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.new_snack_order"), style="Success.TButton", command=self.create_snack_order).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("Ref", _t("cinema.columns.customer"), "Items", "Total", "Status")
    self.snack_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    for col in columns:
        self.snack_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE source_type = 'snack' ORDER BY order_date DESC LIMIT 50")
        for row in cursor.fetchall():
            # id, source_type, source_order_id, student_id, customer_name, order_date, total_amount, payment_method, age_verified, order_status, notes
            notes = row[10] or ""
            items_display = notes[:30] + "..." if len(notes) > 30 else notes
            self.snack_tree.insert("", "end", values=(row[2] or row[0], row[4] or "-", items_display, f"£{row[6]:.2f}", (row[9] or "pending").upper()))
    finally:
        conn.close()
    self.snack_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.snack_tree.yview)
    self.snack_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

def create_snack_order(self):
    form = tk.Toplevel(self.root)
    form.title("New Snack Order")
    form.geometry("400x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.snacks.order"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)
    tk.Label(frame, text=_t("cinema.labels.customer_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    name_e = ttk.Entry(frame, width=35)
    name_e.pack(pady=5)
    tk.Label(frame, text="Select Items:", bg="#ffffff", fg="#333333").pack(anchor="w")
    item_vars = {}
    for item in list(SNACKS_MENU.keys())[:6]:
        var = tk.IntVar(value=0)
        item_vars[item] = var
        f = ttk.Frame(frame, style="Card.TFrame")
        f.pack(fill="x")
        tk.Checkbutton(f, text=item, variable=var, bg="#ffffff", fg="#333333", selectcolor="#0f3460").pack(side="left")
    def order():
        items = {item: 1 for item, var in item_vars.items() if var.get()}
        if not items:
            messagebox.showwarning(_t("cinema.common.warning"), "Select items")
            return
        total = sum(SNACKS_MENU[item] for item in items.keys())
        items_str = ", ".join(items.keys())
        ref = 'SNK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orders (source_type, source_order_id, customer_name, total_amount, order_status, notes, order_number) VALUES ('snack', NULL, ?, ?, 'pending', ?, ?)",
                          (name_e.get().strip(), total, items_str, ref))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.booking.order_created"), f"Ref: {ref}\nTotal: £{total:.2f}")
        form.destroy()
        self.show_snacks_only_page()
    ttk.Button(frame, text=_t("cinema.btn.create_order"), style="Success.TButton", command=order).pack(pady=20)
