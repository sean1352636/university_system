"""
Cinema Booking System - Movie Reviews Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_reviews_page(self):
    """Display movie reviews management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.reviews.title"),
             style="Subtitle.TLabel").pack(pady=10)

    # Filter frame
    filter_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    filter_frame.pack(fill="x", pady=10)

    tk.Label(filter_frame, text=_t("cinema.screenings.filter_by_movie"), bg="#ffffff", fg="#333333").pack(side="left")

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM movies WHERE status = 'active' OR status IS NULL")
        movies = [("all", "All Movies")] + [(str(m[0]), m[1]) for m in cursor.fetchall()]
    finally:
        conn.close()

    movie_var = tk.StringVar(value="all")
    movie_combo = ttk.Combobox(filter_frame, textvariable=movie_var, width=30,
                               values=[m[1] for m in movies])
    movie_combo.pack(side="left", padx=10)

    ttk.Button(filter_frame, text="+ Add Review", style="Success.TButton",
              command=self.add_review).pack(side="right", padx=5)

    # Reviews list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Movie", _t("cinema.columns.customer"), "Rating", "Review", "Date", "Status")
    self.review_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        self.review_tree.heading(col, text=col)
    self.review_tree.column("ID", width=50)
    self.review_tree.column("Movie", width=150)
    self.review_tree.column(_t("cinema.columns.customer"), width=120)
    self.review_tree.column("Rating", width=80)
    self.review_tree.column("Review", width=250)
    self.review_tree.column("Date", width=100)
    self.review_tree.column("Status", width=80)

    def load_reviews():
        for item in self.review_tree.get_children():
            self.review_tree.delete(item)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            selected_movie = movie_combo.get()
            sql = '''
                SELECT r.id, m.title, r.customer_name, r.rating, r.review_text, r.created_at, r.status
                FROM reviews r
                JOIN movies m ON r.movie_id = m.id
            '''
            params = []
            if selected_movie != "All Movies":
                movie_id = next((m[0] for m in movies if m[1] == selected_movie), None)
                if movie_id and movie_id != "all":
                    sql += " WHERE r.movie_id = ?"
                    params.append(movie_id)
            sql += " ORDER BY r.created_at DESC"

            cursor.execute(sql, params)
            for row in cursor.fetchall():
                stars = "\u2605" * row[3] + "\u2606" * (5 - row[3])
                review_preview = (row[4][:40] + "...") if row[4] and len(row[4]) > 40 else (row[4] or "-")
                self.review_tree.insert("", "end", values=(
                    row[0], row[1][:20], row[2] or "Anonymous", stars,
                    review_preview, row[5][:10] if row[5] else "-", row[6].upper()
                ))
        finally:
            conn.close()

    ttk.Button(filter_frame, text=_t("cinema.btn.filter"), style="Primary.TButton",
              command=load_reviews).pack(side="left", padx=5)

    self.review_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.review_tree.yview)
    self.review_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Stats frame
    stats_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    stats_frame.pack(fill="x", pady=10)

    # Get average ratings per movie
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.title, AVG(r.rating), COUNT(r.id)
            FROM movies m
            LEFT JOIN reviews r ON m.id = r.movie_id AND r.status = 'active'
            GROUP BY m.id
            HAVING COUNT(r.id) > 0
            ORDER BY AVG(r.rating) DESC LIMIT 5
        ''')
        top_rated = cursor.fetchall()
    finally:
        conn.close()

    tk.Label(stats_frame, text=_t("cinema.labels.top_rated_movies"), font=("Helvetica", 11, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w")

    for movie in top_rated:
        avg_rating = movie[1] or 0
        stars = "\u2605" * int(round(avg_rating)) + "\u2606" * (5 - int(round(avg_rating)))
        tk.Label(stats_frame, text=f"{movie[0][:25]}: {stars} ({avg_rating:.1f}/5 from {movie[2]} reviews)",
                bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    # Action buttons
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.btn.view_full_review"), style="Secondary.TButton",
              command=self.view_full_review).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.approve"), style="Success.TButton",
              command=lambda: self.update_review_status('active')).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.hide_review"), style="Danger.TButton",
              command=lambda: self.update_review_status('hidden')).pack(side="left", padx=5)

    load_reviews()

def add_review(self):
    """Add a new movie review."""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Review")
    form_window.geometry("500x450")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=_t("cinema.reviews.add_review"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    # Movie selection
    tk.Label(fields_frame, text=_t("cinema.screenings.fields.movie_required"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM movies WHERE status = 'active' OR status IS NULL")
        movies = cursor.fetchall()
    finally:
        conn.close()

    movie_var = tk.StringVar()
    movie_combo = ttk.Combobox(fields_frame, textvariable=movie_var, width=32,
                               values=[f"{m[0]} - {m[1]}" for m in movies])
    movie_combo.grid(row=1, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.labels.your_name"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    name_entry = ttk.Entry(fields_frame, width=35)
    name_entry.grid(row=2, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.labels.rating_required"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    rating_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    rating_frame.grid(row=3, column=1, pady=5, sticky="w")

    rating_var = tk.IntVar(value=5)
    for i in range(1, 6):
        tk.Radiobutton(rating_frame, text="\u2605" * i, variable=rating_var, value=i,
                      bg="#ffffff", fg="#ffd700", selectcolor="#16213e",
                      activebackground="#16213e").pack(side="left")

    tk.Label(fields_frame, text=_t("cinema.reviews.review_label"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="nw", pady=5)
    review_text = tk.Text(fields_frame, width=27, height=6, font=("Helvetica", 10))
    review_text.grid(row=4, column=1, pady=5)

    def save_review():
        movie_selection = movie_var.get()
        if not movie_selection:
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_movie"))
            return

        movie_id = int(movie_selection.split(" - ")[0])
        rating = rating_var.get()
        name = name_entry.get().strip() or "Anonymous"
        review = review_text.get("1.0", tk.END).strip()

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO reviews (movie_id, customer_name, rating, review_text)
                VALUES (?, ?, ?, ?)
            ''', (movie_id, name, rating, review))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Review submitted successfully!")
        form_window.destroy()
        self.show_reviews_page()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=5, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.btn.submit_review"), style="Success.TButton",
              command=save_review).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton",
              command=form_window.destroy).pack(side="left", padx=5)

