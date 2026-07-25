"""
Cinema Reports - Export, save, email, and report window functions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import csv
from datetime import datetime

from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.reports._imports import sqlite3, DB_FILE, _t, EMAIL_AVAILABLE, send_email


def export_report_csv(self, report_type, from_date, to_date):
    """Export report data to CSV."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if report_type == "sales_summary":
        cursor.execute('''
            SELECT booking_ref, customer_name, customer_email, total_amount,
                   payment_method, status, booking_time
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            ORDER BY booking_time DESC
        ''', (from_date, to_date))
        headers = ["Booking Ref", _t("cinema.columns.customer"), "Email", "Amount", "Payment", "Status", "Date"]

    elif report_type == "revenue_by_movie":
        cursor.execute('''
            SELECT m.title, COUNT(b.id), COALESCE(SUM(b.total_amount), 0)
            FROM movies m
            LEFT JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id AND date(b.booking_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
            ORDER BY COALESCE(SUM(b.total_amount), 0) DESC
        ''', (from_date, to_date))
        headers = ["Movie", "Bookings", "Revenue"]

    elif report_type == "daily_sales":
        cursor.execute('''
            SELECT date(booking_time), COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY date(booking_time)
            ORDER BY date(booking_time)
        ''', (from_date, to_date))
        headers = ["Date", "Bookings", "Revenue"]

    else:
        cursor.execute('''
            SELECT * FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
        ''', (from_date, to_date))
        headers = ["ID", "Ref", "Name", "Email", "Phone", "Screening", "Ticket Types",
                  "Subtotal", "Discount", "Promo", "Snacks Total", "Snacks", "Total",
                  "Pay Status", "Pay Method", "Time", "Status", "Notes"]

    data = cursor.fetchall()
    conn.close()

    if not data:
        messagebox.showinfo(_t("cinema.common.info"), _t("cinema.messages.warnings.no_data_to_export"))
        return

    filename = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile=f"cinema_report_{report_type}_{from_date}_{to_date}.csv"
    )

    if not filename:
        return

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)

        messagebox.showinfo(_t("cinema.common.success"), f"Report exported to:\n{filename}")
    except Exception as e:
        messagebox.showerror(_t("cinema.common.error"), f"Export failed: {str(e)}")


