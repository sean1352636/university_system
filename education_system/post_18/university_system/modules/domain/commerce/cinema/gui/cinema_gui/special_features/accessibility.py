"""
Cinema Booking System - Accessibility Features
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import SEAT_TYPES

def show_accessible_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.accessibility.seating_mgmt"), style="Subtitle.TLabel").pack(pady=10)

    info_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    info_frame.pack(fill="x", pady=10)
    tk.Label(info_frame, text=_t("cinema.labels.seat_types_available"), font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w")

    for seat_type, info in SEAT_TYPES.items():
        tk.Label(info_frame, text=f"• {seat_type.replace('_', ' ').title()}: {info['description']} (+\u00a3{info['price_modifier']:.2f})",
                bg="#ffffff", fg="#7f8c8d").pack(anchor="w", pady=2)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.theatre_layout.configure"), style="Primary.TButton",
              command=self.configure_accessible_seats).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.accessibility.view_bookings"), style="Secondary.TButton",
              command=self.view_accessible_bookings).pack(side="left", padx=5)

    # Current accessible seat configuration
    config_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    config_frame.pack(fill="both", expand=True, pady=10)

    tk.Label(config_frame, text=_t("cinema.accessibility.current_layout"), font=("Helvetica", 11, "bold"),
            bg="#ffffff", fg="#27ae60").pack(anchor="w", pady=5)

    canvas = tk.Canvas(config_frame, bg="#ffffff", width=550, height=300, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Draw screen
    canvas.create_rectangle(50, 20, 500, 40, fill="#333333", outline="#555555")
    canvas.create_text(275, 30, text=_t("cinema.labels.screen"), fill="white", font=("Helvetica", 10))

    # Draw seat layout with accessible seats highlighted
    rows = "ABCDEFGH"
    cols = range(1, 13)
    seat_width = 35
    seat_height = 28
    start_x = 50
    start_y = 60

    # Define accessible seat positions
    wheelchair_seats = ["A1", "A2", "A11", "A12", "H1", "H2", "H11", "H12"]
    companion_seats = ["A3", "A10", "H3", "H10"]
    couple_seats = ["H5", "H6", "H7", "H8"]

    for ri, row in enumerate(rows):
        canvas.create_text(start_x - 20, start_y + ri * seat_height + seat_height // 2,
                         text=row, fill="white", font=("Helvetica", 9))

        for ci, col in enumerate(cols):
            seat_id = f"{row}{col}"

            if seat_id in wheelchair_seats:
                color = "#3498db"  # Blue for wheelchair
                symbol = "\u267f"
            elif seat_id in companion_seats:
                color = "#9b59b6"  # Purple for companion
                symbol = "+"
            elif seat_id in couple_seats:
                color = "#e91e63"  # Pink for couple
                symbol = "\u2665"
            else:
                color = "#2d5a27"  # Green for regular
                symbol = ""

            x1 = start_x + ci * seat_width
            y1 = start_y + ri * seat_height
            x2 = x1 + seat_width - 3
            y2 = y1 + seat_height - 3

            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#1a1a2e")
            if symbol:
                canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=symbol, fill="white", font=("Helvetica", 10))

    # Legend
    legend_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    legend_frame.pack(fill="x", pady=10)

    legends = [("#3498db", "\u267f Wheelchair"), ("#9b59b6", "+ Companion"),
              ("#e91e63", "\u2665 Couple"), ("#2d5a27", "Regular")]
    for color, label in legends:
        f = ttk.Frame(legend_frame, style="Main.TFrame")
        f.pack(side="left", padx=15)
        tk.Canvas(f, width=20, height=20, bg=color, highlightthickness=1).pack(side="left")
        tk.Label(f, text=label, bg="#ecf0f1", fg="#333333").pack(side="left", padx=5)

def configure_accessible_seats(self):
    form = tk.Toplevel(self.root)
    form.title("Configure Accessible Seats")
    form.geometry("400x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.accessibility.seat_config"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=_t("cinema.accessibility.config_types"), font=("Helvetica", 10),
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w", pady=(0, 10))

    tk.Label(frame, text="Wheelchair Seats (comma-separated):", bg="#ffffff", fg="#333333").pack(anchor="w")
    wheel_e = ttk.Entry(frame, width=35)
    wheel_e.insert(0, "A1, A2, A11, A12, H1, H2, H11, H12")
    wheel_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.companion_seats"), bg="#ffffff", fg="#333333").pack(anchor="w")
    comp_e = ttk.Entry(frame, width=35)
    comp_e.insert(0, "A3, A10, H3, H10")
    comp_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.theatre_layout.couple_seats"), bg="#ffffff", fg="#333333").pack(anchor="w")
    couple_e = ttk.Entry(frame, width=35)
    couple_e.insert(0, "H5, H6, H7, H8")
    couple_e.pack(pady=5)

    def parse_seats(seat_string):
        """Parse comma-separated seat list like 'A1, A2, H5' into list"""
        seats = []
        for seat in seat_string.split(','):
            seat = seat.strip().upper()
            if seat and len(seat) >= 2:
                row = seat[0]
                try:
                    num = int(seat[1:])
                    seats.append((row, num))
                except ValueError:
                    pass
        return seats

    def save():
        try:
            wheelchair_seats = parse_seats(wheel_e.get())
            companion_seats = parse_seats(comp_e.get())
            couple_seats = parse_seats(couple_e.get())

            conn = sqlite3.connect(DB_FILE)
            try:
                cursor = conn.cursor()

                # First, reset all special seat flags
                cursor.execute("""
                    UPDATE seats
                    SET is_wheelchair = 0, is_companion = 0, is_couple = 0
                """)

                # Update wheelchair seats
                for row, num in wheelchair_seats:
                    cursor.execute("""
                        UPDATE seats
                        SET is_wheelchair = 1
                        WHERE row = ? AND seat_number = ?
                    """, (row, num))

                # Update companion seats
                for row, num in companion_seats:
                    cursor.execute("""
                        UPDATE seats
                        SET is_companion = 1
                        WHERE row = ? AND seat_number = ?
                    """, (row, num))

                # Update couple seats
                for row, num in couple_seats:
                    cursor.execute("""
                        UPDATE seats
                        SET is_couple = 1
                        WHERE row = ? AND seat_number = ?
                    """, (row, num))

                conn.commit()

                # Get counts for confirmation
                cursor.execute("SELECT COUNT(*) FROM seats WHERE is_wheelchair = 1")
                wheelchair_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM seats WHERE is_companion = 1")
                companion_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM seats WHERE is_couple = 1")
                couple_count = cursor.fetchone()[0]

            finally:
                conn.close()

            messagebox.showinfo(_t("cinema.common.config_saved"),
                f"Accessible seat configuration updated successfully!\n\n"
                f"Wheelchair seats: {wheelchair_count}\n"
                f"Companion seats: {companion_count}\n"
                f"Couple seats: {couple_count}\n\n"
                f"Changes applied to all existing screenings.")
            form.destroy()
            self.show_admin_panel()  # Refresh the admin panel

        except Exception as e:
            messagebox.showerror(_t("cinema.common.error"), f"Failed to save configuration:\n{str(e)}")

    ttk.Button(frame, text=_t("cinema.btn.save_configuration"), style="Success.TButton", command=save).pack(pady=20)

def view_accessible_bookings(self):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        # Query bookings that have wheelchair-accessible seats
        cursor.execute("""
            SELECT DISTINCT b.booking_ref, b.customer_name,
                   GROUP_CONCAT(s.row || s.seat_number, ', ') as seats,
                   sc.show_time
            FROM bookings b
            JOIN booked_seats bs ON bs.booking_id = b.id
            JOIN seats s ON s.id = bs.seat_id
            JOIN screenings sc ON sc.id = b.screening_id
            WHERE b.status = 'confirmed'
              AND (s.is_wheelchair = 1 OR s.row || s.seat_number IN ('A1', 'A2', 'A11', 'A12', 'H1', 'H2', 'H11', 'H12'))
            GROUP BY b.id
            ORDER BY sc.show_time DESC
        """)
        accessible_bookings = cursor.fetchall()
    finally:
        conn.close()

    view_win = tk.Toplevel(self.root)
    view_win.title("Accessible Seat Bookings")
    view_win.geometry("500x400")
    view_win.configure(bg="#ecf0f1")

    tk.Label(view_win, text=_t("cinema.accessible.bookings_count"), font=("Helvetica", 14, "bold"),
            bg="#ecf0f1", fg="#e74c3c").pack(pady=10)

    frame = ttk.Frame(view_win, style="Card.TFrame", padding=10)
    frame.pack(fill="both", expand=True, padx=20, pady=10)

    if accessible_bookings:
        for b in accessible_bookings[:20]:
            show_date = b[3][:10] if b[3] else "-"
            tk.Label(frame, text=f"Ref: {b[0]} | {b[1]} | Seats: {b[2]} | Date: {show_date}",
                    bg="#ffffff", fg="#333333").pack(anchor="w", pady=2)
    else:
        tk.Label(frame, text=_t("cinema.messages.no_accessible_bookings"), bg="#ffffff", fg="#7f8c8d").pack()
