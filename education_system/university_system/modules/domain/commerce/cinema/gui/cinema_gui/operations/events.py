"""
Cinema Booking System - Special Events
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

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_events_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.events.special"), style="Subtitle.TLabel").pack(pady=10)
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.create_event"), style="Success.TButton", command=self.create_event).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Name", "Type", "Date", "Screen", "Price", "Capacity", "Sold", "Status")
    self.event_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.event_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM special_events ORDER BY event_date DESC")
        for row in cursor.fetchall():
            self.event_tree.insert("", "end", values=(row[0], row[1], row[2], row[4], row[7] or "-", f"\u00a3{row[9]:.2f}" if row[9] else "-", row[10] or "-", row[11], row[13].upper()))
    finally:
        conn.close()
    self.event_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.event_tree.yview)
    self.event_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

def create_event(self):
    form = tk.Toplevel(self.root)
    form.title("Create Event")
    form.geometry("450x450")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.events.create"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)
    fields = [("Name:*", "name"), ("Type:", "type"), ("Date:*", "date"), ("Time:*", "time"), ("Screen:", "screen"), ("Price:", "price"), ("Capacity:", "cap")]
    entries = {}
    for i, (label, key) in enumerate(fields):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        e = ttk.Entry(frame, width=30)
        e.grid(row=i+1, column=1, pady=5)
        entries[key] = e
    entries['date'].insert(0, datetime.now().strftime("%Y-%m-%d"))
    entries['time'].insert(0, "19:00")
    entries['screen'].insert(0, "1")
    entries['price'].insert(0, "25.00")
    entries['cap'].insert(0, "150")
    entries['type'].insert(0, "premiere")
    def save():
        if not entries['name'].get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Name required")
            return
        try:
            price = float(entries['price'].get() or 25)
            cap = int(entries['cap'].get() or 150)
            screen = int(entries['screen'].get() or 1)
        except (ValueError, TypeError):
            price, cap, screen = 25, 150, 1
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO special_events (name, event_type, event_date, start_time, screen_number, ticket_price, max_capacity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (entries['name'].get(), entries['type'].get(), entries['date'].get(), entries['time'].get(), screen, price, cap))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Event created!")
        form.destroy()
        self.show_events_page()
    ttk.Button(frame, text=_t("cinema.btn.create"), style="Success.TButton", command=save).grid(row=len(fields)+1, column=0, columnspan=2, pady=20)
