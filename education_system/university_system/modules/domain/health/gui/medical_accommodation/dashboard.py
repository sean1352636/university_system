# dashboard.py
# Dashboard, statistics, and reporting mixin for AccommodationGUI.

from ._common import (
    tk, ttk, messagebox, simpledialog, filedialog,
    ScrolledText, datetime, timedelta, sqlite3,
    CLI_AVAILABLE, get_connection, logger,
)

if CLI_AVAILABLE:
    from ._common import (
        generate_statistics_report, check_expiry_notifications,
        log_action,
    )


class DashboardMixin:
    """Dashboard and reporting methods for AccommodationGUI."""

    def refresh_dashboard(self):
        """Refresh the dashboard metrics"""
        if not CLI_AVAILABLE:
            return

        try:
            today = datetime.now().strftime('%Y-%m-%d')
            current_month = datetime.now().strftime('%Y-%m')
            thirty_days_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM accommodations')
                total = cursor.fetchone()[0]
                self.metrics_vars['total'].set(str(total))

                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
                ''', (today,))
                active = cursor.fetchone()[0]
                self.metrics_vars['active'].set(str(active))

                cursor.execute("SELECT COUNT(*) FROM accommodations WHERE status = 'pending'")
                pending = cursor.fetchone()[0]
                self.metrics_vars['pending'].set(str(pending))

                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE (end_date < ? OR status = 'expired')
                ''', (today,))
                expired = cursor.fetchone()[0]
                self.metrics_vars['expired'].set(str(expired))

                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE created_at LIKE ?
                ''', (f"{current_month}%",))
                this_month = cursor.fetchone()[0]
                self.metrics_vars['this_month'].set(str(this_month))

                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE end_date BETWEEN ? AND ? AND status = 'active'
                ''', (today, thirty_days_future))
                expiring_soon = cursor.fetchone()[0]
                self.metrics_vars['expiring_soon'].set(str(expiring_soon))

                self.generate_dashboard_text()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh dashboard: {str(e)}")

    def generate_dashboard_text(self):
        """Generate dashboard statistics text"""
        if not CLI_AVAILABLE:
            return

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT accommodation_type, COUNT(*) as count
                    FROM accommodations
                    GROUP BY accommodation_type
                    ORDER BY count DESC
                ''')
                by_type = cursor.fetchall()

                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM accommodations
                    GROUP BY status
                    ORDER BY count DESC
                ''')
                by_status = cursor.fetchall()

                self.stats_text.delete(1.0, tk.END)

                self.stats_text.insert(tk.END, "ACCOMMODATION BREAKDOWN BY TYPE\n")
                self.stats_text.insert(tk.END, "=" * 50 + "\n\n")

                total = int(self.metrics_vars['total'].get())

                for type_row in by_type:
                    type_name = type_row['accommodation_type']
                    count = type_row['count']
                    percent = (count/total*100) if total > 0 else 0

                    bar_length = int(percent / 2)
                    bar = '\u2588' * bar_length

                    self.stats_text.insert(tk.END, f"{type_name:<25} {count:>3} ({percent:5.1f}%) {bar}\n")

                self.stats_text.insert(tk.END, "\n\nBREAKDOWN BY STATUS\n")
                self.stats_text.insert(tk.END, "=" * 50 + "\n\n")

                for status_row in by_status:
                    status_name = status_row['status']
                    count = status_row['count']
                    percent = (count/total*100) if total > 0 else 0

                    bar_length = int(percent / 2)
                    bar = '\u2588' * bar_length

                    self.stats_text.insert(tk.END, f"{status_name:<15} {count:>3} ({percent:5.1f}%) {bar}\n")

        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, f"Error generating statistics: {str(e)}")

    def show_dashboard(self):
        """Show dashboard metrics"""
        self.notebook.select(2)  # Switch to dashboard tab
        self.refresh_dashboard()

    def generate_statistics(self):
        """Generate statistics report"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        StatisticsDialog(self.root)

    def check_expiry(self):
        """Check expiry notifications"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        days = simpledialog.askinteger("Expiry Check",
            "Check for accommodations expiring in how many days?",
            initialvalue=7, minvalue=1, maxvalue=365)

        if days:
            try:
                import io
                import contextlib

                output = io.StringIO()

                with contextlib.redirect_stdout(output):
                    check_expiry_notifications(days)

                result = output.getvalue()
                ExpiryResultDialog(self.root, result, days)

            except Exception as e:
                messagebox.showerror("Error", f"Expiry check failed: {str(e)}")

    def view_students_by_accommodation_type(self):
        """View students grouped by accommodation type"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                WHERE status = 'active'
                GROUP BY accommodation_type
                ORDER BY count DESC, accommodation_type
            """)
            type_summary = cursor.fetchall()

            if not type_summary:
                messagebox.showinfo("No Data", "No active accommodations found")
                conn.close()
                return

            view_window = tk.Toplevel(self.root)
            view_window.title("Students by Accommodation Type")
            view_window.geometry("900x700")

            main_frame = ttk.Frame(view_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            title_label = ttk.Label(main_frame, text="Students Grouped by Accommodation Type",
                                   font=('Arial', 14, 'bold'))
            title_label.pack(pady=(0, 10))

            summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
            summary_frame.pack(fill=tk.X, pady=5)

            total_students = sum(count for _, count in type_summary)
            summary_text = f"Total Active Accommodations: {total_students}\n"
            summary_text += f"Number of Types: {len(type_summary)}"

            ttk.Label(summary_frame, text=summary_text, font=('Arial', 10)).pack(anchor='w')

            type_notebook = ttk.Notebook(main_frame)
            type_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            for acc_type, count in type_summary:
                cursor.execute("""
                    SELECT a.id, a.student_id, s.first_name, s.last_name,
                           a.start_date, a.end_date, a.description, a.status
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.accommodation_type = ? AND a.status = 'active'
                    ORDER BY a.student_id
                """, (acc_type,))
                students = cursor.fetchall()

                tab_frame = ttk.Frame(type_notebook)
                type_notebook.add(tab_frame, text=f"{acc_type} ({count})")

                tree_frame = ttk.Frame(tab_frame)
                tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                columns = ('Accom ID', 'Student ID', 'Name', 'Start Date', 'End Date', 'Status')
                tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

                tree.column('Accom ID', width=80)
                tree.column('Student ID', width=100)
                tree.column('Name', width=200)
                tree.column('Start Date', width=100)
                tree.column('End Date', width=100)
                tree.column('Status', width=80)

                for col in columns:
                    tree.heading(col, text=col)

                vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

                tree.grid(row=0, column=0, sticky='nsew')
                vsb.grid(row=0, column=1, sticky='ns')
                hsb.grid(row=1, column=0, sticky='ew')

                tree_frame.grid_rowconfigure(0, weight=1)
                tree_frame.grid_columnconfigure(0, weight=1)

                for student in students:
                    acc_id, student_id, first_name, last_name, start_date, end_date, description, status = student
                    name = f"{first_name or ''} {last_name or ''}".strip() or 'N/A'

                    tree.insert('', 'end', values=(
                        acc_id,
                        student_id,
                        name,
                        start_date or 'N/A',
                        end_date or 'Indefinite',
                        status
                    ))

                details_frame = ttk.LabelFrame(tab_frame, text="Description", padding="5")
                details_frame.pack(fill=tk.X, padx=5, pady=5)

                details_text = ScrolledText(details_frame, height=4, wrap=tk.WORD)
                details_text.pack(fill=tk.X)

                def on_select(event, t=tree, dt=details_text, studs=students):
                    selection = t.selection()
                    if selection:
                        item = t.item(selection[0])
                        acc_id = item['values'][0]
                        for s in studs:
                            if s[0] == acc_id:
                                dt.delete('1.0', 'end')
                                desc = s[6] if s[6] else 'No description available'
                                dt.insert('1.0', desc)
                                break

                tree.bind('<<TreeviewSelect>>', on_select)

            ttk.Button(main_frame, text="Close", command=view_window.destroy).pack(pady=5)

            conn.close()

            if CLI_AVAILABLE:
                log_action('view_by_type', None, 'Viewed students grouped by accommodation type')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate view: {str(e)}")
            import traceback
            traceback.print_exc()


# --- Dialog Classes ---

class StatisticsDialog:
    """Dialog for statistics report"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Statistics Report")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.generate_statistics()

    def create_widgets(self):
        """Create statistics widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.stats_text = ScrolledText(main_frame, width=80, height=30)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=self.generate_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def generate_statistics(self):
        """Generate statistics"""
        if not CLI_AVAILABLE:
            return

        try:
            import io
            import contextlib

            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                generate_statistics_report()

            result = output.getvalue()

            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, result)

        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, f"Error generating statistics: {str(e)}")

    def export_report(self):
        """Export statistics report"""
        file_path = filedialog.asksaveasfilename(
            title="Save Statistics Report",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            defaultextension=".txt"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.stats_text.get(1.0, tk.END))

                messagebox.showinfo("Success", f"Report exported to {file_path}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report: {str(e)}")


class ExpiryResultDialog:
    """Dialog for expiry check results"""

    def __init__(self, parent, result_text, days):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Expiry Check - {days} Days")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)

        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        result_text_widget = ScrolledText(main_frame, width=70, height=20)
        result_text_widget.pack(fill=tk.BOTH, expand=True)
        result_text_widget.insert(tk.END, result_text)
        result_text_widget.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
