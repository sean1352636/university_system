"""
Cinema Booking System - Screen Maintenance
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime, timedelta

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE


def show_maintenance_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.maintenance.screen"), style="Subtitle.TLabel").pack(pady=10)
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.add_schedule"), style="Success.TButton", command=self.schedule_maint).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Screen", "Type", "Start", "End", "Technician", "Status")
    self.maint_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.maint_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screen_maintenance ORDER BY start_datetime DESC")
    for row in cursor.fetchall():
        self.maint_tree.insert("", "end", values=(row[0], f"Screen {row[1]}", row[2], row[4], row[5] or "-", row[6] or "-", row[8].upper()))
    conn.close()
    self.maint_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.maint_tree.yview)
    self.maint_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.btn.mark_complete"), style="Success.TButton", command=self.complete_maint).pack(side="left", padx=5)


def schedule_maint(self):
    form = tk.Toplevel(self.root)
    form.title("Schedule Maintenance")
    form.geometry("400x350")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.btn.schedule_maintenance"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)
    fields = [("Screen #:", "screen"), ("Type:", "type"), ("Start:", "start"), ("End:", "end"), ("Technician:", "tech")]
    entries = {}
    for i, (label, key) in enumerate(fields):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        e = ttk.Entry(frame, width=25)
        e.grid(row=i+1, column=1, pady=5)
        entries[key] = e
    entries['screen'].insert(0, "1")
    entries['type'].insert(0, "cleaning")
    entries['start'].insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))
    entries['end'].insert(0, (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"))
    def save():
        try:
            screen = int(entries['screen'].get())
        except:
            messagebox.showwarning(_t("cinema.common.warning"), "Invalid screen")
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO screen_maintenance (screen_number, maintenance_type, start_datetime, end_datetime, technician) VALUES (?, ?, ?, ?, ?)",
                      (screen, entries['type'].get(), entries['start'].get(), entries['end'].get(), entries['tech'].get()))
        conn.commit()
        conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Scheduled!")
        form.destroy()
        self.show_maintenance_page()
    ttk.Button(frame, text=_t("cinema.btn.schedule"), style="Success.TButton", command=save).grid(row=len(fields)+1, column=0, columnspan=2, pady=20)


def complete_maint(self):
    selected = self.maint_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a record")
        return
    maint_id = self.maint_tree.item(selected[0])['values'][0]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE screen_maintenance SET status = 'completed', end_datetime = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), maint_id))
    conn.commit()
    conn.close()
    self.show_maintenance_page()
