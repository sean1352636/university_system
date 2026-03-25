"""
Cinema Booking System - Screening Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import DB_FILE

def show_screening_management(self):
    """Display screening management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.screenings.title"),
             style="Subtitle.TLabel").pack(pady=10)

    # Add screening button
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)

    ttk.Button(btn_frame, text=_t("cinema.screenings.add_screening_btn"), style="Success.TButton",
              command=self.show_add_screening_form).pack(side="left", padx=5)

    # Filter
    filter_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    filter_frame.pack(fill="x", pady=5)

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

    # Screenings list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Movie", "Screen", "Date/Time", "Price", "Booked", "Available", "Status")
    self.screening_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        self.screening_tree.heading(col, text=col)
    self.screening_tree.column("ID", width=50)
    self.screening_tree.column("Movie", width=200)
    self.screening_tree.column("Screen", width=80)
    self.screening_tree.column("Date/Time", width=150)
    self.screening_tree.column("Price", width=80)
    self.screening_tree.column("Booked", width=70)
    self.screening_tree.column("Available", width=80)
    self.screening_tree.column("Status", width=80)

    def load_screenings():
        for item in self.screening_tree.get_children():
            self.screening_tree.delete(item)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            sql = '''
                SELECT s.id, m.title, s.screen_number, s.show_time, s.price,
                       (SELECT COUNT(*) FROM seats WHERE screening_id = s.id AND status = 'booked'),
                       (SELECT COUNT(*) FROM seats WHERE screening_id = s.id AND status = 'available'),
                       COALESCE(s.status, 'active')
                FROM screenings s
                JOIN movies m ON s.movie_id = m.id
            '''

            params = []
            selected_movie = movie_combo.get()
            if selected_movie != "All Movies":
                movie_id = next((m[0] for m in movies if m[1] == selected_movie), None)
                if movie_id and movie_id != "all":
                    sql += " WHERE s.movie_id = ?"
                    params.append(movie_id)

            sql += " ORDER BY s.show_time DESC LIMIT 100"
            cursor.execute(sql, params)

            for row in cursor.fetchall():
                self.screening_tree.insert("", "end", values=(
                    row[0], row[1][:25], f"Screen {row[2]}", row[3],
                    f"\u00a3{row[4]:.2f}", row[5], row[6], row[7].upper()
                ))
        finally:
            conn.close()

    load_screenings()

    ttk.Button(filter_frame, text=_t("cinema.booking.filter"), style="Primary.TButton",
              command=load_screenings).pack(side="left", padx=5)

    self.screening_tree.pack(fill="both", expand=True, side="left")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.screening_tree.yview)
    self.screening_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.buttons.edit_selected"), style="Secondary.TButton",
              command=self.edit_selected_screening).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.cancel_selected"), style="Danger.TButton",
              command=self.cancel_selected_screening).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.refresh"), style="Secondary.TButton",
              command=load_screenings).pack(side="left", padx=5)

