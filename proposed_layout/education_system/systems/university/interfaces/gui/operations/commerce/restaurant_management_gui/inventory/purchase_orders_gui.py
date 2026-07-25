"""
Purchase Orders Management GUI

Manages supplier purchases, inventory ordering, and expense tracking.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import uuid

# Import database connection
from education_system.systems.university.interfaces.gui.operations.commerce.restaurant_management_gui.core.main_gui import get_db_connection


def init_purchase_orders_tables():
    """Initialize purchase orders and related tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Create suppliers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                payment_terms TEXT,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create purchase orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_purchase_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT UNIQUE NOT NULL,
                supplier_id INTEGER NOT NULL,
                order_date DATE NOT NULL,
                expected_delivery_date DATE,
                actual_delivery_date DATE,
                total_cost REAL NOT NULL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'Pending',
                payment_method TEXT,
                payment_status TEXT DEFAULT 'Unpaid',
                notes TEXT,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES restaurant_suppliers(supplier_id)
            )
        ''')

        # Create purchase order items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_purchase_order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_of_measure TEXT,
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                received_quantity REAL DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES restaurant_purchase_orders(order_id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()
        print("✓ Purchase orders tables initialized successfully")
        return True

    except Exception as e:
        print(f"✗ Error initializing purchase orders tables: {e}")
        return False


class PurchaseOrdersGUI:
    """GUI for managing purchase orders"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Purchase Orders Management")
        self.window.geometry("1400x800")

        # Initialize tables
        init_purchase_orders_tables()

        self.create_widgets()
        self.load_purchase_orders()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main notebook
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Purchase Orders Tab
        po_tab = ttk.Frame(notebook)
        notebook.add(po_tab, text="Purchase Orders")
        self.create_po_tab(po_tab)

        # Suppliers Tab
        suppliers_tab = ttk.Frame(notebook)
        notebook.add(suppliers_tab, text="Suppliers")
        self.create_suppliers_tab(suppliers_tab)

    def create_po_tab(self, parent):
        """Create purchase orders tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Purchase Orders",
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text="New Purchase Order",
                  command=self.create_purchase_order).pack(side=tk.RIGHT, padx=5)

        # Filters
        filter_frame = ttk.LabelFrame(parent, text="Filters", padding="10")
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, padx=5)
        self.status_filter = ttk.Combobox(filter_frame, width=15,
                                         values=['All', 'Pending', 'Approved', 'Ordered',
                                                'Received', 'Completed', 'Cancelled'])
        self.status_filter.set('All')
        self.status_filter.grid(row=0, column=1, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_purchase_orders())

        ttk.Button(filter_frame, text="Refresh",
                  command=self.load_purchase_orders).grid(row=0, column=2, padx=10)

        # Purchase Orders List
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('po_number', 'supplier', 'order_date', 'delivery_date',
                  'total_cost', 'status', 'payment_status')
        self.po_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.po_tree.heading('po_number', text='PO Number')
        self.po_tree.heading('supplier', text='Supplier')
        self.po_tree.heading('order_date', text='Order Date')
        self.po_tree.heading('delivery_date', text='Expected Delivery')
        self.po_tree.heading('total_cost', text='Total Cost')
        self.po_tree.heading('status', text='Status')
        self.po_tree.heading('payment_status', text='Payment')

        self.po_tree.column('po_number', width=120)
        self.po_tree.column('supplier', width=200)
        self.po_tree.column('order_date', width=100)
        self.po_tree.column('delivery_date', width=120)
        self.po_tree.column('total_cost', width=100)
        self.po_tree.column('status', width=100)
        self.po_tree.column('payment_status', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.po_tree.yview)
        self.po_tree.configure(yscrollcommand=scrollbar.set)

        self.po_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="View Details",
                  command=self.view_po_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit",
                  command=self.edit_purchase_order).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Mark as Received",
                  command=self.mark_as_received).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Record Payment",
                  command=self.record_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete",
                  command=self.delete_purchase_order).pack(side=tk.LEFT, padx=5)

    def create_suppliers_tab(self, parent):
        """Create suppliers management tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Suppliers",
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text="Add Supplier",
                  command=self.add_supplier).pack(side=tk.RIGHT, padx=5)

        # Suppliers List
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('name', 'contact_person', 'email', 'phone', 'payment_terms', 'is_active')
        self.suppliers_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        self.suppliers_tree.heading('name', text='Supplier Name')
        self.suppliers_tree.heading('contact_person', text='Contact Person')
        self.suppliers_tree.heading('email', text='Email')
        self.suppliers_tree.heading('phone', text='Phone')
        self.suppliers_tree.heading('payment_terms', text='Payment Terms')
        self.suppliers_tree.heading('is_active', text='Status')

        self.suppliers_tree.column('name', width=200)
        self.suppliers_tree.column('contact_person', width=150)
        self.suppliers_tree.column('email', width=200)
        self.suppliers_tree.column('phone', width=120)
        self.suppliers_tree.column('payment_terms', width=150)
        self.suppliers_tree.column('is_active', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.suppliers_tree.yview)
        self.suppliers_tree.configure(yscrollcommand=scrollbar.set)

        self.suppliers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Edit Supplier",
                  command=self.edit_supplier).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Toggle Active/Inactive",
                  command=self.toggle_supplier_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete",
                  command=self.delete_supplier).pack(side=tk.LEFT, padx=5)

        # Load suppliers
        self.load_suppliers()

    def load_purchase_orders(self):
        """Load purchase orders from database"""
        for item in self.po_tree.get_children():
            self.po_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            status_filter = self.status_filter.get()
            if status_filter == 'All':
                cursor.execute('''
                    SELECT po.po_number, s.name, po.order_date, po.expected_delivery_date,
                           po.total_cost, po.status, po.payment_status
                    FROM restaurant_purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    ORDER BY po.order_date DESC
                ''')
            else:
                cursor.execute('''
                    SELECT po.po_number, s.name, po.order_date, po.expected_delivery_date,
                           po.total_cost, po.status, po.payment_status
                    FROM restaurant_purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    WHERE po.status = ?
                    ORDER BY po.order_date DESC
                ''', (status_filter,))

            for row in cursor.fetchall():
                po_number, supplier, order_date, delivery_date, total, status, payment = row
                total_str = f"£{total:.2f}" if total else "£0.00"
                delivery_str = delivery_date if delivery_date else "N/A"
                self.po_tree.insert('', tk.END, values=(
                    po_number, supplier or 'Unknown', order_date, delivery_str,
                    total_str, status, payment
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load purchase orders: {e}")

    def load_suppliers(self):
        """Load suppliers from database"""
        for item in self.suppliers_tree.get_children():
            self.suppliers_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, contact_person, email, phone, payment_terms, is_active
                FROM restaurant_suppliers
                ORDER BY name
            ''')

            for row in cursor.fetchall():
                name, contact, email, phone, terms, is_active = row
                status = "Active" if is_active else "Inactive"
                self.suppliers_tree.insert('', tk.END, values=(
                    name, contact or '', email or '', phone or '', terms or '', status
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load suppliers: {e}")

    def create_purchase_order(self):
        """Create new purchase order"""
        dialog = PurchaseOrderDialog(self.window, None)
        if dialog.result:
            self.load_purchase_orders()

    def view_po_details(self):
        """View purchase order details"""
        selection = self.po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order to view")
            return

        po_number = self.po_tree.item(selection[0])['values'][0]
        PurchaseOrderDetailsDialog(self.window, po_number)

    def edit_purchase_order(self):
        """Edit purchase order"""
        selection = self.po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order to edit")
            return

        po_number = self.po_tree.item(selection[0])['values'][0]
        dialog = PurchaseOrderDialog(self.window, po_number)
        if dialog.result:
            self.load_purchase_orders()

    def mark_as_received(self):
        """Mark purchase order as received"""
        selection = self.po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order")
            return

        po_number = self.po_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm", f"Mark PO {po_number} as received?"):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE restaurant_purchase_orders
                    SET status = 'Received',
                        actual_delivery_date = date('now')
                    WHERE po_number = ?
                ''', (po_number,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Purchase order marked as received")
                self.load_purchase_orders()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status: {e}")

    def record_payment(self):
        """Record payment for purchase order"""
        selection = self.po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order")
            return

        po_number = self.po_tree.item(selection[0])['values'][0]
        PaymentDialog(self.window, po_number, self.load_purchase_orders)

    def delete_purchase_order(self):
        """Delete purchase order"""
        selection = self.po_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a purchase order to delete")
            return

        po_number = self.po_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Delete purchase order {po_number}?\n\nThis cannot be undone."):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('DELETE FROM restaurant_purchase_orders WHERE po_number = ?', (po_number,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Purchase order deleted")
                self.load_purchase_orders()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete purchase order: {e}")

    def add_supplier(self):
        """Add new supplier"""
        dialog = SupplierDialog(self.window, None)
        if dialog.result:
            self.load_suppliers()

    def edit_supplier(self):
        """Edit supplier"""
        selection = self.suppliers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a supplier to edit")
            return

        supplier_name = self.suppliers_tree.item(selection[0])['values'][0]
        dialog = SupplierDialog(self.window, supplier_name)
        if dialog.result:
            self.load_suppliers()

    def toggle_supplier_status(self):
        """Toggle supplier active/inactive"""
        selection = self.suppliers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a supplier")
            return

        supplier_name = self.suppliers_tree.item(selection[0])['values'][0]

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE restaurant_suppliers
                SET is_active = NOT is_active
                WHERE name = ?
            ''', (supplier_name,))

            conn.commit()
            conn.close()

            self.load_suppliers()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update supplier status: {e}")

    def delete_supplier(self):
        """Delete supplier"""
        selection = self.suppliers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a supplier to delete")
            return

        supplier_name = self.suppliers_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Delete supplier '{supplier_name}'?\n\nThis cannot be undone."):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('DELETE FROM restaurant_suppliers WHERE name = ?', (supplier_name,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Supplier deleted")
                self.load_suppliers()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete supplier: {e}")


