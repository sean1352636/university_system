from education_system.systems.university.plugins.campus_commerce.domain.cafe import *  # noqa: F401,F403

def get_db_connection():
    """Get database connection with proper error handling."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        return conn
    except (sqlite3.Error, OSError) as e:
        print(f"Database connection error: {e}")
        return None

def init_cafe_db() -> bool:
    """Initialize cafe database tables."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Unified products table (cafe items have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_product_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                is_alcoholic INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                stock_quantity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Unified orders table (cafe orders have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_order_id INTEGER,
                student_id TEXT,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                payment_method TEXT,
                age_verified INTEGER DEFAULT 0,
                order_status TEXT DEFAULT 'pending',
                notes TEXT
            )
        ''')

        # Unified order_items table (cafe order items have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_order_id INTEGER,
                product_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL,
                FOREIGN KEY (source_order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        ''')

        # NOTE: cafe inventory transactions now use the unified 'transactions' table
        # with source_type = 'cafe_inventory'

        # Suppliers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                payment_terms TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Supplier-product link table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_supplier_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                cost_per_unit REAL,
                notes TEXT,
                FOREIGN KEY (supplier_id) REFERENCES cafe_suppliers(supplier_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        ''')

        # Reservations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_reservations (
                reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                student_id TEXT,
                reservation_date DATE NOT NULL,
                reservation_time TIME NOT NULL,
                party_size INTEGER NOT NULL,
                status TEXT DEFAULT 'confirmed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Loyalty points table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_loyalty (
                loyalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Loyalty points log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_loyalty_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                points_change INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES cafe_loyalty(student_id)
            )
        ''')

        # Staff scheduling table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_staff_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_name TEXT NOT NULL,
                position TEXT NOT NULL DEFAULT 'barista',
                day_of_week TEXT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

        # Insert sample menu items if table is empty
        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'cafe'")
        if cursor.fetchone()[0] == 0:
            sample_items = [
                ('cafe', 'Espresso', 'Hot Drinks', 'Classic Italian espresso', 2.50, 1, 100),
                ('cafe', 'Cappuccino', 'Hot Drinks', 'Espresso with steamed milk and foam', 3.50, 1, 100),
                ('cafe', 'Latte', 'Hot Drinks', 'Espresso with steamed milk', 3.75, 1, 100),
                ('cafe', 'Americano', 'Hot Drinks', 'Espresso with hot water', 2.75, 1, 100),
                ('cafe', 'Hot Chocolate', 'Hot Drinks', 'Rich hot chocolate', 3.25, 1, 100),
                ('cafe', 'Tea', 'Hot Drinks', 'Selection of teas', 2.25, 1, 100),
                ('cafe', 'Iced Coffee', 'Cold Drinks', 'Chilled coffee over ice', 3.50, 1, 100),
                ('cafe', 'Iced Tea', 'Cold Drinks', 'Refreshing iced tea', 2.75, 1, 100),
                ('cafe', 'Smoothie', 'Cold Drinks', 'Fruit smoothie', 4.50, 1, 50),
                ('cafe', 'Fresh Juice', 'Cold Drinks', 'Freshly squeezed juice', 3.95, 1, 50),
                ('cafe', 'Croissant', 'Pastries', 'Buttery French croissant', 2.50, 1, 30),
                ('cafe', 'Muffin', 'Pastries', 'Blueberry or chocolate chip', 2.75, 1, 40),
                ('cafe', 'Danish', 'Pastries', 'Sweet pastry', 3.00, 1, 30),
                ('cafe', 'Cookie', 'Pastries', 'Freshly baked cookie', 1.50, 1, 60),
                ('cafe', 'Brownie', 'Pastries', 'Chocolate brownie', 2.95, 1, 40),
                ('cafe', 'Sandwich', 'Food', 'Various sandwich options', 5.50, 1, 25),
                ('cafe', 'Panini', 'Food', 'Grilled panini', 6.50, 1, 20),
                ('cafe', 'Salad', 'Food', 'Fresh garden salad', 5.95, 1, 15),
                ('cafe', 'Soup', 'Food', 'Soup of the day', 4.50, 1, 20),
                ('cafe', 'Bagel', 'Food', 'Toasted bagel with spreads', 3.25, 1, 35)
            ]
            cursor.executemany(
                "INSERT INTO products (source_type, name, category, description, price, is_available, stock_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                sample_items
            )
            conn.commit()

        conn.close()
        logger.info("Cafe database initialized successfully")
        return True

    except sqlite3.Error as e:
        logger.error(f"Error initializing cafe database: {e}")
        print(f"Database error: {e}")
        return False

