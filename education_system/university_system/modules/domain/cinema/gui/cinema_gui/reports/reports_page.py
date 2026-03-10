"""
Cinema Reports - Main reports page UI.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from ._imports import _t


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
