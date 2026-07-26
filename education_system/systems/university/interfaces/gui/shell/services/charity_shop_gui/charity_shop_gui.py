"""Charity Shop - Main application class."""

from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui._imports import (
    tk, ttk, messagebox,
    init_i18n, _t,
    get_auth, get_current_user,
    ACTIVITY_LOGGER_AVAILABLE, log_activity,
)
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.database import Database
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.dialogs import ItemDialog
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.sales import SalesMixin
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.basket_ops import BasketOpsMixin
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.reports import ReportsMixin
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.refunds import RefundsMixin


class CharityShopApp(SalesMixin, BasketOpsMixin, ReportsMixin, RefundsMixin):
    """Main application class for Charity Shop Stock Management.

    Integrated with the University Management System for authentication
    and database connectivity.
    """

    def __init__(self, root: tk.Tk, auth=None):
        """Initialize the Charity Shop application.

        Args:
            root: The Tkinter root or toplevel window
            auth: Optional authentication instance from the university system
        """
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("charity_shop.title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)

        # Store auth instance (use shared context if not provided)
        self.auth = auth if auth else get_auth()
        self.current_user = get_current_user()

        # Initialize database (uses student_records.db by default)
        self.db = Database()

        # Initialize shopping basket
        # Each item: {'id': int, 'name': str, 'price': float, 'quantity': int, 'max_qty': int}
        self.basket = []
        self.basket_window = None  # Reference to basket window if open

        self.create_menu()
        self.create_widgets()
        self.refresh_stock_list()
        self.update_summary()

        # Log access
        if ACTIVITY_LOGGER_AVAILABLE and self.current_user:
            log_activity('access', 'charity_shop', details={'user': self.current_user.get('username', 'unknown')})

    def close_window(self):
        """Close the charity shop window and return to homepage."""
        self.root.destroy()

    def create_menu(self):
        """Create application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("charity_shop.menu.add_new_item"), command=self.add_item, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label=_t("charity_shop.menu.exit"), command=self.root.quit, accelerator="Ctrl+Q")

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.edit"), menu=edit_menu)
        edit_menu.add_command(label=_t("charity_shop.menu.edit_selected"), command=self.edit_item, accelerator="Ctrl+E")
        edit_menu.add_command(label=_t("charity_shop.menu.delete_selected"), command=self.delete_item, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(label=_t("charity_shop.menu.mark_as_sold"), command=self.sell_item, accelerator="Ctrl+S")
        edit_menu.add_command(label=_t("charity_shop.menu.mark_as_available"), command=self.mark_available)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("charity_shop.menu.refresh"), command=self.refresh_stock_list, accelerator="F5")
        view_menu.add_command(label=_t("charity_shop.menu.clear_search"), command=self.clear_search)
        view_menu.add_separator()
        view_menu.add_command(label=_t("charity_shop.menu.view_charts"), command=self.show_charts, accelerator="Ctrl+G")

        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.reports"), menu=reports_menu)
        reports_menu.add_command(label=_t("charity_shop.menu.daily_sales"), command=lambda: self.show_report_with_type('daily'))
        reports_menu.add_command(label=_t("charity_shop.menu.weekly_sales"), command=lambda: self.show_report_with_type('weekly'))
        reports_menu.add_command(label=_t("charity_shop.menu.monthly_sales"), command=lambda: self.show_report_with_type('monthly'))
        reports_menu.add_command(label=_t("charity_shop.menu.total_revenue"), command=lambda: self.show_report_with_type('total'))
        reports_menu.add_separator()
        reports_menu.add_command(label=_t("charity_shop.menu.stock_status"), command=lambda: self.show_report_with_type('stock'))
        reports_menu.add_command(label=_t("charity_shop.menu.category_analysis"), command=lambda: self.show_report_with_type('category'))
        reports_menu.add_separator()
        reports_menu.add_command(label=_t("charity_shop.menu.open_reports"), command=self.show_reports_window, accelerator="Ctrl+R")

        # Refunds menu
        refunds_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Refunds", menu=refunds_menu)
        refunds_menu.add_command(label="Manage Refunds", command=self.show_refunds_window)

        # Bind keyboard shortcuts
        self.root.bind("<Control-n>", lambda e: self.add_item())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-e>", lambda e: self.edit_item())
        self.root.bind("<Control-s>", lambda e: self.sell_item())
        self.root.bind("<Control-g>", lambda e: self.show_charts())
        self.root.bind("<Control-r>", lambda e: self.show_reports_window())
        self.root.bind("<Delete>", lambda e: self.delete_item())
        self.root.bind("<F5>", lambda e: self.refresh_stock_list())

    def create_widgets(self):
        """Create main application widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with title and summary
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = ttk.Label(header_frame, text=_t("charity_shop.header.stock_management"),
                                font=("Helvetica", 16, "bold"))
        title_label.pack(side=tk.LEFT)

        # Summary frames
        summary_container = ttk.Frame(header_frame)
        summary_container.pack(side=tk.RIGHT)

        # Stock summary
        self.stock_summary_frame = ttk.LabelFrame(summary_container, text=_t("charity_shop.summary.stock"), padding="5")
        self.stock_summary_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.items_label = ttk.Label(self.stock_summary_frame, text="Items: 0")
        self.items_label.pack(side=tk.LEFT, padx=5)

        self.quantity_label = ttk.Label(self.stock_summary_frame, text="Qty: 0")
        self.quantity_label.pack(side=tk.LEFT, padx=5)

        self.value_label = ttk.Label(self.stock_summary_frame, text="Value: \u00a30.00")
        self.value_label.pack(side=tk.LEFT, padx=5)

        # Revenue summary
        self.revenue_summary_frame = ttk.LabelFrame(summary_container, text=_t("charity_shop.summary.revenue"), padding="5")
        self.revenue_summary_frame.pack(side=tk.LEFT)

        self.sold_label = ttk.Label(self.revenue_summary_frame, text="Sold: 0")
        self.sold_label.pack(side=tk.LEFT, padx=5)

        self.revenue_label = ttk.Label(self.revenue_summary_frame, text="Revenue: \u00a30.00", foreground="green")
        self.revenue_label.pack(side=tk.LEFT, padx=5)

        # Return to Homepage button
        ttk.Button(summary_container, text=_t("charity_shop.btn.return_home"),
                   command=self.close_window).pack(side=tk.LEFT, padx=(15, 0))

        # Search and filter frame
        search_frame = ttk.LabelFrame(main_frame, text=_t("charity_shop.filter.search_filter"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("charity_shop.filter.search")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.on_search())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(search_frame, text=_t("charity_shop.filter.category")).pack(side=tk.LEFT)
        self.filter_category_var = tk.StringVar(value="All")
        self.category_filter = ttk.Combobox(search_frame, textvariable=self.filter_category_var,
                                            values=["All"] + ItemDialog.CATEGORIES, width=12, state="readonly")
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.bind("<<ComboboxSelected>>", lambda e: self.on_search())

        ttk.Label(search_frame, text=_t("charity_shop.filter.status")).pack(side=tk.LEFT, padx=(15, 0))
        self.filter_status_var = tk.StringVar(value="all")
        self.status_filter = ttk.Combobox(search_frame, textvariable=self.filter_status_var,
                                          values=["all", "available", "sold"], width=10, state="readonly")
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.on_search())

        ttk.Button(search_frame, text=_t("charity_shop.btn.clear"), command=self.clear_search).pack(side=tk.LEFT, padx=10)
        ttk.Button(search_frame, text=_t("charity_shop.btn.charts"), command=self.show_charts).pack(side=tk.RIGHT, padx=5)

        # Stock table frame
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create Treeview with scrollbars
        columns = ("id", "name", "category", "price", "quantity", "condition", "status", "sold_qty", "date_added")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        # Define column headings and widths
        self.tree.heading("id", text=_t("charity_shop.table.id"))
        self.tree.heading("name", text=_t("charity_shop.table.item_name"))
        self.tree.heading("category", text=_t("charity_shop.table.category"))
        self.tree.heading("price", text=_t("charity_shop.table.price"))
        self.tree.heading("quantity", text=_t("charity_shop.table.qty"))
        self.tree.heading("condition", text=_t("charity_shop.table.condition"))
        self.tree.heading("status", text=_t("charity_shop.table.status"))
        self.tree.heading("sold_qty", text=_t("charity_shop.table.sold"))
        self.tree.heading("date_added", text=_t("charity_shop.table.date_added"))

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("category", width=100, anchor="center")
        self.tree.column("price", width=80, anchor="e")
        self.tree.column("quantity", width=50, anchor="center")
        self.tree.column("condition", width=80, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("sold_qty", width=50, anchor="center")
        self.tree.column("date_added", width=90, anchor="center")

        # Configure tags for row colors
        self.tree.tag_configure('sold', background='#d5f5e3')
        self.tree.tag_configure('low_stock', background='#fadbd8')

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Grid layout for table
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self.edit_item())

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t("charity_shop.btn.add_item"), command=self.add_item, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.edit_item"), command=self.edit_item, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.delete_item"), command=self.delete_item, width=12).pack(side=tk.LEFT, padx=3)

        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(button_frame, text=_t("charity_shop.btn.add_to_basket"), command=self.add_to_basket, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.view_basket"), command=self.show_basket_window, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.quick_sell"), command=self.sell_item, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.mark_available"), command=self.mark_available, width=12).pack(side=tk.LEFT, padx=3)

        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Quick quantity adjustment
        ttk.Label(button_frame, text=_t("charity_shop.btn.quick_qty")).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="-1", command=lambda: self.adjust_quantity(-1), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="+1", command=lambda: self.adjust_quantity(1), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Button(button_frame, text=_t("charity_shop.btn.refresh"), command=self.refresh_stock_list, width=10).pack(side=tk.RIGHT, padx=3)

    def refresh_stock_list(self):
        """Refresh the stock list from database."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get stock data
        search_term = self.search_var.get().strip()
        category = self.filter_category_var.get()
        show_sold = self.filter_status_var.get()

        if search_term or category != "All":
            stock_items = self.db.search_stock(search_term, category, show_sold)
        else:
            stock_items = self.db.get_all_stock(show_sold)

        # Populate tree
        for item in stock_items:
            # item: (id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity)
            status = "Sold" if item[7] else "Available"
            sold_qty = item[9] if len(item) > 9 else 0

            formatted_item = (
                item[0],  # id
                item[1],  # name
                item[2],  # category
                f"\u00a3{item[3]:.2f}",  # price
                item[4],  # quantity
                item[5],  # condition
                status,
                sold_qty or 0,
                item[6],  # date_added
            )

            # Determine row tag
            tag = ''
            if item[7]:  # sold
                tag = 'sold'
            elif item[4] <= 2 and item[4] > 0:  # low stock
                tag = 'low_stock'

            self.tree.insert("", tk.END, values=formatted_item, tags=(tag,))

        self.update_summary()

    def update_summary(self):
        """Update the summary statistics."""
        # Stock summary
        summary = self.db.get_stock_summary()
        total_items = summary[0] or 0
        total_quantity = summary[1] or 0
        total_value = summary[2] or 0.0

        self.items_label.config(text=f"Items: {total_items}")
        self.quantity_label.config(text=f"Qty: {total_quantity}")
        self.value_label.config(text=f"Value: \u00a3{total_value:.2f}")

        # Revenue summary
        revenue = self.db.get_revenue_summary()
        total_sold = revenue[1] or 0
        total_revenue = revenue[2] or 0.0

        self.sold_label.config(text=f"Sold: {total_sold}")
        self.revenue_label.config(text=f"Revenue: \u00a3{total_revenue:.2f}")

    def on_search(self):
        """Handle search/filter changes."""
        self.refresh_stock_list()

    def clear_search(self):
        """Clear search and filter."""
        self.search_var.set("")
        self.filter_category_var.set("All")
        self.filter_status_var.set("all")
        self.refresh_stock_list()

    def get_selected_item(self):
        """Get the currently selected item."""
        selection = self.tree.selection()
        if not selection:
            return None

        values = self.tree.item(selection[0])["values"]
        # Convert price back from string (remove £ symbol)
        price_str = str(values[3]).replace("\u00a3", "").replace(",", "")
        # (id, name, category, price, quantity, condition, status, sold_qty, date_added)
        return {
            "id": values[0],
            "name": values[1],
            "category": values[2],
            "price": float(price_str),
            "quantity": values[4],
            "condition": values[5],
            "status": values[6],
            "sold_qty": values[7],
            "date_added": values[8]
        }

    def add_item(self):
        """Add a new stock item."""
        dialog = ItemDialog(self.root, "Add New Item")

        if dialog.result:
            self.db.add_item(
                dialog.result["name"],
                dialog.result["category"],
                dialog.result["price"],
                dialog.result["quantity"],
                dialog.result["condition"]
            )
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item added successfully!")

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('create', 'charity_shop_item', details={
                    'name': dialog.result["name"],
                    'category': dialog.result["category"],
                    'price': dialog.result["price"],
                    'quantity': dialog.result["quantity"]
                })

    def edit_item(self):
        """Edit the selected stock item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to edit.")
            return

        # Get full item data from database
        all_items = self.db.get_all_stock()
        item_data = None
        for db_item in all_items:
            if db_item[0] == item["id"]:
                item_data = db_item
                break

        if not item_data:
            messagebox.showerror("Error", "Could not find item in database.")
            return

        dialog = ItemDialog(self.root, "Edit Item", item_data)

        if dialog.result:
            self.db.update_item(
                item["id"],
                dialog.result["name"],
                dialog.result["category"],
                dialog.result["price"],
                dialog.result["quantity"],
                dialog.result["condition"],
                dialog.result["sold"],
                dialog.result["sold_quantity"]
            )
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item updated successfully!")

    def delete_item(self):
        """Delete the selected stock item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{item['name']}'?"):
            self.db.delete_item(item["id"])
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item deleted successfully!")

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('delete', 'charity_shop_item', details={
                    'item_id': item["id"],
                    'name': item["name"],
                    'category': item["category"]
                })


def main():
    """Main entry point."""
    root = tk.Tk()

    # Set application icon (if available)
    try:
        root.iconbitmap("charity_shop.ico")
    except tk.TclError:
        pass

    # Configure style
    style = ttk.Style()

    app = CharityShopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
