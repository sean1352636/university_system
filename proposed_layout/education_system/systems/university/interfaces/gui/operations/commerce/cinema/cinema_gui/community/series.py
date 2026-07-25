"""
Cinema Booking System - Movie Series Management
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

def show_series_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.series.title"), style="Subtitle.TLabel").pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.new_series"), style="Success.TButton", command=self.create_series).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.series.link_movie"), style="Primary.TButton", command=self.link_movie_to_series).pack(side="left", padx=5)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Series Name", "Description", "Movie Count", "Created")
    self.series_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    for col in columns:
        self.series_tree.heading(col, text=col)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT s.id, s.name, s.description,
                        (SELECT COUNT(*) FROM movie_series_link WHERE series_id = s.id) as movie_count,
                        s.created_at FROM movie_series s ORDER BY s.name""")
        for row in cursor.fetchall():
            self.series_tree.insert("", "end", values=(row[0], row[1], row[2] or "-", row[3], row[4][:10] if row[4] else "-"))
    finally:
        conn.close()

    self.series_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.series_tree.yview)
    self.series_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Movies in selected series
    ttk.Label(self.content_frame, text=_t("cinema.series.movies_in_series"), style="Subtitle.TLabel").pack(pady=(20, 5))

    movie_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    movie_frame.pack(fill="both", expand=True, pady=10)

    columns2 = ("Order", "Movie Title", "Release Year")
    self.series_movies_tree = ttk.Treeview(movie_frame, columns=columns2, show="headings", height=8)
    for col in columns2:
        self.series_movies_tree.heading(col, text=col)
    self.series_movies_tree.pack(fill="both", expand=True)

    self.series_tree.bind("<<TreeviewSelect>>", self.on_series_select)

def on_series_select(self, event):
    selected = self.series_tree.selection()
    if not selected:
        return
    series_id = self.series_tree.item(selected[0])['values'][0]

    for item in self.series_movies_tree.get_children():
        self.series_movies_tree.delete(item)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT sl.order_in_series, m.title, m.release_year
                        FROM movie_series_link sl JOIN movies m ON sl.movie_id = m.id
                        WHERE sl.series_id = ? ORDER BY sl.order_in_series""", (series_id,))
        for row in cursor.fetchall():
            self.series_movies_tree.insert("", "end", values=(row[0], row[1], row[2] or "-"))
    finally:
        conn.close()

def create_series(self):
    form = tk.Toplevel(self.root)
    form.title("New Series")
    form.geometry("400x300")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.series.create_movie_series"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=_t("cinema.labels.series_name"), bg="#ffffff", fg="#333333").pack(anchor="w")
    name_e = ttk.Entry(frame, width=35)
    name_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.description"), bg="#ffffff", fg="#333333").pack(anchor="w")
    desc_e = ttk.Entry(frame, width=35)
    desc_e.pack(pady=5)

    def save():
        if not name_e.get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Enter series name")
            return
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO movie_series (name, description, created_at) VALUES (?, ?, datetime('now'))",
                          (name_e.get().strip(), desc_e.get().strip()))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Series created")
        form.destroy()
        self.show_series_page()

    ttk.Button(frame, text=_t("cinema.btn.create_series"), style="Success.TButton", command=save).pack(pady=20)

def link_movie_to_series(self):
    form = tk.Toplevel(self.root)
    form.title("Link Movie to Series")
    form.geometry("400x350")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.series.link_movie"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM movie_series ORDER BY name")
        series_list = cursor.fetchall()
        cursor.execute("SELECT id, title FROM movies ORDER BY title")
        movies_list = cursor.fetchall()
    finally:
        conn.close()

    tk.Label(frame, text=_t("cinema.labels.series"), bg="#ffffff", fg="#333333").pack(anchor="w")
    series_var = tk.StringVar()
    series_cb = ttk.Combobox(frame, textvariable=series_var, width=32)
    series_cb['values'] = [f"{s[0]}: {s[1]}" for s in series_list]
    series_cb.pack(pady=5)

    tk.Label(frame, text=_t("cinema.movies.movie_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    movie_var = tk.StringVar()
    movie_cb = ttk.Combobox(frame, textvariable=movie_var, width=32)
    movie_cb['values'] = [f"{m[0]}: {m[1]}" for m in movies_list]
    movie_cb.pack(pady=5)

    tk.Label(frame, text=_t("cinema.series.order_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    order_e = ttk.Entry(frame, width=10)
    order_e.insert(0, "1")
    order_e.pack(pady=5)

    def save():
        if not series_var.get() or not movie_var.get():
            messagebox.showwarning(_t("cinema.common.warning"), "Select series and movie")
            return
        series_id = int(series_var.get().split(":")[0])
        movie_id = int(movie_var.get().split(":")[0])
        order = int(order_e.get() or 1)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO movie_series_link (series_id, movie_id, order_in_series) VALUES (?, ?, ?)",
                          (series_id, movie_id, order))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Movie linked to series")
        form.destroy()
        self.show_series_page()

    ttk.Button(frame, text=_t("cinema.btn.link_movie"), style="Success.TButton", command=save).pack(pady=20)