def save_report_txt(self, report_type, from_date, to_date):
    """Save report as TXT file."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    report_titles = {
        "sales_summary": "Sales Summary Report",
        "revenue_by_movie": "Revenue by Movie Report",
        "daily_sales": "Daily Sales Report",
        "occupancy": "Occupancy Report",
        "payment_methods": "Payment Methods Report",
        "booking_status": "Booking Status Report"
    }

    title = report_titles.get(report_type, "Cinema Report")

    # Get data based on report type
    if report_type == "sales_summary":
        cursor.execute('''
            SELECT booking_ref, customer_name, customer_email, total_amount,
                   payment_method, status, booking_time
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            ORDER BY booking_time DESC
        ''', (from_date, to_date))
        headers = ["Booking Ref", _t("cinema.columns.customer"), "Email", "Amount", "Payment", "Status", "Date"]
    elif report_type == "revenue_by_movie":
        cursor.execute('''
            SELECT m.title, COUNT(b.id), COALESCE(SUM(b.total_amount), 0)
            FROM movies m
            LEFT JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id AND date(b.booking_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
            ORDER BY COALESCE(SUM(b.total_amount), 0) DESC
        ''', (from_date, to_date))
        headers = ["Movie", "Bookings", "Revenue (\u00a3)"]
    elif report_type == "daily_sales":
        cursor.execute('''
            SELECT date(booking_time), COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY date(booking_time)
            ORDER BY date(booking_time)
        ''', (from_date, to_date))
        headers = ["Date", "Bookings", "Revenue (\u00a3)"]
    elif report_type == "occupancy":
        cursor.execute('''
            SELECT m.title,
                   COUNT(bs.id) as booked,
                   COUNT(DISTINCT se.id) as total_seats
            FROM movies m
            JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id
            LEFT JOIN booked_seats bs ON b.id = bs.booking_id
            LEFT JOIN seats se ON s.id = se.screening_id
            WHERE date(s.show_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
        ''', (from_date, to_date))
        headers = ["Movie", "Booked Seats", "Total Seats"]
    elif report_type == "payment_methods":
        cursor.execute('''
            SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY payment_method
        ''', (from_date, to_date))
        headers = ["Payment Method", "Bookings", "Revenue (\u00a3)"]
    else:  # booking_status
        cursor.execute('''
            SELECT status, COUNT(*)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY status
        ''', (from_date, to_date))
        headers = ["Status", "Count"]

    data = cursor.fetchall()
    conn.close()

    if not data:
        messagebox.showinfo(_t("cinema.common.info"), _t("cinema.messages.warnings.no_data_to_save"))
        return

    filename = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        initialfile=f"cinema_report_{report_type}_{from_date}_{to_date}.txt"
    )

    if not filename:
        return

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"{title}\n")
            f.write(f"Period: {from_date} to {to_date}\n")
            f.write("=" * 80 + "\n\n")
            f.write("\t".join(headers) + "\n")
            f.write("-" * 80 + "\n")
            for row in data:
                f.write("\t".join(str(val) for val in row) + "\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        messagebox.showinfo(_t("cinema.common.success"), f"Report saved to:\n{filename}")
    except Exception as e:
        messagebox.showerror(_t("cinema.common.error"), f"Save failed: {str(e)}")


def email_report_to_admin(self, report_type, from_date, to_date):
    """Email report to admin."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # First try to get admin email from cinema_settings
    cursor.execute("SELECT value FROM cinema_settings WHERE key = 'admin_email'")
    result = cursor.fetchone()
    admin_email = result[0] if result else None

    # If not in settings, try to get from users table (admin/staff)
    if not admin_email:
        cursor.execute("""
            SELECT email FROM users
            WHERE role IN ('admin', 'administrator', 'staff', 'Admin', 'Administrator', 'Staff')
            AND email IS NOT NULL AND email != ''
            ORDER BY CASE
                WHEN role IN ('admin', 'Admin', 'administrator', 'Administrator') THEN 1
                ELSE 2
            END
            LIMIT 1
        """)
        result = cursor.fetchone()
        if result:
            admin_email = result[0]
            # Save it to settings for future use
            try:
                cursor.execute("""INSERT OR REPLACE INTO cinema_settings (key, value)
                                VALUES ('admin_email', ?)""", (admin_email,))
                conn.commit()
            except Exception:
                pass

    # If still not found, prompt for it
    if not admin_email:
        admin_email = simpledialog.askstring("Admin Email",
            "No admin email configured.\nEnter admin email address:")
        if admin_email:
            # Save it for future use
            cursor.execute("""INSERT OR REPLACE INTO cinema_settings (key, value)
                            VALUES ('admin_email', ?)""", (admin_email,))
            conn.commit()

    if not admin_email:
        conn.close()
        return

    report_titles = {
        "sales_summary": "Sales Summary Report",
        "revenue_by_movie": "Revenue by Movie Report",
        "daily_sales": "Daily Sales Report",
        "occupancy": "Occupancy Report",
        "payment_methods": "Payment Methods Report",
        "booking_status": "Booking Status Report"
    }

    title = report_titles.get(report_type, "Cinema Report")

    # Get data based on report type
    if report_type == "sales_summary":
        cursor.execute('''
            SELECT booking_ref, customer_name, customer_email, total_amount,
                   payment_method, status, booking_time
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            ORDER BY booking_time DESC
        ''', (from_date, to_date))
        headers = ["Booking Ref", _t("cinema.columns.customer"), "Email", "Amount", "Payment", "Status", "Date"]
    elif report_type == "revenue_by_movie":
        cursor.execute('''
            SELECT m.title, COUNT(b.id), COALESCE(SUM(b.total_amount), 0)
            FROM movies m
            LEFT JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id AND date(b.booking_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
            ORDER BY COALESCE(SUM(b.total_amount), 0) DESC
        ''', (from_date, to_date))
        headers = ["Movie", "Bookings", "Revenue (\u00a3)"]
    elif report_type == "daily_sales":
        cursor.execute('''
            SELECT date(booking_time), COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY date(booking_time)
            ORDER BY date(booking_time)
        ''', (from_date, to_date))
        headers = ["Date", "Bookings", "Revenue (\u00a3)"]
    elif report_type == "occupancy":
        cursor.execute('''
            SELECT m.title,
                   COUNT(bs.id) as booked,
                   COUNT(DISTINCT se.id) as total_seats
            FROM movies m
            JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id
            LEFT JOIN booked_seats bs ON b.id = bs.booking_id
            LEFT JOIN seats se ON s.id = se.screening_id
            WHERE date(s.show_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
        ''', (from_date, to_date))
        headers = ["Movie", "Booked Seats", "Total Seats"]
    elif report_type == "payment_methods":
        cursor.execute('''
            SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY payment_method
        ''', (from_date, to_date))
        headers = ["Payment Method", "Bookings", "Revenue (\u00a3)"]
    else:  # booking_status
        cursor.execute('''
            SELECT status, COUNT(*)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY status
        ''', (from_date, to_date))
        headers = ["Status", "Count"]

    data = cursor.fetchall()
    conn.close()

    if not data:
        messagebox.showinfo(_t("cinema.common.info"), _t("cinema.messages.warnings.no_data_to_email"))
        return

    if EMAIL_AVAILABLE:
        # Build report content
        report_content = f"{title}\n"
        report_content += f"Period: {from_date} to {to_date}\n"
        report_content += "=" * 80 + "\n\n"
        report_content += "\t".join(headers) + "\n"
        report_content += "-" * 80 + "\n"
        for row in data:
            report_content += "\t".join(str(val) for val in row) + "\n"
        report_content += "\n" + "=" * 80 + "\n"
        report_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_content += "\n---\nUniversity Cinema System\n"

        try:
            send_email(admin_email, f"Cinema Report: {title}", report_content)
            messagebox.showinfo(_t("cinema.common.success"), f"Report sent to {admin_email}")
        except Exception as e:
            messagebox.showerror(_t("cinema.common.error"), f"Email failed: {str(e)}")
    else:
        messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.email_not_available"))


