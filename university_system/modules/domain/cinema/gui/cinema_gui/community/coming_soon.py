"""
Cinema Booking System - Coming Soon Movies
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import webbrowser

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

def show_coming_soon_page(self):
    """Display coming soon movies page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.movies.coming_soon"),
             style="Subtitle.TLabel").pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)

    ttk.Button(btn_frame, text="+ Add Coming Soon Movie", style="Success.TButton",
              command=self.add_coming_soon).pack(side="left", padx=5)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Title", "Genre", "Rating", "Release Date", "Countdown", "Notify", "Status")
    self.coming_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

    for col in columns:
        self.coming_tree.heading(col, text=col)

    def load_coming_soon():
        for item in self.coming_tree.get_children():
            self.coming_tree.delete(item)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM coming_soon ORDER BY release_date")
        for row in cursor.fetchall():
            release = row[6] if row[6] else ""
            if release:
                try:
                    days = (datetime.strptime(release, "%Y-%m-%d") - datetime.now()).days
                    countdown = f"{days} days" if days > 0 else "Released!"
                except (ValueError, TypeError):
                    countdown = "TBA"
            else:
                countdown = "TBA"
            self.coming_tree.insert("", "end", values=(row[0], row[1], row[3] or "-", row[4] or "-", release, countdown, row[9], row[10].upper()))
        conn.close()

    self.coming_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.coming_tree.yview)
    self.coming_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.btn.watch_trailer"), style="Primary.TButton",
              command=self.watch_trailer).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.notify_me"), style="Success.TButton",
              command=self.notify_me).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.move_to_active"), style="Warning.TButton",
              command=self.activate_movie).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.delete"), style="Danger.TButton",
              command=self.delete_coming).pack(side="left", padx=5)
    load_coming_soon()

def add_coming_soon(self):
    form = tk.Toplevel(self.root)
    form.title("Add Coming Soon Movie")
    form.geometry("500x450")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.coming_soon.add_movie"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)
    fields = [("Title:*", "title"), ("Genre:", "genre"), ("Rating:", "rating"), ("Director:", "director"), ("Release Date:*", "release"), ("Trailer URL:", "trailer"), ("Description:", "desc")]
    entries = {}
    for i, (label, key) in enumerate(fields):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        e = ttk.Entry(frame, width=35)
        e.grid(row=i+1, column=1, pady=5)
        entries[key] = e
    entries['release'].insert(0, (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
    def save():
        if not entries['title'].get().strip() or not entries['release'].get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Title and release date required")
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO coming_soon (title, description, genre, rating, director, release_date, trailer_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (entries['title'].get(), entries['desc'].get(), entries['genre'].get(), entries['rating'].get(), entries['director'].get(), entries['release'].get(), entries['trailer'].get()))
        conn.commit()
        conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Movie added!")
        form.destroy()
        self.show_coming_soon_page()
    ttk.Button(frame, text=_t("cinema.buttons.save"), style="Success.TButton", command=save).grid(row=len(fields)+1, column=0, columnspan=2, pady=20)

def watch_trailer(self):
    selected = self.coming_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a movie")
        return
    movie_id = self.coming_tree.item(selected[0])['values'][0]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT trailer_url FROM coming_soon WHERE id = ?", (movie_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        webbrowser.open(result[0])
    else:
        messagebox.showinfo(_t("cinema.common.info"), "No trailer available")

def notify_me(self):
    selected = self.coming_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a movie")
        return
    movie_id = self.coming_tree.item(selected[0])['values'][0]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE coming_soon SET notify_count = notify_count + 1 WHERE id = ?", (movie_id,))
    conn.commit()
    conn.close()
    messagebox.showinfo(_t("cinema.common.success"), "You'll be notified!")
    self.show_coming_soon_page()

def activate_movie(self):
    selected = self.coming_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a movie")
        return
    movie_id = self.coming_tree.item(selected[0])['values'][0]

    # Prompt for movie duration
    from tkinter import simpledialog
    duration = simpledialog.askinteger(
        "Movie Duration",
        "Enter movie duration in minutes:",
        minvalue=1,
        maxvalue=500,
        initialvalue=120
    )

    if not duration:
        return  # User cancelled

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coming_soon WHERE id = ?", (movie_id,))
    movie = cursor.fetchone()
    if movie:
        # Insert into movies table with duration
        cursor.execute("INSERT INTO movies (title, duration, description, genre, rating, director, release_date, poster_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (movie[1], duration, movie[2], movie[3], movie[4], movie[5], movie[6], movie[8]))
        cursor.execute("UPDATE coming_soon SET status = 'released' WHERE id = ?", (movie_id,))
        conn.commit()
        messagebox.showinfo(_t("cinema.common.success"), f"Movie activated with {duration} min duration!")
    conn.close()
    self.show_coming_soon_page()

def delete_coming(self):
    selected = self.coming_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a movie")
        return
    if not messagebox.askyesno(_t("cinema.common.confirm"), "Delete this movie?"):
        return
    movie_id = self.coming_tree.item(selected[0])['values'][0]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM coming_soon WHERE id = ?", (movie_id,))
    conn.commit()
    conn.close()
    self.show_coming_soon_page()
