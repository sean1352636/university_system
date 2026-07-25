"""
Cinema Booking System - Dashboard

Functions for displaying the main dashboard with quick stats,
recent bookings, upcoming screenings, and quick action buttons.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.database import DB_FILE

def show_dashboard(self):
    """Display the dashboard with quick stats."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.dashboard.title", default="Dashboard"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        # Get today's stats
        today = datetime.now().strftime("%Y-%m-%d")

        cursor.execute('''
            SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings WHERE date(booking_time) = ? AND status = 'active'
        ''', (today,))
        today_bookings, today_revenue = cursor.fetchone()

        cursor.execute('''
            SELECT COUNT(*) FROM bookings WHERE status = 'active'
        ''')
        total_active = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM screenings
            WHERE date(show_time) = ? AND (status = 'active' OR status IS NULL)
        ''', (today,))
        today_screenings = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM movies WHERE status = 'active' OR status IS NULL
        ''')
        active_movies = cursor.fetchone()[0]

        # Stats cards
        stats_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
        stats_frame.pack(fill="x", pady=10)

        stats = [
            ("Today's Bookings", today_bookings, "#e94560"),
            ("Today's Revenue", f"\u00a3{today_revenue:.2f}", "#4ecca3"),
            ("Today's Screenings", today_screenings, "#ffa500"),
            ("Active Movies", active_movies, "#45b7d1"),
            ("Total Active Bookings", total_active, "#9b59b6"),
        ]

        for i, (label, value, color) in enumerate(stats):
            card = ttk.Frame(stats_frame, style="Card.TFrame", padding=15)
            card.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")
            stats_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=str(value), font=("Helvetica", 28, "bold"),
                    bg="#ffffff", fg=color).pack()
            tk.Label(card, text=label, font=("Helvetica", 10),
                    bg="#ffffff", fg="#7f8c8d").pack()

        # Recent bookings
        recent_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        recent_frame.pack(fill="x", pady=10)

        tk.Label(recent_frame, text=_t("cinema.dashboard.recent_activity", default="Recent Bookings"), font=("Helvetica", 14, "bold"),
                bg="#ffffff", fg="#e74c3c").pack(anchor="w")

        columns = ("Ref", _t("cinema.columns.customer"), "Movie", "Time", "Amount", "Status")
        tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        cursor.execute('''
            SELECT b.booking_ref, b.customer_name, m.title, s.show_time, b.total_amount, b.status
            FROM bookings b
            JOIN screenings s ON b.screening_id = s.id
            JOIN movies m ON s.movie_id = m.id
            ORDER BY b.booking_time DESC LIMIT 10
        ''')

        for row in cursor.fetchall():
            tree.insert("", "end", values=(
                row[0], row[1], row[2][:20], row[3], f"\u00a3{row[4]:.2f}", row[5].upper()
            ))

        tree.pack(fill="x", pady=10)

        # Upcoming screenings
        upcoming_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        upcoming_frame.pack(fill="x", pady=10)

        tk.Label(upcoming_frame, text=_t("cinema.dashboard.todays_screenings", default="Today's Upcoming Screenings"), font=("Helvetica", 14, "bold"),
                bg="#ffffff", fg="#e74c3c").pack(anchor="w")

        columns2 = ("Time", "Movie", "Screen", "Available Seats")
        tree2 = ttk.Treeview(upcoming_frame, columns=columns2, show="headings", height=6)

        for col in columns2:
            tree2.heading(col, text=col)

        cursor.execute('''
            SELECT s.show_time, m.title, s.screen_number,
                   (SELECT COUNT(*) FROM seats WHERE screening_id = s.id AND status = 'available')
            FROM screenings s
            JOIN movies m ON s.movie_id = m.id
            WHERE date(s.show_time) = ? AND s.show_time >= datetime('now')
            AND (s.status = 'active' OR s.status IS NULL)
            ORDER BY s.show_time LIMIT 10
        ''', (today,))

        for row in cursor.fetchall():
            tree2.insert("", "end", values=(
                row[0].split(' ')[1] if ' ' in row[0] else row[0],
                row[1][:25], f"Screen {row[2]}", f"{row[3]} seats"
            ))

        tree2.pack(fill="x", pady=10)

    finally:
        conn.close()

    # Quick actions
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.booking.new_booking", default="+ New Booking"), style="Success.TButton",
              command=self.show_movies_page).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.movies.add_movie", default="+ Add Movie"), style="Primary.TButton",
              command=lambda: (self.show_movie_management(), self.root.after(100, self.show_add_movie_form))).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.screenings.add_screening", default="+ Add Screening"), style="Secondary.TButton",
              command=self.show_screening_management).pack(side="left", padx=5)
