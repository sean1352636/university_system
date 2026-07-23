from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth

# Authentication is imported unconditionally above (required, no fallback)
AUTH_AVAILABLE = True
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.post_18.university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def manage_purchase_orders_dialog(self):
    """Launch the comprehensive Purchase Orders management GUI"""
    try:
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.purchase_orders_gui import (
            PurchaseOrdersGUI,
            init_purchase_orders_tables
        )

        # Initialize tables if needed
        init_purchase_orders_tables()

        # Create and show the Purchase Orders GUI
        po_window = tk.Toplevel(self.root)
        po_window.title("Purchase Orders Management")
        po_window.geometry("1200x700")
        po_window.transient(self.root)

        # Launch the comprehensive GUI
        PurchaseOrdersGUI(po_window)

    except ImportError as e:
        messagebox.showerror("Error", f"Failed to load Purchase Orders module:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Purchase Orders:\n{str(e)}")

def view_purchase_orders(self, parent_dialog):
    """View all purchase orders with filtering options"""
    view_dialog = tk.Toplevel(parent_dialog)
    view_dialog.title("View Purchase Orders")
    view_dialog.geometry("1200x700")
    view_dialog.transient(parent_dialog)
    view_dialog.grab_set()
    main_frame = ttk.Frame(view_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Purchase Orders List",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Filter frame
    filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
    filter_frame.pack(fill='x', pady=10)
    filter_row1 = ttk.Frame(filter_frame)
    filter_row1.pack(fill='x', pady=5)
    ttk.Label(filter_row1, text="Status:").pack(side='left', padx=5)
    status_var = tk.StringVar(value='All')
    status_combo = ttk.Combobox(filter_row1, textvariable=status_var,
                               values=['All', 'Pending', 'Approved', 'Received', 'Cancelled'],
                               width=15, state='readonly')
    status_combo.pack(side='left', padx=5)
    ttk.Label(filter_row1, text="Supplier:").pack(side='left', padx=5)
    supplier_var = tk.StringVar(value='All')
    supplier_combo = ttk.Combobox(filter_row1, textvariable=supplier_var,
                                 values=['All'], width=20, state='readonly')
    supplier_combo.pack(side='left', padx=5)
    # Treeview frame
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    # Scrollbars
    v_scroll = ttk.Scrollbar(tree_frame, orient='vertical')
    h_scroll = ttk.Scrollbar(tree_frame, orient='horizontal')
    columns = ('PO#', 'Supplier', 'Order Date', 'Expected', 'Status', 'Total', 'Items', 'Notes')
    po_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                          yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set, height=20)
    v_scroll.config(command=po_tree.yview)
    h_scroll.config(command=po_tree.xview)
    # Configure columns
    column_widths = {'PO#': 100, 'Supplier': 150, 'Order Date': 100, 'Expected': 100,
                    'Status': 100, 'Total': 100, 'Items': 80, 'Notes': 200}
    for col in columns:
        po_tree.heading(col, text=col)
        po_tree.column(col, width=column_widths.get(col, 100))
    po_tree.pack(side='left', fill='both', expand=True)
    v_scroll.pack(side='right', fill='y')
    h_scroll.pack(side='bottom', fill='x')
    def load_purchase_orders():
        # Clear existing items
        for item in po_tree.get_children():
            po_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Build query with filters
                query = '''
                    SELECT po.po_number, COALESCE(s.name, 'N/A') as supplier_name,
                           po.order_date, po.expected_delivery, po.status,
                           po.total_amount, COUNT(poi.po_item_id) as item_count,
                           po.notes
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
                    WHERE 1=1
                '''
                params = []
                if status_var.get() != 'All':
                    query += ' AND po.status = ?'
                    params.append(status_var.get())
                if supplier_var.get() != 'All':
                    query += ' AND s.name = ?'
                    params.append(supplier_var.get())
                query += ' GROUP BY po.po_id ORDER BY po.order_date DESC'
                cursor.execute(query, params)
                orders = cursor.fetchall()
                for order in orders:
                    po_tree.insert('', 'end', values=(
                        order[0],  # PO Number
                        order[1],  # Supplier
                        order[2],  # Order Date
                        order[3] or 'N/A',  # Expected Delivery
                        order[4],  # Status
                        f"£{order[5]:,.2f}",  # Total
                        order[6],  # Item Count
                        order[7] or ''  # Notes
                    ))
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load purchase orders: {e}")
    def load_suppliers():
        """Load supplier list for filter"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT name FROM restaurant_suppliers ORDER BY name")
                suppliers = [row[0] for row in cursor.fetchall()]
                supplier_combo['values'] = ['All'] + suppliers
                conn.close()
        except sqlite3.Error:
            pass
    def view_po_details():
        """View detailed information about selected PO"""
        selection = po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order to view details")
            return
        item = po_tree.item(selection[0])
        po_number = item['values'][0]
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Get PO header details
                cursor.execute('''
                    SELECT po.*, s.name as supplier_name
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    WHERE po.po_number = ?
                ''', (po_number,))
                po_data = cursor.fetchone()
                # Get PO line items
                cursor.execute('''
                    SELECT item_name, description, quantity, unit, unit_price,
                           total_price, received_quantity
                    FROM purchase_order_items
                    WHERE po_id = ?
                ''', (po_data[0],))
                items = cursor.fetchall()
                conn.close()
                # Create details dialog
                details_dialog = tk.Toplevel(view_dialog)
                details_dialog.title(f"PO Details - {po_number}")
                details_dialog.geometry("800x600")
                details_dialog.transient(view_dialog)
                details_frame = ttk.Frame(details_dialog, padding=20)
                details_frame.pack(fill='both', expand=True)
                # Header info
                header_text = f"""
