"""Revenue by Source Manager - Visual analytics for revenue breakdown by transaction source"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from typing import Optional

from university_system.modules.domain.finance.reporting.revenue_by_source_report import (
    get_revenue_by_source,
    get_source_revenue_trend,
    compare_source_revenue_periods,
    export_revenue_by_source_csv
)


class RevenueSourceManager:
    """Manages revenue by source reporting and visualization"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn

        # Color scheme
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8'
        }

        # Revenue source colors for charts
        self.source_colors = {
            'Library': '#3498db',
            'Housing': '#e74c3c',
            'Shop': '#f39c12',
            'Restaurant': '#9b59b6',
            'Alumni': '#1abc9c',
            'Student Union': '#34495e',
            'Trip Management': '#e67e22',
            'Tuition & Fees': '#27ae60'
        }

        # Current filter state
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()

    def create_revenue_source_tab(self):
        """Create the Revenue by Source tab"""
        # Create main frame for this tab
        revenue_source_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['revenue_source'] = revenue_source_frame

        # Title
        title_label = tk.Label(
            revenue_source_frame,
            text="💰 Revenue by Source Analytics",
            font=('Arial', 18, 'bold'),
            bg='white'
        )
        title_label.pack(pady=10)

        # Toolbar with filters
        toolbar = tk.Frame(revenue_source_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        # Date filters
        tk.Label(toolbar, text="Start Date:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        start_entry = ttk.Entry(toolbar, textvariable=self.start_date_var, width=12)
        start_entry.pack(side='left', padx=5)
        start_entry.insert(0, (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

        tk.Label(toolbar, text="End Date:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        end_entry = ttk.Entry(toolbar, textvariable=self.end_date_var, width=12)
        end_entry.pack(side='left', padx=5)
        end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Action buttons
        tk.Button(
            toolbar,
            text="🔍 Load Data",
            command=self.load_revenue_data,
            bg=self.colors['secondary'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="📊 Show Charts",
            command=self.show_charts,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="📈 Trends",
            command=self.show_trends,
            bg=self.colors['warning'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="💾 Export CSV",
            command=self.export_data,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        # Main content area with paned window
        paned = ttk.PanedWindow(revenue_source_frame, orient=tk.HORIZONTAL)
        paned.pack(fill='both', expand=True, padx=10, pady=10)

        # Left panel - Data table
        left_frame = tk.Frame(paned, bg='white')
        paned.add(left_frame, weight=1)

        tk.Label(
            left_frame,
            text="Revenue Breakdown by Source",
            font=('Arial', 12, 'bold'),
            bg='white'
        ).pack(pady=5)

        # Create treeview for data
        tree_frame = tk.Frame(left_frame)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')

        tree_scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')

        # Treeview
        self.revenue_tree = ttk.Treeview(
            tree_frame,
            columns=('Source', 'Count', 'Total', 'Average', 'Min', 'Max', 'Percentage'),
            show='headings',
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )

        tree_scroll_y.config(command=self.revenue_tree.yview)
        tree_scroll_x.config(command=self.revenue_tree.xview)

        # Configure columns
        self.revenue_tree.heading('Source', text='Transaction Source')
        self.revenue_tree.heading('Count', text='Count')
        self.revenue_tree.heading('Total', text='Total Revenue')
        self.revenue_tree.heading('Average', text='Avg Amount')
        self.revenue_tree.heading('Min', text='Min')
        self.revenue_tree.heading('Max', text='Max')
        self.revenue_tree.heading('Percentage', text='% of Total')

        self.revenue_tree.column('Source', width=150)
        self.revenue_tree.column('Count', width=80, anchor='center')
        self.revenue_tree.column('Total', width=120, anchor='e')
        self.revenue_tree.column('Average', width=100, anchor='e')
        self.revenue_tree.column('Min', width=80, anchor='e')
        self.revenue_tree.column('Max', width=80, anchor='e')
        self.revenue_tree.column('Percentage', width=100, anchor='e')

        self.revenue_tree.pack(fill='both', expand=True)

        # Summary labels
        self.summary_label = tk.Label(
            left_frame,
            text="Total: £0.00 | Transactions: 0",
            font=('Arial', 10, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        self.summary_label.pack(pady=5)

        # Right panel - Chart area
        right_frame = tk.Frame(paned, bg='white')
        paned.add(right_frame, weight=1)

        tk.Label(
            right_frame,
            text="Visual Analytics",
            font=('Arial', 12, 'bold'),
            bg='white'
        ).pack(pady=5)

        # Chart canvas
        self.chart_frame = tk.Frame(right_frame, bg='white')
        self.chart_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Initially load data
        self.root.after(100, self.load_revenue_data)

    def load_revenue_data(self):
        """Load and display revenue by source data"""
        try:
            # Clear existing data
            for item in self.revenue_tree.get_children():
                self.revenue_tree.delete(item)

            # Get date filters
            start_date = self.start_date_var.get().strip()
            end_date = self.end_date_var.get().strip()

            # Validate dates
            if not start_date or not end_date:
                messagebox.showwarning("Input Required", "Please enter both start and end dates.")
                return

            # Get revenue data
            revenue_data = get_revenue_by_source(start_date, end_date)

            if not revenue_data:
                messagebox.showinfo("No Data", "No revenue data found for the specified period.")
                return

            # Calculate totals
            total_transactions = sum(data['count'] for data in revenue_data.values())
            total_revenue = sum(data['total'] for data in revenue_data.values())

            # Populate treeview
            for source, data in sorted(revenue_data.items(), key=lambda x: x[1]['total'], reverse=True):
                percentage = (data['total'] / total_revenue * 100) if total_revenue > 0 else 0

                self.revenue_tree.insert('', 'end', values=(
                    source,
                    f"{data['count']:,}",
                    f"£{data['total']:,.2f}",
                    f"£{data['average']:,.2f}",
                    f"£{data['min']:,.2f}",
                    f"£{data['max']:,.2f}",
                    f"{percentage:.1f}%"
                ))

            # Update summary
            self.summary_label.config(
                text=f"Total: £{total_revenue:,.2f} | Transactions: {total_transactions:,}"
            )

            # Store data for charting
            self.current_revenue_data = revenue_data

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load revenue data:\n{str(e)}")

    def show_charts(self):
        """Display pie and bar charts for revenue breakdown"""
        if not hasattr(self, 'current_revenue_data') or not self.current_revenue_data:
            messagebox.showwarning("No Data", "Please load data first using the 'Load Data' button.")
            return

        try:
            # Clear existing charts
            for widget in self.chart_frame.winfo_children():
                widget.destroy()

            # Create figure with subplots
            fig = Figure(figsize=(10, 8), dpi=100)

            # Prepare data
            sources = list(self.current_revenue_data.keys())
            revenues = [data['total'] for data in self.current_revenue_data.values()]
            counts = [data['count'] for data in self.current_revenue_data.values()]

            # Sort by revenue
            sorted_data = sorted(zip(sources, revenues, counts), key=lambda x: x[1], reverse=True)
            sources, revenues, counts = zip(*sorted_data)

            # Pie chart - Revenue distribution
            ax1 = fig.add_subplot(2, 1, 1)
            colors = [self.source_colors.get(src, '#95a5a6') for src in sources]
            wedges, texts, autotexts = ax1.pie(
                revenues,
                labels=sources,
                autopct='%1.1f%%',
                colors=colors,
                startangle=90
            )
            ax1.set_title('Revenue Distribution by Source', fontsize=12, fontweight='bold')

            # Make percentage text bold
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            # Bar chart - Revenue amounts
            ax2 = fig.add_subplot(2, 1, 2)
            bars = ax2.bar(range(len(sources)), revenues, color=colors)
            ax2.set_xticks(range(len(sources)))
            ax2.set_xticklabels(sources, rotation=45, ha='right')
            ax2.set_ylabel('Revenue (£)', fontweight='bold')
            ax2.set_title('Revenue by Source (Bar Chart)', fontsize=12, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax2.text(
                    bar.get_x() + bar.get_width() / 2.,
                    height,
                    f'£{height:,.0f}',
                    ha='center',
                    va='bottom',
                    fontsize=8
                )

            fig.tight_layout()

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create charts:\n{str(e)}")

    def show_trends(self):
        """Display trend analysis for selected source"""
        if not hasattr(self, 'current_revenue_data') or not self.current_revenue_data:
            messagebox.showwarning("No Data", "Please load data first.")
            return

        # Create dialog for source selection
        trend_window = tk.Toplevel(self.root)
        trend_window.title("Revenue Trends by Source")
        trend_window.geometry("900x600")

        # Source selection
        top_frame = tk.Frame(trend_window, bg='white')
        top_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(top_frame, text="Select Source:", bg='white', font=('Arial', 10, 'bold')).pack(side='left', padx=5)

        source_var = tk.StringVar()
        source_combo = ttk.Combobox(
            top_frame,
            textvariable=source_var,
            values=list(self.current_revenue_data.keys()),
            state='readonly',
            width=20
        )
        source_combo.pack(side='left', padx=5)
        source_combo.current(0)

        tk.Label(top_frame, text="Months:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        months_var = tk.StringVar(value="12")
        months_entry = ttk.Entry(top_frame, textvariable=months_var, width=5)
        months_entry.pack(side='left', padx=5)

        def show_trend_chart():
            source = source_var.get()
            try:
                months = int(months_var.get())
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid number of months.")
                return

            # Get trend data
            trend_data = get_source_revenue_trend(source, months)

            if not trend_data:
                messagebox.showinfo("No Data", f"No trend data available for {source}.")
                return

            # Clear chart area
            for widget in chart_container.winfo_children():
                widget.destroy()

            # Create chart
            fig = Figure(figsize=(8, 5), dpi=100)
            ax = fig.add_subplot(111)

            # Extract data
            month_labels = [item[0] for item in trend_data]
            revenues = [item[1] for item in trend_data]
            counts = [item[2] for item in trend_data]

            # Reverse to show oldest first
            month_labels.reverse()
            revenues.reverse()
            counts.reverse()

            # Plot revenue trend
            color = self.source_colors.get(source, '#3498db')
            ax.plot(month_labels, revenues, marker='o', linewidth=2, color=color, label='Revenue')
            ax.set_xlabel('Month', fontweight='bold')
            ax.set_ylabel('Revenue (£)', fontweight='bold', color=color)
            ax.tick_params(axis='y', labelcolor=color)
            ax.grid(True, alpha=0.3)
            ax.set_title(f'{source} Revenue Trend (Last {months} Months)', fontsize=12, fontweight='bold')

            # Rotate x-axis labels
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            # Add transaction count on secondary axis
            ax2 = ax.twinx()
            ax2.bar(month_labels, counts, alpha=0.3, color='gray', label='Transactions')
            ax2.set_ylabel('Transaction Count', fontweight='bold', color='gray')
            ax2.tick_params(axis='y', labelcolor='gray')

            fig.tight_layout()

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=chart_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        tk.Button(
            top_frame,
            text="📈 Show Trend",
            command=show_trend_chart,
            bg=self.colors['secondary'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5
        ).pack(side='left', padx=5)

        # Chart container
        chart_container = tk.Frame(trend_window, bg='white')
        chart_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Show initial trend
        show_trend_chart()

    def export_data(self):
        """Export revenue by source data to CSV"""
        try:
            # Ask for filename
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"revenue_by_source_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if not filename:
                return

            # Get date filters
            start_date = self.start_date_var.get().strip() or None
            end_date = self.end_date_var.get().strip() or None

            # Export
            if export_revenue_by_source_csv(filename, start_date, end_date):
                messagebox.showinfo("Success", f"Revenue data exported to:\n{filename}")
            else:
                messagebox.showerror("Error", "Failed to export revenue data.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data:\n{str(e)}")
