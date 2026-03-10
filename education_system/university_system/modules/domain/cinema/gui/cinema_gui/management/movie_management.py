"""
Cinema Booking System - Movie Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

def show_movie_management(self):
    """Display movie management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.movies.title"),
             style="Subtitle.TLabel").pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)

    ttk.Button(btn_frame, text=_t("cinema.movies.add_movie_btn"), style="Success.TButton",
              command=self.show_add_movie_form).pack(side="left", padx=5)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Title", "Duration", "Genre", "Rating", "Director", "Status")
    self.movie_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        self.movie_tree.heading(col, text=col)
    self.movie_tree.column("ID", width=50)
    self.movie_tree.column("Title", width=200)

    self.refresh_movie_list()

    self.movie_tree.pack(fill="both", expand=True, side="left")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.movie_tree.yview)
    self.movie_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.buttons.edit_selected"), style="Secondary.TButton",
              command=self.edit_selected_movie).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.delete_selected"), style="Danger.TButton",
              command=self.delete_selected_movie).pack(side="left", padx=5)

def refresh_movie_list(self):
    if hasattr(self, 'movie_tree'):
        for item in self.movie_tree.get_children():
            self.movie_tree.delete(item)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, duration, genre, rating, director, COALESCE(status, 'active')
            FROM movies ORDER BY id DESC
        ''')
        for movie in cursor.fetchall():
            self.movie_tree.insert("", "end", values=movie)
        conn.close()

def show_add_movie_form(self):
    self.show_movie_form(None)

def show_movie_form(self, movie_data):
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Movie" if movie_data is None else "Edit Movie")
    form_window.geometry("500x500")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=_t("cinema.movies.movie_details"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    entries = {}
    fields = [("Title:*", "title"), ("Duration (min):*", "duration"), ("Genre:", "genre"),
              ("Rating:", "rating"), ("Director:", "director"), ("Description:", "description")]

    for i, (label, field) in enumerate(fields):
        tk.Label(fields_frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        entry = ttk.Entry(fields_frame, width=40)
        entry.grid(row=i+1, column=1, pady=5)
        entries[field] = entry

    if movie_data:
        entries['title'].insert(0, movie_data[1])
        entries['duration'].insert(0, str(movie_data[2]))
        entries['genre'].insert(0, movie_data[3] or "")
        entries['rating'].insert(0, movie_data[4] or "")
        if len(movie_data) > 7:
            entries['director'].insert(0, movie_data[7] or "")
        if len(movie_data) > 5:
            entries['description'].insert(0, movie_data[5] or "")

    def save_movie():
        title = entries['title'].get().strip()
        if not title:
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.enter_title"))
            return

        try:
            duration = int(entries['duration'].get())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.invalid_duration"))
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if movie_data:
            cursor.execute('''
                UPDATE movies SET title=?, duration=?, genre=?, rating=?, director=?, description=?
                WHERE id=?
            ''', (title, duration, entries['genre'].get(), entries['rating'].get(),
                  entries['director'].get(), entries['description'].get(), movie_data[0]))
        else:
            cursor.execute('''
                INSERT INTO movies (title, duration, genre, rating, director, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, duration, entries['genre'].get(), entries['rating'].get(),
                  entries['director'].get(), entries['description'].get()))

        conn.commit()
        conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Movie saved!")
        form_window.destroy()
        self.refresh_movie_list()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=8, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.buttons.save"), style="Success.TButton", command=save_movie).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton", command=form_window.destroy).pack(side="left", padx=5)

def edit_selected_movie(self):
    selected = self.movie_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_movie"))
        return

    movie_id = self.movie_tree.item(selected[0])['values'][0]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    movie = cursor.fetchone()
    conn.close()

    if movie:
        self.show_movie_form(movie)

def delete_selected_movie(self):
    selected = self.movie_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_movie"))
        return

    if messagebox.askyesno(_t("cinema.common.confirm"), _t("cinema.messages.confirm.delete_movie")):
        movie_id = self.movie_tree.item(selected[0])['values'][0]
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        cursor.execute("DELETE FROM screenings WHERE movie_id = ?", (movie_id,))
        conn.commit()
        conn.close()
        self.refresh_movie_list()