hase Order: {po_data[1]}
lier: {po_data[14]}
r Date: {po_data[3]}
cted Delivery: {po_data[4] or 'Not specified'}
al Delivery: {po_data[5] or 'Not delivered'}
us: {po_data[6]}
l Amount: £{po_data[7]:,.2f}
Amount: £{po_data[8]:,.2f}
ping Cost: £{po_data[9]:,.2f}
red By: {po_data[11] or 'N/A'}
oved By: {po_data[12] or 'Not approved'}
ived By: {po_data[13] or 'Not received'}
s: {po_data[10] or 'None'}
                """.strip()
                ttk.Label(details_frame, text=header_text, justify='left',
                         font=('Courier', 9)).pack(pady=10)
                # Items list
                ttk.Label(details_frame, text="Line Items:", font=('Arial', 10, 'bold')).pack(pady=5)
                items_tree = ttk.Treeview(details_frame,
                                        columns=('Item', 'Qty', 'Unit', 'Price', 'Total', 'Received'),
                                        show='headings', height=15)
                for col in ('Item', 'Qty', 'Unit', 'Price', 'Total', 'Received'):
                    items_tree.heading(col, text=col)
                    items_tree.column(col, width=120)
                for item in items:
                    items_tree.insert('', 'end', values=(
                        f"{item[0]} - {item[1] or ''}",
                        item[2],
                        item[3],
                        f"£{item[4]:.2f}",
                        f"£{item[5]:.2f}",
                        item[6]
                    ))
                items_tree.pack(fill='both', expand=True)
                ttk.Button(details_frame, text="Close",
                          command=details_dialog.destroy).pack(pady=10)
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to load PO details: {e}")
    # Load data
    load_suppliers()
    load_purchase_orders()
    # Button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Apply Filters", command=load_purchase_orders).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="View Details", command=view_po_details).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=load_purchase_orders).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Close", command=view_dialog.destroy).pack(side='right', padx=5)

def create_purchase_order(self, parent_dialog):
    """Create a new purchase order with items"""
    create_dialog = tk.Toplevel(parent_dialog)
    create_dialog.title("Create Purchase Order")
    create_dialog.geometry("900x700")
    create_dialog.transient(parent_dialog)
    create_dialog.grab_set()
    main_frame = ttk.Frame(create_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Create New Purchase Order",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # PO Header Form
    header_frame = ttk.LabelFrame(main_frame, text="Purchase Order Details", padding=15)
    header_frame.pack(fill='x', pady=10)
    fields = {}
    # Row 1: PO Number and Supplier
    row1 = ttk.Frame(header_frame)
    row1.pack(fill='x', pady=5)
    ttk.Label(row1, text="PO Number:*").pack(side='left', padx=5)
    fields['po_number'] = ttk.Entry(row1, width=20)
    fields['po_number'].pack(side='left', padx=5)
    # Auto-generate PO number
    fields['po_number'].insert(0, f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    ttk.Label(row1, text="Supplier:*").pack(side='left', padx=20)
    fields['supplier'] = ttk.Combobox(row1, width=30, state='readonly')
    fields['supplier'].pack(side='left', padx=5)
    # Load suppliers
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT supplier_id, name FROM restaurant_suppliers WHERE status = 'Active'")
            suppliers = cursor.fetchall()
            supplier_dict = {f"{s[1]} (ID: {s[0]})": s[0] for s in suppliers}
            fields['supplier']['values'] = list(supplier_dict.keys())
            fields['supplier_dict'] = supplier_dict
            conn.close()
    except sqlite3.Error:
        pass
    # Row 2: Dates
    row2 = ttk.Frame(header_frame)
    row2.pack(fill='x', pady=5)
    ttk.Label(row2, text="Order Date:*").pack(side='left', padx=5)
    fields['order_date'] = ttk.Entry(row2, width=15)
    fields['order_date'].pack(side='left', padx=5)
    fields['order_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
    ttk.Label(row2, text="Expected Delivery:").pack(side='left', padx=20)
    fields['expected_date'] = ttk.Entry(row2, width=15)
    fields['expected_date'].pack(side='left', padx=5)
    # Default to 7 days from now
    fields['expected_date'].insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
    # Row 3: Additional costs
    row3 = ttk.Frame(header_frame)
    row3.pack(fill='x', pady=5)
    ttk.Label(row3, text="Shipping Cost (£):").pack(side='left', padx=5)
    fields['shipping'] = ttk.Entry(row3, width=15)
    fields['shipping'].pack(side='left', padx=5)
    fields['shipping'].insert(0, "0.00")
    ttk.Label(row3, text="Tax Rate (%):").pack(side='left', padx=20)
    fields['tax_rate'] = ttk.Entry(row3, width=15)
    fields['tax_rate'].pack(side='left', padx=5)
    fields['tax_rate'].insert(0, "20.0")
    # Row 4: Notes
    row4 = ttk.Frame(header_frame)
    row4.pack(fill='x', pady=5)
    ttk.Label(row4, text="Notes:").pack(side='left', padx=5)
    fields['notes'] = ttk.Entry(row4, width=60)
    fields['notes'].pack(side='left', padx=5)
    # Items Section
    items_frame = ttk.LabelFrame(main_frame, text="Order Items", padding=15)
    items_frame.pack(fill='both', expand=True, pady=10)
    # Items list storage
    po_items = []
    # Items treeview
    items_tree = ttk.Treeview(items_frame,
                             columns=('Item', 'Description', 'Qty', 'Unit', 'Price', 'Total'),
                             show='headings', height=10)
    for col in ('Item', 'Description', 'Qty', 'Unit', 'Price', 'Total'):
        items_tree.heading(col, text=col)
        items_tree.column(col, width=120)
    items_tree.pack(fill='both', expand=True, pady=5)
    def add_item():
        """Add item to PO"""
        item_dialog = tk.Toplevel(create_dialog)
        item_dialog.title("Add Item")
        item_dialog.geometry("500x400")
        item_dialog.transient(create_dialog)
        item_dialog.grab_set()
        item_frame = ttk.Frame(item_dialog, padding=20)
        item_frame.pack(fill='both', expand=True)
        item_fields = {}
        ttk.Label(item_frame, text="Item Name:*").grid(row=0, column=0, sticky='w', pady=5)
        item_fields['name'] = ttk.Entry(item_frame, width=40)
        item_fields['name'].grid(row=0, column=1, pady=5, padx=10)
        ttk.Label(item_frame, text="Description:").grid(row=1, column=0, sticky='w', pady=5)
        item_fields['desc'] = ttk.Entry(item_frame, width=40)
        item_fields['desc'].grid(row=1, column=1, pady=5, padx=10)
        ttk.Label(item_frame, text="Quantity:*").grid(row=2, column=0, sticky='w', pady=5)
        item_fields['qty'] = ttk.Entry(item_frame, width=40)
        item_fields['qty'].grid(row=2, column=1, pady=5, padx=10)
        ttk.Label(item_frame, text="Unit:").grid(row=3, column=0, sticky='w', pady=5)
        item_fields['unit'] = ttk.Combobox(item_frame,
                                          values=['kg', 'L', 'pieces', 'boxes', 'cases', 'units'],
                                          width=38)
        item_fields['unit'].grid(row=3, column=1, pady=5, padx=10)
        item_fields['unit'].current(0)
        ttk.Label(item_frame, text="Unit Price (£):*").grid(row=4, column=0, sticky='w', pady=5)
        item_fields['price'] = ttk.Entry(item_frame, width=40)
        item_fields['price'].grid(row=4, column=1, pady=5, padx=10)
        ttk.Label(item_frame, text="Total:").grid(row=5, column=0, sticky='w', pady=5)
        total_label = ttk.Label(item_frame, text="£0.00", font=('Arial', 10, 'bold'))
        total_label.grid(row=5, column=1, sticky='w', pady=5, padx=10)
        def update_total(*args):
            try:
                qty = float(item_fields['qty'].get() or 0)
                price = float(item_fields['price'].get() or 0)
                total = qty * price
                total_label.config(text=f"£{total:.2f}")
            except (sqlite3.Error, tk.TclError):
                total_label.config(text="£0.00")
        item_fields['qty'].bind('<KeyRelease>', update_total)
        item_fields['price'].bind('<KeyRelease>', update_total)
        def save_item():
            try:
                if not item_fields['name'].get().strip():
                    messagebox.showwarning("Missing Info", "Item name is required")
                    return
                qty = float(item_fields['qty'].get())
                price = float(item_fields['price'].get())
                total = qty * price
                item = {
                    'name': item_fields['name'].get().strip(),
                    'desc': item_fields['desc'].get().strip(),
                    'qty': qty,
                    'unit': item_fields['unit'].get(),
                    'price': price,
                    'total': total
                }
                po_items.append(item)
                items_tree.insert('', 'end', values=(
                    item['name'],
                    item['desc'],
                    item['qty'],
                    item['unit'],
                    f"£{item['price']:.2f}",
                    f"£{item['total']:.2f}"
                ))
                update_order_total()
                item_dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for quantity and price")
        btn_frame = ttk.Frame(item_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add Item", command=save_item).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=item_dialog.destroy).pack(side='left', padx=5)
    def remove_item():
        """Remove selected item"""
        selection = items_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to remove")
            return
        index = items_tree.index(selection[0])
        po_items.pop(index)
        items_tree.delete(selection[0])
        update_order_total()
    # Total display
    total_frame = ttk.Frame(items_frame)
    total_frame.pack(fill='x', pady=5)
    total_label = ttk.Label(total_frame, text="Subtotal: £0.00 | Tax: £0.00 | Shipping: £0.00 | Total: £0.00",
                           font=('Arial', 10, 'bold'))
    total_label.pack()
    def update_order_total():
        try:
            subtotal = sum(item['total'] for item in po_items)
            shipping = float(fields['shipping'].get() or 0)
            tax_rate = float(fields['tax_rate'].get() or 0) / 100
            tax = subtotal * tax_rate
            total = subtotal + tax + shipping
            total_label.config(text=f"Subtotal: £{subtotal:.2f} | Tax: £{tax:.2f} | "
                                  f"Shipping: £{shipping:.2f} | Total: £{total:.2f}")
        except (sqlite3.Error, tk.TclError):
            pass
    fields['shipping'].bind('<KeyRelease>', lambda e: update_order_total())
    fields['tax_rate'].bind('<KeyRelease>', lambda e: update_order_total())
    # Item buttons
    item_btn_frame = ttk.Frame(items_frame)
    item_btn_frame.pack(fill='x', pady=5)
    ttk.Button(item_btn_frame, text="Add Item", command=add_item).pack(side='left', padx=5)
    ttk.Button(item_btn_frame, text="Remove Item", command=remove_item).pack(side='left', padx=5)
    # Save PO
    def save_purchase_order():
        try:
            # Validation
            if not fields['po_number'].get().strip():
                messagebox.showwarning("Missing Info", "PO Number is required")
                return
            if not fields['supplier'].get():
                messagebox.showwarning("Missing Info", "Please select a supplier")
                return
            if not po_items:
                messagebox.showwarning("Missing Items", "Please add at least one item to the purchase order")
                return
            # Get supplier ID
            supplier_id = fields['supplier_dict'][fields['supplier'].get()]
            # Calculate totals
            subtotal = sum(item['total'] for item in po_items)
            shipping = float(fields['shipping'].get() or 0)
            tax_rate = float(fields['tax_rate'].get() or 0) / 100
            tax = subtotal * tax_rate
            total = subtotal + tax + shipping
            # Get current user
            current_user = "System"
            if AUTH_AVAILABLE:
                try:
                    from education_system.post_18.university_system.infrastructure.shared_context import get_auth
                    auth = get_auth()
                    if auth.current_user:
                        current_user = auth.current_user.get('username', 'Unknown')
                except (sqlite3.Error, tk.TclError, ValueError, TypeError):
                    pass
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Insert PO header
                cursor.execute('''
                    INSERT INTO purchase_orders
                    (po_number, supplier_id, order_date, expected_delivery,
                     total_amount, tax_amount, shipping_cost, notes, ordered_by, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
                ''', (fields['po_number'].get().strip(),
                      supplier_id,
                      fields['order_date'].get(),
                      fields['expected_date'].get() or None,
                      total,
                      tax,
                      shipping,
                      fields['notes'].get().strip() or None,
                      current_user))
                po_id = cursor.lastrowid
                # Insert line items
                for item in po_items:
                    cursor.execute('''
                        INSERT INTO purchase_order_items
                        (po_id, item_name, description, quantity, unit, unit_price, total_price)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (po_id, item['name'], item['desc'], item['qty'],
                          item['unit'], item['price'], item['total']))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success",
                                  f"Purchase Order {fields['po_number'].get()} created successfully!\n\n"
                                  f"Total: £{total:,.2f}\n"
                                  f"Items: {len(po_items)}")
                create_dialog.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "PO Number already exists. Please use a unique PO number.")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create purchase order: {e}")
    # Bottom buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Save Purchase Order",
              command=save_purchase_order).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel",
              command=create_dialog.destroy).pack(side='right', padx=5)

def update_purchase_order(self, parent_dialog):
    """Update an existing purchase order"""
    # First, select which PO to update
    select_dialog = tk.Toplevel(parent_dialog)
    select_dialog.title("Select Purchase Order to Update")
    select_dialog.geometry("800x500")
    select_dialog.transient(parent_dialog)
    select_dialog.grab_set()
    main_frame = ttk.Frame(select_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Select Purchase Order to Update",
             font=('Arial', 12, 'bold')).pack(pady=10)
    # Only show Pending or Approved POs
    ttk.Label(main_frame, text="Only Pending and Approved purchase orders can be updated",
             foreground='blue').pack(pady=5)
    # PO list
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    columns = ('PO#', 'Supplier', 'Date', 'Status', 'Total', 'Items')
    po_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
    for col in columns:
        po_tree.heading(col, text=col)
        po_tree.column(col, width=120)
    po_tree.pack(fill='both', expand=True)
    def load_pos():
        for item in po_tree.get_children():
            po_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT po.po_id, po.po_number, COALESCE(s.name, 'N/A'),
                           po.order_date, po.status, po.total_amount,
                           COUNT(poi.po_item_id)
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
                    WHERE po.status IN ('Pending', 'Approved')
                    GROUP BY po.po_id
                    ORDER BY po.order_date DESC
                ''')
                pos = cursor.fetchall()
                for po in pos:
                    po_tree.insert('', 'end', values=(
                        po[1],  # PO Number
                        po[2],  # Supplier
                        po[3],  # Date
                        po[4],  # Status
                        f"£{po[5]:,.2f}",  # Total
                        po[6]  # Items
                    ), tags=(po[0],))  # Store PO ID in tags
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load purchase orders: {e}")
    load_pos()
    def proceed_to_update():
        selection = po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order to update")
            return
        po_id = po_tree.item(selection[0])['tags'][0]
        select_dialog.destroy()
        show_update_dialog(po_id)
    def show_update_dialog(po_id):
        """Show update dialog for selected PO"""
        update_dialog = tk.Toplevel(parent_dialog)
        update_dialog.title("Update Purchase Order")
        update_dialog.geometry("700x600")
        update_dialog.transient(parent_dialog)
        update_dialog.grab_set()
        main_frame = ttk.Frame(update_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Update Purchase Order",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Load current PO data
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute('''
                SELECT po.*, s.name
                FROM purchase_orders po
                LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.po_id = ?
            ''', (po_id,))
            po_data = cursor.fetchone()
            conn.close()
            if not po_data:
                messagebox.showerror("Error", "Purchase order not found")
                update_dialog.destroy()
                return
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load PO data: {e}")
            update_dialog.destroy()
            return
        # Update form
        form_frame = ttk.LabelFrame(main_frame, text="Update Fields", padding=15)
        form_frame.pack(fill='both', expand=True, pady=10)
        fields = {}
        # PO Number (read-only)
        row = 0
        ttk.Label(form_frame, text="PO Number:").grid(row=row, column=0, sticky='w', pady=5)
        ttk.Label(form_frame, text=po_data[1], font=('Arial', 10, 'bold')).grid(
            row=row, column=1, sticky='w', pady=5, padx=10)
        # Status
        row += 1
        ttk.Label(form_frame, text="Status:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['status'] = ttk.Combobox(form_frame,
                                      values=['Pending', 'Approved', 'Cancelled'],
                                      width=30, state='readonly')
        fields['status'].grid(row=row, column=1, sticky='w', pady=5, padx=10)
        fields['status'].set(po_data[6])
        # Expected Delivery
        row += 1
        ttk.Label(form_frame, text="Expected Delivery:").grid(row=row, column=0, sticky='w', pady=5)
        fields['expected'] = ttk.Entry(form_frame, width=32)
        fields['expected'].grid(row=row, column=1, sticky='w', pady=5, padx=10)
        fields['expected'].insert(0, po_data[4] or '')
        # Shipping Cost
        row += 1
        ttk.Label(form_frame, text="Shipping Cost (£):").grid(row=row, column=0, sticky='w', pady=5)
        fields['shipping'] = ttk.Entry(form_frame, width=32)
        fields['shipping'].grid(row=row, column=1, sticky='w', pady=5, padx=10)
        fields['shipping'].insert(0, f"{po_data[9]:.2f}")
        # Notes
        row += 1
        ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
        fields['notes'] = tk.Text(form_frame, height=4, width=32)
        fields['notes'].grid(row=row, column=1, pady=5, padx=10)
        if po_data[10]:
            fields['notes'].insert('1.0', po_data[10])
        # Current info display
        row += 1
        info_text = f"""