class PurchaseOrderDialog:
    """Dialog for creating/editing purchase orders"""

    def __init__(self, parent, po_number=None):
        self.result = False
        self.po_number = po_number
        self.is_edit = po_number is not None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Purchase Order" if self.is_edit else "New Purchase Order")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.items = []
        self.create_widgets()

        if self.is_edit:
            self.load_po_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header info
        header_frame = ttk.LabelFrame(main_frame, text="Purchase Order Details", padding="10")
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # PO Number
        ttk.Label(header_frame, text="PO Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.po_number_var = tk.StringVar(value=f"PO-{uuid.uuid4().hex[:8].upper()}")
        ttk.Entry(header_frame, textvariable=self.po_number_var, width=30,
                 state='readonly' if self.is_edit else 'normal').grid(row=0, column=1, pady=5, padx=5)

        # Supplier
        ttk.Label(header_frame, text="Supplier:*").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(20,0))
        self.supplier_var = tk.StringVar()
        self.supplier_combo = ttk.Combobox(header_frame, textvariable=self.supplier_var, width=30)
        self.supplier_combo.grid(row=0, column=3, pady=5, padx=5)
        self.load_suppliers()

        # Order Date
        ttk.Label(header_frame, text="Order Date:*").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.order_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(header_frame, textvariable=self.order_date_var, width=30).grid(row=1, column=1, pady=5, padx=5)

        # Expected Delivery
        ttk.Label(header_frame, text="Expected Delivery:").grid(row=1, column=2, sticky=tk.W, pady=5, padx=(20,0))
        self.delivery_date_var = tk.StringVar()
        ttk.Entry(header_frame, textvariable=self.delivery_date_var, width=30).grid(row=1, column=3, pady=5, padx=5)

        # Status
        ttk.Label(header_frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value='Pending')
        ttk.Combobox(header_frame, textvariable=self.status_var, width=28,
                    values=['Pending', 'Approved', 'Ordered', 'Received', 'Completed', 'Cancelled']).grid(row=2, column=1, pady=5, padx=5)

        # Items Section
        items_frame = ttk.LabelFrame(main_frame, text="Order Items", padding="10")
        items_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Items list
        columns = ('item_name', 'quantity', 'unit', 'unit_cost', 'total')
        self.items_tree = ttk.Treeview(items_frame, columns=columns, show='headings', height=10)

        self.items_tree.heading('item_name', text='Item Name')
        self.items_tree.heading('quantity', text='Quantity')
        self.items_tree.heading('unit', text='Unit')
        self.items_tree.heading('unit_cost', text='Unit Cost')
        self.items_tree.heading('total', text='Total')

        self.items_tree.column('item_name', width=250)
        self.items_tree.column('quantity', width=100)
        self.items_tree.column('unit', width=100)
        self.items_tree.column('unit_cost', width=100)
        self.items_tree.column('total', width=100)

        scrollbar = ttk.Scrollbar(items_frame, orient=tk.VERTICAL, command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=scrollbar.set)

        self.items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Item buttons
        item_btn_frame = ttk.Frame(items_frame)
        item_btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(item_btn_frame, text="Add Item", command=self.add_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(item_btn_frame, text="Remove Item", command=self.remove_item).pack(side=tk.LEFT, padx=5)

        # Total
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X, pady=(0, 10))

        self.total_label = ttk.Label(total_frame, text="Total: £0.00", font=('Arial', 12, 'bold'))
        self.total_label.pack(side=tk.RIGHT)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def load_suppliers(self):
        """Load suppliers for combobox"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('SELECT name FROM restaurant_suppliers WHERE is_active = 1 ORDER BY name')
            suppliers = [row[0] for row in cursor.fetchall()]
            self.supplier_combo['values'] = suppliers
            conn.close()

        except Exception as e:
            print(f"Error loading suppliers: {e}")

    def load_po_data(self):
        """Load existing PO data for editing"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Load PO header
            cursor.execute('''
                SELECT po.po_number, s.name, po.order_date, po.expected_delivery_date, po.status
                FROM restaurant_purchase_orders po
                LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.po_number = ?
            ''', (self.po_number,))

            po_data = cursor.fetchone()
            if po_data:
                self.po_number_var.set(po_data[0])
                self.supplier_var.set(po_data[1] or '')
                self.order_date_var.set(po_data[2])
                self.delivery_date_var.set(po_data[3] or '')
                self.status_var.set(po_data[4])

            # Load items
            cursor.execute('''
                SELECT item_name, quantity, unit_of_measure, unit_cost, total_cost
                FROM restaurant_purchase_order_items
                WHERE order_id = (SELECT order_id FROM restaurant_purchase_orders WHERE po_number = ?)
            ''', (self.po_number,))

            for row in cursor.fetchall():
                self.items.append({
                    'name': row[0],
                    'quantity': row[1],
                    'unit': row[2],
                    'unit_cost': row[3],
                    'total': row[4]
                })

            conn.close()
            self.refresh_items_display()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PO data: {e}")

    def add_item(self):
        """Add item to order"""
        dialog = OrderItemDialog(self.dialog)
        if dialog.result:
            self.items.append(dialog.result)
            self.refresh_items_display()

    def remove_item(self):
        """Remove selected item"""
        selection = self.items_tree.selection()
        if not selection:
            return

        index = self.items_tree.index(selection[0])
        del self.items[index]
        self.refresh_items_display()

    def refresh_items_display(self):
        """Refresh items treeview"""
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)

        total = 0
        for item in self.items:
            self.items_tree.insert('', tk.END, values=(
                item['name'],
                item['quantity'],
                item['unit'],
                f"£{item['unit_cost']:.2f}",
                f"£{item['total']:.2f}"
            ))
            total += item['total']

        self.total_label.config(text=f"Total: £{total:.2f}")

    def save(self):
        """Save purchase order"""
        # Validation
        if not self.supplier_var.get():
            messagebox.showwarning("Missing Info", "Please select a supplier")
            return

        if not self.items:
            messagebox.showwarning("Missing Items", "Please add at least one item")
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get supplier ID
            cursor.execute('SELECT supplier_id FROM restaurant_suppliers WHERE name = ?',
                         (self.supplier_var.get(),))
            supplier_row = cursor.fetchone()
            if not supplier_row:
                messagebox.showerror("Error", "Supplier not found")
                conn.close()
                return

            supplier_id = supplier_row[0]
            total_cost = sum(item['total'] for item in self.items)

            if self.is_edit:
                # Update existing PO
                cursor.execute('''
                    UPDATE restaurant_purchase_orders
                    SET supplier_id = ?, order_date = ?, expected_delivery_date = ?,
                        total_cost = ?, status = ?
                    WHERE po_number = ?
                ''', (supplier_id, self.order_date_var.get(),
                     self.delivery_date_var.get() or None, total_cost,
                     self.status_var.get(), self.po_number))

                order_id = cursor.execute('SELECT order_id FROM restaurant_purchase_orders WHERE po_number = ?',
                                        (self.po_number,)).fetchone()[0]

                # Delete old items
                cursor.execute('DELETE FROM restaurant_purchase_order_items WHERE order_id = ?', (order_id,))

            else:
                # Create new PO
                cursor.execute('''
                    INSERT INTO restaurant_purchase_orders
                    (po_number, supplier_id, order_date, expected_delivery_date, total_cost, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.po_number_var.get(), supplier_id, self.order_date_var.get(),
                     self.delivery_date_var.get() or None, total_cost, self.status_var.get()))

                order_id = cursor.lastrowid

            # Insert items
            for item in self.items:
                cursor.execute('''
                    INSERT INTO restaurant_purchase_order_items
                    (order_id, item_name, quantity, unit_of_measure, unit_cost, total_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (order_id, item['name'], item['quantity'], item['unit'],
                     item['unit_cost'], item['total']))

            conn.commit()
            conn.close()

            self.result = True
            messagebox.showinfo("Success", "Purchase order saved successfully")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save purchase order: {e}")


class OrderItemDialog:
    """Dialog for adding order item"""

    def __init__(self, parent):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Order Item")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Item Name:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Quantity:*").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.quantity_var = tk.DoubleVar(value=1.0)
        ttk.Entry(frame, textvariable=self.quantity_var, width=30).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Unit:*").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.unit_var = tk.StringVar(value='kg')
        ttk.Combobox(frame, textvariable=self.unit_var, width=28,
                    values=['kg', 'g', 'L', 'ml', 'units', 'boxes', 'cases']).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Unit Cost (£):*").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.cost_var = tk.DoubleVar(value=0.0)
        ttk.Entry(frame, textvariable=self.cost_var, width=30).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Total:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.total_label = ttk.Label(frame, text="£0.00", font=('Arial', 10, 'bold'))
        self.total_label.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Update total on change
        self.quantity_var.trace('w', self.update_total)
        self.cost_var.trace('w', self.update_total)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Add", command=self.add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def update_total(self, *args):
        """Update total cost"""
        try:
            total = self.quantity_var.get() * self.cost_var.get()
            self.total_label.config(text=f"£{total:.2f}")
        except (ValueError, TypeError):
            pass

    def add(self):
        """Add item"""
        if not self.name_var.get():
            messagebox.showwarning("Missing Info", "Please enter item name")
            return

        try:
            quantity = self.quantity_var.get()
            unit_cost = self.cost_var.get()
            total = quantity * unit_cost

            self.result = {
                'name': self.name_var.get(),
                'quantity': quantity,
                'unit': self.unit_var.get(),
                'unit_cost': unit_cost,
                'total': total
            }

            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Invalid values: {e}")


