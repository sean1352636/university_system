"""
Cinema Booking System - Payment Processing

Functions for displaying the payment form with promo code support,
processing bookings, and generating printable tickets.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import json

# i18n support
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE, generate_booking_ref
from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import SNACKS_MENU

# Finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        record_payment_to_finance
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    def process_student_finance_account_payment(*args, **kwargs):
        return {'success': False, 'message': 'Finance integration not available'}
    def get_student_finance_account_balance(*args, **kwargs):
        return None
    def record_payment_to_finance(*args, **kwargs):
        return None

# QR code support
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

def show_payment_page(self, screening, movie):
    """Display payment form with promo code."""
    self.clear_content()
    self.applied_promo = None

    subtotal = sum(price for _, price in self.ticket_types.values())
    snacks_total = sum(SNACKS_MENU[item] * qty for item, qty in self.selected_snacks.items())

    ttk.Label(self.content_frame, text=_t("cinema.booking.complete_booking"),
             style="Subtitle.TLabel").pack(pady=10)

    # Order summary
    summary_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=20)
    summary_frame.pack(fill="x", pady=10)

    tk.Label(summary_frame, text=f"Movie: {movie[1]}", font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    tk.Label(summary_frame, text=f"Date/Time: {screening[3]}",
            bg="#ffffff", fg="#333333").pack(anchor="w")

    # Ticket breakdown
    types_summary = {}
    for t, p in self.ticket_types.values():
        if t not in types_summary:
            types_summary[t] = {"count": 0, "total": 0}
        types_summary[t]["count"] += 1
        types_summary[t]["total"] += p

    for ticket_type, data in types_summary.items():
        tk.Label(summary_frame, text=f"  {ticket_type} x{data['count']}: £{data['total']:.2f}",
                bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    tk.Label(summary_frame, text=f"Tickets Subtotal: £{subtotal:.2f}",
            bg="#ffffff", fg="#333333").pack(anchor="w")

    # Snacks
    if self.selected_snacks:
        tk.Label(summary_frame, text=_t("cinema.booking.snacks_label"), bg="#ffffff", fg="#333333").pack(anchor="w", pady=(10, 0))
        for item, qty in self.selected_snacks.items():
            tk.Label(summary_frame, text=f"  {item} x{qty}: £{SNACKS_MENU[item] * qty:.2f}",
                    bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
        tk.Label(summary_frame, text=f"Snacks Subtotal: £{snacks_total:.2f}",
                bg="#ffffff", fg="#333333").pack(anchor="w")

    # Promo code section
    promo_frame = ttk.Frame(summary_frame, style="Card.TFrame")
    promo_frame.pack(fill="x", pady=10)

    tk.Label(promo_frame, text=_t("cinema.booking.promo_code"), bg="#ffffff", fg="#333333").pack(side="left")
    promo_entry = ttk.Entry(promo_frame, width=15)
    promo_entry.pack(side="left", padx=10)

    self.promo_status_label = tk.Label(promo_frame, text="", bg="#ffffff", fg="#27ae60")
    self.promo_status_label.pack(side="left", padx=10)

    self.discount_amount = 0
    self.total_label = tk.Label(summary_frame, text=f"Total: £{subtotal + snacks_total:.2f}",
                                font=("Helvetica", 16, "bold"), bg="#ffffff", fg="#27ae60")
    self.total_label.pack(anchor="w", pady=(10, 0))

    def apply_promo():
        code = promo_entry.get().strip().upper()
        if not code:
            return

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM promo_codes
                WHERE code = ? AND status = 'active'
                AND (valid_from IS NULL OR valid_from <= date('now'))
                AND (valid_until IS NULL OR valid_until >= date('now'))
                AND (max_uses IS NULL OR times_used < max_uses)
            ''', (code,))
            promo = cursor.fetchone()
        finally:
            conn.close()

        if not promo:
            self.promo_status_label.config(text=_t("cinema.booking.invalid_promo"), fg="#dc3545")
            self.applied_promo = None
            self.discount_amount = 0
        else:
            min_purchase = promo[4]
            if subtotal + snacks_total < min_purchase:
                self.promo_status_label.config(text=f"Min. £{min_purchase:.2f} required", fg="#dc3545")
                return

            if promo[2] == 'percentage':
                self.discount_amount = (subtotal + snacks_total) * (promo[3] / 100)
            else:
                self.discount_amount = promo[3]

            self.applied_promo = promo
            self.promo_status_label.config(text=f"-£{self.discount_amount:.2f} applied!", fg="#27ae60")

        new_total = subtotal + snacks_total - self.discount_amount
        self.total_label.config(text=f"Total: £{new_total:.2f}")

    ttk.Button(promo_frame, text=_t("cinema.booking.apply_promo"), style="Success.TButton",
              command=apply_promo).pack(side="left")

    # Customer form
    form_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=20)
    form_frame.pack(fill="x", pady=10)

    tk.Label(form_frame, text=_t("cinema.booking.customer_details"), font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#333333").pack(anchor="w", pady=(0, 10))

    fields_frame = ttk.Frame(form_frame, style="Card.TFrame")
    fields_frame.pack(fill="x")

    tk.Label(fields_frame, text=_t("cinema.booking.name_label"), bg="#ffffff", fg="#333333").grid(row=0, column=0, sticky="w", pady=5)
    name_entry = ttk.Entry(fields_frame, width=40)
    name_entry.grid(row=0, column=1, pady=5, padx=10)

    tk.Label(fields_frame, text=_t("cinema.booking.email_label"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    email_entry = ttk.Entry(fields_frame, width=40)
    email_entry.grid(row=1, column=1, pady=5, padx=10)

    tk.Label(fields_frame, text=_t("cinema.booking.phone_label"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    phone_entry = ttk.Entry(fields_frame, width=40)
    phone_entry.grid(row=2, column=1, pady=5, padx=10)

    # Auto-fill customer details from logged-in user
    user_info = self.get_current_user_info()
    if user_info:
        if user_info.get('name'):
            name_entry.insert(0, user_info['name'])
        if user_info.get('email'):
            email_entry.insert(0, user_info['email'])
        self.booking_student_id = user_info.get('student_id', '')

    tk.Label(fields_frame, text=_t("cinema.payment.payment_label"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    payment_var = tk.StringVar(value="Credit Card")
    payment_combo = ttk.Combobox(fields_frame, textvariable=payment_var, width=37,
                                 values=["Credit Card", "Debit Card", "PayPal", "Cash", "Gift Card", "Student Account", "Split Payment"])
    payment_combo.grid(row=3, column=1, pady=5, padx=10)

    # Student account balance display
    student_balance_label = tk.Label(fields_frame, text="", bg="#ffffff", fg="#27ae60")
    student_balance_label.grid(row=4, column=1, sticky="w", pady=2, padx=10)

    def on_payment_change(*args):
        if payment_var.get() == "Student Account":
            # Show balance info
            student_id = self.booking_student_id
            if not student_id:
                student_id = tk.simpledialog.askstring("Student Account", "Enter your Student ID:")
                if student_id:
                    self.booking_student_id = student_id
            if student_id and FINANCE_AVAILABLE:
                balance = get_student_finance_account_balance(student_id)
                if balance is not None:
                    student_balance_label.config(text=f"Account Balance: £{balance:.2f}")
                else:
                    student_balance_label.config(text=_t("cinema.messages.errors.student_not_found"), fg="#dc3545")
            else:
                student_balance_label.config(text="")
        else:
            student_balance_label.config(text="")

    payment_var.trace('w', on_payment_change)

    # Split payment details storage
    self.split_payments = []

    def configure_split_payment():
        final_total = subtotal + snacks_total - self.discount_amount
        split_win = tk.Toplevel(self.root)
        split_win.title("Split Payment")
        split_win.geometry("450x500")
        split_win.configure(bg="#ecf0f1")
        split_win.transient(self.root)
        split_win.grab_set()

        frame = ttk.Frame(split_win, style="Card.TFrame", padding=20)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(frame, text=_t("cinema.payment.split_config_title"), font=("Helvetica", 14, "bold"),
                bg="#ffffff", fg="#e74c3c").pack(pady=10)
        tk.Label(frame, text=f"Total Amount: £{final_total:.2f}", font=("Helvetica", 12),
                bg="#ffffff", fg="#27ae60").pack(pady=5)

        # Payment entries
        entries_frame = ttk.Frame(frame, style="Card.TFrame")
        entries_frame.pack(fill="x", pady=10)

        payment_entries = []
        methods = ["Credit Card", "Debit Card", "PayPal", "Cash", "Gift Card"]

        for i in range(3):  # Allow up to 3 split payments
            row = ttk.Frame(entries_frame, style="Card.TFrame")
            row.pack(fill="x", pady=5)

            tk.Label(row, text=f"Payment {i+1}:", bg="#ffffff", fg="#333333").pack(side="left")
            method_var = tk.StringVar(value=methods[i % len(methods)])
            method_cb = ttk.Combobox(row, textvariable=method_var, width=15, values=methods)
            method_cb.pack(side="left", padx=5)

            tk.Label(row, text="£", bg="#ffffff", fg="#333333").pack(side="left")
            amount_e = ttk.Entry(row, width=10)
            amount_e.pack(side="left", padx=5)

            payment_entries.append((method_var, amount_e))

        # Remaining label
        remaining_label = tk.Label(frame, text=f"Remaining: £{final_total:.2f}",
                                  font=("Helvetica", 11), bg="#ffffff", fg="#f4a261")
        remaining_label.pack(pady=10)

        def update_remaining(*args):
            total_entered = 0
            for method_var, amount_e in payment_entries:
                try:
                    total_entered += float(amount_e.get() or 0)
                except ValueError:
                    pass
            remaining = final_total - total_entered
            if remaining < -0.01:
                remaining_label.config(text=f"Overpaid by £{-remaining:.2f}!", fg="#dc3545")
            elif remaining < 0.01:
                remaining_label.config(text=_t("cinema.payment.fully_allocated"), fg="#27ae60")
            else:
                remaining_label.config(text=f"Remaining: £{remaining:.2f}", fg="#f4a261")

        for _, amount_e in payment_entries:
            amount_e.bind("<KeyRelease>", update_remaining)

        def confirm_split():
            self.split_payments = []
            total_entered = 0
            for method_var, amount_e in payment_entries:
                try:
                    amount = float(amount_e.get() or 0)
                    if amount > 0:
                        self.split_payments.append({
                            'method': method_var.get(),
                            'amount': amount
                        })
                        total_entered += amount
                except ValueError:
                    pass

            if abs(total_entered - final_total) > 0.01:
                messagebox.showwarning(_t("cinema.common.warning"), f"Total must equal £{final_total:.2f}\nCurrent: £{total_entered:.2f}")
                return

            if len(self.split_payments) < 2:
                messagebox.showwarning(_t("cinema.common.warning"), "Split payment requires at least 2 payment methods")
                return

            payment_var.set("Split Payment")
            messagebox.showinfo(_t("cinema.common.success"), f"Split payment configured:\n" +
                               "\n".join([f"• {p['method']}: £{p['amount']:.2f}" for p in self.split_payments]))
            split_win.destroy()

        ttk.Button(frame, text=_t("cinema.payment.confirm_split"), style="Success.TButton",
                  command=confirm_split).pack(pady=20)

    # Add split payment button
    split_btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    split_btn_frame.grid(row=4, column=1, sticky="w", pady=5, padx=10)
    ttk.Button(split_btn_frame, text=_t("cinema.payment.configure_split"), style="Secondary.TButton",
              command=configure_split_payment).pack(side="left")

    def process_payment():
        name = name_entry.get().strip()
        email = email_entry.get().strip()
        phone = phone_entry.get().strip()
        payment = payment_var.get()

        if not name:
            messagebox.showwarning(_t("cinema.common.warning", default="Warning"), _t("cinema.messages.warnings.enter_name", default="Please enter your name"))
            return

        final_total = subtotal + snacks_total - self.discount_amount
        booking_ref = generate_booking_ref()
        self.current_booking_ref = booking_ref

        # Handle Student Account payment
        if payment == "Student Account":
            student_id = self.booking_student_id
            if not student_id:
                student_id = simpledialog.askstring("Student Account", "Enter your Student ID:")
                if not student_id:
                    messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.enter_student_id"))
                    return
                self.booking_student_id = student_id

            if FINANCE_AVAILABLE:
                # Check balance
                balance = get_student_finance_account_balance(student_id)
                if balance is None:
                    messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.student_not_found"))
                    return
                if balance < final_total:
                    messagebox.showerror(_t("cinema.common.error"), f"Insufficient balance.\nRequired: £{final_total:.2f}\nAvailable: £{balance:.2f}")
                    return

                # Process student account payment
                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=final_total,
                    description=f"Cinema booking - {movie[1]}",
                    transaction_source="Cinema",
                    transaction_ref=booking_ref
                )
                if not result.get('success'):
                    messagebox.showerror(_t("cinema.common.error"), f"Payment failed: {result.get('message', 'Unknown error')}")
                    return
            else:
                messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.payment_not_available"))
                return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            # Create booking
            ticket_types_json = json.dumps({str(k): v for k, v in self.ticket_types.items()})
            snacks_json = json.dumps(self.selected_snacks) if self.selected_snacks else None

            cursor.execute('''
                INSERT INTO bookings
                (booking_ref, customer_name, customer_email, customer_phone,
                 screening_id, ticket_types, subtotal, discount_amount, promo_code,
                 snacks_total, snacks_items, total_amount, payment_status, payment_method, booking_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', ?, ?)
            ''', (booking_ref, name, email, phone, screening[0], ticket_types_json, subtotal,
                  self.discount_amount, self.applied_promo[1] if self.applied_promo else None,
                  snacks_total, snacks_json, final_total, payment,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            booking_id = cursor.lastrowid

            # Book seats
            for seat_id in self.selected_seats:
                cursor.execute("UPDATE seats SET status = 'booked' WHERE id = ?", (seat_id,))
                ticket_type = self.ticket_types.get(seat_id, ("Adult", 0))[0]
                cursor.execute("INSERT INTO booked_seats (booking_id, seat_id, ticket_type) VALUES (?, ?, ?)",
                             (booking_id, seat_id, ticket_type))

            # Update promo code usage
            if self.applied_promo:
                cursor.execute("UPDATE promo_codes SET times_used = times_used + 1 WHERE id = ?",
                             (self.applied_promo[0],))

            conn.commit()

            # Record revenue to central finance system
            if FINANCE_AVAILABLE and payment != "Student Account":
                # Student account already recorded via process_student_finance_account_payment
                try:
                    record_payment_to_finance(
                        student_id=self.booking_student_id or "GUEST",
                        amount=final_total,
                        payment_method=payment,
                        transaction_source="Cinema",
                        transaction_ref=booking_ref,
                        currency="GBP",
                        status="completed",
                        notes=f"Cinema booking: {movie[1]}"
                    )
                except Exception:
                    pass  # Don't fail booking if finance recording fails

            # Get seats for receipt
            cursor_seats = conn.cursor()
            cursor_seats.execute('''
                SELECT se.row, se.seat_number FROM booked_seats bs
                JOIN seats se ON bs.seat_id = se.id
                WHERE bs.booking_id = ?
            ''', (booking_id,))
            seat_list = [f"{r}{n}" for r, n in cursor_seats.fetchall()]
            seats_str = ", ".join(seat_list)

            # Send email receipt
            if email:
                self.send_booking_receipt(
                    booking_ref=booking_ref,
                    customer_email=email,
                    customer_name=name,
                    movie_title=movie[1],
                    show_time=screening[3],
                    seats=seats_str,
                    total=final_total,
                    payment_method=payment
                )

            # Show success and offer to print
            if messagebox.askyesno(_t("cinema.messages.success.booking_confirmed"),
                f"Booking confirmed!\n\nReference: {booking_ref}\n"
                f"Movie: {movie[1]}\nSeats: {len(self.selected_seats)}\n"
                f"Total: £{final_total:.2f}\n\nWould you like to print your ticket?"):
                self.print_ticket(booking_ref)

            self.selected_seats = []
            self.ticket_types = {}
            self.selected_snacks = {}
            self.booking_student_id = None
            self.show_dashboard()

        except Exception as e:
            conn.rollback()
            messagebox.showerror(_t("cinema.common.error"), f"Booking failed: {str(e)}")
        finally:
            conn.close()

    ttk.Button(self.content_frame, text=_t("cinema.booking.complete_payment"), style="Primary.TButton",
              command=process_payment).pack(pady=20)

def print_ticket(self, booking_ref):
    """Generate and display printable ticket."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, m.title, s.show_time, s.screen_number
            FROM bookings b
            JOIN screenings s ON b.screening_id = s.id
            JOIN movies m ON s.movie_id = m.id
            WHERE b.booking_ref = ?
        ''', (booking_ref,))
        booking = cursor.fetchone()

        cursor.execute('''
            SELECT se.row, se.seat_number, bs.ticket_type
            FROM booked_seats bs
            JOIN seats se ON bs.seat_id = se.id
            WHERE bs.booking_id = ?
        ''', (booking[0],))
        seats = cursor.fetchall()
    finally:
        conn.close()

    if not booking:
        messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.booking_not_found"))
        return

    # Create print window
    print_window = tk.Toplevel(self.root)
    print_window.title(f"Ticket - {booking_ref}")
    print_window.geometry("500x600")
    print_window.configure(bg="white")

    # Ticket content
    ticket_frame = tk.Frame(print_window, bg="white", padx=30, pady=20)
    ticket_frame.pack(fill="both", expand=True)

    tk.Label(ticket_frame, text=_t("cinema.tickets.cinema_ticket"), font=("Helvetica", 20, "bold"),
            bg="white", fg="#e74c3c").pack(pady=10)

    tk.Label(ticket_frame, text="=" * 40, bg="white", fg="black").pack()

    tk.Label(ticket_frame, text=booking[-3], font=("Helvetica", 16, "bold"),
            bg="white", fg="black").pack(pady=10)

    details = [
        f"Booking Reference: {booking[1]}",
        f"Customer: {booking[2]}",
        f"Date/Time: {booking[-2]}",
        f"Screen: {booking[-1]}",
        "",
        "SEATS:",
    ]

    for detail in details:
        tk.Label(ticket_frame, text=detail, font=("Helvetica", 11),
                bg="white", fg="black").pack(anchor="w")

    for seat in seats:
        tk.Label(ticket_frame, text=f"  Row {seat[0]} Seat {seat[1]} ({seat[2]})",
                font=("Helvetica", 10), bg="white", fg="#333333").pack(anchor="w")

    tk.Label(ticket_frame, text="", bg="white").pack()
    tk.Label(ticket_frame, text=f"Total Paid: £{booking[12]:.2f}",
            font=("Helvetica", 14, "bold"), bg="white", fg="#27ae60").pack()

    tk.Label(ticket_frame, text="=" * 40, bg="white", fg="black").pack(pady=10)

    tk.Label(ticket_frame, text=_t("cinema.tickets.arrival_notice"),
            font=("Helvetica", 9), bg="white", fg="#666666").pack()
    tk.Label(ticket_frame, text=_t("cinema.tickets.present_notice"),
            font=("Helvetica", 9), bg="white", fg="#666666").pack()

    # QR Code generation
    try:
        qr_data = f"CINEMA-TICKET:{booking_ref}|{booking[2]}|{booking[-3]}|{booking[-2]}"
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert to PhotoImage
        from io import BytesIO
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        buffer.seek(0)

        from PIL import Image, ImageTk
        pil_img = Image.open(buffer)
        photo = ImageTk.PhotoImage(pil_img)

        qr_label = tk.Label(ticket_frame, image=photo, bg="white")
        qr_label.image = photo  # Keep reference
        qr_label.pack(pady=10)

        tk.Label(ticket_frame, text=_t("cinema.tickets.qr_notice"),
                font=("Helvetica", 8), bg="white", fg="#666666").pack()
    except Exception as e:
        # QR code generation failed - show text alternative
        tk.Label(ticket_frame, text=f"[QR Code: {booking_ref}]",
                font=("Courier", 10), bg="white", fg="#333333").pack(pady=10)

    # Print button (simulated)
    def do_print():
        messagebox.showinfo(_t("cinema.common.print"), "Ticket sent to printer!\n(In a real system, this would print)")
        print_window.destroy()

    def save_ticket():
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")],
                initialfile=f"ticket_{booking_ref}.txt"
            )
            if filename:
                with open(filename, 'w') as f:
                    f.write("=" * 50 + "\n")
                    f.write("           CINEMA TICKET\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Movie: {booking[-3]}\n")
                    f.write(f"Booking Reference: {booking[1]}\n")
                    f.write(f"Customer: {booking[2]}\n")
                    f.write(f"Date/Time: {booking[-2]}\n")
                    f.write(f"Screen: {booking[-1]}\n\n")
                    f.write("SEATS:\n")
                    for seat in seats:
                        f.write(f"  Row {seat[0]} Seat {seat[1]} ({seat[2]})\n")
                    f.write(f"\nTotal Paid: £{booking[12]:.2f}\n\n")
                    f.write("=" * 50 + "\n")
                    f.write("Please arrive 15 minutes before showtime\n")
                    f.write("Present this ticket at the entrance\n")
                messagebox.showinfo(_t("cinema.messages.success.saved"), f"Ticket saved to {filename}")
        except Exception as e:
            messagebox.showerror(_t("cinema.common.error"), f"Failed to save: {str(e)}")

    btn_row = tk.Frame(ticket_frame, bg="white")
    btn_row.pack(pady=20)
    tk.Button(btn_row, text=_t("cinema.tickets.print_ticket"), font=("Helvetica", 12),
             bg="#e94560", fg="white", command=do_print).pack(side="left", padx=5)
    tk.Button(btn_row, text=_t("cinema.tickets.save_ticket"), font=("Helvetica", 12),
             bg="#4ecca3", fg="white", command=save_ticket).pack(side="left", padx=5)
