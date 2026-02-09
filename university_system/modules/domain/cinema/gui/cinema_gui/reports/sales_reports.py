"""
Cinema Booking System - Sales Reports

Functions for generating, displaying, and exporting various sales and
revenue reports including charts, CSV/TXT exports, and email delivery.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import csv
from datetime import datetime, timedelta

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Email integration
try:
    from university_system.infrastructure.email import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        return False


def show_reports_page(self):
    """Display reports and analytics page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.reports.title"),
             style="Subtitle.TLabel").pack(pady=10)

    report_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    report_frame.pack(fill="x", pady=10)

    tk.Label(report_frame, text=_t("cinema.reports.select_report"), bg="#ffffff", fg="#333333").pack(side="left")

    report_var = tk.StringVar(value="sales_summary")
    reports = ["sales_summary", "revenue_by_movie", "daily_sales", "occupancy", "payment_methods", "booking_status"]
    report_combo = ttk.Combobox(report_frame, textvariable=report_var, width=25, values=reports)
    report_combo.pack(side="left", padx=10)

    tk.Label(report_frame, text=_t("cinema.reports.from_label"), bg="#ffffff", fg="#333333").pack(side="left", padx=(20, 5))
    from_entry = ttk.Entry(report_frame, width=12)
    from_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    from_entry.pack(side="left")

    tk.Label(report_frame, text=_t("cinema.reports.to_label"), bg="#ffffff", fg="#333333").pack(side="left", padx=(10, 5))
    to_entry = ttk.Entry(report_frame, width=12)
    to_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
    to_entry.pack(side="left")

    self.report_display = ttk.Frame(self.content_frame, style="Card.TFrame")
    self.report_display.pack(fill="both", expand=True, pady=10)

    def generate_report():
        report_type = report_var.get()
        from_date = from_entry.get()
        to_date = to_entry.get()

        for widget in self.report_display.winfo_children():
            widget.destroy()

        if report_type == "sales_summary":
            self.generate_sales_summary(from_date, to_date)
        elif report_type == "revenue_by_movie":
            self.generate_revenue_by_movie(from_date, to_date)
        elif report_type == "daily_sales":
            self.generate_daily_sales(from_date, to_date)
        elif report_type == "occupancy":
            self.generate_occupancy_report(from_date, to_date)
        elif report_type == "payment_methods":
            self.generate_payment_methods_report(from_date, to_date)
        elif report_type == "booking_status":
            self.generate_booking_status_report(from_date, to_date)

    ttk.Button(report_frame, text=_t("cinema.reports.generate_report"), style="Primary.TButton",
              command=generate_report).pack(side="left", padx=10)
    ttk.Button(report_frame, text=_t("cinema.reports.open_new_window"), style="Secondary.TButton",
              command=lambda: self.open_report_in_window(report_var.get(), from_entry.get(),
                                                          to_entry.get())).pack(side="left", padx=5)

    export_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    export_frame.pack(fill="x", pady=5)

    ttk.Button(export_frame, text=_t("cinema.reports.save_as_txt"), style="Secondary.TButton",
              command=lambda: self.save_report_txt(report_var.get(), from_entry.get(),
                                                   to_entry.get())).pack(side="left", padx=5)
    ttk.Button(export_frame, text=_t("cinema.reports.export_to_csv"), style="Secondary.TButton",
              command=lambda: self.export_report_csv(report_var.get(), from_entry.get(),
                                                     to_entry.get())).pack(side="left", padx=5)
    ttk.Button(export_frame, text=_t("cinema.reports.email_to_admin"), style="Success.TButton",
              command=lambda: self.email_report_to_admin(report_var.get(), from_entry.get(),
                                                         to_entry.get())).pack(side="left", padx=5)

    generate_report()