def show_add_screening_form(self):
    """Show form to add a new screening."""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Screening")
    form_window.geometry("500x400")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=_t("cinema.screenings.add_new_screening"), font=("Helvetica", 14, "bold"),
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
    movie_combo = ttk.Combobox(fields_frame, textvariable=movie_var, width=37,
                               values=[f"{m[0]} - {m[1]}" for m in movies])
    movie_combo.grid(row=1, column=1, pady=5)

    # Screen number
    tk.Label(fields_frame, text=_t("cinema.screenings.fields.screen_required"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    screen_var = tk.StringVar(value="1")
    screen_combo = ttk.Combobox(fields_frame, textvariable=screen_var, width=37,
                                values=[str(i) for i in range(1, 11)])
    screen_combo.grid(row=2, column=1, pady=5)

    # Date
    tk.Label(fields_frame, text=_t("cinema.screenings.fields.date_required"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    date_entry = ttk.Entry(fields_frame, width=40)
    date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
    date_entry.grid(row=3, column=1, pady=5)

    # Time
    tk.Label(fields_frame, text=_t("cinema.screenings.fields.time_required"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    time_var = tk.StringVar(value="19:00")
    time_combo = ttk.Combobox(fields_frame, textvariable=time_var, width=37,
                              values=["10:00", "13:00", "16:00", "19:00", "22:00"])
    time_combo.grid(row=4, column=1, pady=5)

    # Price
    tk.Label(fields_frame, text=_t("cinema.screenings.fields.base_price"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    price_entry = ttk.Entry(fields_frame, width=40)
    price_entry.insert(0, "14.99")
    price_entry.grid(row=5, column=1, pady=5)

    def save_screening():
        movie_selection = movie_var.get()
        if not movie_selection:
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_movie"))
            return

        movie_id = int(movie_selection.split(" - ")[0])
        screen = int(screen_var.get())
        date = date_entry.get().strip()
        time = time_var.get()
        show_time = f"{date} {time}"

        try:
            price = float(price_entry.get().strip())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.errors.invalid_price"))
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO screenings (movie_id, screen_number, show_time, price)
                VALUES (?, ?, ?, ?)
            ''', (movie_id, screen, show_time, price))

            screening_id = cursor.lastrowid

            # Create seats
            rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            for row in rows:
                for seat_num in range(1, 13):
                    seat_type = 'vip' if row in ['A', 'B'] else 'standard'
                    cursor.execute('''
                        INSERT INTO seats (screening_id, row, seat_number, seat_type, status)
                        VALUES (?, ?, ?, ?, 'available')
                    ''', (screening_id, row, seat_num, seat_type))

            conn.commit()
            messagebox.showinfo(_t("cinema.common.success", default="Success"), _t("cinema.messages.success.screening_added", default="Screening added successfully!"))
            form_window.destroy()
            self.show_screening_management()

        except Exception as e:
            conn.rollback()
            messagebox.showerror(_t("cinema.common.error"), f"Failed to add screening: {str(e)}")
        finally:
            conn.close()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=6, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.buttons.save"), style="Success.TButton",
              command=save_screening).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton",
              command=form_window.destroy).pack(side="left", padx=5)

def edit_selected_screening(self):
    """Edit selected screening."""
    selected = self.screening_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_screening_to_edit"))
        return

    screening_id = self.screening_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM screenings WHERE id = ?", (screening_id,))
        screening = cursor.fetchone()
    finally:
        conn.close()

    if not screening:
        return

    form_window = tk.Toplevel(self.root)
    form_window.title("Edit Screening")
    form_window.geometry("400x300")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    # Screen
    tk.Label(fields_frame, text=_t("cinema.screenings.screen_label"), bg="#ffffff", fg="#333333").grid(row=0, column=0, sticky="w", pady=5)
    screen_var = tk.StringVar(value=str(screening[2]))
    screen_combo = ttk.Combobox(fields_frame, textvariable=screen_var, width=30,
                                values=[str(i) for i in range(1, 11)])
    screen_combo.grid(row=0, column=1, pady=5)

    # Price
    tk.Label(fields_frame, text=_t("cinema.screenings.price_label"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    price_entry = ttk.Entry(fields_frame, width=33)
    price_entry.insert(0, str(screening[4]))
    price_entry.grid(row=1, column=1, pady=5)

    # Status
    tk.Label(fields_frame, text=_t("cinema.screenings.status_label"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    status_var = tk.StringVar(value=screening[5] or "active")
    status_combo = ttk.Combobox(fields_frame, textvariable=status_var, width=30,
                                values=["active", "cancelled"])
    status_combo.grid(row=2, column=1, pady=5)

    def save_changes():
        try:
            price = float(price_entry.get())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.errors.invalid_price_short"))
            return

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE screenings SET screen_number=?, price=?, status=? WHERE id=?
            ''', (int(screen_var.get()), price, status_var.get(), screening_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Screening updated!")
        form_window.destroy()
        self.show_screening_management()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.buttons.save"), style="Success.TButton", command=save_changes).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton", command=form_window.destroy).pack(side="left", padx=5)

def cancel_selected_screening(self):
    """Cancel selected screening."""
    selected = self.screening_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_screening_to_cancel"))
        return

    screening_id = self.screening_tree.item(selected[0])['values'][0]

    if not messagebox.askyesno(_t("cinema.common.confirm"), _t("cinema.messages.confirm.cancel_screening")):
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        cursor.execute("UPDATE screenings SET status = 'cancelled' WHERE id = ?", (screening_id,))
        cursor.execute("UPDATE seats SET status = 'available' WHERE screening_id = ?", (screening_id,))
        cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE screening_id = ?", (screening_id,))

        conn.commit()
    finally:
        conn.close()

    messagebox.showinfo(_t("cinema.common.success"), "Screening cancelled")
    self.show_screening_management()
