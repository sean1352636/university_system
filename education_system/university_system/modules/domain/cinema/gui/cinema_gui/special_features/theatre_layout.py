"""
Cinema Booking System - Theatre Layout Configuration
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

from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import DB_FILE

def show_theatre_layout_page(self):
    """Display theatre layout configuration page (per-screen)."""
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.layout.title"),
             style="Subtitle.TLabel").pack(pady=10)

    # Info frame
    info_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    info_frame.pack(fill="x", pady=10)
    tk.Label(info_frame, text=_t("cinema.accessibility.config_layout"),
            font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    tk.Label(info_frame, text=_t("cinema.layout.screen_config_help"),
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    # Screen selector
    selector_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    selector_frame.pack(fill="x", pady=10)

    tk.Label(selector_frame, text="Select Screen:", bg="#ffffff", fg="#333333").pack(side="left")
    screen_var = tk.StringVar(value="1")
    screen_combo = ttk.Combobox(selector_frame, textvariable=screen_var, width=10,
                                values=["1", "2", "3", "4", "5", "6", "7", "8"])
    screen_combo.pack(side="left", padx=10)

    # Configuration form
    config_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    config_frame.pack(fill="both", expand=True, pady=10)

    # Fields
    fields = {}

    tk.Label(config_frame, text=_t("cinema.labels.screen_name"), bg="#ffffff", fg="#333333").grid(row=0, column=0, sticky="w", pady=5)
    fields['name'] = ttk.Entry(config_frame, width=30)
    fields['name'].grid(row=0, column=1, pady=5, padx=10, sticky="w")

    tk.Label(config_frame, text=_t("cinema.theatre_layout.num_rows"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    fields['rows'] = ttk.Spinbox(config_frame, from_=4, to=20, width=10)
    fields['rows'].set(8)
    fields['rows'].grid(row=1, column=1, pady=5, padx=10, sticky="w")

    tk.Label(config_frame, text=_t("cinema.labels.seats_per_row"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    fields['seats_per_row'] = ttk.Spinbox(config_frame, from_=6, to=30, width=10)
    fields['seats_per_row'].set(12)
    fields['seats_per_row'].grid(row=2, column=1, pady=5, padx=10, sticky="w")

    tk.Label(config_frame, text="VIP Rows (comma-separated):", bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    fields['vip_rows'] = ttk.Entry(config_frame, width=30)
    fields['vip_rows'].insert(0, "A, B")
    fields['vip_rows'].grid(row=3, column=1, pady=5, padx=10, sticky="w")
    tk.Label(config_frame, text=_t("cinema.placeholders.row_letters"), bg="#ffffff", fg="#7f8c8d").grid(row=3, column=2, sticky="w")

    tk.Label(config_frame, text=_t("cinema.labels.wheelchair_seats"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    fields['wheelchair'] = ttk.Entry(config_frame, width=30)
    fields['wheelchair'].insert(0, "A1, A2, H1, H2")
    fields['wheelchair'].grid(row=4, column=1, pady=5, padx=10, sticky="w")
    tk.Label(config_frame, text=_t("cinema.placeholders.seat_examples"), bg="#ffffff", fg="#7f8c8d").grid(row=4, column=2, sticky="w")

    def load_layout():
        """Load layout for selected screen."""
        screen_num = int(screen_var.get())
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM screen_layouts WHERE screen_number = ?", (screen_num,))
            layout = cursor.fetchone()
        finally:
            conn.close()

        # Clear fields
        fields['name'].delete(0, tk.END)
        fields['rows'].delete(0, tk.END)
        fields['seats_per_row'].delete(0, tk.END)
        fields['vip_rows'].delete(0, tk.END)
        fields['wheelchair'].delete(0, tk.END)

        if layout:
            fields['name'].insert(0, layout[2] or f"Screen {screen_num}")
            fields['rows'].insert(0, str(layout[3]))
            fields['seats_per_row'].insert(0, str(layout[4]))
            fields['vip_rows'].insert(0, layout[5] or "A, B")
            fields['wheelchair'].insert(0, layout[6] or "A1, A2")
        else:
            # Default values
            fields['name'].insert(0, f"Screen {screen_num}")
            fields['rows'].insert(0, "8")
            fields['seats_per_row'].insert(0, "12")
            fields['vip_rows'].insert(0, "A, B")
            fields['wheelchair'].insert(0, "A1, A2, H1, H2")

    def save_layout():
        """Save layout for selected screen."""
        screen_num = int(screen_var.get())
        name = fields['name'].get().strip()
        rows = int(fields['rows'].get())
        seats_per_row = int(fields['seats_per_row'].get())
        vip_rows = fields['vip_rows'].get().strip()
        wheelchair = fields['wheelchair'].get().strip()

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO screen_layouts
                (screen_number, name, rows, seats_per_row, vip_rows, wheelchair_positions, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (screen_num, name, rows, seats_per_row, vip_rows, wheelchair))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), f"Layout saved for Screen {screen_num}")

    screen_combo.bind('<<ComboboxSelected>>', lambda e: load_layout())

    # Button frame
    btn_frame = ttk.Frame(config_frame, style="Card.TFrame")
    btn_frame.grid(row=5, column=0, columnspan=3, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.theatre_layout.load_layout"), style="Secondary.TButton",
              command=load_layout).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.save_layout"), style="Success.TButton",
              command=save_layout).pack(side="left", padx=5)

    # Preview section
    preview_frame = ttk.LabelFrame(config_frame, text=_t("cinema.labels.layout_preview"), padding=10)
    preview_frame.grid(row=6, column=0, columnspan=3, pady=10, sticky="ew")

    preview_canvas = tk.Canvas(preview_frame, bg="#2c3e50", width=500, height=200, highlightthickness=0)
    preview_canvas.pack(fill="both", expand=True)

    def update_preview():
        """Update the seat layout preview."""
        preview_canvas.delete("all")
        try:
            num_rows = int(fields['rows'].get())
            seats_per_row = int(fields['seats_per_row'].get())
            vip_row_str = fields['vip_rows'].get().upper()
            vip_rows_list = [r.strip() for r in vip_row_str.split(',') if r.strip()]
            wheelchair_str = fields['wheelchair'].get().upper()
            wheelchair_list = [s.strip() for s in wheelchair_str.split(',') if s.strip()]
        except (ValueError, TypeError):
            return

        # Draw screen
        preview_canvas.create_rectangle(20, 10, 480, 25, fill="#e74c3c", outline="#c0392b")
        preview_canvas.create_text(250, 17, text=_t("cinema.labels.screen"), fill="white", font=("Helvetica", 8))

        # Calculate seat size
        max_seat_width = 450 // seats_per_row
        max_seat_height = 150 // num_rows
        seat_size = min(max_seat_width, max_seat_height, 25) - 2

        start_y = 35
        row_letters = [chr(65 + i) for i in range(num_rows)]  # A, B, C, ...

        for ri, row_letter in enumerate(row_letters):
            for ci in range(seats_per_row):
                seat_id = f"{row_letter}{ci + 1}"
                x = 20 + ci * (seat_size + 2)
                y = start_y + ri * (seat_size + 2)

                if seat_id in wheelchair_list:
                    color = "#3498db"  # Blue for wheelchair
                elif row_letter in vip_rows_list:
                    color = "#f1c40f"  # Gold for VIP
                else:
                    color = "#27ae60"  # Green for standard

                preview_canvas.create_rectangle(x, y, x + seat_size, y + seat_size,
                                               fill=color, outline="#1a1a1a")

        # Legend
        preview_canvas.create_rectangle(20, 190, 30, 198, fill="#27ae60", outline="#1a1a1a")
        preview_canvas.create_text(35, 194, text=_t("cinema.seat_types.standard"), anchor="w", fill="white", font=("Helvetica", 7))
        preview_canvas.create_rectangle(100, 190, 110, 198, fill="#f1c40f", outline="#1a1a1a")
        preview_canvas.create_text(115, 194, text=_t("cinema.seat_types.vip"), anchor="w", fill="white", font=("Helvetica", 7))
        preview_canvas.create_rectangle(160, 190, 170, 198, fill="#3498db", outline="#1a1a1a")
        preview_canvas.create_text(175, 194, text=_t("cinema.seat_types.wheelchair"), anchor="w", fill="white", font=("Helvetica", 7))

    ttk.Button(btn_frame, text=_t("cinema.btn.preview"), style="Primary.TButton",
              command=update_preview).pack(side="left", padx=5)

    # Load initial layout
    load_layout()
    update_preview()