ent Information:
lier: {po_data[15]}
r Date: {po_data[3]}
l Amount: £{po_data[7]:,.2f}
Amount: £{po_data[8]:,.2f}
red By: {po_data[11] or 'N/A'}
        """.strip()
        ttk.Label(form_frame, text=info_text, justify='left', foreground='blue').grid(
            row=row, column=0, columnspan=2, sticky='w', pady=10)
        def save_updates():
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE purchase_orders
                        SET status = ?,
                            expected_delivery = ?,
                            shipping_cost = ?,
                            notes = ?
                        WHERE po_id = ?
                    ''', (fields['status'].get(),
                          fields['expected'].get() or None,
                          float(fields['shipping'].get() or 0),
                          fields['notes'].get('1.0', tk.END).strip() or None,
                          po_id))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", "Purchase order updated successfully!")
                    update_dialog.destroy()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to update purchase order: {e}")
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=row+1, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save Updates", command=save_updates).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=update_dialog.destroy).pack(side='left', padx=5)
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Update Selected", command=proceed_to_update).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=load_pos).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel", command=select_dialog.destroy).pack(side='right', padx=5)

def receive_purchase_order(self, parent_dialog):
    """Mark purchase order as received and optionally update inventory"""
    # Select PO to receive
    select_dialog = tk.Toplevel(parent_dialog)
    select_dialog.title("Receive Purchase Order")
    select_dialog.geometry("900x600")
    select_dialog.transient(parent_dialog)
    select_dialog.grab_set()
    main_frame = ttk.Frame(select_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Receive Purchase Order",
             font=('Arial', 14, 'bold')).pack(pady=10)
    ttk.Label(main_frame, text="Select an Approved purchase order to receive",
             foreground='blue').pack(pady=5)
    # PO list
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    columns = ('PO#', 'Supplier', 'Order Date', 'Expected', 'Total', 'Items')
    po_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
    for col in columns:
        po_tree.heading(col, text=col)
        po_tree.column(col, width=130)
    po_tree.pack(fill='both', expand=True)
    def load_approved_pos():
        for item in po_tree.get_children():
            po_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT po.po_id, po.po_number, COALESCE(s.name, 'N/A'),
                           po.order_date, po.expected_delivery, po.total_amount,
                           COUNT(poi.po_item_id)
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
                    WHERE po.status = 'Approved'
                    GROUP BY po.po_id
                    ORDER BY po.expected_delivery
                ''')
                pos = cursor.fetchall()
                for po in pos:
                    po_tree.insert('', 'end', values=(
                        po[1],  # PO Number
                        po[2],  # Supplier
                        po[3],  # Order Date
                        po[4] or 'N/A',  # Expected
                        f"£{po[5]:,.2f}",  # Total
                        po[6]  # Items
                    ), tags=(po[0],))
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load purchase orders: {e}")
    load_approved_pos()
    def proceed_to_receive():
        selection = po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order to receive")
            return
        po_id = po_tree.item(selection[0])['tags'][0]
        po_number = po_tree.item(selection[0])['values'][0]
        select_dialog.destroy()
        show_receive_dialog(po_id, po_number)
    def show_receive_dialog(po_id, po_number):
        """Show receiving dialog with item quantities"""
        receive_dialog = tk.Toplevel(parent_dialog)
        receive_dialog.title(f"Receive PO - {po_number}")
        receive_dialog.geometry("900x700")
        receive_dialog.transient(parent_dialog)
        receive_dialog.grab_set()
        main_frame = ttk.Frame(receive_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text=f"Receive Purchase Order: {po_number}",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Instructions
        ttk.Label(main_frame,
                 text="Enter the actual quantity received for each item (defaults to ordered quantity)",
                 foreground='blue').pack(pady=5)
        # Load PO items
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute('''
                SELECT po_item_id, item_name, description, quantity, unit
                FROM purchase_order_items
                WHERE po_id = ?
            ''', (po_id,))
            items = cursor.fetchall()
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load items: {e}")
            receive_dialog.destroy()
            return
        # Items frame with scrollbar
        items_frame = ttk.LabelFrame(main_frame, text="Items to Receive", padding=15)
        items_frame.pack(fill='both', expand=True, pady=10)
        canvas = tk.Canvas(items_frame)
        scrollbar = ttk.Scrollbar(items_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # Header row
        ttk.Label(scrollable_frame, text="Item", font=('Arial', 9, 'bold'),
                 width=25).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Ordered Qty", font=('Arial', 9, 'bold'),
                 width=15).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Received Qty", font=('Arial', 9, 'bold'),
                 width=15).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Unit", font=('Arial', 9, 'bold'),
                 width=10).grid(row=0, column=3, padx=5, pady=5)
        # Create entry fields for each item
        item_entries = {}
        for idx, item in enumerate(items, start=1):
            item_id, name, desc, qty, unit = item
            # Item name
            display_name = f"{name}\n{desc}" if desc else name
            ttk.Label(scrollable_frame, text=display_name, width=25,
                     wraplength=180).grid(row=idx, column=0, padx=5, pady=5, sticky='w')
            # Ordered quantity
            ttk.Label(scrollable_frame, text=str(qty), width=15).grid(
                row=idx, column=1, padx=5, pady=5)
            # Received quantity entry
            rec_entry = ttk.Entry(scrollable_frame, width=15)
            rec_entry.grid(row=idx, column=2, padx=5, pady=5)
            rec_entry.insert(0, str(qty))  # Default to ordered quantity
            item_entries[item_id] = rec_entry
            # Unit
            ttk.Label(scrollable_frame, text=unit, width=10).grid(
                row=idx, column=3, padx=5, pady=5)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        # Receiving details
        details_frame = ttk.Frame(main_frame)
        details_frame.pack(fill='x', pady=10)
        ttk.Label(details_frame, text="Received By:").pack(side='left', padx=5)
        received_by = ttk.Entry(details_frame, width=20)
        received_by.pack(side='left', padx=5)
        # Get current user
        current_user = "System"
        if AUTH_AVAILABLE:
            try:
                from education_system.post_18.university_system.infrastructure.shared_context import get_auth
                auth = get_auth()
                if auth.current_user:
                    current_user = auth.current_user.get('username', 'Unknown')
            except (sqlite3.Error, tk.TclError):
                pass
        received_by.insert(0, current_user)
        ttk.Label(details_frame, text="Received Date:").pack(side='left', padx=20)
        received_date = ttk.Entry(details_frame, width=15)
        received_date.pack(side='left', padx=5)
        received_date.insert(0, datetime.now().strftime('%Y-%m-%d'))
        # Update inventory checkbox
        update_inv_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Update inventory quantities",
                      variable=update_inv_var).pack(pady=5)
        def save_receipt():
            try:
                conn = get_db_connection()
                if not conn:
                    return
                cursor = conn.cursor()
                # Update PO status
                cursor.execute('''
                    UPDATE purchase_orders
                    SET status = 'Received',
                        actual_delivery = ?,
                        received_by = ?
                    WHERE po_id = ?
                ''', (received_date.get(), received_by.get(), po_id))
                # Update received quantities for each item
                for item_id, entry in item_entries.items():
                    received_qty = float(entry.get() or 0)
                    cursor.execute('''
                        UPDATE purchase_order_items
                        SET received_quantity = ?
                        WHERE po_item_id = ?
                    ''', (received_qty, item_id))
                # Optionally update inventory
                if update_inv_var.get():
                    for item_id, entry in item_entries.items():
                        received_qty = float(entry.get() or 0)
                        # Get item name
                        cursor.execute('''
                            SELECT item_name FROM purchase_order_items
                            WHERE po_item_id = ?
                        ''', (item_id,))
                        item_name = cursor.fetchone()[0]
                        # Check if item exists in inventory
                        cursor.execute('''
                            SELECT item_id, quantity FROM restaurant_inventory
                            WHERE LOWER(item_name) = LOWER(?)
                        ''', (item_name,))
                        existing = cursor.fetchone()
                        if existing:
                            # Update existing inventory
                            new_qty = existing[1] + received_qty
                            cursor.execute('''
                                UPDATE restaurant_inventory
                                SET quantity = ?,
                                    last_updated = CURRENT_TIMESTAMP
                                WHERE item_id = ?
                            ''', (new_qty, existing[0]))
                        # If not in inventory, could add here but skipping for safety
                conn.commit()
                conn.close()
                messagebox.showinfo("Success",
                                  f"Purchase Order {po_number} marked as received!\n\n"
                                  f"Received by: {received_by.get()}\n"
                                  f"Date: {received_date.get()}")
                receive_dialog.destroy()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to receive purchase order: {e}")
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Complete Receipt",
                  command=save_receipt).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=receive_dialog.destroy).pack(side='right', padx=5)
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Receive Selected", command=proceed_to_receive).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=load_approved_pos).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel", command=select_dialog.destroy).pack(side='right', padx=5)

def purchase_order_reports(self, parent_dialog):
    """Generate various purchase order reports and analytics"""
    reports_dialog = tk.Toplevel(parent_dialog)
    reports_dialog.title("Purchase Order Reports")
    reports_dialog.geometry("900x700")
    reports_dialog.transient(parent_dialog)
    reports_dialog.grab_set()
    main_frame = ttk.Frame(reports_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Purchase Order Reports & Analytics",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Report options
    reports_frame = ttk.LabelFrame(main_frame, text="Available Reports", padding=15)
    reports_frame.pack(fill='both', expand=True, pady=10)
    # Report output area
    output_frame = ttk.LabelFrame(main_frame, text="Report Output", padding=10)
    output_frame.pack(fill='both', expand=True, pady=10)
    output_text = ScrolledText(output_frame, height=20, width=100, font=('Courier', 9))
    output_text.pack(fill='both', expand=True)
    def generate_summary_report():
        """Overall PO summary statistics"""
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM purchase_orders")
            total_pos = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Pending'")
            pending = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Approved'")
            approved = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Received'")
            received = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Cancelled'")
            cancelled = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(total_amount) FROM purchase_orders WHERE status != 'Cancelled'")
            total_value = cursor.fetchone()[0] or 0
            cursor.execute("SELECT AVG(total_amount) FROM purchase_orders WHERE status != 'Cancelled'")
            avg_value = cursor.fetchone()[0] or 0
            cursor.execute('''
                SELECT s.name, COUNT(po.po_id), SUM(po.total_amount)
                FROM purchase_orders po
                JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.status != 'Cancelled'
                GROUP BY s.name
                ORDER BY SUM(po.total_amount) DESC
                LIMIT 5
            ''')
            top_suppliers = cursor.fetchall()
            conn.close()
            # Generate report
            report = f"""
{'='*80}
                    PURCHASE ORDER SUMMARY REPORT
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