def generate_sales_summary(self, from_date, to_date):
    """Generate sales summary report."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total_bookings,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
            COALESCE(SUM(CASE WHEN status = 'active' THEN total_amount ELSE 0 END), 0) as total_revenue,
            COALESCE(AVG(CASE WHEN status = 'active' THEN total_amount END), 0) as avg_booking
        FROM bookings
        WHERE date(booking_time) BETWEEN ? AND ?
    ''', (from_date, to_date))
    summary = cursor.fetchone()

    cursor.execute('''
        SELECT COUNT(bs.id)
        FROM booked_seats bs
        JOIN bookings b ON bs.booking_id = b.id
        WHERE b.status = 'active' AND date(b.booking_time) BETWEEN ? AND ?
    ''', (from_date, to_date))
    tickets_sold = cursor.fetchone()[0] or 0

    conn.close()

    summary_frame = ttk.Frame(self.report_display, style="Card.TFrame", padding=20)
    summary_frame.pack(fill="x", pady=10)

    tk.Label(summary_frame, text=_t("cinema.reports.sales_summary"), font=("Helvetica", 16, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    tk.Label(summary_frame, text=f"Period: {from_date} to {to_date}",
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    stats_frame = ttk.Frame(summary_frame, style="Card.TFrame")
    stats_frame.pack(fill="x", pady=20)

    stats = [
        ("Total Bookings", summary[0] or 0),
        ("Active Bookings", summary[1] or 0),
        ("Cancelled", summary[2] or 0),
        ("Tickets Sold", tickets_sold),
        ("Total Revenue", f"\u00a3{summary[3]:.2f}"),
        ("Avg. Booking Value", f"\u00a3{summary[4]:.2f}"),
    ]

    for i, (label, value) in enumerate(stats):
        col = i % 3
        row = i // 3

        stat_box = ttk.Frame(stats_frame, style="Card.TFrame")
        stat_box.grid(row=row, column=col, padx=20, pady=10)

        tk.Label(stat_box, text=str(value), font=("Helvetica", 24, "bold"),
                bg="#ffffff", fg="#27ae60").pack()
        tk.Label(stat_box, text=label, font=("Helvetica", 10),
                bg="#ffffff", fg="#7f8c8d").pack()


def generate_revenue_by_movie(self, from_date, to_date):
    """Generate revenue by movie report with chart."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT m.title,
               COUNT(b.id) as bookings,
               COALESCE(SUM(CASE WHEN b.status = 'active' THEN b.total_amount ELSE 0 END), 0) as revenue
        FROM movies m
        LEFT JOIN screenings s ON m.id = s.movie_id
        LEFT JOIN bookings b ON s.id = b.screening_id AND date(b.booking_time) BETWEEN ? AND ?
        GROUP BY m.id, m.title
        ORDER BY revenue DESC
    ''', (from_date, to_date))
    data = cursor.fetchall()
    conn.close()

    tree_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    tree_frame.pack(fill="x", pady=10)

    columns = ("Movie", "Bookings", "Revenue")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)

    for col in columns:
        tree.heading(col, text=col)
    tree.column("Movie", width=300)
    tree.column("Bookings", width=100)
    tree.column("Revenue", width=150)

    for row in data:
        tree.insert("", "end", values=(row[0], row[1], f"\u00a3{row[2]:.2f}"))

    tree.pack(fill="x")

    if MATPLOTLIB_AVAILABLE and data:
        self.create_bar_chart(
            [d[0][:15] for d in data[:10]],
            [d[2] for d in data[:10]],
            "Revenue by Movie",
            "Movie",
            "Revenue (\u00a3)"
        )


def generate_daily_sales(self, from_date, to_date):
    """Generate daily sales report with chart."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT date(booking_time) as date,
               COUNT(*) as bookings,
               COALESCE(SUM(CASE WHEN status = 'active' THEN total_amount ELSE 0 END), 0) as revenue
        FROM bookings
        WHERE date(booking_time) BETWEEN ? AND ?
        GROUP BY date(booking_time)
        ORDER BY date(booking_time)
    ''', (from_date, to_date))
    data = cursor.fetchall()
    conn.close()

    tree_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    tree_frame.pack(fill="x", pady=10)

    columns = ("Date", "Bookings", "Revenue")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)

    for col in columns:
        tree.heading(col, text=col)

    for row in data:
        tree.insert("", "end", values=(row[0], row[1], f"\u00a3{row[2]:.2f}"))

    tree.pack(fill="x")

    if MATPLOTLIB_AVAILABLE and data:
        self.create_line_chart(
            [d[0] for d in data],
            [d[2] for d in data],
            "Daily Revenue",
            "Date",
            "Revenue (\u00a3)"
        )


