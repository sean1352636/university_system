"""
Cinema Booking System - Bookings Page
"""

import tkinter as tk
from tkinter import ttk, messagebox
from university_system.infrastructure.database.db import sqlite3
try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

def show_bookings_page(self):
    """Display bookings search page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.tickets.search_tickets"),
             style="Subtitle.TLabel").pack(pady=10)

    search_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    search_frame.pack(fill="x", pady=10)

    tk.Label(search_frame, text=_t("cinema.booking.customer_email"), bg="#ffffff", fg="#333333").pack(side="left")
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side="left", padx=10)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("Ref", _t("cinema.columns.customer"), "Movie", "Date/Time", "Seats", "Total", "Status")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=130)

    def search():
        for item in tree.get_children():
            tree.delete(item)

        query = search_entry.get().strip()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if query:
            cursor.execute('''
                SELECT b.booking_ref, b.customer_name, m.title, s.show_time,
                       (SELECT COUNT(*) FROM booked_seats WHERE booking_id = b.id),
                       b.total_amount, b.status
                FROM bookings b
                JOIN screenings s ON b.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
                WHERE b.booking_ref LIKE ? OR b.customer_email LIKE ?
                ORDER BY b.booking_time DESC
            ''', (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute('''
                SELECT b.booking_ref, b.customer_name, m.title, s.show_time,
                       (SELECT COUNT(*) FROM booked_seats WHERE booking_id = b.id),
                       b.total_amount, b.status
                FROM bookings b
                JOIN screenings s ON b.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
                ORDER BY b.booking_time DESC LIMIT 50
            ''')

        for row in cursor.fetchall():
            tree.insert("", "end", values=(
                row[0], row[1], row[2][:20], row[3], row[4], f"\u00a3{row[5]:.2f}", row[6].upper()
            ))
        conn.close()

    ttk.Button(search_frame, text=_t("cinema.buttons.search"), style="Primary.TButton", command=search).pack(side="left", padx=5)
    ttk.Button(search_frame, text=_t("cinema.buttons.show_all"), style="Secondary.TButton",
              command=lambda: (search_entry.delete(0, tk.END), search())).pack(side="left", padx=5)

    tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Print ticket button
    def print_selected():
        selected = tree.selection()
        if selected:
            ref = tree.item(selected[0])['values'][0]
            self.print_ticket(ref)

    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.tickets.print_ticket"), style="Primary.TButton",
              command=print_selected).pack(side="left", padx=5)

    search()
