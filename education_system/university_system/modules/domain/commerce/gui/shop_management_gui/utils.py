import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.university_system.modules.domain.commerce.services.shop_management import (
        auth, add_to_shopping_cart, browse_products, checkout_process,
        display_product_management_menu, display_shop_menu,
        get_customer_analytics, get_inventory_valuation, init_shop_db,
        print_product_labels, search_products, set_auth,
        toggle_discount_status, toggle_product_status, view_purchase_history
    )
except Exception:
    try:
        from shop_management import (
            auth, add_to_shopping_cart, browse_products, checkout_process,
            display_product_management_menu, display_shop_menu,
            get_customer_analytics, get_inventory_valuation, init_shop_db,
            print_product_labels, search_products, set_auth,
            toggle_discount_status, toggle_product_status, view_purchase_history
        )
    except Exception:
        # If running standalone, we'll define the essential fallback functions
        def get_customer_analytics():
            return None

        def get_inventory_valuation():
            return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}

        def print_product_labels(product_ids=None):
            print("Label printing functionality not available")

        # Note: get_low_stock_items is implemented as a class method in UniversityShopGUI

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Initialize logger
logger = logging.getLogger(__name__)


def setup_styles(self):
    """Configure GUI styles and themes"""
    style = ttk.Style()
    
    # Configure colors and fonts
    self.colors = {
        'primary': '#2E3440',
        'secondary': '#3B4252',
        'accent': '#88C0D0',
        'success': '#A3BE8C',
        'warning': '#EBCB8B',
        'error': '#BF616A',
        'background': '#ECEFF4',
        'text': '#2E3440'
    }
    
    # Configure styles
    style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground=self.colors['primary'])
    style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), foreground=self.colors['primary'])
    style.configure('Success.TLabel', foreground=self.colors['success'])
    style.configure('Warning.TLabel', foreground=self.colors['warning'])
    style.configure('Error.TLabel', foreground=self.colors['error'])
    
    # Configure button styles
    style.configure('Primary.TButton', background=self.colors['accent'])
    style.configure('Success.TButton', background=self.colors['success'])
    style.configure('Warning.TButton', background=self.colors['warning'])
    style.configure('Danger.TButton', background=self.colors['error'])
    

def _bind_sidebar_scroll_events(self):
    """Bind mouse wheel and keys to sidebar scrolling"""
    def _on_mousewheel(event):
        # Only scroll if bar is visible (i.e., content taller than viewport)
        if hasattr(self, 'sidebar_scrollbar') and self.sidebar_scrollbar.winfo_viewable():
            if event.delta:  # Windows
                self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            else:            # Linux
                if event.num == 4:
                    self.sidebar_canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.sidebar_canvas.yview_scroll(1, "units")

    def _on_keypress(event):
        if hasattr(self, 'sidebar_scrollbar') and self.sidebar_scrollbar.winfo_viewable():
            if event.keysym == 'Up':
                self.sidebar_canvas.yview_scroll(-1, "units")
            elif event.keysym == 'Down':
                self.sidebar_canvas.yview_scroll(1, "units")
            elif event.keysym == 'Page_Up':
                self.sidebar_canvas.yview_scroll(-10, "units")
            elif event.keysym == 'Page_Down':
                self.sidebar_canvas.yview_scroll(10, "units")

    # Bind to sidebar and its children
    if hasattr(self, 'sidebar_canvas'):
        self.sidebar_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
        self.sidebar_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
        self.sidebar_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
        self.sidebar_canvas.bind("<KeyPress>", _on_keypress)
        self.sidebar_canvas.focus_set()

    # Main content area with scrollbar
    content_container = ttk.Frame(self.main_frame, padding="10")
    content_container.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Create canvas and scrollbar for content area
    self.content_canvas = tk.Canvas(content_container, highlightthickness=0)
    content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
    self.content_frame = ttk.Frame(self.content_canvas)

    self.content_frame.bind(
        "<Configure>",
        lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
    )

    self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
    self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

    self.content_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    content_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    content_container.columnconfigure(0, weight=1)
    content_container.rowconfigure(0, weight=1)
    self.content_frame.columnconfigure(0, weight=1)
    self.content_frame.rowconfigure(0, weight=1)
    
    # Status bar
    self.status_frame = ttk.Frame(self.main_frame)
    self.status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    self.status_label = ttk.Label(self.status_frame, text=_t("common.ready"))
    self.status_label.grid(row=0, column=0, sticky=tk.W)
    
    # Progress bar (hidden by default)
    self.progress_var = tk.DoubleVar()
    self.progress_bar = ttk.Progressbar(self.status_frame, variable=self.progress_var)
    self.progress_bar.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
    self.progress_bar.grid_remove()
    