def view_full_review(self):
    """View full review text."""
    selected = self.review_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a review")
        return

    review_id = self.review_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, m.title FROM reviews r
            JOIN movies m ON r.movie_id = m.id
            WHERE r.id = ?
        ''', (review_id,))
        review = cursor.fetchone()
    finally:
        conn.close()

    if not review:
        return

    view_window = tk.Toplevel(self.root)
    view_window.title(f"Review for {review[-1]}")
    view_window.geometry("500x400")
    view_window.configure(bg="#ecf0f1")
    view_window.transient(self.root)

    frame = ttk.Frame(view_window, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=review[-1], font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").pack()

    stars = "\u2605" * review[4] + "\u2606" * (5 - review[4])
    tk.Label(frame, text=stars, font=("Helvetica", 16),
            bg="#ffffff", fg="#ffd700").pack(pady=5)

    tk.Label(frame, text=f"By: {review[3] or 'Anonymous'}",
            bg="#ffffff", fg="#7f8c8d").pack()
    tk.Label(frame, text=f"Date: {review[7][:10] if review[7] else 'N/A'}",
            bg="#ffffff", fg="#7f8c8d").pack()

    review_label = tk.Label(frame, text=review[5] or "No written review",
                           bg="#ffffff", fg="#333333", wraplength=400, justify="left")
    review_label.pack(pady=20)

def update_review_status(self, new_status):
    """Update review status."""
    selected = self.review_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a review")
        return

    review_id = self.review_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE reviews SET status = ? WHERE id = ?", (new_status, review_id))
        conn.commit()
    finally:
        conn.close()

    self.show_reviews_page()
