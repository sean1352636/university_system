"""
Waste Tracking GUI

Manages food waste tracking, cost analysis, and waste reduction insights.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import csv
from tkinter import filedialog

# Import database connection
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection

# Import translation function
from education_system.university_system.core.i18n import get_text as get_translation
_t = get_translation


def init_waste_tracking_tables():
    """Initialize waste tracking tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Create waste tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_waste (
                waste_id INTEGER PRIMARY KEY AUTOINCREMENT,
                waste_date DATE NOT NULL,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_of_measure TEXT,
                cost_value REAL NOT NULL,
                waste_type TEXT,
                reason TEXT NOT NULL,
                responsible_staff TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create waste categories table for reporting
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_waste_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL,
                description TEXT,
                target_percentage REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert default categories if table is empty
        cursor.execute('SELECT COUNT(*) FROM restaurant_waste_categories')
        if cursor.fetchone()[0] == 0:
            default_categories = [
                (_t("waste_tracking.waste_categories.spoilage", default="Spoilage"),
                 _t("waste_tracking.waste_categories.spoilage_desc", default="Food spoiled before use"), 5.0),
                (_t("waste_tracking.waste_categories.preparation_waste", default="Preparation Waste"),
                 _t("waste_tracking.waste_categories.preparation_waste_desc", default="Trimmings and preparation waste"), 10.0),
                (_t("waste_tracking.waste_categories.over_production", default="Over-production"),
                 _t("waste_tracking.waste_categories.over_production_desc", default="Food prepared but not sold"), 3.0),
                (_t("waste_tracking.waste_categories.plate_waste", default="Plate Waste"),
                 _t("waste_tracking.waste_categories.plate_waste_desc", default="Food returned by customers"), 2.0),
                (_t("waste_tracking.waste_categories.storage_issues", default="Storage Issues"),
                 _t("waste_tracking.waste_categories.storage_issues_desc", default="Improper storage leading to waste"), 1.0),
                (_t("waste_tracking.waste_categories.other", default="Other"),
                 _t("waste_tracking.waste_categories.other_desc", default="Miscellaneous waste"), 2.0)
            ]

            cursor.executemany('''
                INSERT INTO restaurant_waste_categories (category_name, description, target_percentage)
                VALUES (?, ?, ?)
            ''', default_categories)

        conn.commit()
        conn.close()
        print(_t("waste_tracking.init_success", default="✓ Waste tracking tables initialized successfully"))
        return True

    except Exception as e:
        print(_t("waste_tracking.init_error", default="✗ Error initializing waste tracking tables: {error}").format(error=e))
        return False


class WasteTrackingGUI:
    """GUI for tracking and analyzing food waste"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(_t("waste_tracking.window_title", default="Waste Tracking & Analysis"))
        self.window.geometry("1400x800")

        # Initialize tables
        init_waste_tracking_tables()

        self.create_widgets()
        self.load_waste_entries()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main notebook
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Waste Entries Tab
        entries_tab = ttk.Frame(notebook)
        notebook.add(entries_tab, text=_t("waste_tracking.tabs.waste_entries", default="Waste Entries"))
        self.create_entries_tab(entries_tab)

        # Analytics Tab
        analytics_tab = ttk.Frame(notebook)
        notebook.add(analytics_tab, text=_t("waste_tracking.tabs.analytics", default="Analytics"))
        self.create_analytics_tab(analytics_tab)

        # Categories Tab
        categories_tab = ttk.Frame(notebook)
        notebook.add(categories_tab, text=_t("waste_tracking.tabs.waste_categories", default="Waste Categories"))
        self.create_categories_tab(categories_tab)

    def create_entries_tab(self, parent):
        """Create waste entries tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("waste_tracking.entries_tab.header_title", default="Waste Tracking"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("waste_tracking.buttons.record_waste", default="Record Waste"),
                  command=self.record_waste).pack(side=tk.RIGHT, padx=5)

        # Filters
        filter_frame = ttk.LabelFrame(parent, text=_t("waste_tracking.entries_tab.filters_title", default="Filters"), padding="10")
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("waste_tracking.labels.date_range", default="Date Range:")).grid(row=0, column=0, padx=5)
        self.start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=self.start_date_var, width=12).grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text=_t("waste_tracking.labels.to", default="to")).grid(row=0, column=2, padx=5)
        self.end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=self.end_date_var, width=12).grid(row=0, column=3, padx=5)

        ttk.Label(filter_frame, text=_t("waste_tracking.labels.waste_type", default="Waste Type:")).grid(row=0, column=4, padx=5)
        self.type_filter = ttk.Combobox(filter_frame, width=20)
        self.type_filter.set(_t("waste_tracking.filters.all", default="All"))
        self.type_filter.grid(row=0, column=5, padx=5)
        self.load_waste_types()

        ttk.Button(filter_frame, text=_t("waste_tracking.buttons.search", default="Search"),
                  command=self.load_waste_entries).grid(row=0, column=6, padx=10)

        # Waste Entries List
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('date', 'item_name', 'quantity', 'unit', 'cost', 'waste_type', 'reason')
        self.waste_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.waste_tree.heading('date', text=_t("waste_tracking.columns.date", default="Date"))
        self.waste_tree.heading('item_name', text=_t("waste_tracking.columns.item_name", default="Item Name"))
        self.waste_tree.heading('quantity', text=_t("waste_tracking.columns.quantity", default="Quantity"))
        self.waste_tree.heading('unit', text=_t("waste_tracking.columns.unit", default="Unit"))
        self.waste_tree.heading('cost', text=_t("waste_tracking.columns.cost", default="Cost Value"))
        self.waste_tree.heading('waste_type', text=_t("waste_tracking.columns.waste_type", default="Waste Type"))
        self.waste_tree.heading('reason', text=_t("waste_tracking.columns.reason", default="Reason"))

        self.waste_tree.column('date', width=100)
        self.waste_tree.column('item_name', width=200)
        self.waste_tree.column('quantity', width=100)
        self.waste_tree.column('unit', width=80)
        self.waste_tree.column('cost', width=100)
        self.waste_tree.column('waste_type', width=150)
        self.waste_tree.column('reason', width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.waste_tree.yview)
        self.waste_tree.configure(yscrollcommand=scrollbar.set)

        self.waste_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary frame
        summary_frame = ttk.LabelFrame(parent, text=_t("waste_tracking.entries_tab.summary_title", default="Summary"), padding="10")
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.summary_label = ttk.Label(summary_frame, text=_t("waste_tracking.summary.total_waste_cost", default="Total Waste Cost: £{cost}").format(cost="0.00"),
                                      font=('Arial', 11, 'bold'))
        self.summary_label.pack()

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.view_details", default="View Details"),
                  command=self.view_waste_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.edit", default="Edit"),
                  command=self.edit_waste_entry).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.delete", default="Delete"),
                  command=self.delete_waste_entry).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.export_csv", default="Export to CSV"),
                  command=self.export_waste_data).pack(side=tk.LEFT, padx=5)

    def create_analytics_tab(self, parent):
        """Create analytics tab"""
        from tkinter.scrolledtext import ScrolledText

        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("waste_tracking.analytics_tab.header_title", default="Waste Analytics"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("waste_tracking.buttons.generate_report", default="Generate Report"),
                  command=self.generate_analytics_report).pack(side=tk.RIGHT, padx=5)

        # Report display
        self.analytics_text = ScrolledText(parent, height=30, width=120, font=('Courier', 9))
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_categories_tab(self, parent):
        """Create waste categories tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("waste_tracking.categories_tab.header_title", default="Waste Categories"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("waste_tracking.buttons.add_category", default="Add Category"),
                  command=self.add_category).pack(side=tk.RIGHT, padx=5)

        # Categories List
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('category_name', 'description', 'target_percentage')
        self.categories_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        self.categories_tree.heading('category_name', text=_t("waste_tracking.columns.category_name", default="Category Name"))
        self.categories_tree.heading('description', text=_t("waste_tracking.columns.description", default="Description"))
        self.categories_tree.heading('target_percentage', text=_t("waste_tracking.columns.target_percentage", default="Target %"))

        self.categories_tree.column('category_name', width=200)
        self.categories_tree.column('description', width=400)
        self.categories_tree.column('target_percentage', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.categories_tree.yview)
        self.categories_tree.configure(yscrollcommand=scrollbar.set)

        self.categories_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.edit_category", default="Edit Category"),
                  command=self.edit_category).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.delete", default="Delete"),
                  command=self.delete_category).pack(side=tk.LEFT, padx=5)

        # Load categories
        self.load_categories()

    def load_waste_types(self):
        """Load waste types for filter"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('SELECT category_name FROM restaurant_waste_categories ORDER BY category_name')
            types = [_t("waste_tracking.filters.all", default="All")] + [row[0] for row in cursor.fetchall()]
            self.type_filter['values'] = types
            conn.close()

        except Exception as e:
            print(_t("waste_tracking.errors.load_waste_types", default="Error loading waste types: {error}").format(error=e))

    def load_waste_entries(self):
        """Load waste entries from database"""
        for item in self.waste_tree.get_children():
            self.waste_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Build query based on filters
            query = '''
                SELECT waste_date, item_name, quantity, unit_of_measure,
                       cost_value, waste_type, reason
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
            '''
            params = [self.start_date_var.get(), self.end_date_var.get()]

            type_filter = self.type_filter.get()
            all_text = _t("waste_tracking.filters.all", default="All")
            if type_filter and type_filter != all_text:
                query += ' AND waste_type = ?'
                params.append(type_filter)

            query += ' ORDER BY waste_date DESC'

            cursor.execute(query, params)

            total_cost = 0
            for row in cursor.fetchall():
                date, item, qty, unit, cost, waste_type, reason = row
                cost = cost if cost else 0
                total_cost += cost

                self.waste_tree.insert('', tk.END, values=(
                    date, item, f"{qty:.2f}", unit or '',
                    f"£{cost:.2f}", waste_type or _t("waste_tracking.details.na", default="N/A"), reason
                ))

            conn.close()

            # Update summary
            self.summary_label.config(text=_t("waste_tracking.summary.total_waste_cost", default="Total Waste Cost: £{cost}").format(cost=f"{total_cost:.2f}"))

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.load_waste_entries", default="Failed to load waste entries: {error}").format(error=e))

    def load_categories(self):
        """Load waste categories"""
        for item in self.categories_tree.get_children():
            self.categories_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT category_name, description, target_percentage
                FROM restaurant_waste_categories
                ORDER BY category_name
            ''')

            for row in cursor.fetchall():
                self.categories_tree.insert('', tk.END, values=row)

            conn.close()

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.load_categories", default="Failed to load categories: {error}").format(error=e))

    def record_waste(self):
        """Record new waste entry"""
        dialog = WasteEntryDialog(self.window, None)
        if dialog.result:
            self.load_waste_entries()

    def view_waste_details(self):
        """View waste entry details"""
        selection = self.waste_tree.selection()
        if not selection:
            messagebox.showwarning(_t("waste_tracking.messages.no_selection_view", default="No Selection"),
                                 _t("waste_tracking.messages.no_selection_view", default="Please select a waste entry to view"))
            return

        values = self.waste_tree.item(selection[0])['values']

        details = f"""{_t("waste_tracking.details.title", default="WASTE ENTRY DETAILS")}
{_t("waste_tracking.details.separator", default="====================")}

{_t("waste_tracking.details.date", default="Date: {date}").format(date=values[0])}
{_t("waste_tracking.details.item_name", default="Item Name: {name}").format(name=values[1])}
{_t("waste_tracking.details.quantity", default="Quantity: {qty} {unit}").format(qty=values[2], unit=values[3])}
{_t("waste_tracking.details.cost_value", default="Cost Value: {cost}").format(cost=values[4])}
{_t("waste_tracking.details.waste_type", default="Waste Type: {type}").format(type=values[5])}
{_t("waste_tracking.details.reason", default="Reason: {reason}").format(reason=values[6])}
"""

        messagebox.showinfo(_t("waste_tracking.dialogs.waste_entry_details_title", default="Waste Entry Details"), details)

    def edit_waste_entry(self):
        """Edit waste entry"""
        selection = self.waste_tree.selection()
        if not selection:
            messagebox.showwarning(_t("waste_tracking.messages.no_selection_edit", default="No Selection"),
                                 _t("waste_tracking.messages.no_selection_edit", default="Please select a waste entry to edit"))
            return

        values = self.waste_tree.item(selection[0])['values']

        # Find waste_id
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT waste_id
                FROM restaurant_waste
                WHERE waste_date = ? AND item_name = ?
                ORDER BY waste_id DESC
                LIMIT 1
            ''', (values[0], values[1]))

            result = cursor.fetchone()
            conn.close()

            if result:
                waste_id = result[0]
                dialog = WasteEntryDialog(self.window, waste_id)
                if dialog.result:
                    self.load_waste_entries()

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.load_waste_entry", default="Failed to load waste entry: {error}").format(error=e))

    def delete_waste_entry(self):
        """Delete waste entry"""
        selection = self.waste_tree.selection()
        if not selection:
            messagebox.showwarning(_t("waste_tracking.messages.no_selection_delete", default="No Selection"),
                                 _t("waste_tracking.messages.no_selection_delete", default="Please select a waste entry to delete"))
            return

        if messagebox.askyesno(_t("waste_tracking.buttons.delete", default="Confirm Delete"),
                              _t("waste_tracking.messages.confirm_delete_entry", default="Delete selected waste entry?\n\nThis cannot be undone.")):
            try:
                values = self.waste_tree.item(selection[0])['values']

                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM restaurant_waste
                    WHERE waste_id IN (
                        SELECT waste_id FROM restaurant_waste
                        WHERE waste_date = ? AND item_name = ?
                        ORDER BY waste_id DESC
                        LIMIT 1
                    )
                ''', (values[0], values[1]))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t("waste_tracking.messages.success_delete_entry", default="Success"),
                                  _t("waste_tracking.messages.success_delete_entry", default="Waste entry deleted"))
                self.load_waste_entries()

            except Exception as e:
                messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                                   _t("waste_tracking.errors.delete_waste_entry", default="Failed to delete waste entry: {error}").format(error=e))

    def export_waste_data(self):
        """Export waste data to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=_t("waste_tracking.export.csv_extension", default=".csv"),
                filetypes=[(_t("waste_tracking.export.csv_files", default="CSV files"), "*.csv"),
                          (_t("waste_tracking.export.all_files", default="All files"), "*.*")],
                initialfile=_t("waste_tracking.export.default_filename", default="waste_data_{date}.csv").format(date=datetime.now().strftime('%Y%m%d'))
            )

            if not filename:
                return

            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT waste_date, item_name, quantity, unit_of_measure, cost_value,
                       waste_type, reason, responsible_staff, notes
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
                ORDER BY waste_date DESC
            ''', (self.start_date_var.get(), self.end_date_var.get()))

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                headers = _t("waste_tracking.export.csv_headers", default=['Date', 'Item Name', 'Quantity', 'Unit', 'Cost Value',
                               'Waste Type', 'Reason', 'Responsible Staff', 'Notes'])
                writer.writerow(headers)

                for row in cursor.fetchall():
                    writer.writerow(row)

            conn.close()

            messagebox.showinfo(_t("waste_tracking.messages.export_success", default="Success"),
                              _t("waste_tracking.messages.export_success", default="Waste data exported to:\n{filename}").format(filename=filename))

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.export_data", default="Failed to export data: {error}").format(error=e))

    def generate_analytics_report(self):
        """Generate waste analytics report"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get date range (last 30 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')

            report = _t("waste_tracking.report.title", default="WASTE ANALYTICS REPORT") + "\n"
            report += _t("waste_tracking.report.period", default="Period: {start} to {end}").format(start=start_str, end=end_str) + "\n"
            report += _t("waste_tracking.report.separator_main", default="=" * 100) + "\n\n"

            # Overall statistics
            cursor.execute('''
                SELECT
                    COUNT(*) as total_entries,
                    SUM(cost_value) as total_cost,
                    AVG(cost_value) as avg_cost,
                    SUM(quantity) as total_quantity
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
            ''', (start_str, end_str))

            stats = cursor.fetchone()
            total_entries = stats[0] if stats[0] else 0
            total_cost = stats[1] if stats[1] else 0
            avg_cost = stats[2] if stats[2] else 0
            total_quantity = stats[3] if stats[3] else 0

            report += _t("waste_tracking.report.overall_stats_title", default="OVERALL STATISTICS:") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"
            report += _t("waste_tracking.report.total_entries", default="Total Waste Entries: {count}").format(count=total_entries) + "\n"
            report += _t("waste_tracking.report.total_cost", default="Total Waste Cost: £{cost}").format(cost=f"{total_cost:.2f}") + "\n"
            report += _t("waste_tracking.report.avg_cost", default="Average Cost per Entry: £{cost}").format(cost=f"{avg_cost:.2f}") + "\n"
            report += _t("waste_tracking.report.total_quantity", default="Total Quantity Wasted: {quantity} units").format(quantity=f"{total_quantity:.2f}") + "\n\n"

            # Waste by type
            cursor.execute('''
                SELECT waste_type, COUNT(*), SUM(cost_value)
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
                GROUP BY waste_type
                ORDER BY SUM(cost_value) DESC
            ''', (start_str, end_str))

            waste_by_type = cursor.fetchall()

            report += _t("waste_tracking.report.waste_by_type_title", default="WASTE BY TYPE:") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"
            report += _t("waste_tracking.report.waste_by_type_header_labels", default="Type                          Entries         Total Cost      % of Total     ") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"

            for waste_type, count, cost in waste_by_type:
                cost = cost if cost else 0
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                unknown_text = _t("waste_tracking.report.unknown", default="Unknown")
                report += f"{waste_type or unknown_text:<30} {count:<15} £{cost:<14.2f} {percentage:<14.1f}%\n"

            report += "\n"

            # Top 10 most wasted items
            cursor.execute('''
                SELECT item_name, SUM(quantity), SUM(cost_value)
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
                GROUP BY item_name
                ORDER BY SUM(cost_value) DESC
                LIMIT 10
            ''', (start_str, end_str))

            top_items = cursor.fetchall()

            report += _t("waste_tracking.report.top_items_title", default="TOP 10 MOST WASTED ITEMS:") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"
            report += _t("waste_tracking.report.top_items_header_labels", default="Item Name                               Total Quantity       Total Cost     ") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"

            for item_name, quantity, cost in top_items:
                cost = cost if cost else 0
                report += f"{item_name:<40} {quantity:<20.2f} £{cost:<14.2f}\n"

            report += "\n"

            # Daily average
            cursor.execute('''
                SELECT COUNT(DISTINCT waste_date)
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
            ''', (start_str, end_str))

            days_with_waste = cursor.fetchone()[0]
            daily_avg = total_cost / days_with_waste if days_with_waste > 0 else 0

            report += _t("waste_tracking.report.daily_stats_title", default="DAILY STATISTICS:") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"
            report += _t("waste_tracking.report.days_with_waste", default="Days with waste recorded: {days}").format(days=days_with_waste) + "\n"
            report += _t("waste_tracking.report.avg_daily_cost", default="Average waste cost per day: £{cost}").format(cost=f"{daily_avg:.2f}") + "\n"
            report += _t("waste_tracking.report.projected_monthly", default="Projected monthly waste cost: £{cost}").format(cost=f"{daily_avg * 30:.2f}") + "\n\n"

            # Recommendations
            report += _t("waste_tracking.report.recommendations_title", default="RECOMMENDATIONS:") + "\n"
            report += _t("waste_tracking.report.separator_section", default="-" * 100) + "\n"

            if total_cost > 500:
                report += _t("waste_tracking.report.high_waste_warning", default="⚠ HIGH WASTE COST: Monthly waste exceeds £500") + "\n"
                report += _t("waste_tracking.report.high_waste_advice_1", default="  - Review portion sizes") + "\n"
                report += _t("waste_tracking.report.high_waste_advice_2", default="  - Improve inventory management") + "\n"
                report += _t("waste_tracking.report.high_waste_advice_3", default="  - Train staff on food handling") + "\n\n"

            report += _t("waste_tracking.report.focus_top_items", default="• Focus on reducing top wasted items") + "\n"
            report += _t("waste_tracking.report.monitor_patterns", default="• Monitor waste patterns to identify trends") + "\n"
            report += _t("waste_tracking.report.implement_fifo", default="• Implement FIFO (First In, First Out) inventory system") + "\n"
            report += _t("waste_tracking.report.staff_training", default="• Regular staff training on waste reduction") + "\n"

            report += "\n" + _t("waste_tracking.report.separator_main", default="=" * 100) + "\n"

            conn.close()

            self.analytics_text.delete('1.0', tk.END)
            self.analytics_text.insert('1.0', report)

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.generate_analytics", default="Failed to generate analytics: {error}").format(error=e))

    def add_category(self):
        """Add waste category"""
        dialog = WasteCategoryDialog(self.window, None)
        if dialog.result:
            self.load_categories()
            self.load_waste_types()

    def edit_category(self):
        """Edit waste category"""
        selection = self.categories_tree.selection()
        if not selection:
            messagebox.showwarning(_t("waste_tracking.messages.no_selection_category", default="No Selection"),
                                 _t("waste_tracking.messages.no_selection_category", default="Please select a category to edit"))
            return

        category_name = self.categories_tree.item(selection[0])['values'][0]
        dialog = WasteCategoryDialog(self.window, category_name)
        if dialog.result:
            self.load_categories()
            self.load_waste_types()

    def delete_category(self):
        """Delete waste category"""
        selection = self.categories_tree.selection()
        if not selection:
            messagebox.showwarning(_t("waste_tracking.messages.no_selection_category_delete", default="No Selection"),
                                 _t("waste_tracking.messages.no_selection_category_delete", default="Please select a category to delete"))
            return

        category_name = self.categories_tree.item(selection[0])['values'][0]

        if messagebox.askyesno(_t("waste_tracking.buttons.delete", default="Confirm Delete"),
                              _t("waste_tracking.messages.confirm_delete_category", default="Delete category '{category}'?\n\nThis cannot be undone.").format(category=category_name)):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('DELETE FROM restaurant_waste_categories WHERE category_name = ?',
                             (category_name,))
                conn.commit()
                conn.close()

                messagebox.showinfo(_t("waste_tracking.messages.success_delete_category", default="Success"),
                                  _t("waste_tracking.messages.success_delete_category", default="Category deleted"))
                self.load_categories()
                self.load_waste_types()

            except Exception as e:
                messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                                   _t("waste_tracking.errors.delete_category", default="Failed to delete category: {error}").format(error=e))


class WasteEntryDialog:
    """Dialog for recording/editing waste entries"""

    def __init__(self, parent, waste_id=None):
        self.result = False
        self.waste_id = waste_id
        self.is_edit = waste_id is not None

        self.dialog = tk.Toplevel(parent)
        title = _t("waste_tracking.dialogs.edit_waste_title", default="Edit Waste Entry") if self.is_edit else _t("waste_tracking.dialogs.record_waste_title", default="Record Waste")
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if self.is_edit:
            self.load_waste_data()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Date
        ttk.Label(frame, text=_t("waste_tracking.labels.date", default="Date:*")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=self.date_var, width=40).grid(row=0, column=1, pady=5)

        # Item name
        ttk.Label(frame, text=_t("waste_tracking.labels.item_name", default="Item Name:*")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.item_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.item_var, width=40).grid(row=1, column=1, pady=5)

        # Quantity
        ttk.Label(frame, text=_t("waste_tracking.labels.quantity", default="Quantity:*")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.quantity_var = tk.DoubleVar(value=0.0)
        ttk.Entry(frame, textvariable=self.quantity_var, width=40).grid(row=2, column=1, pady=5)

        # Unit
        ttk.Label(frame, text=_t("waste_tracking.labels.unit_of_measure", default="Unit of Measure:*")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.unit_var = tk.StringVar(value=_t("waste_tracking.units.kg", default="kg"))
        unit_values = [
            _t("waste_tracking.units.kg", default="kg"),
            _t("waste_tracking.units.g", default="g"),
            _t("waste_tracking.units.l", default="L"),
            _t("waste_tracking.units.ml", default="ml"),
            _t("waste_tracking.units.units", default="units"),
            _t("waste_tracking.units.portions", default="portions")
        ]
        ttk.Combobox(frame, textvariable=self.unit_var, width=38,
                    values=unit_values).grid(row=3, column=1, pady=5)

        # Cost
        ttk.Label(frame, text=_t("waste_tracking.labels.cost_value", default="Cost Value (£):*")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.cost_var = tk.DoubleVar(value=0.0)
        ttk.Entry(frame, textvariable=self.cost_var, width=40).grid(row=4, column=1, pady=5)

        # Waste type
        ttk.Label(frame, text=_t("waste_tracking.labels.waste_type_field", default="Waste Type:*")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(frame, textvariable=self.type_var, width=38)
        self.type_combo.grid(row=5, column=1, pady=5)
        self.load_waste_types()

        # Reason
        ttk.Label(frame, text=_t("waste_tracking.labels.reason", default="Reason:*")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.reason_var = tk.StringVar()
        reason_values = [
            _t("waste_tracking.reasons.expired", default="Expired"),
            _t("waste_tracking.reasons.spoiled", default="Spoiled"),
            _t("waste_tracking.reasons.over_cooked", default="Over-cooked"),
            _t("waste_tracking.reasons.customer_return", default="Customer Return"),
            _t("waste_tracking.reasons.dropped", default="Dropped"),
            _t("waste_tracking.reasons.over_production", default="Over-production"),
            _t("waste_tracking.reasons.quality_issues", default="Quality Issues"),
            _t("waste_tracking.reasons.other", default="Other")
        ]
        ttk.Combobox(frame, textvariable=self.reason_var, width=38,
                    values=reason_values).grid(row=6, column=1, pady=5)

        # Responsible staff
        ttk.Label(frame, text=_t("waste_tracking.labels.responsible_staff", default="Responsible Staff:")).grid(row=7, column=0, sticky=tk.W, pady=5)
        self.staff_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.staff_var, width=40).grid(row=7, column=1, pady=5)

        # Notes
        ttk.Label(frame, text=_t("waste_tracking.labels.notes", default="Notes:")).grid(row=8, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(frame, height=4, width=40)
        self.notes_text.grid(row=8, column=1, pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.save", default="Save"), command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.cancel", default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_waste_types(self):
        """Load waste types for combobox"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('SELECT category_name FROM restaurant_waste_categories ORDER BY category_name')
            types = [row[0] for row in cursor.fetchall()]
            self.type_combo['values'] = types
            if types:
                self.type_var.set(types[0])
            conn.close()

        except Exception as e:
            print(_t("waste_tracking.errors.load_waste_types", default="Error loading waste types: {error}").format(error=e))

    def load_waste_data(self):
        """Load existing waste data"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT waste_date, item_name, quantity, unit_of_measure, cost_value,
                       waste_type, reason, responsible_staff, notes
                FROM restaurant_waste
                WHERE waste_id = ?
            ''', (self.waste_id,))

            data = cursor.fetchone()
            conn.close()

            if data:
                self.date_var.set(data[0])
                self.item_var.set(data[1])
                self.quantity_var.set(data[2])
                self.unit_var.set(data[3] or _t("waste_tracking.units.kg", default="kg"))
                self.cost_var.set(data[4])
                self.type_var.set(data[5] or '')
                self.reason_var.set(data[6])
                self.staff_var.set(data[7] or '')
                self.notes_text.insert('1.0', data[8] or '')

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.load_waste_data", default="Failed to load waste data: {error}").format(error=e))

    def save(self):
        """Save waste entry"""
        # Validation
        if not all([self.item_var.get(), self.date_var.get(), self.type_var.get(),
                   self.reason_var.get()]):
            messagebox.showwarning(_t("waste_tracking.messages.missing_info", default="Missing Info"),
                                 _t("waste_tracking.messages.missing_info", default="Please fill in all required fields"))
            return

        if self.quantity_var.get() <= 0 or self.cost_var.get() <= 0:
            messagebox.showwarning(_t("waste_tracking.messages.invalid_values", default="Invalid Values"),
                                 _t("waste_tracking.messages.invalid_values", default="Quantity and cost must be greater than 0"))
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            notes = self.notes_text.get('1.0', tk.END).strip()

            if self.is_edit:
                cursor.execute('''
                    UPDATE restaurant_waste
                    SET waste_date = ?, item_name = ?, quantity = ?, unit_of_measure = ?,
                        cost_value = ?, waste_type = ?, reason = ?, responsible_staff = ?, notes = ?
                    WHERE waste_id = ?
                ''', (self.date_var.get(), self.item_var.get(), self.quantity_var.get(),
                     self.unit_var.get(), self.cost_var.get(), self.type_var.get(),
                     self.reason_var.get(), self.staff_var.get(), notes, self.waste_id))
            else:
                cursor.execute('''
                    INSERT INTO restaurant_waste
                    (waste_date, item_name, quantity, unit_of_measure, cost_value,
                     waste_type, reason, responsible_staff, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.date_var.get(), self.item_var.get(), self.quantity_var.get(),
                     self.unit_var.get(), self.cost_var.get(), self.type_var.get(),
                     self.reason_var.get(), self.staff_var.get(), notes))

            conn.commit()
            conn.close()

            self.result = True
            messagebox.showinfo(_t("waste_tracking.messages.success_save_entry", default="Success"),
                              _t("waste_tracking.messages.success_save_entry", default="Waste entry saved successfully"))
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.save_waste_entry", default="Failed to save waste entry: {error}").format(error=e))


class WasteCategoryDialog:
    """Dialog for adding/editing waste categories"""

    def __init__(self, parent, category_name=None):
        self.result = False
        self.category_name = category_name
        self.is_edit = category_name is not None

        self.dialog = tk.Toplevel(parent)
        title = _t("waste_tracking.dialogs.edit_category_title", default="Edit Category") if self.is_edit else _t("waste_tracking.dialogs.new_category_title", default="New Category")
        self.dialog.title(title)
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if self.is_edit:
            self.load_category_data()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t("waste_tracking.labels.category_name", default="Category Name:*")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t("waste_tracking.labels.description", default="Description:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.desc_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.desc_var, width=40).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t("waste_tracking.labels.target_percentage", default="Target % of Total:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.DoubleVar(value=5.0)
        ttk.Entry(frame, textvariable=self.target_var, width=40).grid(row=2, column=1, pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.save", default="Save"), command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("waste_tracking.buttons.cancel", default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_category_data(self):
        """Load existing category data"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT category_name, description, target_percentage
                FROM restaurant_waste_categories
                WHERE category_name = ?
            ''', (self.category_name,))

            data = cursor.fetchone()
            conn.close()

            if data:
                self.name_var.set(data[0])
                self.desc_var.set(data[1] or '')
                self.target_var.set(data[2] or 5.0)

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.load_category_data", default="Failed to load category data: {error}").format(error=e))

    def save(self):
        """Save category"""
        if not self.name_var.get():
            messagebox.showwarning(_t("waste_tracking.messages.missing_category_name", default="Missing Info"),
                                 _t("waste_tracking.messages.missing_category_name", default="Please enter category name"))
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if self.is_edit:
                cursor.execute('''
                    UPDATE restaurant_waste_categories
                    SET category_name = ?, description = ?, target_percentage = ?
                    WHERE category_name = ?
                ''', (self.name_var.get(), self.desc_var.get(),
                     self.target_var.get(), self.category_name))
            else:
                cursor.execute('''
                    INSERT INTO restaurant_waste_categories
                    (category_name, description, target_percentage)
                    VALUES (?, ?, ?)
                ''', (self.name_var.get(), self.desc_var.get(), self.target_var.get()))

            conn.commit()
            conn.close()

            self.result = True
            messagebox.showinfo(_t("waste_tracking.messages.success_save_category", default="Success"),
                              _t("waste_tracking.messages.success_save_category", default="Category saved successfully"))
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("waste_tracking.buttons.delete", default="Error"),
                               _t("waste_tracking.errors.save_category", default="Failed to save category: {error}").format(error=e))
