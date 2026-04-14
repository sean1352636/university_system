"""
Cinema Booking System - Movie Browsing

Functions for displaying movie listings, creating movie cards,
and showing available screenings for selected movies.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

# i18n support
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_movies_page(self):
    """Display the movies listing page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.movies.now_showing", default="Now Showing"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movies WHERE status = 'active' OR status IS NULL")
        movies = cursor.fetchall()
    finally:
        conn.close()

    movies_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    movies_frame.pack(fill="both", expand=True)

    for i, movie in enumerate(movies):
        self.create_movie_card(movies_frame, movie, i)

def create_movie_card(self, parent, movie, index):
    """Create a movie card widget."""
    card = ttk.Frame(parent, style="Card.TFrame", padding=15)
    card.pack(fill="x", pady=5)

    info_frame = ttk.Frame(card, style="Card.TFrame")
    info_frame.pack(side="left", fill="x", expand=True)

    title_label = tk.Label(info_frame, text=movie[1], font=("Helvetica", 14, "bold"),
                          bg="#ffffff", fg="#e74c3c")
    title_label.pack(anchor="w")

    details = f"Duration: {movie[2]} min  |  Genre: {movie[3]}  |  Rating: {movie[4]}"
    tk.Label(info_frame, text=details, font=("Helvetica", 10),
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    if len(movie) > 5 and movie[5]:
        tk.Label(info_frame, text=movie[5], font=("Helvetica", 9),
                bg="#ffffff", fg="#888888").pack(anchor="w")

    ttk.Button(card, text=_t("cinema.screenings.view"), style="Primary.TButton",
              command=lambda m=movie: self.show_screenings(m)).pack(side="right")

def show_screenings(self, movie):
    """Show available screenings for a movie."""
    self.clear_content()

    ttk.Button(self.content_frame, text="← " + _t("cinema.booking.back_to_movies"), style="Secondary.TButton",
              command=self.show_movies_page).pack(anchor="w")

    ttk.Label(self.content_frame, text=f"Screenings: {movie[1]}",
             style="Subtitle.TLabel").pack(anchor="w", pady=10)

    # Date filter
    filter_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    filter_frame.pack(fill="x", pady=5)

    tk.Label(filter_frame, text=_t("cinema.common.filter_by_date"), bg="#ffffff", fg="#333333").pack(side="left")
    date_var = tk.StringVar(value="all")
    dates = ["all"] + [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    date_combo = ttk.Combobox(filter_frame, textvariable=date_var, values=dates, width=15)
    date_combo.pack(side="left", padx=10)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Screen", "Date & Time", "Price", "Available Seats")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)
    tree.column("ID", width=50)

    def load_screenings():
        for item in tree.get_children():
            tree.delete(item)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            sql = '''
                SELECT s.id, s.screen_number, s.show_time, s.price,
                       (SELECT COUNT(*) FROM seats WHERE screening_id = s.id AND status = 'available')
                FROM screenings s
                WHERE s.movie_id = ? AND s.show_time >= datetime('now') AND (s.status = 'active' OR s.status IS NULL)
            '''
            params = [movie[0]]

            if date_var.get() != "all":
                sql += " AND date(s.show_time) = ?"
                params.append(date_var.get())

            sql += " ORDER BY s.show_time"
            cursor.execute(sql, params)
            screenings = cursor.fetchall()
        finally:
            conn.close()

        for screening in screenings:
            tree.insert("", "end", values=(
                screening[0], f"Screen {screening[1]}", screening[2],
                f"£{screening[3]:.2f}", f"{screening[4]} seats"
            ))

    def select_screening():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning(_t("cinema.common.warning", default="Warning"), _t("cinema.messages.warnings.select_screening", default="Please select a screening from the list"))
            return
        screening_id = tree.item(selected[0])['values'][0]
        self.show_seat_selection(screening_id, movie)

    load_screenings()
    ttk.Button(filter_frame, text=_t("cinema.booking.filter"), style="Primary.TButton",
              command=load_screenings).pack(side="left", padx=5)
    ttk.Button(filter_frame, text=_t("cinema.booking.select_seats") + " →", style="Success.TButton",
              command=select_screening).pack(side="right", padx=10)

    tree.pack(fill="both", expand=True, side="left")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