def show_print_labels_dialog(self):
    """Show dialog for printing product labels"""
    # Create print labels window
    labels_window = tk.Toplevel(self.root)
    labels_window.title(_t("shop_management.titles.print_labels"))
    labels_window.geometry("400x300")
    labels_window.resizable(False, False)

    # Make it modal
    labels_window.transient(self.root)
    labels_window.grab_set()

    main_frame = ttk.Frame(labels_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Title
    ttk.Label(main_frame, text=_t("shop_management.titles.print_labels"), style='Title.TLabel').grid(row=0, column=0, pady=(0, 20))

    # Options
    print_option = tk.StringVar(value="all")

    ttk.Radiobutton(main_frame, text=_t("shop_management.labels.print_all_products"),
                   variable=print_option, value="all").grid(row=1, column=0, sticky=tk.W, pady=5)
    ttk.Radiobutton(main_frame, text=_t("shop_management.labels.print_by_category"),
                   variable=print_option, value="category").grid(row=2, column=0, sticky=tk.W, pady=5)
    ttk.Radiobutton(main_frame, text=_t("shop_management.labels.print_low_stock_only"),
                   variable=print_option, value="low_stock").grid(row=3, column=0, sticky=tk.W, pady=5)

    # Category selection (initially disabled)
    category_frame = ttk.Frame(main_frame)
    category_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)

    ttk.Label(category_frame, text=_t("shop_management.labels.category") + ":").grid(row=0, column=0, sticky=tk.W)
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(category_frame, textvariable=category_var, 
                                 values=[], state="disabled", width=25)
    category_combo.grid(row=0, column=1, padx=(10, 0))
    
    # Load categories
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category")
            categories = [row[0] for row in cursor.fetchall()]
            category_combo.configure(values=categories)
            conn.close()
    except Exception as e:
        logger.error(f"Failed to load categories for label printing: {e}")
        # Set empty list as fallback
        category_combo.configure(values=[])
    
    def on_option_change():
        if print_option.get() == "category":
            category_combo.configure(state="readonly")
        else:
            category_combo.configure(state="disabled")
    
    # Bind option change
    for widget in main_frame.winfo_children():
        if isinstance(widget, ttk.Radiobutton):
            widget.configure(command=on_option_change)
    
    def print_labels():
        try:
            option = print_option.get()
            product_ids = None

            if option == "all":
                product_ids = None  # Will get all products
            elif option == "category":
                if not category_var.get():
                    messagebox.showerror(_t("common.error"), _t("shop_management.messages.select_category"))
                    return
                # Get products by category and print labels
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT product_id FROM shop_products WHERE category = ? AND is_active = 1",
                              [category_var.get()])
                product_ids = [row[0] for row in cursor.fetchall()]
                conn.close()
            elif option == "low_stock":
                # Get low stock product IDs
                low_stock_items = self.get_low_stock_items()
                product_ids = [item['product_id'] for item in low_stock_items]

            labels_window.destroy()
            # Call GUI-specific label printing method
            self.display_product_labels_gui(product_ids)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('shop_management.messages.print_labels_failed')}: {e}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=5, column=0, pady=20)

    ttk.Button(button_frame, text=_t("shop_management.buttons.print_labels"), command=print_labels,
              style='Primary.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=labels_window.destroy).grid(row=0, column=1, padx=5)


def display_product_labels_gui(self, product_ids=None):
    """Display product labels in a GUI window for printing"""
    try:
        # Get product information
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if product_ids:
            # Get specific products
            placeholders = ','.join('?' * len(product_ids))
            query = f"""
                SELECT p.product_id, p.name, p.category, p.price, p.description, i.quantity
                FROM shop_products p
                LEFT JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.product_id IN ({placeholders}) AND p.is_active = 1
                ORDER BY p.name
            """
            cursor.execute(query, product_ids)
        else:
            # Get all active products
            cursor.execute("""
                SELECT p.product_id, p.name, p.category, p.price, p.description, i.quantity
                FROM shop_products p
                LEFT JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1
                ORDER BY p.name
            """)

        products = cursor.fetchall()
        conn.close()

        if not products:
            messagebox.showinfo("No Products", "No products found to print labels.")
            return

        # Create labels window
        labels_window = tk.Toplevel(self.root)
        labels_window.title("Product Labels")
        labels_window.geometry("800x600")
        labels_window.transient(self.root)

        main_frame = ttk.Frame(labels_window, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Product Labels ({len(products)} items)",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Scrollable frame for labels
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Generate labels
        for idx, product in enumerate(products):
            label_frame = ttk.LabelFrame(scrollable_frame, text=f"Label {idx + 1}", padding=10)
            label_frame.grid(row=idx // 2, column=idx % 2, padx=10, pady=10, sticky='nsew')

            # Product info
            desc = product['description'] if product['description'] else 'N/A'
            if len(desc) > 40:
                desc = desc[:37] + '...'
            info_text = f"""
Product: {product['name']}
Category: {product['category']}
Price: £{product['price']:.2f}
Stock: {product['quantity'] if product['quantity'] else 0}
Description: {desc}
ID: {product['product_id']}
"""
            ttk.Label(label_frame, text=info_text, justify='left',
                     font=('Courier', 9)).pack()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        button_frame = ttk.Frame(labels_window, padding="10")
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Print Labels",
                  command=lambda: self._print_labels_to_printer(products)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Export to PDF",
                  command=lambda: self._export_labels_to_pdf(products)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Export to Text File",
                  command=lambda: self._export_labels_to_file(products)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close",
                  command=labels_window.destroy).pack(side='left', padx=5)

    except Exception as e:
        logger.error(f"Error displaying product labels: {e}")
        messagebox.showerror("Error", f"Failed to display product labels: {e}")


def _print_labels_to_printer(self, products):
    """Send labels to printer (placeholder)"""
    messagebox.showinfo("Print Labels",
                      f"Sending {len(products)} labels to printer...\n\n"
                      "Note: This feature requires printer configuration.")


def _export_labels_to_pdf(self, products):
    """Export labels to PDF file"""
    try:
        # Try to import reportlab
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            pdf_available = True
        except ImportError:
            pdf_available = False
            messagebox.showerror("PDF Export Not Available",
                               "The reportlab library is not installed.\n\n"
                               "To enable PDF export, install it with:\n"
                               "pip install reportlab\n\n"
                               "Use 'Export to Text File' instead.")
            return

        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"product_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        if not filename:
            return

        # Create PDF
        pdf = canvas.Canvas(filename, pagesize=letter)
        width, height = letter

        # Title
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(1*inch, height - 1*inch, "Product Labels")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(1*inch, height - 1.3*inch,
                      f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        pdf.drawString(1*inch, height - 1.5*inch, f"Total Products: {len(products)}")

        # Draw labels in a grid (2 columns)
        y_position = height - 2.2*inch
        x_positions = [1*inch, 4.5*inch]
        label_height = 2.2*inch
        label_width = 3*inch
        col = 0

        for idx, product in enumerate(products):
            x = x_positions[col]

            # Draw border
            pdf.setStrokeColor(colors.grey)
            pdf.setLineWidth(1)
            pdf.rect(x, y_position - label_height, label_width, label_height)

            # Product info
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(x + 0.1*inch, y_position - 0.3*inch,
                          f"{product['name'][:35]}")

            pdf.setFont("Helvetica", 9)
            text_y = y_position - 0.6*inch

            pdf.drawString(x + 0.1*inch, text_y,
                          f"Category: {product['category']}")
            text_y -= 0.25*inch

            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(x + 0.1*inch, text_y,
                          f"Price: £{product['price']:.2f}")
            text_y -= 0.3*inch

            pdf.setFont("Helvetica", 9)
            stock_qty = product['quantity'] if product['quantity'] else 0
            pdf.drawString(x + 0.1*inch, text_y,
                          f"Stock: {stock_qty}")
            text_y -= 0.25*inch

            # Description (truncated)
            desc = product['description'] if product['description'] else 'N/A'
            if len(desc) > 35:
                desc = desc[:32] + '...'
            pdf.drawString(x + 0.1*inch, text_y,
                          f"Desc: {desc}")
            text_y -= 0.25*inch

            pdf.setFont("Helvetica", 8)
            pdf.drawString(x + 0.1*inch, text_y,
                          f"ID: {product['product_id']}")

            # Move to next position
            col += 1
            if col >= 2:
                col = 0
                y_position -= label_height + 0.3*inch

                # New page if needed
                if y_position < 1.5*inch:
                    pdf.showPage()
                    y_position = height - 1*inch
                    pdf.setFont("Helvetica-Bold", 16)
                    pdf.drawString(1*inch, y_position, "Product Labels (continued)")
                    y_position -= 0.7*inch

        # Save PDF
        pdf.save()

        messagebox.showinfo("Export Successful",
                          f"PDF exported successfully to:\n{filename}\n\n"
                          f"Total labels: {len(products)}")

    except Exception as e:
        logger.error(f"Error exporting labels to PDF: {e}")
        messagebox.showerror("Export Error", f"Failed to export PDF: {e}")


def _export_labels_to_file(self, products):
    """Export labels to text file"""
    try:
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"product_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("PRODUCT LABELS\n")
            f.write("=" * 80 + "\n\n")

            for idx, product in enumerate(products, 1):
                f.write(f"Label {idx}\n")
                f.write("-" * 40 + "\n")
                f.write(f"Product: {product['name']}\n")
                f.write(f"Category: {product['category']}\n")
                f.write(f"Price: £{product['price']:.2f}\n")
                f.write(f"Stock: {product['quantity'] if product['quantity'] else 0}\n")
                f.write(f"Description: {product['description'] if product['description'] else 'N/A'}\n")
                f.write(f"ID: {product['product_id']}\n")
                f.write("\n")

        messagebox.showinfo("Export Successful", f"Labels exported to:\n{filename}")

    except Exception as e:
        logger.error(f"Error exporting labels: {e}")
        messagebox.showerror("Export Error", f"Failed to export labels: {e}")


def clear_content(self):
    """Clear the main content area"""
    for widget in self.content_frame.winfo_children():
        widget.destroy()
        

def show_product_context_menu(self, event):
    """Show context menu for products"""
    item = self.products_tree.identify_row(event.y)
    if item:
        self.products_tree.selection_set(item)
        self.product_context_menu.post(event.x_root, event.y_root)
        

def load_products(self):
    """Load products into the treeview"""
    try:
        # Clear existing items
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)
        
        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.product_id, p.name, p.category, p.price, p.description, i.quantity
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1
                ORDER BY p.category, p.name
            """)
            
            products = cursor.fetchall()
            categories = set()
            
            for product in products:
                # Format price
                price_str = f"£{product['price']:.2f}"
                
                # Insert into tree
                self.products_tree.insert('', 'end', values=(
                    product['product_id'],
                    product['name'],
                    product['category'],
                    price_str,
                    product['quantity'],
                    product['description'][:50] + "..." if len(product['description']) > 50 else product['description']
                ))
                
                categories.add(product['category'])
            
            # Update category filter
            category_list = ["All"] + sorted(list(categories))
            self.category_combo.configure(values=category_list)
            
            conn.close()
            
        else:
            # Fallback sample data
            sample_products = [
                ("P001", "University Hoodie", "Clothing", "£29.99", "50", "Comfortable hoodie with logo"),
                ("P002", "University T-Shirt", "Clothing", "£19.99", "75", "Cotton t-shirt with logo"),
                ("P003", "Notebook Pack", "Stationery", "£12.99", "30", "Set of 3 branded notebooks"),
            ]
            
            for product in sample_products:
                self.products_tree.insert('', 'end', values=product)
                
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load products: {e}")
        

def view_product_sales(self):
    """View sales data for selected product"""
    if not hasattr(self, 'mgmt_products_tree'):
        return
        
    selection = self.mgmt_products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product")
        return
    
    item = self.mgmt_products_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    product_name = values[1]
    
    # Create sales window
    sales_window = tk.Toplevel(self.root)
    sales_window.title(f"Sales Data - {product_name}")
    sales_window.geometry("700x500")
    sales_window.resizable(True, True)
    
    # Make it modal
    sales_window.transient(self.root)
    sales_window.grab_set()
    
    main_frame = ttk.Frame(sales_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)
    
    # Title
    ttk.Label(main_frame, text=f"Sales Data: {product_name} ({product_id})", 
             style='Title.TLabel').grid(row=0, column=0, pady=(0, 10))
    
    try:
        # Get sales data
        sales_data = self.get_product_sales_data(product_id)
        
        if not sales_data:
            ttk.Label(main_frame, text="No sales data found for this product").grid(row=1, column=0)
        else:
            # Sales table
            sales_frame = ttk.Frame(main_frame)
            sales_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            sales_frame.columnconfigure(0, weight=1)
            sales_frame.rowconfigure(0, weight=1)
            
            columns = ('Date', 'Transaction ID', 'Quantity', 'Price', 'Subtotal')
            sales_tree = ttk.Treeview(sales_frame, columns=columns, show='headings')
            
            for col in columns:
                sales_tree.heading(col, text=col)
            
            sales_scrollbar = ttk.Scrollbar(sales_frame, orient='vertical', command=sales_tree.yview)
            sales_tree.configure(yscrollcommand=sales_scrollbar.set)
            
            sales_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            sales_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            # Populate sales data
            total_quantity = 0
            total_revenue = 0
            
            for sale in sales_data:
                sales_tree.insert('', 'end', values=(
                    sale['transaction_date'],
                    sale['transaction_id'],
                    sale['quantity'],
                    f"£{sale['price_per_item']:.2f}",
                    f"£{sale['subtotal']:.2f}"
                ))
                total_quantity += sale['quantity']
                total_revenue += sale['subtotal']
            
            # Summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
            
            ttk.Label(summary_frame, text=f"Total Sales: {len(sales_data)} transactions, "
                                         f"{total_quantity} units, £{total_revenue:.2f} revenue",
                     font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W)
    
    except Exception as e:
        ttk.Label(main_frame, text=f"Error loading sales data: {e}").grid(row=1, column=0)
    
    # Close button
    ttk.Button(main_frame, text="Close", command=sales_window.destroy).grid(row=3, column=0, pady=10)


def get_product_sales_data(self, product_id):
    """Get sales data for a specific product"""
    try:
        if 'get_connection' not in globals():
            return []
        
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.transaction_date, t.transaction_id,
                   ti.quantity, ti.price_per_item, ti.subtotal
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            WHERE ti.product_id = ?
            ORDER BY t.transaction_date DESC
        """, [product_id])
        
        sales = cursor.fetchall()
        conn.close()
        
        return [dict(sale) for sale in sales]
        
    except Exception as e:
        return []


def edit_selected_product(self):
    """Edit the selected product"""
    if not hasattr(self, 'mgmt_products_tree'):
        return
        
    selection = self.mgmt_products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product to edit")
        return
    
    item = self.mgmt_products_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    
    # Get current product data
    try:
        product_data = self.get_product_details(product_id)
        if not product_data:
            messagebox.showerror("Error", "Product not found")
            return
        
        # Create edit window
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit Product - {product_id}")
        edit_window.geometry("500x600")
        edit_window.resizable(False, False)
        
        # Make it modal
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        main_frame = ttk.Frame(edit_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Form fields with current values
        ttk.Label(main_frame, text="Product ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(main_frame, text=product_id, font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(main_frame, text="Product Name*:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=product_data.get('name', ''))
        ttk.Entry(main_frame, textvariable=name_var, width=40).grid(row=1, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
        desc_text = tk.Text(main_frame, height=4, width=40)
        desc_text.grid(row=2, column=1, pady=5, padx=(10, 0))
        desc_text.insert('1.0', product_data.get('description', ''))
        
        ttk.Label(main_frame, text="Price (£)*:").grid(row=3, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar(value=str(product_data.get('price', '')))
        ttk.Entry(main_frame, textvariable=price_var, width=40).grid(row=3, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Category*:").grid(row=4, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar(value=product_data.get('category', ''))
        ttk.Entry(main_frame, textvariable=category_var, width=40).grid(row=4, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(main_frame, text="Tax Rate (%):").grid(row=5, column=0, sticky=tk.W, pady=5)
        tax_rate = product_data.get('tax_rate', 0.2) * 100
        tax_var = tk.StringVar(value=str(tax_rate))
        ttk.Entry(main_frame, textvariable=tax_var, width=40).grid(row=5, column=1, pady=5, padx=(10, 0))
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=6, column=0, sticky=tk.W, pady=5)
        status_var = tk.BooleanVar(value=product_data.get('is_active', True))
        ttk.Checkbutton(main_frame, text="Active", variable=status_var).grid(row=6, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        def save_changes():
            try:
                # Validate inputs
                if not all([name_var.get().strip(), price_var.get().strip(), category_var.get().strip()]):
                    messagebox.showerror("Error", "Please fill in all required fields (*)")
                    return
                
                # Update product
                updated_data = {
                    'name': name_var.get().strip(),
                    'description': desc_text.get('1.0', 'end-1c').strip(),
                    'price': float(price_var.get()),
                    'category': category_var.get().strip(),
                    'tax_rate': float(tax_var.get()) / 100,
                    'is_active': status_var.get()
                }
                
                self.update_product(product_id, updated_data)
                edit_window.destroy()
                self.load_products_for_management()
                messagebox.showinfo("Success", "Product updated successfully!")
                
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numeric values")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update product: {e}")
        
        ttk.Button(button_frame, text="Save Changes", command=save_changes, 
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_window.destroy).grid(row=0, column=1, padx=5)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load product for editing: {e}")
        

def delete_selected_product(self):
    """Delete selected product (with confirmation)"""
    if not hasattr(self, 'mgmt_products_tree'):
        return
        
    selection = self.mgmt_products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product to delete")
        return
    
    item = self.mgmt_products_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    product_name = values[1]
    
    if messagebox.askyesno("Confirm Delete", 
                          f"Are you sure you want to delete product '{product_name}' ({product_id})?\n\n"
                          "This action cannot be undone!"):
        try:
            self.delete_product(product_id)
            self.load_products_for_management()
            messagebox.showinfo("Success", f"Product {product_id} deleted successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete product: {e}")
            