def open_report_in_window(self, report_type, from_date, to_date):
    """Open report in a new window with save options."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    report_titles = {
        "sales_summary": "Sales Summary Report",
        "revenue_by_movie": "Revenue by Movie Report",
        "daily_sales": "Daily Sales Report",
        "occupancy": "Occupancy Report",
        "payment_methods": "Payment Methods Report",
        "booking_status": "Booking Status Report"
    }

    if report_type == "sales_summary":
        cursor.execute('''
            SELECT booking_ref, customer_name, customer_email, total_amount,
                   payment_method, status, booking_time
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            ORDER BY booking_time DESC
        ''', (from_date, to_date))
        headers = ["Booking Ref", _t("cinema.columns.customer"), "Email", "Amount", "Payment", "Status", "Date"]
    elif report_type == "revenue_by_movie":
        cursor.execute('''
            SELECT m.title, COUNT(b.id), COALESCE(SUM(b.total_amount), 0)
            FROM movies m
            LEFT JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id AND date(b.booking_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
            ORDER BY COALESCE(SUM(b.total_amount), 0) DESC
        ''', (from_date, to_date))
        headers = ["Movie", "Bookings", "Revenue (\u00a3)"]
    elif report_type == "daily_sales":
        cursor.execute('''
            SELECT date(booking_time), COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY date(booking_time)
            ORDER BY date(booking_time)
        ''', (from_date, to_date))
        headers = ["Date", "Bookings", "Revenue (\u00a3)"]
    elif report_type == "occupancy":
        cursor.execute('''
            SELECT m.title,
                   COUNT(bs.id) as booked,
                   COUNT(DISTINCT se.id) as total_seats
            FROM movies m
            JOIN screenings s ON m.id = s.movie_id
            LEFT JOIN bookings b ON s.id = b.screening_id
            LEFT JOIN booked_seats bs ON b.id = bs.booking_id
            LEFT JOIN seats se ON s.id = se.screening_id
            WHERE date(s.show_time) BETWEEN ? AND ?
            GROUP BY m.id, m.title
        ''', (from_date, to_date))
        headers = ["Movie", "Booked Seats", "Total Seats"]
    elif report_type == "payment_methods":
        cursor.execute('''
            SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY payment_method
        ''', (from_date, to_date))
        headers = ["Payment Method", "Bookings", "Revenue (\u00a3)"]
    else:  # booking_status
        cursor.execute('''
            SELECT status, COUNT(*)
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY status
        ''', (from_date, to_date))
        headers = ["Status", "Count"]

    data = cursor.fetchall()
    conn.close()

    title = report_titles.get(report_type, "Report")

    # Create new window
    win = tk.Toplevel(self.root)
    win.title(f"{title} ({from_date} to {to_date})")
    win.geometry("800x600")
    win.configure(bg="#ecf0f1")

    # Title
    tk.Label(win, text=title, font=("Helvetica", 16, "bold"),
            bg="#ecf0f1", fg="#e74c3c").pack(pady=10)
    tk.Label(win, text=f"Period: {from_date} to {to_date}",
            bg="#ecf0f1", fg="#7f8c8d").pack()

    # Treeview frame
    tree_frame = ttk.Frame(win)
    tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

    tree = ttk.Treeview(tree_frame, columns=headers, show="headings", height=20)
    for col in headers:
        tree.heading(col, text=col)
        tree.column(col, width=100)

    for row in data:
        tree.insert("", "end", values=row)

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Button frame
    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill="x", padx=20, pady=10)

    def save_as_txt():
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"cinema_report_{report_type}_{from_date}_{to_date}.txt"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"{title}\n")
                    f.write(f"Period: {from_date} to {to_date}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("\t".join(headers) + "\n")
                    f.write("-" * 60 + "\n")
                    for row in data:
                        f.write("\t".join(str(val) for val in row) + "\n")
                messagebox.showinfo(_t("cinema.common.success"), f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror(_t("cinema.common.error"), f"Save failed: {str(e)}")

    def save_as_csv():
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"cinema_report_{report_type}_{from_date}_{to_date}.csv"
        )
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(data)
                messagebox.showinfo(_t("cinema.common.success"), f"Report exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror(_t("cinema.common.error"), f"Export failed: {str(e)}")

    def email_to_admin():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # First try to get admin email from cinema_settings
        cursor.execute("SELECT value FROM cinema_settings WHERE key = 'admin_email'")
        result = cursor.fetchone()
        admin_email = result[0] if result else None

        # If not in settings, try to get from users table (admin/staff)
        if not admin_email:
            cursor.execute("""
                SELECT email FROM users
                WHERE role IN ('admin', 'administrator', 'staff', 'Admin', 'Administrator', 'Staff')
                AND email IS NOT NULL AND email != ''
                ORDER BY CASE
                    WHEN role IN ('admin', 'Admin', 'administrator', 'Administrator') THEN 1
                    ELSE 2
                END
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                admin_email = result[0]
                # Save it to settings for future use
                try:
                    cursor.execute("""INSERT OR REPLACE INTO cinema_settings (key, value)
                                    VALUES ('admin_email', ?)""", (admin_email,))
                    conn.commit()
                except Exception:
                    pass

        # If still not found, prompt for it
        if not admin_email:
            admin_email = simpledialog.askstring("Admin Email",
                "No admin email configured.\nEnter admin email address:")
            if admin_email:
                # Save it for future use
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("""INSERT OR REPLACE INTO cinema_settings (key, value)
                                VALUES ('admin_email', ?)""", (admin_email,))
                conn.commit()
                conn.close()

        if not admin_email:
            return

        if EMAIL_AVAILABLE:
            # Build report content
            report_content = f"{title}\n"
            report_content += f"Period: {from_date} to {to_date}\n"
            report_content += "=" * 60 + "\n\n"
            report_content += "\t".join(headers) + "\n"
            report_content += "-" * 60 + "\n"
            for row in data:
                report_content += "\t".join(str(val) for val in row) + "\n"

            try:
                send_email(admin_email, f"Cinema Report: {title}", report_content)
                messagebox.showinfo(_t("cinema.common.success"), f"Report sent to {admin_email}")
            except Exception as e:
                messagebox.showerror(_t("cinema.common.error"), f"Email failed: {str(e)}")
        else:
            messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.errors.email_not_available"))

    ttk.Button(btn_frame, text=_t("cinema.reports.save_as_txt"), style="Secondary.TButton",
              command=save_as_txt).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.save_as_csv"), style="Secondary.TButton",
              command=save_as_csv).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.email_to_admin"), style="Primary.TButton",
              command=email_to_admin).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.close"), style="Danger.TButton",
              command=win.destroy).pack(side="right", padx=5)
