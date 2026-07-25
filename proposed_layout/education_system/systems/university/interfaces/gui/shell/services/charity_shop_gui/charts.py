"""Charity Shop - Charts and analytics window."""

from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui._imports import (
    tk, ttk,
    MATPLOTLIB_AVAILABLE, plt, FigureCanvasTkAgg, Figure,
    logging,
)
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.database import Database

logger = logging.getLogger(__name__)


class ChartsWindow(tk.Toplevel):
    """Window for displaying charts and analytics."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.title("Sales Analytics & Charts")
        self.geometry("900x700")
        self.db = db

        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self, text="matplotlib is not installed.\nPlease install it with: pip install matplotlib",
                     font=("Helvetica", 12)).pack(expand=True)
            return

        self.create_widgets()

    def create_widgets(self):
        """Create chart widgets."""
        # Create notebook for different chart tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Revenue Overview Tab
        revenue_frame = ttk.Frame(notebook)
        notebook.add(revenue_frame, text="Revenue Overview")
        self.create_revenue_overview(revenue_frame)

        # Category Breakdown Tab
        category_frame = ttk.Frame(notebook)
        notebook.add(category_frame, text="Category Analysis")
        self.create_category_charts(category_frame)

        # Sales Timeline Tab
        timeline_frame = ttk.Frame(notebook)
        notebook.add(timeline_frame, text="Sales Timeline")
        self.create_timeline_chart(timeline_frame)

        # Stock Status Tab
        stock_frame = ttk.Frame(notebook)
        notebook.add(stock_frame, text="Stock Status")
        self.create_stock_charts(stock_frame)

    def create_revenue_overview(self, parent):
        """Create revenue overview with summary stats."""
        # Summary stats at top
        stats_frame = ttk.LabelFrame(parent, text="Revenue Summary", padding="10")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        revenue_data = self.db.get_revenue_summary()
        stock_data = self.db.get_stock_summary()

        sold_items = revenue_data[0] or 0
        total_sold = revenue_data[1] or 0
        total_revenue = revenue_data[2] or 0.0

        stock_items = stock_data[0] or 0
        stock_qty = stock_data[1] or 0
        stock_value = stock_data[2] or 0.0

        # Create stats grid
        stats = [
            ("Total Revenue:", f"\u00a3{total_revenue:.2f}"),
            ("Items Sold:", str(total_sold)),
            ("Unique Products Sold:", str(sold_items)),
            ("Current Stock Items:", str(stock_items)),
            ("Current Stock Qty:", str(stock_qty)),
            ("Stock Value:", f"\u00a3{stock_value:.2f}"),
        ]

        for i, (label, value) in enumerate(stats):
            row, col = divmod(i, 3)
            ttk.Label(stats_frame, text=label, font=("Helvetica", 10)).grid(row=row, column=col*2, sticky="e", padx=5, pady=5)
            ttk.Label(stats_frame, text=value, font=("Helvetica", 10, "bold")).grid(row=row, column=col*2+1, sticky="w", padx=5, pady=5)

        # Pie chart: Revenue vs Remaining Stock Value
        fig = Figure(figsize=(8, 4), dpi=100)
        ax = fig.add_subplot(121)

        if total_revenue > 0 or stock_value > 0:
            values = [total_revenue, stock_value]
            labels = [f'Revenue\n\u00a3{total_revenue:.2f}', f'Stock Value\n\u00a3{stock_value:.2f}']
            colors = ['#2ecc71', '#3498db']
            ax.pie(values, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax.set_title('Revenue vs Stock Value')
        else:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center')
            ax.set_title('Revenue vs Stock Value')

        # Bar chart: Sold vs Available
        ax2 = fig.add_subplot(122)
        categories = ['Items Sold', 'In Stock']
        values = [total_sold, stock_qty]
        colors = ['#2ecc71', '#3498db']
        ax2.bar(categories, values, color=colors)
        ax2.set_ylabel('Quantity')
        ax2.set_title('Sold vs Available Stock')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_category_charts(self, parent):
        """Create category breakdown charts."""
        fig = Figure(figsize=(10, 5), dpi=100)

        # Revenue by category (pie chart)
        ax1 = fig.add_subplot(121)
        revenue_by_cat = self.db.get_revenue_by_category()

        if revenue_by_cat:
            categories = [r[0] for r in revenue_by_cat]
            revenues = [r[1] for r in revenue_by_cat]
            colors = plt.cm.Set3(range(len(categories)))
            ax1.pie(revenues, labels=categories, autopct='%1.1f%%', colors=colors, startangle=90)
            ax1.set_title('Revenue by Category')
        else:
            ax1.text(0.5, 0.5, 'No sales data', ha='center', va='center')
            ax1.set_title('Revenue by Category')

        # Stock by category (bar chart)
        ax2 = fig.add_subplot(122)
        stock_by_cat = self.db.get_stock_by_category()

        if stock_by_cat:
            categories = [s[0] for s in stock_by_cat]
            quantities = [s[2] for s in stock_by_cat]
            colors = plt.cm.Set3(range(len(categories)))
            bars = ax2.barh(categories, quantities, color=colors)
            ax2.set_xlabel('Quantity')
            ax2.set_title('Current Stock by Category')
            ax2.invert_yaxis()
        else:
            ax2.text(0.5, 0.5, 'No stock data', ha='center', va='center')
            ax2.set_title('Current Stock by Category')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_timeline_chart(self, parent):
        """Create sales timeline chart."""
        # Controls frame
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(control_frame, text="Show last:").pack(side=tk.LEFT)
        self.days_var = tk.StringVar(value="30")
        days_combo = ttk.Combobox(control_frame, textvariable=self.days_var,
                                  values=["7", "14", "30", "60", "90"], width=5, state="readonly")
        days_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(control_frame, text="days").pack(side=tk.LEFT)

        self.timeline_container = ttk.Frame(parent)
        self.timeline_container.pack(fill=tk.BOTH, expand=True)

        days_combo.bind("<<ComboboxSelected>>", lambda e: self.update_timeline())
        self.update_timeline()

    def update_timeline(self):
        """Update the timeline chart."""
        for widget in self.timeline_container.winfo_children():
            widget.destroy()

        days = int(self.days_var.get())
        revenue_by_date = self.db.get_revenue_by_date(days)

        fig = Figure(figsize=(10, 5), dpi=100)
        ax = fig.add_subplot(111)

        if revenue_by_date:
            dates = [r[0] for r in revenue_by_date]
            revenues = [r[1] for r in revenue_by_date]

            ax.plot(dates, revenues, marker='o', linewidth=2, markersize=6, color='#2ecc71')
            ax.fill_between(dates, revenues, alpha=0.3, color='#2ecc71')
            ax.set_xlabel('Date')
            ax.set_ylabel('Revenue (\u00a3)')
            ax.set_title(f'Daily Revenue - Last {days} Days')
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            # Add total
            total = sum(revenues)
            ax.text(0.02, 0.98, f'Total: \u00a3{total:.2f}', transform=ax.transAxes,
                   fontsize=12, verticalalignment='top', fontweight='bold')
        else:
            ax.text(0.5, 0.5, f'No sales in the last {days} days', ha='center', va='center')
            ax.set_title(f'Daily Revenue - Last {days} Days')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self.timeline_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_stock_charts(self, parent):
        """Create stock status charts."""
        fig = Figure(figsize=(10, 5), dpi=100)

        # Sales by condition
        ax1 = fig.add_subplot(121)
        sales_by_condition = self.db.get_sales_by_condition()

        if sales_by_condition:
            conditions = [s[0] for s in sales_by_condition]
            revenues = [s[2] for s in sales_by_condition]
            colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c']
            ax1.bar(conditions, revenues, color=colors[:len(conditions)])
            ax1.set_xlabel('Condition')
            ax1.set_ylabel('Revenue (\u00a3)')
            ax1.set_title('Revenue by Item Condition')
        else:
            ax1.text(0.5, 0.5, 'No sales data', ha='center', va='center')
            ax1.set_title('Revenue by Item Condition')

        # Stock health (quantity distribution)
        ax2 = fig.add_subplot(122)
        stock_items = self.db.get_all_stock(show_sold="available")

        if stock_items:
            quantities = [item[4] for item in stock_items]
            bins = [0, 1, 5, 10, 20, 50, max(quantities)+1] if max(quantities) > 50 else [0, 1, 5, 10, 20, 50]
            ax2.hist(quantities, bins=bins, color='#3498db', edgecolor='white')
            ax2.set_xlabel('Quantity per Item')
            ax2.set_ylabel('Number of Items')
            ax2.set_title('Stock Quantity Distribution')
        else:
            ax2.text(0.5, 0.5, 'No stock data', ha='center', va='center')
            ax2.set_title('Stock Quantity Distribution')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
