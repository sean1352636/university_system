"""
Cinema Booking System - Waitlist Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_waitlist_page(self):
    """Display waitlist management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.waiting_list.title"),
             style="Subtitle.TLabel").pack(pady=10)

    # Filter frame
    filter_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    filter_frame.pack(fill="x", pady=10)

    tk.Label(filter_frame, text=_t("cinema.labels.filter_by_status"), bg="#ffffff", fg="#333333").pack(side="left")
    status_var = tk.StringVar(value="waiting")
    status_combo = ttk.Combobox(filter_frame, textvariable=status_var, width=15,
                                values=["all", "waiting", "notified", "fulfilled", "expired"])
    status_combo.pack(side="left", padx=10)

    # Waitlist entries
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Movie", "Screening", _t("cinema.columns.customer"), "Email", "Seats", "Created", "Status")
    self.waitlist_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        self.waitlist_tree.heading(col, text=col)
    self.waitlist_tree.column("ID", width=50)
    self.waitlist_tree.column("Movie", width=150)
    self.waitlist_tree.column("Screening", width=130)
    self.waitlist_tree.column(_t("cinema.columns.customer"), width=120)
    self.waitlist_tree.column("Email", width=150)
    self.waitlist_tree.column("Seats", width=60)
    self.waitlist_tree.column("Created", width=100)
    self.waitlist_tree.column("Status", width=80)

    def load_waitlist():
        for item in self.waitlist_tree.get_children():
            self.waitlist_tree.delete(item)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            status = status_var.get()
            sql = '''
                SELECT w.id, m.title, s.show_time, w.customer_name, w.customer_email,
                       w.seats_wanted, w.created_at, w.status
                FROM waitlist w
                JOIN screenings s ON w.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
            '''
            params = []
            if status != "all":
                sql += " WHERE w.status = ?"
                params.append(status)
            sql += " ORDER BY w.created_at DESC"

            cursor.execute(sql, params)
            for row in cursor.fetchall():
                self.waitlist_tree.insert("", "end", values=(
                    row[0], row[1][:20], row[2], row[3], row[4],
                    row[5], row[6][:10] if row[6] else "-", row[7].upper()
                ))
        finally:
            conn.close()

    ttk.Button(filter_frame, text=_t("cinema.btn.filter"), style="Primary.TButton",
              command=load_waitlist).pack(side="left", padx=5)

    self.waitlist_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.waitlist_tree.yview)
    self.waitlist_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.waitlist.notify_customer"), style="Success.TButton",
              command=self.notify_waitlist_customer).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.waiting_list.mark_fulfilled"), style="Primary.TButton",
              command=self.mark_waitlist_fulfilled).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.remove_entry"), style="Danger.TButton",
              command=self.remove_waitlist_entry).pack(side="left", padx=5)

    load_waitlist()

def notify_waitlist_customer(self):
    """Mark waitlist entry as notified."""
    selected = self.waitlist_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a waitlist entry")
        return

    entry_id = self.waitlist_tree.item(selected[0])['values'][0]
    email = self.waitlist_tree.item(selected[0])['values'][4]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE waitlist SET status = 'notified', notified = 1 WHERE id = ?", (entry_id,))
        conn.commit()
    finally:
        conn.close()

    messagebox.showinfo(_t("cinema.common.notified"), f"Customer {email} has been marked as notified.\n\n(In a real system, an email would be sent)")
    self.show_waitlist_page()

def mark_waitlist_fulfilled(self):
    """Mark waitlist entry as fulfilled."""
    selected = self.waitlist_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a waitlist entry")
        return

    entry_id = self.waitlist_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE waitlist SET status = 'fulfilled' WHERE id = ?", (entry_id,))
        conn.commit()
    finally:
        conn.close()

    self.show_waitlist_page()

def remove_waitlist_entry(self):
    """Remove waitlist entry."""
    selected = self.waitlist_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a waitlist entry")
        return

    entry_id = self.waitlist_tree.item(selected[0])['values'][0]

    if not messagebox.askyesno(_t("cinema.common.confirm"), "Remove this waitlist entry?"):
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM waitlist WHERE id = ?", (entry_id,))
        conn.commit()
    finally:
        conn.close()

    self.show_waitlist_page()
