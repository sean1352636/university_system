"""
Cinema Booking System - Sales Reports

Re-export shim for backward compatibility.
All functions split into focused modules:
  reports_page.py  - show_reports_page
  generators.py    - 6 generate_* report functions
  charts.py        - create_bar_chart, create_line_chart, create_pie_chart
  exports.py       - export_report_csv, save_report_txt, email_report_to_admin, open_report_in_window
"""

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.reports_page import show_reports_page

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.generators import (
    generate_sales_summary,
    generate_revenue_by_movie,
    generate_daily_sales,
    generate_occupancy_report,
    generate_payment_methods_report,
    generate_booking_status_report,
)

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.charts import (
    create_bar_chart,
    create_line_chart,
    create_pie_chart,
)

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports.exports import (
    export_report_csv,
    save_report_txt,
    email_report_to_admin,
    open_report_in_window,
)

__all__ = [
    "show_reports_page",
    "generate_sales_summary",
    "generate_revenue_by_movie",
    "generate_daily_sales",
    "generate_occupancy_report",
    "generate_payment_methods_report",
    "generate_booking_status_report",
    "create_bar_chart",
    "create_line_chart",
    "create_pie_chart",
    "export_report_csv",
    "save_report_txt",
    "email_report_to_admin",
    "open_report_in_window",
]
