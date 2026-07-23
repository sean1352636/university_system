import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
from pathlib import Path
import uuid
from PIL import Image, ImageTk
import io
import os
import csv
import re
import shutil
from collections import deque

# Import internationalization support
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.misc_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.misc_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.post_18.university_system.core.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.post_18.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:50 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        AttendancePredictiveAnalytics, BackupRecoverySystem,
        EnhancedNotificationSystem, FaceRecognitionSystem, GeofencingSystem,
        QRAttendanceSystem, create_missing_tables, display_attendance_menu,
        generate_executive_summary_report, get_enhanced_setting,
        get_module_attendance, get_modules, get_student_attendance,
        init_enhanced_attendance_db, record_attendance, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import attendance notification service
try:
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class CustomReportWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.custom_report_builder"))
        self.window.geometry("700x500")
        self.window.transient(parent)

        # Load modules from database
        self.modules = self._load_modules()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📊 Custom Report Builder", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Report configuration
        config_frame = ttk.LabelFrame(self.window, text="Report Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Report type
        ttk.Label(config_frame, text="Report Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.report_type_var = tk.StringVar(value="Attendance Summary")
        type_combo = ttk.Combobox(config_frame, textvariable=self.report_type_var,
                                 values=["Attendance Summary", "Detailed Records", "Statistical Analysis"],
                                 state="readonly", width=30)
        type_combo.grid(row=0, column=1, padx=(10, 0), pady=5)

        # Date range
        ttk.Label(config_frame, text="Date Range:").grid(row=1, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(config_frame)
        date_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        self.start_date_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=12).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" to ").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=12).pack(side=tk.LEFT)

        # Filters
        filters_frame = ttk.LabelFrame(self.window, text="Filters", padding=10)
        filters_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Module filter
        self.module_filter_var = tk.BooleanVar()
        ttk.Checkbutton(filters_frame, text="Filter by Module:", variable=self.module_filter_var).grid(row=0, column=0, sticky=tk.W)
        self.selected_module_var = tk.StringVar()
        module_combo = ttk.Combobox(filters_frame, textvariable=self.selected_module_var,
                                   values=self.modules, state="readonly", width=20)
        module_combo.grid(row=0, column=1, padx=(10, 0))

        # Student filter
        self.student_filter_var = tk.BooleanVar()
        ttk.Checkbutton(filters_frame, text="Filter by Student:", variable=self.student_filter_var).grid(row=1, column=0, sticky=tk.W)
        self.selected_student_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self.selected_student_var, width=20).grid(row=1, column=1, padx=(10, 0))

        # Output options
        output_frame = ttk.LabelFrame(self.window, text="Output Options", padding=10)
        output_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(output_frame, text="Output Format:").grid(row=0, column=0, sticky=tk.W)
        self.output_format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(output_frame, textvariable=self.output_format_var,
                                   values=["Excel", "PDF", "CSV", "HTML"], state="readonly")
        format_combo.grid(row=0, column=1, padx=(10, 0))

        self.include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_frame, text="Include Charts", variable=self.include_charts_var).grid(row=1, column=0, columnspan=2, sticky=tk.W)

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Generate Report", command=self.generate_report, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.preview"), command=self.preview_report, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"), command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def generate_report(self):
        """Generate the custom report and export to selected format"""
        report_content = self._build_report()
        if not report_content:
            return

        fmt = self.output_format_var.get()
        ext_map = {"Excel": ".xlsx", "PDF": ".pdf", "CSV": ".csv", "HTML": ".html"}
        ext = ext_map.get(fmt, ".txt")
        ft_map = {"Excel": [("Excel files", "*.xlsx")], "PDF": [("PDF files", "*.pdf")],
                  "CSV": [("CSV files", "*.csv")], "HTML": [("HTML files", "*.html")]}

        filename = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=ext,
            filetypes=ft_map.get(fmt, [("Text files", "*.txt")]) + [("All files", "*.*")],
            parent=self.window)
        if not filename:
            return

        try:
            if fmt == "CSV":
                self._export_csv(filename, report_content)
            elif fmt == "HTML":
                self._export_html(filename, report_content)
            elif fmt == "PDF":
                self._export_pdf(filename, report_content)
            elif fmt == "Excel":
                self._export_excel(filename, report_content)
            else:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report_content)
            messagebox.showinfo(_("common.success"), f"Report exported to {filename}", parent=self.window)
        except Exception as e:
            logger.exception("misc_windows.py:1139 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Export failed: {e}", parent=self.window)

    def preview_report(self):
        """Preview the report in a window"""
        report_content = self._build_report()
        if not report_content:
            return
        preview = tk.Toplevel(self.window)
        preview.title("Report Preview")
        preview.geometry("700x500")
        preview.transient(self.window)
        from tkinter import scrolledtext as st
        txt = st.ScrolledText(preview, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert('1.0', report_content)
        txt.config(state='disabled')
        ttk.Button(preview, text=_("common.close"), command=preview.destroy).pack(pady=10)

    def _build_report(self):
        """Build the report content from DB"""
        report_type = self.report_type_var.get()
        start_date = self.start_date_var.get()
        end_date = self.end_date_var.get()

        lines = []
        lines.append(f"{report_type.upper()}")
        lines.append("=" * 50)
        lines.append(f"Date Range: {start_date} to {end_date}")
        lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query based on filters
            where_parts = ["date BETWEEN ? AND ?"]
            params = [start_date, end_date]

            if self.module_filter_var.get() and self.selected_module_var.get():
                mod_code = self.selected_module_var.get().split(' - ')[0]
                where_parts.append("module_code = ?")
                params.append(mod_code)

            if self.student_filter_var.get() and self.selected_student_var.get():
                where_parts.append("student_id = ?")
                params.append(self.selected_student_var.get().strip())

            where_clause = " AND ".join(where_parts)

            if report_type == "Attendance Summary":
                cursor.execute(f"""
                    SELECT module_code,
                           COUNT(*) as total,
                           SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
                           SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent,
                           SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late
                    FROM attendance_records
                    WHERE {where_clause}
                    GROUP BY module_code
                    ORDER BY module_code
                """, params)
                rows = cursor.fetchall()
                if rows:
                    lines.append(f"{'Module':<15} {'Total':>8} {'Present':>8} {'Absent':>8} {'Late':>8} {'Rate':>8}")
                    lines.append("-" * 63)
                    for r in rows:
                        rate = (r['attended'] / r['total'] * 100) if r['total'] > 0 else 0
                        lines.append(f"{r['module_code']:<15} {r['total']:>8} {r['attended']:>8} {r['absent']:>8} {r['late']:>8} {rate:>7.1f}%")
                else:
                    lines.append("No attendance records found for the specified criteria.")

            elif report_type == "Detailed Records":
                cursor.execute(f"""
                    SELECT student_id, module_code, date, status
                    FROM attendance_records
                    WHERE {where_clause}
                    ORDER BY date DESC, module_code, student_id
                    LIMIT 500
                """, params)
                rows = cursor.fetchall()
                if rows:
                    lines.append(f"{'Student':<15} {'Module':<15} {'Date':<12} {'Status':<10}")
                    lines.append("-" * 52)
                    for r in rows:
                        lines.append(f"{r['student_id']:<15} {r['module_code']:<15} {r['date']:<12} {r['status']:<10}")
                    lines.append(f"\nShowing {len(rows)} records (max 500)")
                else:
                    lines.append("No records found.")

            elif report_type == "Statistical Analysis":
                cursor.execute(f"""
                    SELECT student_id,
                           COUNT(*) as total,
                           SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended
                    FROM attendance_records
                    WHERE {where_clause}
                    GROUP BY student_id
                """, params)
                rows = cursor.fetchall()
                if rows:
                    rates = [(r['attended'] / r['total'] * 100) if r['total'] > 0 else 0 for r in rows]
                    avg_rate = sum(rates) / len(rates) if rates else 0
                    min_rate = min(rates) if rates else 0
                    max_rate = max(rates) if rates else 0
                    below_70 = sum(1 for r in rates if r < 70)
                    above_90 = sum(1 for r in rates if r >= 90)

                    lines.append("STATISTICAL SUMMARY:")
                    lines.append(f"  Total Students: {len(rows)}")
                    lines.append(f"  Average Attendance: {avg_rate:.1f}%")
                    lines.append(f"  Highest: {max_rate:.1f}%")
                    lines.append(f"  Lowest: {min_rate:.1f}%")
                    lines.append(f"  Students above 90%: {above_90}")
                    lines.append(f"  Students below 70%: {below_70}")

                    lines.append("\nDISTRIBUTION:")
                    brackets = [(90, 100, "Excellent"), (80, 90, "Good"), (70, 80, "Fair"), (0, 70, "At Risk")]
                    for low, high, label in brackets:
                        count = sum(1 for r in rates if low <= r < high) if high < 100 else sum(1 for r in rates if low <= r <= high)
                        lines.append(f"  {label} ({low}-{high}%): {count} students")
                else:
                    lines.append("No records found.")

            conn.close()

        except Exception as e:
            logger.exception("misc_windows.py:1266 %s", 'except Exception as e')
            lines.append(f"\nError querying database: {e}")

        return "\n".join(lines)

    def _export_csv(self, filename, content):
        """Export report as CSV"""
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            for line in content.split('\n'):
                f.write(line + '\n')

    def _export_html(self, filename, content):
        """Export report as HTML"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Attendance Report</title>
<style>body{{font-family:monospace;padding:20px;}} pre{{background:#f5f5f5;padding:15px;border-radius:5px;}}</style>
</head><body><h1>Attendance Report</h1><pre>{content}</pre></body></html>"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

    def _export_pdf(self, filename, content):
        """Export report as a valid PDF file"""
        lines = content.split('\n')
        # Build PDF manually (minimal valid PDF without external libraries)
        pdf_lines = []
        pdf_lines.append("%PDF-1.4")

        # Font object
        pdf_lines.append("1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj")
        pdf_lines.append("2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj")

        # Build text content with line breaks
        escaped = []
        for line in lines:
            # Escape PDF special chars
            safe = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            escaped.append(safe)

        # Calculate page height needed
        font_size = 10
        line_height = 12
        margin_top = 750
        margin_left = 50

        text_ops = [f"BT /F1 {font_size} Tf"]
        y = margin_top
        for line in escaped:
            if y < 50:
                break  # Simple single page for now
            text_ops.append(f"{margin_left} {y} Td ({line}) Tj")
            text_ops.append(f"-{margin_left} -{line_height} Td")
            y -= line_height
        text_ops.append("ET")
        stream_content = "\n".join(text_ops)

        pdf_lines.append("3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
                         "/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj")
        pdf_lines.append(f"4 0 obj<</Length {len(stream_content)}>>stream\n{stream_content}\nendstream endobj")
        pdf_lines.append("5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Courier>>endobj")

        # Cross-reference table
        body = "\n".join(pdf_lines)
        xref_offset = len(body.encode('latin-1')) + 1

        pdf_lines.append("xref")
        pdf_lines.append("0 6")
        pdf_lines.append("0000000000 65535 f ")
        # Calculate offsets
        offsets = []
        pos = len("%PDF-1.4\n")
        for i in range(1, 6):
            offsets.append(pos)
            marker = f"{i} 0 obj"
            idx = body.find(marker)
            if idx >= 0:
                offsets[-1] = idx

        for off in offsets:
            pdf_lines.append(f"{off:010d} 00000 n ")

        pdf_lines.append("trailer<</Size 6/Root 1 0 R>>")
        pdf_lines.append(f"startxref\n{xref_offset}")
        pdf_lines.append("%%EOF")

        with open(filename, 'wb') as f:
            f.write("\n".join(pdf_lines).encode('latin-1'))

    def _export_excel(self, filename, content):
        """Export report as Excel (.xlsx) file"""
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Attendance Report"
            for i, line in enumerate(content.split('\n'), 1):
                ws.cell(row=i, column=1, value=line)
            wb.save(filename)
        except ImportError:
            # Fallback: save as CSV with .xlsx extension note
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showwarning("Export", "openpyxl not installed. Report saved as plain text.\n"
                                   "Install with: pip install openpyxl", parent=self.window)

    def _load_modules(self):
        """Load modules from database"""
        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()

            # Try to get modules from modules table
            cursor.execute('''
                SELECT DISTINCT module_code, module_name
                FROM modules
                ORDER BY module_code
            ''')
            rows = cursor.fetchall()

            if rows:
                # Return formatted as "CODE - Name"
                modules = [f"{code} - {name}" if name else code for code, name in rows]
            else:
                # Fallback: try to get from attendance_records
                cursor.execute('''
                    SELECT DISTINCT module_code
                    FROM attendance_records
                    ORDER BY module_code
                ''')
                rows = cursor.fetchall()
                modules = [code for (code,) in rows if code]

            conn.close()
            return modules if modules else ["No modules found"]

        except Exception as e:
            logger.exception("misc_windows.py:1400 %s", 'except Exception as e')
            print(f"Error loading modules: {e}")
            return ["Error loading modules"]

