"""
Cinema Booking System - Seat Heatmap
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_heatmap_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.analytics.seat_heatmap"), style="Subtitle.TLabel").pack(pady=10)

    # Get seat booking frequency
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.row || s.seat_number as seat_name
            FROM booked_seats bs
            JOIN seats s ON bs.seat_id = s.id
            JOIN bookings b ON bs.booking_id = b.id
            WHERE b.status = 'active' OR b.payment_status = 'paid'
        """)
        bookings = cursor.fetchall()
    finally:
        conn.close()

    seat_counts = {}
    for booking in bookings:
        seat = booking[0] if booking[0] else None
        if seat:
            seat_counts[seat] = seat_counts.get(seat, 0) + 1

    max_count = max(seat_counts.values()) if seat_counts else 1

    info_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    info_frame.pack(fill="x", pady=10)
    tk.Label(info_frame, text=_t("cinema.analytics.seat_frequency"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    tk.Label(info_frame, text=_t("cinema.analytics.heatmap_legend"),
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    # Create heatmap grid
    heatmap_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=20)
    heatmap_frame.pack(fill="both", expand=True, pady=10)

    canvas = tk.Canvas(heatmap_frame, bg="#ffffff", width=600, height=400, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Draw screen
    canvas.create_rectangle(50, 20, 550, 40, fill="#333333", outline="#555555")
    canvas.create_text(300, 30, text=_t("cinema.labels.screen"), fill="white", font=("Helvetica", 10))

    # Draw seat grid (10 rows x 15 cols)
    rows = "ABCDEFGHIJ"
    cols = range(1, 16)
    seat_width = 35
    seat_height = 30
    start_x = 50
    start_y = 60

    for ri, row in enumerate(rows):
        # Row label
        canvas.create_text(start_x - 20, start_y + ri * seat_height + seat_height // 2,
                         text=row, fill="white", font=("Helvetica", 9))

        for ci, col in enumerate(cols):
            seat_id = f"{row}{col}"
            count = seat_counts.get(seat_id, 0)

            # Calculate color based on count
            if count == 0:
                color = "#444444"  # Gray - never booked
            elif count < max_count * 0.3:
                color = "#2d5a27"  # Dark green - low
            elif count < max_count * 0.6:
                color = "#4ecca3"  # Green - medium
            elif count < max_count * 0.8:
                color = "#f4a261"  # Orange - high
            else:
                color = "#e94560"  # Red - very high

            x1 = start_x + ci * seat_width
            y1 = start_y + ri * seat_height
            x2 = x1 + seat_width - 3
            y2 = y1 + seat_height - 3

            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#1a1a2e")
            canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=str(count),
                             fill="white", font=("Helvetica", 7))

    # Legend
    legend_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    legend_frame.pack(fill="x", pady=10)

    colors = [("#444444", "0"), ("#2d5a27", "Low"), ("#4ecca3", "Medium"),
             ("#f4a261", "High"), ("#e94560", "Very High")]
    for color, label in colors:
        f = ttk.Frame(legend_frame, style="Main.TFrame")
        f.pack(side="left", padx=10)
        tk.Canvas(f, width=20, height=20, bg=color, highlightthickness=1).pack(side="left")
        tk.Label(f, text=label, bg="#ecf0f1", fg="#333333").pack(side="left", padx=5)

    # Top seats
    stats_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    stats_frame.pack(fill="x", pady=10)
    tk.Label(stats_frame, text=_t("cinema.analytics.top_seats"), font=("Helvetica", 11, "bold"),
            bg="#ffffff", fg="#27ae60").pack(anchor="w")

    top_seats = sorted(seat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_seats:
        seats_text = ", ".join([f"{s[0]} ({s[1]} bookings)" for s in top_seats])
        tk.Label(stats_frame, text=seats_text, bg="#ffffff", fg="#7f8c8d", wraplength=550).pack(anchor="w")
    else:
        tk.Label(stats_frame, text=_t("cinema.messages.no_booking_data"), bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
