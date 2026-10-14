"""Extracted function implementation."""

from education_system.systems.university.infrastructure.database.schemas import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_commerce_tables():
    """Initialize commerce system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="commerce"))

        # Create inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        unit TEXT NOT NULL,
                        minimum_threshold INTEGER DEFAULT 10,
                        supplier TEXT,
                        cost_per_unit REAL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # Create meal_accounts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS meal_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT UNIQUE,
                        balance DECIMAL(10,2) DEFAULT 0.00,
                        low_balance_threshold DECIMAL(10,2) DEFAULT 10.00,
                        auto_topup_enabled BOOLEAN DEFAULT 0,
                        auto_topup_amount DECIMAL(10,2) DEFAULT 20.00,
                        last_updated TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create menu_items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        price REAL NOT NULL,
                        category TEXT,
                        allergens TEXT,
                        vegetarian BOOLEAN DEFAULT 0,
                        vegan BOOLEAN DEFAULT 0,
                        available BOOLEAN DEFAULT 1
                    )
        ''')

        # Create restaurant_customers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_customers (
                        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT,
                        phone TEXT,
                        loyalty_tier TEXT DEFAULT 'Bronze',
                        loyalty_points INTEGER DEFAULT 0,
                        total_spent REAL DEFAULT 0
                    )
        ''')

        # Create restaurant_inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_inventory (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        quantity REAL DEFAULT 0,
                        unit TEXT,
                        cost_per_unit REAL,
                        reorder_level REAL DEFAULT 0
                    )
        ''')

        # Create restaurant_orders table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_price REAL,
                        tax_amount REAL,
                        status TEXT DEFAULT 'Pending',
                        payment_method TEXT
                    )
        ''')

        # Create restaurant_staff table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_staff (
                        staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        hourly_rate REAL,
                        status TEXT DEFAULT 'Active',
                        performance_score REAL
                    )
        ''')

        # Create restaurant_tables table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_tables (
                        table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        capacity INTEGER NOT NULL,
                        status TEXT DEFAULT 'Available',
                        location TEXT,
                        table_type TEXT DEFAULT 'Standard'
                    )
        ''')

        # Create shop_cart table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_cart (
                    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (product_id) REFERENCES products (product_id),
                    UNIQUE(user_id, product_id)
                )
        ''')

        # Create shop_discounts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_discounts (
                    discount_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    discount_type TEXT NOT NULL,
                    discount_value REAL NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    applicable_products TEXT,
                    min_purchase_amount REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create shop_inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    last_restock_date TEXT,
                    restock_threshold INTEGER DEFAULT 5
                )
        ''')

        # Create shop_products table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    category TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tax_rate REAL DEFAULT 0.2,
                    is_active BOOLEAN DEFAULT 1
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="commerce"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="commerce", error=str(e)))
        if 'conn' in locals():
            conn.close()
