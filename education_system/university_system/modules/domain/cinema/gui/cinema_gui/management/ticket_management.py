"""
Cinema Booking System - Ticket Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import DB_FILE

def show_ticket_management(self):
    """Display ticket/booking management page."""
    self.clear_content()

    # Header with New Booking button
    header_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    header_frame.pack(fill="x", pady=10)

    ttk.Label(header_frame, text=_t("cinema.tickets.title"),
             style="Subtitle.TLabel").pack(side="left")

    ttk.Button(header_frame, text=_t("cinema.booking.new_booking"), style="Success.TButton",
              command=self.show_movies_page).pack(side="right", padx=10)

    # Search frame
    search_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    search_frame.pack(fill="x", pady=10)

    tk.Label(search_frame, text=_t("cinema.buttons.search_label"), bg="#ffffff", fg="#333333").pack(side="left")
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side="left", padx=10)

    tk.Label(search_frame, text=_t("cinema.screenings.status_label"), bg="#ffffff", fg="#333333").pack(side="left", padx=(20, 5))
    status_var = tk.StringVar(value="all")
    status_combo = ttk.Combobox(search_frame, textvariable=status_var, width=15,
                                values=["all", "active", "cancelled", "pending"])
    status_combo.pack(side="left")

    # Tickets list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Ref", _t("cinema.columns.customer"), "Email", "Movie", "Date/Time", "Seats", "Total", "Status")
    self.ticket_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

    for col in columns:
        self.ticket_tree.heading(col, text=col)
    self.ticket_tree.column("ID", width=50)
    self.ticket_tree.column("Ref", width=80)
    self.ticket_tree.column(_t("cinema.columns.customer"), width=120)
    self.ticket_tree.column("Email", width=150)
    self.ticket_tree.column("Movie", width=150)
    self.ticket_tree.column("Date/Time", width=130)
    self.ticket_tree.column("Seats", width=60)
    self.ticket_tree.column("Total", width=80)
    self.ticket_tree.column("Status", width=80)

    def search_tickets():
        for item in self.ticket_tree.get_children():
            self.ticket_tree.delete(item)

        query = search_entry.get().strip()
        status = status_var.get()

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            sql = '''
                SELECT b.id, b.booking_ref, b.customer_name, b.customer_email,
                       m.title, s.show_time,
                       (SELECT COUNT(*) FROM booked_seats WHERE booking_id = b.id),
                       b.total_amount, b.status
                FROM bookings b
                JOIN screenings s ON b.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
                WHERE 1=1
            '''
            params = []

            if query:
                sql += " AND (b.booking_ref LIKE ? OR b.customer_name LIKE ? OR b.customer_email LIKE ?)"
                params.extend([f"%{escape_like(query)}%", f"%{escape_like(query)}%", f"%{escape_like(query)}%"])

            if status != "all":
                sql += " AND b.status = ?"
                params.append(status)

            sql += " ORDER BY b.booking_time DESC LIMIT 100"

            cursor.execute(sql, params)
            tickets = cursor.fetchall()
        finally:
            conn.close()

        for ticket in tickets:
            self.ticket_tree.insert("", "end", values=(
                ticket[0], ticket[1], ticket[2], ticket[3] or "-",
                ticket[4], ticket[5], ticket[6], f"\u00a3{ticket[7]:.2f}",
                ticket[8].upper()
            ))

    ttk.Button(search_frame, text=_t("cinema.buttons.search"), style="Primary.TButton",
              command=search_tickets).pack(side="left", padx=5)
    ttk.Button(search_frame, text=_t("cinema.buttons.show_all"), style="Secondary.TButton",
              command=lambda: (search_entry.delete(0, tk.END), status_var.set("all"),
                              search_tickets())).pack(side="left", padx=5)

    self.ticket_tree.pack(fill="both", expand=True, side="left")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ticket_tree.yview)
    self.ticket_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons - with padding to ensure visibility
    action_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    action_frame.pack(fill="x", pady=(5, 15))

    ttk.Button(action_frame, text=_t("cinema.buttons.edit_selected"), style="Secondary.TButton",
              command=self.edit_selected_ticket).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.cancel_selected"), style="Danger.TButton",
              command=self.cancel_selected_ticket).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.delete_selected"), style="Danger.TButton",
              command=self.delete_selected_ticket).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.buttons.reactivate_selected"), style="Success.TButton",
              command=self.reactivate_selected_ticket).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.tickets.print_ticket"), style="Primary.TButton",
              command=lambda: self.print_selected_ticket()).pack(side="left", padx=5)

    search_tickets()

def print_selected_ticket(self):
    """Print selected ticket."""
    selected = self.ticket_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_ticket_to_print"))
        return
    ref = self.ticket_tree.item(selected[0])['values'][1]
    self.print_ticket(ref)

def edit_selected_ticket(self):
    """Edit the selected ticket/booking."""
    selected = self.ticket_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_ticket_to_edit"))
        return

    booking_id = self.ticket_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, m.title, s.show_time
            FROM bookings b
            JOIN screenings s ON b.screening_id = s.id
            JOIN movies m ON s.movie_id = m.id
            WHERE b.id = ?
        ''', (booking_id,))
        booking = cursor.fetchone()
    finally:
        conn.close()

    if not booking:
        messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.booking_not_found"))
        return

    form_window = tk.Toplevel(self.root)
    form_window.title(f"Edit Booking {booking[1]}")
    form_window.geometry("500x450")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=f"Edit Booking: {booking[1]}", font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    tk.Label(fields_frame, text=_t("cinema.movies.movie_label"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    tk.Label(fields_frame, text=booking[-2], bg="#ffffff", fg="#7f8c8d").grid(row=1, column=1, sticky="w", pady=5)

    tk.Label(fields_frame, text=_t("cinema.tickets.show_time_label"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    tk.Label(fields_frame, text=booking[-1], bg="#ffffff", fg="#7f8c8d").grid(row=2, column=1, sticky="w", pady=5)

    tk.Label(fields_frame, text=_t("cinema.booking.customer_name"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    name_entry = ttk.Entry(fields_frame, width=40)
    name_entry.insert(0, booking[2])
    name_entry.grid(row=3, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.common.email_label"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    email_entry = ttk.Entry(fields_frame, width=40)
    email_entry.insert(0, booking[3] or "")
    email_entry.grid(row=4, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.members.phone_label"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    phone_entry = ttk.Entry(fields_frame, width=40)
    phone_entry.insert(0, booking[4] or "")
    phone_entry.grid(row=5, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.tickets.payment_method_label"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="w", pady=5)
    payment_var = tk.StringVar(value=booking[14] or "Credit Card")
    payment_combo = ttk.Combobox(fields_frame, textvariable=payment_var, width=37,
                                 values=["Credit Card", "Debit Card", "PayPal", "Cash", "Gift Card"])
    payment_combo.grid(row=6, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.tickets.payment_status_label"), bg="#ffffff", fg="#333333").grid(row=7, column=0, sticky="w", pady=5)
    pay_status_var = tk.StringVar(value=booking[13] or "pending")
    pay_status_combo = ttk.Combobox(fields_frame, textvariable=pay_status_var, width=37,
                                    values=["pending", "paid", "refunded"])
    pay_status_combo.grid(row=7, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.tickets.notes_label"), bg="#ffffff", fg="#333333").grid(row=8, column=0, sticky="nw", pady=5)
    notes_text = tk.Text(fields_frame, width=30, height=3, font=("Helvetica", 10))
    if len(booking) > 17 and booking[17]:
        notes_text.insert("1.0", booking[17])
    notes_text.grid(row=8, column=1, pady=5)

    def save_booking():
        name = name_entry.get().strip()
        if not name:
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.enter_customer_name"))
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE bookings
                SET customer_name=?, customer_email=?, customer_phone=?,
                    payment_method=?, payment_status=?, notes=?
                WHERE id=?
            ''', (name, email_entry.get().strip(), phone_entry.get().strip(),
                  payment_var.get(), pay_status_var.get(), notes_text.get("1.0", tk.END).strip(), booking_id))

            conn.commit()
            messagebox.showinfo(_t("cinema.common.success"), "Booking updated successfully!")
            form_window.destroy()
            self.show_ticket_management()

        except Exception as e:
            conn.rollback()
            messagebox.showerror(_t("cinema.common.error"), f"Failed to update booking: {str(e)}")
        finally:
            conn.close()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=9, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.buttons.save_changes"), style="Success.TButton",
              command=save_booking).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton",
              command=form_window.destroy).pack(side="left", padx=5)

def cancel_selected_ticket(self):
    """Cancel the selected ticket/booking."""
    selected = self.ticket_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_ticket_to_cancel"))
        return

    values = self.ticket_tree.item(selected[0])['values']
    booking_id = values[0]
    booking_ref = values[1]
    current_status = values[8].lower()

    if current_status == "cancelled":
        messagebox.showinfo(_t("cinema.common.info"), _t("cinema.messages.warnings.already_cancelled"))
        return

    if not messagebox.askyesno(_t("cinema.messages.confirm.cancel"),
        f"Are you sure you want to cancel booking {booking_ref}?\n"
        "This will release the booked seats."):
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT seat_id FROM booked_seats WHERE booking_id = ?", (booking_id,))
        seat_ids = cursor.fetchall()

        for (seat_id,) in seat_ids:
            cursor.execute("UPDATE seats SET status = 'available' WHERE id = ?", (seat_id,))

        cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))

        conn.commit()
        messagebox.showinfo(_t("cinema.common.success"), f"Booking {booking_ref} has been cancelled")
        self.show_ticket_management()

    except Exception as e:
        conn.rollback()
        messagebox.showerror(_t("cinema.common.error"), f"Cancellation failed: {str(e)}")
    finally:
        conn.close()

def delete_selected_ticket(self):
    """Permanently delete the selected ticket/booking."""
    selected = self.ticket_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_ticket_to_delete"))
        return

    values = self.ticket_tree.item(selected[0])['values']
    booking_id = values[0]
    booking_ref = values[1]

    if not messagebox.askyesno(_t("cinema.messages.confirm.delete"),
        f"Are you sure you want to PERMANENTLY delete booking {booking_ref}?\n\n"
        "This action cannot be undone!"):
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT seat_id FROM booked_seats WHERE booking_id = ?", (booking_id,))
        seat_ids = cursor.fetchall()

        for (seat_id,) in seat_ids:
            cursor.execute("UPDATE seats SET status = 'available' WHERE id = ?", (seat_id,))

        cursor.execute("DELETE FROM booked_seats WHERE booking_id = ?", (booking_id,))
        cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))

        conn.commit()
        messagebox.showinfo(_t("cinema.common.success"), f"Booking {booking_ref} has been deleted")
        self.show_ticket_management()

    except Exception as e:
        conn.rollback()
        messagebox.showerror(_t("cinema.common.error"), f"Deletion failed: {str(e)}")
    finally:
        conn.close()

def reactivate_selected_ticket(self):
    """Reactivate a cancelled booking."""
    selected = self.ticket_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.select_ticket_to_reactivate"))
        return

    values = self.ticket_tree.item(selected[0])['values']
    booking_id = values[0]
    booking_ref = values[1]
    current_status = values[8].lower()

    if current_status == "active":
        messagebox.showinfo(_t("cinema.common.info"), _t("cinema.messages.warnings.already_active"))
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT seat_id FROM booked_seats WHERE booking_id = ?", (booking_id,))
        seat_ids = [row[0] for row in cursor.fetchall()]

        if seat_ids:
            cursor.execute(
                "SELECT COUNT(*) FROM seats"
                " WHERE id IN (" + ",".join("?" * len(seat_ids)) + ") AND status != 'available'",
                seat_ids)
            unavailable = cursor.fetchone()[0]

            if unavailable > 0:
                messagebox.showerror(_t("cinema.common.error"),
                    f"{unavailable} seat(s) are no longer available.\n"
                    "Cannot reactivate this booking.")
                return

            for seat_id in seat_ids:
                cursor.execute("UPDATE seats SET status = 'booked' WHERE id = ?", (seat_id,))

        cursor.execute("UPDATE bookings SET status = 'active' WHERE id = ?", (booking_id,))

        conn.commit()
        messagebox.showinfo(_t("cinema.common.success"), f"Booking {booking_ref} has been reactivated")
        self.show_ticket_management()

    except Exception as e:
        conn.rollback()
        messagebox.showerror(_t("cinema.common.error"), f"Reactivation failed: {str(e)}")
    finally:
        conn.close()
