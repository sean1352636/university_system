"""
Cinema Booking System - Analytics

Functions for displaying advanced analytics including revenue forecasts,
top members, and occupancy alerts.
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

def show_analytics_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.analytics.advanced_title"), style="Subtitle.TLabel").pack(pady=10)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        # Revenue forecast
        forecast = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        forecast.pack(fill="x", pady=10)
        tk.Label(forecast, text=_t("cinema.analytics.revenue_forecast"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
        cursor.execute("SELECT SUM(total_amount) FROM bookings b JOIN screenings s ON b.screening_id = s.id WHERE b.status = 'active' AND date(s.show_time) > date('now') AND date(s.show_time) <= date('now', '+7 days')")
        rev = cursor.fetchone()[0] or 0
        tk.Label(forecast, text=f"Advance Sales: \u00a3{rev:.2f}", font=("Helvetica", 14), bg="#ffffff", fg="#27ae60").pack(anchor="w")
        # Top members
        clv = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        clv.pack(fill="x", pady=10)
        tk.Label(clv, text=_t("cinema.analytics.top_members"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
        cursor.execute("SELECT name, total_spent, bookings_count, tier FROM members ORDER BY total_spent DESC LIMIT 10")
        for m in cursor.fetchall():
            tk.Label(clv, text=f"{m[0]} ({m[3]}): \u00a3{m[1]:.2f} ({m[2]} bookings)", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
        # Occupancy alerts
        occ = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        occ.pack(fill="x", pady=10)
        tk.Label(occ, text=_t("cinema.analytics.high_occupancy"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
        cursor.execute("SELECT m.title, s.show_time, COUNT(CASE WHEN seats.status = 'booked' THEN 1 END) as b, COUNT(seats.id) as t FROM screenings s JOIN movies m ON s.movie_id = m.id JOIN seats ON s.id = seats.screening_id WHERE date(s.show_time) >= date('now') GROUP BY s.id HAVING (CAST(b AS FLOAT) / t) >= 0.8 LIMIT 5")
        high = cursor.fetchall()
        if high:
            for h in high:
                pct = (h[2] / h[3] * 100) if h[3] > 0 else 0
                tk.Label(occ, text=f"{h[0]} - {h[1]}: {pct:.0f}%", bg="#ffffff", fg="#ffc107").pack(anchor="w")
        else:
            tk.Label(occ, text=_t("cinema.messages.no_high_occupancy"), bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
    finally:
        conn.close()
