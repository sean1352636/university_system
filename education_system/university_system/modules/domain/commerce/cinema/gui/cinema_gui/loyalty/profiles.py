"""
Cinema Booking System - Customer Profile Management
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE
from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import BIRTHDAY_REWARD_TICKET

def show_profiles_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.profiles.title"), style="Subtitle.TLabel").pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.new_profile"), style="Success.TButton", command=self.create_profile).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.rewards.birthday"), style="Primary.TButton", command=self.show_birthday_rewards).pack(side="left", padx=5)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Name", "Email", "Phone", "Birthday", "Favorite Seats", "Total Bookings", "Preferences")
    self.profile_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
    for col in columns:
        self.profile_tree.heading(col, text=col)
        self.profile_tree.column(col, width=100 if col != "Preferences" else 150)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.id, m.name, m.email, m.phone, m.birthday, cp.favorite_seats, m.bookings_count, cp.preferred_snacks
            FROM customer_profiles cp
            JOIN members m ON cp.member_id = m.id
            ORDER BY m.name
        """)
        for row in cursor.fetchall():
            self.profile_tree.insert("", "end", values=(row[0], row[1] or '', row[2] or '', row[3] or '', row[4] or '', row[5] or '', row[6] or 0, row[7] or ''))
    finally:
        conn.close()

    self.profile_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.profile_tree.yview)
    self.profile_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Profile actions
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.btn.edit_profile"), command=self.edit_profile).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.view_history"), command=self.view_profile_history).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.set_favorite_seats"), command=self.set_favorite_seats).pack(side="left", padx=5)

def create_profile(self):
    form = tk.Toplevel(self.root)
    form.title("Create Customer Profile")
    form.geometry("400x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.customers.new_profile"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=_t("cinema.labels.full_name"), bg="#ffffff", fg="#333333").pack(anchor="w")
    name_e = ttk.Entry(frame, width=35)
    name_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.common.email_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    email_e = ttk.Entry(frame, width=35)
    email_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.members.phone_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    phone_e = ttk.Entry(frame, width=35)
    phone_e.pack(pady=5)

    tk.Label(frame, text="Birthday (YYYY-MM-DD):", bg="#ffffff", fg="#333333").pack(anchor="w")
    bday_e = ttk.Entry(frame, width=35)
    bday_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.preferences"), bg="#ffffff", fg="#333333").pack(anchor="w")
    prefs_e = ttk.Entry(frame, width=35)
    prefs_e.insert(0, "e.g., Action movies, Front row")
    prefs_e.pack(pady=5)

    def save():
        if not name_e.get().strip() or not email_e.get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Name and email required")
            return
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO customer_profiles (name, email, phone, birthday, preferences, created_at)
                            VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                          (name_e.get().strip(), email_e.get().strip(), phone_e.get().strip(),
                           bday_e.get().strip(), prefs_e.get().strip()))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Profile created")
        form.destroy()
        self.show_profiles_page()

    ttk.Button(frame, text=_t("cinema.btn.save_profile"), style="Success.TButton", command=save).pack(pady=20)

def edit_profile(self):
    selected = self.profile_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a profile")
        return
    profile_id = self.profile_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customer_profiles WHERE id = ?", (profile_id,))
        profile = cursor.fetchone()
    finally:
        conn.close()

    if not profile:
        return

    form = tk.Toplevel(self.root)
    form.title("Edit Profile")
    form.geometry("400x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.btn.edit_customer_profile"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=_t("cinema.labels.full_name"), bg="#ffffff", fg="#333333").pack(anchor="w")
    name_e = ttk.Entry(frame, width=35)
    name_e.insert(0, profile[1] or "")
    name_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.common.email_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    email_e = ttk.Entry(frame, width=35)
    email_e.insert(0, profile[2] or "")
    email_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.members.phone_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    phone_e = ttk.Entry(frame, width=35)
    phone_e.insert(0, profile[3] or "")
    phone_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.members.birthday_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    bday_e = ttk.Entry(frame, width=35)
    bday_e.insert(0, profile[4] or "")
    bday_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.preferences"), bg="#ffffff", fg="#333333").pack(anchor="w")
    prefs_e = ttk.Entry(frame, width=35)
    prefs_e.insert(0, profile[7] or "")
    prefs_e.pack(pady=5)

    def save():
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("""UPDATE customer_profiles SET name=?, email=?, phone=?, birthday=?, preferences=?
                            WHERE id=?""",
                          (name_e.get().strip(), email_e.get().strip(), phone_e.get().strip(),
                           bday_e.get().strip(), prefs_e.get().strip(), profile_id))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Profile updated")
        form.destroy()
        self.show_profiles_page()

    ttk.Button(frame, text=_t("cinema.buttons.save_changes"), style="Success.TButton", command=save).pack(pady=20)