OVERALL STATISTICS:
------------------
Total Purchase Orders:     {total_pos}
  - Pending:              {pending}
  - Approved:             {approved}
  - Received:             {received}
  - Cancelled:            {cancelled}

FINANCIAL SUMMARY:
-----------------
Total Value (excl. cancelled):  £{total_value:,.2f}
Average PO Value:               £{avg_value:,.2f}

TOP 5 SUPPLIERS BY VALUE:
------------------------
"""
            for idx, (supplier, count, value) in enumerate(top_suppliers, 1):
                report += f"{idx}. {supplier:<30} POs: {count:>3}  Value: £{value:>10,.2f}\n"

            report += "\n" + "="*80 + "\n"

            output_text.delete('1.0', tk.END)
            output_text.insert('1.0', report)

        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    def generate_status_report():
        """Detailed report by status"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            report = f"""
{'='*80}
                    PURCHASE ORDERS BY STATUS
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

"""

            for status in ['Pending', 'Approved', 'Received', 'Cancelled']:
                cursor.execute('''
                    SELECT po.po_number, s.name, po.order_date, po.total_amount
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    WHERE po.status = ?
                    ORDER BY po.order_date DESC
                ''', (status,))
                pos = cursor.fetchall()

                report += f"\n{status.upper()} PURCHASE ORDERS ({len(pos)}):\n"
                report += "-" * 80 + "\n"

                if pos:
                    report += f"{'PO Number':<20} {'Supplier':<25} {'Date':<12} {'Amount':>12}\n"
                    report += "-" * 80 + "\n"
                    for po in pos:
                        report += f"{po[0]:<20} {(po[1] or 'N/A'):<25} {po[2]:<12} £{po[3]:>10,.2f}\n"
                else:
                    report += "No purchase orders with this status\n"

                report += "\n"

            conn.close()

            report += "="*80 + "\n"

            output_text.delete('1.0', tk.END)
            output_text.insert('1.0', report)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    def generate_supplier_report():
        """Report by supplier"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            cursor.execute('''
                SELECT s.name, s.supplier_id
                FROM restaurant_suppliers s
                ORDER BY s.name
            ''')
            suppliers = cursor.fetchall()

            report = f"""
{'='*80}
                    PURCHASE ORDERS BY SUPPLIER
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

"""

            for supplier_name, supplier_id in suppliers:
                cursor.execute('''
                    SELECT COUNT(*), SUM(total_amount), AVG(total_amount)
                    FROM purchase_orders
                    WHERE supplier_id = ? AND status != 'Cancelled'
                ''', (supplier_id,))
                stats = cursor.fetchone()
                count, total, avg = stats[0], stats[1] or 0, stats[2] or 0

                cursor.execute('''
                    SELECT po_number, order_date, status, total_amount
                    FROM purchase_orders
                    WHERE supplier_id = ?
                    ORDER BY order_date DESC
                    LIMIT 5
                ''', (supplier_id,))
                recent_pos = cursor.fetchall()

                report += f"\n{supplier_name.upper()}\n"
                report += "-" * 80 + "\n"
                report += f"Total POs: {count}  |  Total Value: £{total:,.2f}  |  Avg Value: £{avg:,.2f}\n\n"

                if recent_pos:
                    report += f"{'Recent POs:':<20} {'Date':<12} {'Status':<12} {'Amount':>12}\n"
                    report += "-" * 80 + "\n"
                    for po in recent_pos:
                        report += f"{po[0]:<20} {po[1]:<12} {po[2]:<12} £{po[3]:>10,.2f}\n"
                else:
                    report += "No purchase orders for this supplier\n"

                report += "\n"

            conn.close()

            report += "="*80 + "\n"

            output_text.delete('1.0', tk.END)
            output_text.insert('1.0', report)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    def export_to_csv():
        """Export all POs to CSV"""
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute('''
                SELECT po.po_number, s.name, po.order_date, po.expected_delivery,
                       po.actual_delivery, po.status, po.total_amount, po.tax_amount,
                       po.shipping_cost, po.ordered_by, po.received_by, po.notes
                FROM purchase_orders po
                LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                ORDER BY po.order_date DESC
            ''')
            pos = cursor.fetchall()
            conn.close()
            # Create CSV content
            import csv
            from io import StringIO
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['PO Number', 'Supplier', 'Order Date', 'Expected Delivery',
                           'Actual Delivery', 'Status', 'Total Amount', 'Tax Amount',
                           'Shipping Cost', 'Ordered By', 'Received By', 'Notes'])
            for po in pos:
                writer.writerow(po)
            csv_content = output.getvalue()
            # Save to file
            filename = f"purchase_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(os.getcwd(), filename)
            with open(filepath, 'w', newline='') as f:
                f.write(csv_content)
            messagebox.showinfo("Export Success",
                              f"Purchase orders exported successfully!\n\n"
                              f"File: {filename}\n"
                              f"Location: {filepath}\n"
                              f"Records: {len(pos)}")
        except (OSError, IOError) as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    # Report buttons
    btn_frame = ttk.Frame(reports_frame)
    btn_frame.pack(fill='x', pady=5)
    ttk.Button(btn_frame, text="Summary Report",
              command=generate_summary_report).pack(side='left', padx=5, pady=5)
    ttk.Button(btn_frame, text="Status Report",
              command=generate_status_report).pack(side='left', padx=5, pady=5)
    ttk.Button(btn_frame, text="Supplier Report",
              command=generate_supplier_report).pack(side='left', padx=5, pady=5)
    ttk.Button(btn_frame, text="Export to CSV",
              command=export_to_csv).pack(side='left', padx=5, pady=5)
    # Close button
    ttk.Button(main_frame, text="Close", command=reports_dialog.destroy).pack(pady=10)

def manage_suppliers_dialog(self):
    """Launch the Suppliers management dialog (part of Purchase Orders GUI)"""
    try:
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.purchase_orders_gui import (
            PurchaseOrdersGUI,
            init_purchase_orders_tables
        )

        # Initialize tables if needed
        init_purchase_orders_tables()

        # Create and show the Purchase Orders GUI
        suppliers_window = tk.Toplevel(self.root)
        suppliers_window.title("Suppliers Management")
        suppliers_window.geometry("1200x700")
        suppliers_window.transient(self.root)

        # Launch the GUI
        gui = PurchaseOrdersGUI(suppliers_window)
        # Switch to suppliers tab (index 1)
        if hasattr(gui, 'notebook'):
            gui.notebook.select(1)

    except ImportError as e:
        messagebox.showerror("Error", f"Failed to load Suppliers module:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Suppliers:\n{str(e)}")