class SupplierDialog:
    """Dialog for adding/editing suppliers"""

    def __init__(self, parent, supplier_name=None):
        self.result = False
        self.supplier_name = supplier_name
        self.is_edit = supplier_name is not None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Supplier" if self.is_edit else "New Supplier")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if self.is_edit:
            self.load_supplier_data()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Supplier Name:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Contact Person:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.contact_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.contact_var, width=40).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.email_var, width=40).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Phone:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.phone_var, width=40).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Address:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.address_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.address_var, width=40).grid(row=4, column=1, pady=5)

        ttk.Label(frame, text="Payment Terms:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.terms_var = tk.StringVar(value='Net 30')
        ttk.Combobox(frame, textvariable=self.terms_var, width=38,
                    values=['Cash on Delivery', 'Net 7', 'Net 15', 'Net 30', 'Net 60']).grid(row=5, column=1, pady=5)

        ttk.Label(frame, text="Notes:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(frame, height=4, width=40)
        self.notes_text.grid(row=6, column=1, pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_supplier_data(self):
        """Load existing supplier data"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, contact_person, email, phone, address, payment_terms, notes
                FROM restaurant_suppliers
                WHERE name = ?
            ''', (self.supplier_name,))

            data = cursor.fetchone()
            conn.close()

            if data:
                self.name_var.set(data[0])
                self.contact_var.set(data[1] or '')
                self.email_var.set(data[2] or '')
                self.phone_var.set(data[3] or '')
                self.address_var.set(data[4] or '')
                self.terms_var.set(data[5] or 'Net 30')
                self.notes_text.insert('1.0', data[6] or '')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load supplier data: {e}")

    def save(self):
        """Save supplier"""
        if not self.name_var.get():
            messagebox.showwarning("Missing Info", "Please enter supplier name")
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            notes = self.notes_text.get('1.0', tk.END).strip()

            if self.is_edit:
                cursor.execute('''
                    UPDATE restaurant_suppliers
                    SET name = ?, contact_person = ?, email = ?, phone = ?,
                        address = ?, payment_terms = ?, notes = ?
                    WHERE name = ?
                ''', (self.name_var.get(), self.contact_var.get(), self.email_var.get(),
                     self.phone_var.get(), self.address_var.get(), self.terms_var.get(),
                     notes, self.supplier_name))
            else:
                cursor.execute('''
                    INSERT INTO restaurant_suppliers
                    (name, contact_person, email, phone, address, payment_terms, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.name_var.get(), self.contact_var.get(), self.email_var.get(),
                     self.phone_var.get(), self.address_var.get(), self.terms_var.get(), notes))

            conn.commit()
            conn.close()

            self.result = True
            messagebox.showinfo("Success", "Supplier saved successfully")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save supplier: {e}")


class PaymentDialog:
    """Dialog for recording payment"""

    def __init__(self, parent, po_number, callback):
        self.po_number = po_number
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Record Payment")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Record Payment for PO: {self.po_number}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(frame, text="Payment Method:").pack(anchor=tk.W, pady=5)
        self.method_var = tk.StringVar(value='Bank Transfer')
        ttk.Combobox(frame, textvariable=self.method_var, width=38,
                    values=['Cash', 'Check', 'Bank Transfer', 'Credit Card']).pack(pady=5)

        ttk.Label(frame, text="Payment Date:").pack(anchor=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=self.date_var, width=40).pack(pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Record Payment", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def save(self):
        """Save payment"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE restaurant_purchase_orders
                SET payment_status = 'Paid', payment_method = ?, status = 'Completed'
                WHERE po_number = ?
            ''', (self.method_var.get(), self.po_number))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Payment recorded successfully")
            self.dialog.destroy()
            if self.callback:
                self.callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to record payment: {e}")


class PurchaseOrderDetailsDialog:
    """Dialog for viewing PO details"""

    def __init__(self, parent, po_number):
        self.po_number = po_number

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Purchase Order Details - {po_number}")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_details()

    def create_widgets(self):
        """Create widgets"""
        from tkinter.scrolledtext import ScrolledText

        self.text = ScrolledText(self.dialog, height=30, width=80, font=('Courier', 10))
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)

    def load_details(self):
        """Load and display PO details"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get PO header
            cursor.execute('''
                SELECT po.po_number, s.name, s.contact_person, s.phone, s.email,
                       po.order_date, po.expected_delivery_date, po.actual_delivery_date,
                       po.total_cost, po.status, po.payment_status, po.payment_method
                FROM restaurant_purchase_orders po
                LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.po_number = ?
            ''', (self.po_number,))

            po_data = cursor.fetchone()

            if not po_data:
                self.text.insert('1.0', "Purchase order not found")
                conn.close()
                return

            # Get items
            cursor.execute('''
                SELECT item_name, quantity, unit_of_measure, unit_cost, total_cost
                FROM restaurant_purchase_order_items
                WHERE order_id = (SELECT order_id FROM restaurant_purchase_orders WHERE po_number = ?)
            ''', (self.po_number,))

            items = cursor.fetchall()
            conn.close()

            # Build report
            report = "PURCHASE ORDER\n"
            report += "=" * 70 + "\n\n"

            report += f"PO Number: {po_data[0]}\n"
            report += f"Order Date: {po_data[5]}\n"
            report += f"Status: {po_data[9]}\n"
            report += f"Payment Status: {po_data[10]}\n\n"

            report += "SUPPLIER INFORMATION:\n"
            report += "-" * 70 + "\n"
            report += f"Name: {po_data[1] or 'N/A'}\n"
            report += f"Contact: {po_data[2] or 'N/A'}\n"
            report += f"Phone: {po_data[3] or 'N/A'}\n"
            report += f"Email: {po_data[4] or 'N/A'}\n\n"

            report += "DELIVERY INFORMATION:\n"
            report += "-" * 70 + "\n"
            report += f"Expected Delivery: {po_data[6] or 'N/A'}\n"
            report += f"Actual Delivery: {po_data[7] or 'Not yet delivered'}\n\n"

            report += "ORDER ITEMS:\n"
            report += "-" * 70 + "\n"
            report += f"{'Item':<30} {'Qty':<10} {'Unit':<10} {'Price':<10} {'Total':<10}\n"
            report += "-" * 70 + "\n"

            for item in items:
                report += f"{item[0]:<30} {item[1]:<10} {item[2]:<10} £{item[3]:<9.2f} £{item[4]:<9.2f}\n"

            report += "-" * 70 + "\n"
            report += f"{'TOTAL:':<50} £{po_data[8]:.2f}\n"

            if po_data[11]:
                report += f"\nPayment Method: {po_data[11]}\n"

            self.text.insert('1.0', report)
            self.text.config(state='disabled')

        except Exception as e:
            self.text.insert('1.0', f"Error loading details: {e}")
