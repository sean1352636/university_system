"""
Library Fines Management - Reporting and CSV export.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from education_system.university_system.core.i18n import get_text as _

from education_system.university_system.modules.domain.academics.gui.library.fines.constants import ORIGINAL_LIBRARY_AVAILABLE

try:
    from education_system.university_system.modules.domain.academics.services.library.database import get_db_connection
except ImportError:
    pass


def generate_fine_statistics_report(self):
    """Generate comprehensive statistics report for all library fines"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get overall statistics
            cursor.execute('''
                SELECT
                    COUNT(*) as total_fines_issued,
                    COUNT(CASE WHEN fine_amount = 0 AND notes LIKE '%Fine paid on%' THEN 1 END) as total_paid,
                    COUNT(CASE WHEN fine_amount = 0 AND notes LIKE '%Fine waived on%' THEN 1 END) as total_waived,
                    COUNT(CASE WHEN fine_amount > 0 THEN 1 END) as total_outstanding,
                    SUM(CASE WHEN fine_amount > 0 THEN fine_amount ELSE 0 END) as outstanding_amount,
                    AVG(CASE WHEN fine_amount > 0 THEN fine_amount ELSE NULL END) as avg_outstanding_fine
                FROM book_loans
                WHERE fine_amount > 0 OR notes LIKE '%Fine%'
            ''')

            stats = cursor.fetchone()
            total_fines, total_paid, total_waived, total_outstanding, outstanding_amt, avg_fine = stats

            # Get top defaulters
            cursor.execute('''
                SELECT user_id, SUM(fine_amount) as total_owed, COUNT(*) as fine_count
                FROM book_loans
                WHERE fine_amount > 0
                GROUP BY user_id
                ORDER BY total_owed DESC
                LIMIT 10
            ''')

            top_defaulters = cursor.fetchall()

            # Get recent fine activity
            cursor.execute('''
                SELECT COUNT(*) as recent_fines
                FROM book_loans
                WHERE (notes LIKE '%Fine paid on%' OR notes LIKE '%Fine waived on%')
                AND (notes LIKE '%' || date('now', '-30 days') || '%')
            ''')

            recent_activity = cursor.fetchone()[0]

            conn.close()

            # Create report window
            report_window = tk.Toplevel()
            report_window.title("Library Fine Statistics Report")
            report_window.geometry("700x600")

            # Header
            header_frame = ttk.Frame(report_window, relief='raised', borderwidth=2)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text="Library Fine Statistics Report",
                     font=('Arial', 14, 'bold')).pack(pady=10)
            ttk.Label(header_frame, text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                     font=('Arial', 9)).pack(pady=5)

            # Create scrollable text widget
            text_frame = ttk.Frame(report_window)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)

            text_widget = tk.Text(text_frame, wrap='word', font=('Courier', 10))
            scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side='right', fill='y')
            text_widget.pack(side='left', fill='both', expand=True)

            # Build report content
            report_content = f"""
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
OVERALL FINE STATISTICS
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

Total Fines Issued:       {total_fines or 0}
Total Paid:               {total_paid or 0}
Total Waived:             {total_waived or 0}
Total Outstanding:        {total_outstanding or 0}
Outstanding Amount:       £{outstanding_amt or 0:.2f}
Average Outstanding Fine: £{avg_fine or 0:.2f}

Recent Activity (30 days): {recent_activity} fine transactions

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
TOP 10 USERS WITH OUTSTANDING FINES
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

"""
            if top_defaulters:
                report_content += f"{'User ID':<20} {'Total Owed':>12} {'Fine Count':>12}\n"
                report_content += "-" * 55 + "\n"
                for user_id, total_owed, fine_count in top_defaulters:
                    report_content += f"{user_id:<20} £{total_owed:>11.2f} {fine_count:>12}\n"
            else:
                report_content += "No outstanding fines found.\n"

            report_content += "\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n"
            report_content += "RECOMMENDATIONS\n"
            report_content += "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n\n"

            if outstanding_amt and outstanding_amt > 1000:
                report_content += "\u26a0 High outstanding balance - consider reminder campaign\n"
            if total_outstanding and total_outstanding > 50:
                report_content += "\u26a0 Many outstanding fines - review fine policy\n"
            if avg_fine and avg_fine > 20:
                report_content += "\u26a0 High average fine - users may need overdue alerts\n"

            text_widget.insert('1.0', report_content)
            text_widget.configure(state='disabled')

            # Button frame
            button_frame = ttk.Frame(report_window)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Export to File",
                      command=lambda: self._save_text_report(report_content, "fine_statistics")).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_("common.close"),
                      command=report_window.destroy).pack(side='right', padx=5)

        else:
            messagebox.showinfo(_("common.demo"), "Demo: Fine statistics report")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to generate statistics: {str(e)}")


def export_fines_to_csv(self):
    """Export all outstanding fines to CSV file"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get all fines
            cursor.execute('''
                SELECT bl.user_id, bl.loan_id, bl.book_id, bl.checkout_date, bl.due_date,
                       bl.return_date, bl.fine_amount, bl.status, bl.notes,
                       b.title, b.author
                FROM book_loans bl
                LEFT JOIN books b ON bl.book_id = b.book_id
                WHERE bl.fine_amount > 0
                ORDER BY bl.due_date ASC
            ''')

            fines_data = cursor.fetchall()
            conn.close()

            if not fines_data:
                messagebox.showinfo("No Data", "No outstanding fines to export")
                return

            # Ask for save location
            default_filename = f"library_fines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=default_filename
            )

            if not file_path:
                return

            # Write CSV
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Header
                writer.writerow(['User ID', 'Loan ID', 'Book ID', 'Book Title', 'Author',
                               'Checkout Date', 'Due Date', 'Return Date',
                               'Fine Amount', 'Status', 'Notes'])

                # Data rows
                for row in fines_data:
                    writer.writerow(row)

                # Summary row
                writer.writerow([])
                writer.writerow(['SUMMARY'])
                writer.writerow(['Total Outstanding Fines:', len(fines_data)])
                writer.writerow(['Total Amount:', f'£{sum(row[6] for row in fines_data):.2f}'])

            messagebox.showinfo(_("common.success"),
                f"Fines exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Records: {len(fines_data)}")

        else:
            messagebox.showinfo(_("common.demo"), "Demo: Export fines to CSV")

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to export fines: {str(e)}")


def _save_text_report(self, content, report_type):
    """Helper function to save text report to file"""
    try:
        default_filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo(_("common.success"), f"Report saved to:\n{file_path}")

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to save report: {str(e)}")
