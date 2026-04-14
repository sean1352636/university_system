"""
Cinema Booking System - Occupancy Dashboard
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

def show_occupancy_dashboard(self):
    """Display real-time screen occupancy dashboard."""
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.dashboard.realtime_occupancy"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    # Auto-refresh control
    control_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    control_frame.pack(fill="x", pady=5)

    self.auto_refresh_var = getattr(self, 'auto_refresh_var', tk.BooleanVar(value=False))
    ttk.Checkbutton(control_frame, text=_t("cinema.labels.auto_refresh"), variable=self.auto_refresh_var,
                   command=self.toggle_occupancy_refresh).pack(side="left")
    ttk.Button(control_frame, text=_t("cinema.btn.refresh_now"), style="Primary.TButton",
              command=self.refresh_occupancy_display).pack(side="left", padx=10)

    # Current time
    time_label = tk.Label(control_frame, text=f"Updated: {datetime.now().strftime('%H:%M:%S')}",
                         bg="#ecf0f1", fg="#27ae60")
    time_label.pack(side="right")
    self.occupancy_time_label = time_label

    # Get today's screenings data
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get all screens (1-5)
    screens_data = {}
    for screen_num in range(1, 6):
        # Get current/next screening for this screen
        cursor.execute('''
            SELECT s.id, m.title, s.show_time, s.price
            FROM screenings s
            JOIN movies m ON s.movie_id = m.id
            WHERE s.screen_number = ?
            AND date(s.show_time) = ?
            AND (s.status = 'active' OR s.status IS NULL)
            ORDER BY s.show_time
        ''', (screen_num, today))
        screenings = cursor.fetchall()

        # Find current or next screening
        now = datetime.now()
        current_screening = None
        for scr in screenings:
            try:
                show_time = datetime.strptime(scr[2], "%Y-%m-%d %H:%M")
                end_time = show_time + timedelta(hours=2)  # Assume 2 hour slot
                if show_time <= now <= end_time:
                    current_screening = scr
                    break
                elif show_time > now and not current_screening:
                    current_screening = scr
            except (ValueError, TypeError):
                pass

        if current_screening:
            # Get seat counts
            cursor.execute("SELECT COUNT(*) FROM seats WHERE screening_id = ?", (current_screening[0],))
            total_seats = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM seats s
                JOIN booked_seats bs ON s.id = bs.seat_id
                WHERE s.screening_id = ?
            ''', (current_screening[0],))
            booked_seats = cursor.fetchone()[0]

            screens_data[screen_num] = {
                'screening_id': current_screening[0],
                'movie': current_screening[1],
                'time': current_screening[2],
                'total': total_seats,
                'booked': booked_seats,
                'occupancy': (booked_seats / total_seats * 100) if total_seats > 0 else 0
            }
        else:
            screens_data[screen_num] = None

    conn.close()

    # Display screens grid
    screens_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    screens_frame.pack(fill="both", expand=True, pady=10)

    for i, screen_num in enumerate(range(1, 6)):
        screen_frame = ttk.Frame(screens_frame, style="Card.TFrame", padding=10)
        screen_frame.grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nsew")

        tk.Label(screen_frame, text=f"Screen {screen_num}", font=("Helvetica", 14, "bold"),
                bg="#ffffff", fg="#e74c3c").pack()

        data = screens_data.get(screen_num)
        if data:
            # Movie info
            tk.Label(screen_frame, text=data['movie'][:20], bg="#ffffff", fg="#333333",
                    font=("Helvetica", 10)).pack()

            try:
                show_time = datetime.strptime(data['time'], "%Y-%m-%d %H:%M")
                tk.Label(screen_frame, text=show_time.strftime("%H:%M"), bg="#ffffff", fg="#7f8c8d").pack()
            except (ValueError, TypeError):
                pass

            # Occupancy bar
            bar_frame = tk.Frame(screen_frame, bg="#ffffff")
            bar_frame.pack(fill="x", pady=10)

            occupancy = data['occupancy']
            if occupancy < 50:
                bar_color = "#4ecca3"  # Green
            elif occupancy < 80:
                bar_color = "#f4a261"  # Yellow
            else:
                bar_color = "#e94560"  # Red

            bar_canvas = tk.Canvas(bar_frame, width=150, height=25, bg="#333333", highlightthickness=0)
            bar_canvas.pack()
            bar_width = int(150 * occupancy / 100)
            bar_canvas.create_rectangle(0, 0, bar_width, 25, fill=bar_color, outline="")
            bar_canvas.create_text(75, 12, text=f"{occupancy:.1f}%", fill="white", font=("Helvetica", 10, "bold"))

            # Seat count
            tk.Label(screen_frame, text=f"{data['booked']}/{data['total']} seats",
                    bg="#ffffff", fg="#7f8c8d").pack()

            # View seats button
            ttk.Button(screen_frame, text=_t("cinema.btn.view_seats"), style="Secondary.TButton",
                      command=lambda sid=data['screening_id']: self.show_occupancy_seat_map(sid)).pack(pady=5)
        else:
            tk.Label(screen_frame, text=_t("cinema.messages.no_active_screening"), bg="#ffffff", fg="#666666",
                    font=("Helvetica", 10)).pack(pady=20)

    for i in range(3):
        screens_frame.columnconfigure(i, weight=1)

    # Summary stats
    summary_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    summary_frame.pack(fill="x", pady=10)

    total_booked = sum(d['booked'] for d in screens_data.values() if d)
    total_capacity = sum(d['total'] for d in screens_data.values() if d)
    active_screens = sum(1 for d in screens_data.values() if d)

    overall_occupancy = (total_booked / total_capacity * 100) if total_capacity > 0 else 0

    tk.Label(summary_frame, text=f"Overall: {overall_occupancy:.1f}% ({total_booked}/{total_capacity} seats) | "
                                 f"Active Screens: {active_screens}/5",
            bg="#ffffff", fg="#27ae60", font=("Helvetica", 11)).pack()

def toggle_occupancy_refresh(self):
    """Toggle auto-refresh for occupancy dashboard."""
    if self.auto_refresh_var.get():
        self.schedule_occupancy_refresh()
    else:
        if hasattr(self, 'occupancy_refresh_id'):
            self.root.after_cancel(self.occupancy_refresh_id)

def schedule_occupancy_refresh(self):
    """Schedule next occupancy refresh."""
    if self.auto_refresh_var.get():
        self.refresh_occupancy_display()
        self.occupancy_refresh_id = self.root.after(5000, self.schedule_occupancy_refresh)

def refresh_occupancy_display(self):
    """Refresh the occupancy display."""
    self.show_occupancy_dashboard()

def show_occupancy_seat_map(self, screening_id):
    """Show seat map for a specific screening."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT m.title, s.screen_number, s.show_time
        FROM screenings s
        JOIN movies m ON s.movie_id = m.id
        WHERE s.id = ?
    ''', (screening_id,))
    screening_info = cursor.fetchone()

    if not screening_info:
        conn.close()
        return

    cursor.execute('''
        SELECT s.row, s.seat_number, s.status,
               CASE WHEN bs.id IS NOT NULL THEN 1 ELSE 0 END as is_booked
        FROM seats s
        LEFT JOIN booked_seats bs ON s.id = bs.seat_id
        WHERE s.screening_id = ?
        ORDER BY s.row, s.seat_number
    ''', (screening_id,))
    seats = cursor.fetchall()
    conn.close()

    form = tk.Toplevel(self.root)
    form.title(f"Seat Map - {screening_info[0]}")
    form.geometry("600x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=f"{screening_info[0]} - Screen {screening_info[1]}",
            font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack()
    tk.Label(frame, text=f"Showtime: {screening_info[2]}", bg="#ffffff", fg="#7f8c8d").pack()

    # Screen indicator
    tk.Label(frame, text=_t("cinema.labels.screen_bracket"), bg="#333333", fg="white", font=("Courier", 10)).pack(pady=10)

    # Seat map
    seat_canvas = tk.Canvas(frame, bg="#ffffff", width=500, height=250, highlightthickness=0)
    seat_canvas.pack(pady=10)

    rows = {}
    for seat in seats:
        row, num, status, is_booked = seat
        if row not in rows:
            rows[row] = []
        rows[row].append((num, status, is_booked))

    y_offset = 10
    for row in sorted(rows.keys()):
        seat_canvas.create_text(15, y_offset + 10, text=row, fill="white", font=("Helvetica", 9))
        x_offset = 30
        for num, status, is_booked in sorted(rows[row], key=lambda x: x[0]):
            if is_booked:
                color = "#e94560"  # Red - booked
            else:
                color = "#4ecca3"  # Green - available

            seat_canvas.create_rectangle(x_offset, y_offset, x_offset + 25, y_offset + 20,
                                        fill=color, outline="#1a1a2e")
            seat_canvas.create_text(x_offset + 12, y_offset + 10, text=str(num),
                                   fill="white", font=("Helvetica", 7))
            x_offset += 30
        y_offset += 28

    # Legend
    legend_frame = ttk.Frame(frame, style="Card.TFrame")
    legend_frame.pack(pady=10)
    tk.Canvas(legend_frame, width=15, height=15, bg="#4ecca3", highlightthickness=0).pack(side="left")
    tk.Label(legend_frame, text=_t("cinema.status.available"), bg="#ffffff", fg="#333333").pack(side="left", padx=(5, 20))
    tk.Canvas(legend_frame, width=15, height=15, bg="#e94560", highlightthickness=0).pack(side="left")
    tk.Label(legend_frame, text=_t("cinema.status.booked"), bg="#ffffff", fg="#333333").pack(side="left", padx=5)
