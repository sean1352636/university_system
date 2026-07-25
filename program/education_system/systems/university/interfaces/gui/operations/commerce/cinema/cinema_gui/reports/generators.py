"""
Cinema Reports - Report generation functions.

Each function queries the database and renders results into self.report_display.
"""

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.reports._imports import sqlite3, DB_FILE, _t, MATPLOTLIB_AVAILABLE


def generate_sales_summary(self, from_date, to_date):
    """Generate sales summary report."""
    conn = sqlite3.connect(DB_FILE)
    try:
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

    finally:
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
    try:
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
    finally:
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
    try:
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
    finally:
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
    try:
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
    finally:
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
    try:
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
    finally:
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
    try:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM bookings
            WHERE date(booking_time) BETWEEN ? AND ?
            GROUP BY status
        ''', (from_date, to_date))
        data = cursor.fetchall()
    finally:
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
