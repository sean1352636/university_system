"""
Cinema Booking System - Seat Selection

Functions for displaying the seat selection grid with ticket types
and toggling individual seat selections.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.database import DB_FILE
from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.constants import TICKET_TYPES

def show_seat_selection(self, screening_id, movie):
    """Display seat selection grid with ticket types."""
    self.clear_content()
    self.selected_seats = []
    self.ticket_types = {}
    self.current_screening = screening_id

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM screenings WHERE id = ?", (screening_id,))
        screening = cursor.fetchone()
        cursor.execute("SELECT * FROM seats WHERE screening_id = ?", (screening_id,))
        seats = cursor.fetchall()
    finally:
        conn.close()

    ttk.Button(self.content_frame, text=_t("cinema.buttons.back"), style="Secondary.TButton",
              command=lambda: self.show_screenings(movie)).pack(anchor="w")

    info_text = f"{movie[1]} | Screen {screening[2]} | {screening[3]} | Base: £{screening[4]:.2f}"
    ttk.Label(self.content_frame, text=info_text, style="Subtitle.TLabel").pack(pady=10)

    # Ticket type selector
    type_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    type_frame.pack(fill="x", pady=5)

    tk.Label(type_frame, text=_t("cinema.booking.ticket_type_label"), bg="#ffffff", fg="#333333").pack(side="left")
    self.ticket_type_var = tk.StringVar(value="Adult")
    type_combo = ttk.Combobox(type_frame, textvariable=self.ticket_type_var, width=15,
                              values=list(TICKET_TYPES.keys()))
    type_combo.pack(side="left", padx=10)

    # Show pricing
    pricing_text = " | ".join([f"{t}: £{screening[4] * m:.2f}" for t, m in TICKET_TYPES.items()])
    tk.Label(type_frame, text=pricing_text, bg="#ffffff", fg="#27ae60").pack(side="left", padx=20)

    # Screen indicator
    screen_label = tk.Label(self.content_frame, text=_t("cinema.booking.screen_label"),
                           font=("Helvetica", 12), bg="#ecf0f1", fg="#e74c3c")
    screen_label.pack(pady=20)

    # Seat grid
    seats_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    seats_frame.pack()

    self.seat_buttons = {}
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

    for row_idx, row in enumerate(rows):
        row_frame = ttk.Frame(seats_frame, style="Main.TFrame")
        row_frame.pack()

        tk.Label(row_frame, text=row, font=("Helvetica", 10, "bold"),
                bg="#ecf0f1", fg="#333333", width=3).pack(side="left")

        for seat_num in range(1, 13):
            seat_data = next((s for s in seats if s[2] == row and s[3] == seat_num), None)
            if seat_data:
                btn = tk.Button(row_frame, text=str(seat_num), width=3, height=1,
                               font=("Helvetica", 9))

                # VIP seats have gold border
                is_vip = len(seat_data) > 4 and seat_data[4] == 'vip'

                if seat_data[5 if len(seat_data) > 5 else 4] == 'available':
                    bg_color = "#ffd700" if is_vip else "#0f3460"
                    btn.configure(bg=bg_color, fg="white" if not is_vip else "black",
                                 activebackground="#e94560")
                    btn.configure(command=lambda s=seat_data, b=btn, v=is_vip: self.toggle_seat(s, b, screening[4], v))
                elif seat_data[5 if len(seat_data) > 5 else 4] == 'reserved':
                    btn.configure(bg="#ffa500", fg="white", state="disabled")
                else:
                    btn.configure(bg="#555555", fg="white", state="disabled")

                btn.pack(side="left", padx=2, pady=2)
                self.seat_buttons[seat_data[0]] = btn

        tk.Label(row_frame, text=row, font=("Helvetica", 10, "bold"),
                bg="#ecf0f1", fg="#333333", width=3).pack(side="left")

    # Legend
    legend_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    legend_frame.pack(pady=20)

    for color, text in [("#0f3460", "Standard"), ("#ffd700", "VIP"), ("#e94560", "Selected"),
                       ("#ffa500", "Reserved"), ("#555555", "Booked")]:
        tk.Label(legend_frame, text=_t("cinema.labels.unavailable_marker"), font=("Helvetica", 10),
                bg="#ecf0f1", fg=color).pack(side="left", padx=5)
        tk.Label(legend_frame, text=text, font=("Helvetica", 10),
                bg="#ecf0f1", fg="#333333").pack(side="left", padx=(0, 15))

    self.selection_label = tk.Label(self.content_frame, text=_t("cinema.booking.no_seats_selected"),
                                    font=("Helvetica", 12), bg="#ecf0f1", fg="#333333")
    self.selection_label.pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(pady=10)

    ttk.Button(btn_frame, text=_t("cinema.booking.proceed_payment") + " →", style="Primary.TButton",
              command=lambda: self.show_snacks_page(screening, movie)).pack(side="left", padx=5)

def toggle_seat(self, seat_data, button, base_price, is_vip):
    """Toggle seat selection with ticket type."""
    seat_id = seat_data[0]
    ticket_type = self.ticket_type_var.get()
    multiplier = TICKET_TYPES.get(ticket_type, 1.0)
    vip_surcharge = 5.0 if is_vip else 0

    if seat_id in self.selected_seats:
        self.selected_seats.remove(seat_id)
        del self.ticket_types[seat_id]
        bg_color = "#ffd700" if is_vip else "#0f3460"
        button.configure(bg=bg_color)
    else:
        self.selected_seats.append(seat_id)
        self.ticket_types[seat_id] = (ticket_type, base_price * multiplier + vip_surcharge)
        button.configure(bg="#e94560")

    total = sum(price for _, price in self.ticket_types.values())
    types_summary = {}
    for t, _ in self.ticket_types.values():
        types_summary[t] = types_summary.get(t, 0) + 1

    summary = ", ".join([f"{c}x {t}" for t, c in types_summary.items()])
    self.selection_label.config(
        text=f"Selected: {len(self.selected_seats)} seats ({summary}) | Total: £{total:.2f}"
    )