def generate_occupancy_report(self, from_date, to_date):
    """Generate seat occupancy report."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT m.title,
               COUNT(CASE WHEN seats.status = 'booked' THEN 1 END) as booked,
               COUNT(CASE WHEN seats.status = 'available' THEN 1 END) as available,
               COUNT(seats.id) as total
        FROM movies m
        JOIN screenings s ON m.id = s.movie_id
        JOIN seats ON s.id = seats.screening_id
        WHERE date(s.show_time) BETWEEN ? AND ?
        GROUP BY m.id, m.title
    ''', (from_date, to_date))
    data = cursor.fetchall()
    conn.close()

    tree_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    tree_frame.pack(fill="x", pady=10)

    columns = ("Movie", "Booked", "Available", "Total", "Occupancy %")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)

    for col in columns:
        tree.heading(col, text=col)

    chart_data = []
    for row in data:
        occupancy = (row[1] / row[3] * 100) if row[3] > 0 else 0
        tree.insert("", "end", values=(row[0], row[1], row[2], row[3], f"{occupancy:.1f}%"))
        chart_data.append((row[0], occupancy))

    tree.pack(fill="x")

    if MATPLOTLIB_AVAILABLE and chart_data:
        self.create_bar_chart(
            [d[0][:15] for d in chart_data[:10]],
            [d[1] for d in chart_data[:10]],
            "Seat Occupancy by Movie",
            "Movie",
            "Occupancy (%)"
        )


def generate_payment_methods_report(self, from_date, to_date):
    """Generate payment methods report with pie chart."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COALESCE(payment_method, 'Unknown') as method,
               COUNT(*) as count,
               COALESCE(SUM(total_amount), 0) as total
        FROM bookings
        WHERE status = 'active' AND date(booking_time) BETWEEN ? AND ?
        GROUP BY payment_method
        ORDER BY count DESC
    ''', (from_date, to_date))
    data = cursor.fetchall()
    conn.close()

    tree_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    tree_frame.pack(fill="x", pady=10)

    columns = ("Payment Method", "Bookings", "Total Revenue")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=6)

    for col in columns:
        tree.heading(col, text=col)

    for row in data:
        tree.insert("", "end", values=(row[0], row[1], f"\u00a3{row[2]:.2f}"))

    tree.pack(fill="x")

    if MATPLOTLIB_AVAILABLE and data:
        self.create_pie_chart(
            [d[0] for d in data],
            [d[1] for d in data],
            "Payment Methods Distribution"
        )


def generate_booking_status_report(self, from_date, to_date):
    """Generate booking status report with pie chart."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT status, COUNT(*) as count
        FROM bookings
        WHERE date(booking_time) BETWEEN ? AND ?
        GROUP BY status
    ''', (from_date, to_date))
    data = cursor.fetchall()
    conn.close()

    tree_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    tree_frame.pack(fill="x", pady=10)

    columns = ("Status", "Count")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=5)

    for col in columns:
        tree.heading(col, text=col)

    for row in data:
        tree.insert("", "end", values=(row[0].upper(), row[1]))

    tree.pack(fill="x")

    if MATPLOTLIB_AVAILABLE and data:
        self.create_pie_chart(
            [d[0].upper() for d in data],
            [d[1] for d in data],
            "Booking Status Distribution"
        )


def create_bar_chart(self, labels, values, title, xlabel, ylabel):
    """Create a bar chart."""
    chart_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    chart_frame.pack(fill="both", expand=True, pady=10)

    fig = Figure(figsize=(8, 4), facecolor='#16213e')
    ax = fig.add_subplot(111)

    ax.set_facecolor('#16213e')
    ax.bar(range(len(labels)), values, color='#e94560')

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8, color='white')
    ax.set_ylabel(ylabel, color='white')
    ax.set_xlabel(xlabel, color='white')
    ax.set_title(title, color='#e94560', fontsize=12, fontweight='bold')
    ax.tick_params(colors='white')

    for spine in ax.spines.values():
        spine.set_color('#0f3460')

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def create_line_chart(self, labels, values, title, xlabel, ylabel):
    """Create a line chart."""
    chart_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    chart_frame.pack(fill="both", expand=True, pady=10)

    fig = Figure(figsize=(8, 4), facecolor='#16213e')
    ax = fig.add_subplot(111)

    ax.set_facecolor('#16213e')
    ax.plot(range(len(labels)), values, color='#4ecca3', linewidth=2, marker='o')
    ax.fill_between(range(len(labels)), values, alpha=0.3, color='#4ecca3')

    step = max(1, len(labels) // 10)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)],
                      rotation=45, ha='right', fontsize=8, color='white')
    ax.set_ylabel(ylabel, color='white')
    ax.set_xlabel(xlabel, color='white')
    ax.set_title(title, color='#e94560', fontsize=12, fontweight='bold')
    ax.tick_params(colors='white')

    for spine in ax.spines.values():
        spine.set_color('#0f3460')

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def create_pie_chart(self, labels, values, title):
    """Create a pie chart."""
    chart_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    chart_frame.pack(fill="both", expand=True, pady=10)

    fig = Figure(figsize=(6, 4), facecolor='#16213e')
    ax = fig.add_subplot(111)

    colors = ['#e94560', '#4ecca3', '#0f3460', '#ffa500', '#ff6b6b', '#45b7d1']

    wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                      colors=colors[:len(labels)], textprops={'color': 'white'})

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(9)

    ax.set_title(title, color='#e94560', fontsize=12, fontweight='bold')

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


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
            except:
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
                except:
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