def view_profile_history(self):
    selected = self.profile_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a profile")
        return
    email = self.profile_tree.item(selected[0])['values'][2]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT b.booking_ref, m.title, b.booking_time, b.ticket_types, b.total_amount, b.booking_time
                        FROM bookings b JOIN movies m ON b.movie_id = m.id
                        WHERE b.customer_email = ? ORDER BY b.created_at DESC LIMIT 20""", (email,))
        bookings = cursor.fetchall()
    finally:
        conn.close()

    history = tk.Toplevel(self.root)
    history.title("Booking History")
    history.geometry("600x400")
    history.configure(bg="#ecf0f1")

    tk.Label(history, text=f"Booking History for {email}", font=("Helvetica", 14, "bold"), bg="#ecf0f1", fg="#e74c3c").pack(pady=10)

    tree_frame = ttk.Frame(history)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

    columns = ("Ref", "Movie", "Date", "Seats", "Total", "Booked On")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        tree.heading(col, text=col)
    for row in bookings:
        tree.insert("", "end", values=(row[0], row[1], row[2], row[3], f"£{row[4]:.2f}", row[5][:10]))
    tree.pack(fill="both", expand=True)

def set_favorite_seats(self):
    selected = self.profile_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a profile")
        return
    profile_id = self.profile_tree.item(selected[0])['values'][0]

    seats = simpledialog.askstring("Favorite Seats", "Enter favorite seats (e.g., A1, A2, B3):")
    if seats:
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE customer_profiles SET favorite_seats = ? WHERE id = ?", (seats, profile_id))
            conn.commit()
        finally:
            conn.close()
        self.show_profiles_page()

def show_birthday_rewards(self):
    today = datetime.now()
    this_month = today.strftime("%m")

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, name, email, birthday FROM customer_profiles
                        WHERE substr(birthday, 6, 2) = ?""", (this_month,))
        birthdays = cursor.fetchall()
    finally:
        conn.close()

    reward_win = tk.Toplevel(self.root)
    reward_win.title("Birthday Rewards This Month")
    reward_win.geometry("500x400")
    reward_win.configure(bg="#ecf0f1")

    tk.Label(reward_win, text=_t("cinema.rewards.birthday_this_month"), font=("Helvetica", 14, "bold"),
            bg="#ecf0f1", fg="#e74c3c").pack(pady=10)
    tk.Label(reward_win, text=f"Reward: {BIRTHDAY_REWARD_TICKET}", font=("Helvetica", 11),
            bg="#ecf0f1", fg="#27ae60").pack()

    frame = ttk.Frame(reward_win, style="Card.TFrame", padding=10)
    frame.pack(fill="both", expand=True, padx=20, pady=10)

    if birthdays:
        for p in birthdays:
            bday = p[3][5:] if p[3] else "Unknown"
            tk.Label(frame, text=f"• {p[1]} ({p[2]}) - Birthday: {bday}", bg="#ffffff", fg="#333333").pack(anchor="w", pady=2)
    else:
        tk.Label(frame, text=_t("cinema.messages.no_birthdays"), bg="#ffffff", fg="#7f8c8d").pack()
