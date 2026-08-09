from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.operations.commerce.services.shop_management.config import auth


def _heal_legacy_shop_fk_targets(cursor) -> None:
    """Rebuild shop_inventory / shop_transaction_items to drop their broken
    FOREIGN KEY clauses.

    The legacy DDL referenced tables that don't exist (``shop_products`` /
    ``shop_transactions``). Pointing the FKs at the real tables
    (``products`` / ``transactions``) doesn't work either: the columns
    the shop actually writes (`item['product_id']`, the generated
    string ``transaction_id``) don't match any PRIMARY KEY or UNIQUE
    column — `transactions.transaction_id` is an INTEGER autoincrement,
    and `transactions.source_transaction_id` (where the shop's string
    lives) has no UNIQUE constraint. With FK enforcement ON, every
    INSERT raised either ``no such table: main.shop_products`` or
    ``foreign key mismatch`` and killed the checkout.

    The cleanest fix is to drop the FK clauses entirely on these two
    tables. They were never correct, and removing them lets the real
    INSERTs / UPDATEs through without papering over the real data
    relationships.

    Idempotent — a no-op when the tables are already FK-free.
    """
    legacy_tables = {
        'shop_inventory': (
            """
            CREATE TABLE shop_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                last_restock_date TEXT,
                restock_threshold INTEGER DEFAULT 5
            )
            """,
            (
                'inventory_id', 'product_id', 'quantity',
                'last_restock_date', 'restock_threshold',
            ),
        ),
        'shop_transaction_items': (
            """
            CREATE TABLE shop_transaction_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_per_item REAL NOT NULL,
                subtotal REAL NOT NULL
            )
            """,
            (
                'id', 'transaction_id', 'product_id', 'quantity',
                'price_per_item', 'subtotal',
            ),
        ),
    }

    for name, (new_sql, cols) in legacy_tables.items():
        row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        if not row or not row[0]:
            continue
        if 'FOREIGN KEY' not in row[0].upper():
            continue  # already FK-free

        tmp = f"{name}__healed_tmp"
        col_list = ', '.join(cols)
        cursor.execute("PRAGMA foreign_keys = OFF")
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {tmp}")
            cursor.execute(new_sql.replace(name, tmp, 1))
            cursor.execute(
                f"INSERT INTO {tmp} ({col_list}) "
                f"SELECT {col_list} FROM {name}"
            )
            cursor.execute(f"DROP TABLE {name}")
            cursor.execute(f"ALTER TABLE {tmp} RENAME TO {name}")
        finally:
            cursor.execute("PRAGMA foreign_keys = ON")


def init_shop_db() -> bool:
    """Initialize the shop database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Heal the legacy FK targets on existing DBs before we let
        # CREATE TABLE IF NOT EXISTS keep the broken rows in place.
        _heal_legacy_shop_fk_targets(cursor)

        # Note: shop products now use the unified 'products' table
        # with source_type = 'shop'. No CREATE TABLE needed here.

        # Create inventory table. No FK on product_id: enforcement moves
        # to the service layer, because the historical FK target
        # ``shop_products`` doesn't exist and the real products table
        # can't be used without dragging other bad assumptions along.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_inventory (
            inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            last_restock_date TEXT,
            restock_threshold INTEGER DEFAULT 5
        )
        ''')

        # Note: shop transactions now use the unified 'transactions' table
        # with source_type = 'shop'. No CREATE TABLE needed here.

        # Create transaction items table. No FKs: transaction_id is the
        # generated string the shop stores in transactions.source_transaction_id
        # (not transactions.transaction_id, which is an INTEGER PK), and
        # source_transaction_id has no UNIQUE constraint so it can't be
        # an FK target.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_item REAL NOT NULL,
            subtotal REAL NOT NULL
        )
        ''')

        # Create discounts table
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

        # Shop cart uses unified cart table with source_type='shop'

        # Sample products (if no products exist)
        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'shop'")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            products = [
                ('P001', 'shop', 'University Hoodie', 'Comfortable hoodie with university logo', 29.99, 'Clothing', now, now, 0.2, 1),
                ('P002', 'shop', 'University T-Shirt', 'Cotton t-shirt with university logo', 19.99, 'Clothing', now, now, 0.2, 1),
                ('P003', 'shop', 'Notebook Pack', 'Set of 3 university branded notebooks', 12.99, 'Stationery', now, now, 0.2, 1),
                ('P004', 'shop', 'Water Bottle', 'Stainless steel water bottle with university logo', 14.99, 'Accessories', now, now, 0.2, 1),
                ('P005', 'shop', 'Coffee Mug', 'Ceramic mug with university logo', 9.99, 'Accessories', now, now, 0.2, 1),
                ('P006', 'shop', 'Pen Set', 'Set of 5 high-quality pens', 7.99, 'Stationery', now, now, 0.2, 1),
                ('P007', 'shop', 'Laptop Bag', 'Padded laptop bag with university logo', 34.99, 'Accessories', now, now, 0.2, 1),
                ('P008', 'shop', 'USB Drive', '32GB USB flash drive with university logo', 15.99, 'Electronics', now, now, 0.2, 1),
                ('P009', 'shop', 'Keychain', 'Metal keychain with university logo', 4.99, 'Accessories', now, now, 0.2, 1),
                ('P010', 'shop', 'Baseball Cap', 'Adjustable cap with university logo', 16.99, 'Clothing', now, now, 0.2, 1)
            ]
            cursor.executemany(
                'INSERT INTO products (source_product_id, source_type, name, description, price, category, created_at, updated_at, tax_rate, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                products
            )

            # Add inventory for sample products (batch insert to avoid N+1)
            inventory_data = [
                (product[0], 50, now, 10)  # product_id, quantity, last_restock_date, restock_threshold
                for product in products
            ]
            cursor.executemany(
                'INSERT INTO shop_inventory (product_id, quantity, last_restock_date, restock_threshold) VALUES (?, ?, ?, ?)',
                inventory_data
            )

            # Add sample discounts
            discounts = [
                ('D001', 'Student Discount', '10% off for all students', 'percentage', 10.0,
                 now, None, 1, 'all', 0.0, now),
                ('D002', 'Bulk Purchase', '15% off when buying 5 or more items', 'percentage', 15.0,
                 now, None, 1, 'all', 0.0, now),
                ('D003', 'Clothing Sale', '20% off all clothing items', 'percentage', 20.0,
                 now, datetime.now().replace(year=datetime.now().year + 1).strftime('%Y-%m-%d %H:%M:%S'),
                 1, 'Clothing', 0.0, now)
            ]
            cursor.executemany(
                'INSERT INTO shop_discounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                discounts
            )

        conn.commit()
        conn.close()
        print("University shop database initialized successfully!")
        return True

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the shop database: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Unexpected error during shop database initialization: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def create_sample_users() -> bool:
    """Seed a handful of sample shop customers into the ``users`` table.

    Dev/seed helper used by ``setup_shop_system``. Inserts a few realistic
    sample users (students and staff) so the shop has customers to work with
    out of the box. Idempotent: uses ``INSERT OR IGNORE`` keyed on the UNIQUE
    ``username``/``email`` columns, so re-running never raises on duplicates.
    Only writes when called — importing this module has no side effects.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # (username, first_name, last_name, email, role, student_id)
        sample_users = [
            ('shop_alice', 'Alice', 'Turner', 'alice.turner@university.edu', 'student', 'S20001'),
            ('shop_ben', 'Ben', 'Carter', 'ben.carter@university.edu', 'student', 'S20002'),
            ('shop_chloe', 'Chloe', 'Davies', 'chloe.davies@university.edu', 'student', 'S20003'),
            ('shop_daniel', 'Daniel', 'Evans', 'daniel.evans@university.edu', 'staff', None),
            ('shop_manager1', 'Grace', 'Foster', 'grace.foster@university.edu', 'shop_manager', None),
        ]

        # Determine which usernames already exist so we can report an
        # accurate created count (INSERT OR IGNORE silently skips dupes).
        usernames = [u[0] for u in sample_users]
        placeholders = ','.join('?' * len(usernames))
        cursor.execute(
            f'SELECT username FROM users WHERE username IN ({placeholders})',
            usernames,
        )
        existing = {row[0] for row in cursor.fetchall()}

        rows = [
            (username, first_name, last_name, email, role, student_id, timestamp, timestamp)
            for username, first_name, last_name, email, role, student_id in sample_users
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO users '
            '(username, first_name, last_name, email, role, student_id, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            rows,
        )

        conn.commit()
        conn.close()

        created = len(usernames) - len(existing)
        print(f"Created {created} sample shop user(s) ({len(existing)} already existed).")
        return True

    except sqlite3.Error as e:
        if 'conn' in locals():
            conn.close()
        print(f"An error occurred while creating sample users: {e}")
        return False
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Unexpected error while creating sample users: {e}")
        return False


def setup_shop_permissions(auth_instance=None):
    """Setup permissions for the shop module"""
    from education_system.systems.university.domain.operations.commerce.services.shop_management import config

    if auth_instance:
        config.auth = auth_instance

    if not config.auth:
        print("Authentication system not initialized.")
        return False

    try:
        # Connect to the database directly
        conn = get_connection()
        cursor = conn.cursor()

        # Define permissions
        shop_permissions = [
            # Customer permissions
            ('view_products', 'View available products in the shop'),
            ('make_purchase', 'Purchase items from the shop'),
            ('view_own_purchase_history', 'View own purchase history'),

            # Admin permissions
            ('manage_products', 'Add, update, or delete products'),
            ('manage_inventory', 'Manage product inventory levels'),
            ('view_all_transactions', 'View all shop transactions'),
            ('manage_discounts', 'Manage shop discounts and promotions'),
            ('generate_sales_reports', 'Generate and view sales reports')
        ]

        # Add permissions directly to the database if they don't exist
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Batch fetch existing permissions to avoid N+1 queries
        perm_names = [p[0] for p in shop_permissions]
        placeholders = ','.join('?' * len(perm_names))
        cursor.execute(
            f'SELECT permission_name FROM permissions WHERE permission_name IN ({placeholders})',
            perm_names
        )
        existing_perms = {row[0] for row in cursor.fetchall()}

        # Batch insert new permissions
        new_perms = [
            (perm_name, perm_desc, timestamp)
            for perm_name, perm_desc in shop_permissions
            if perm_name not in existing_perms
        ]
        if new_perms:
            cursor.executemany(
                'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                new_perms
            )

        conn.commit()

        # Define role-permission mapping
        role_permissions = {
            'student': ['view_products', 'make_purchase', 'view_own_purchase_history'],
            'staff': ['view_products', 'make_purchase', 'view_own_purchase_history',
                      'view_all_transactions', 'generate_sales_reports'],
            'admin': ['view_products', 'make_purchase', 'view_own_purchase_history',
                      'manage_products', 'manage_inventory', 'view_all_transactions',
                      'manage_discounts', 'generate_sales_reports'],
            'shop_manager': ['view_products', 'make_purchase', 'view_own_purchase_history',
                            'manage_products', 'manage_inventory', 'view_all_transactions',
                            'manage_discounts', 'generate_sales_reports']
        }

        # Batch fetch all roles to avoid N+1 queries
        role_names = list(role_permissions.keys())
        placeholders = ','.join('?' * len(role_names))
        cursor.execute(
            f'SELECT id, role_name FROM roles WHERE role_name IN ({placeholders})',
            role_names
        )
        role_id_map = {row['role_name']: row['id'] for row in cursor.fetchall()}

        # Create shop_manager role if it doesn't exist
        if 'shop_manager' not in role_id_map:
            cursor.execute(
                'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                ('shop_manager', 'Shop Manager role', timestamp, timestamp)
            )
            conn.commit()
            role_id_map['shop_manager'] = cursor.lastrowid

        # Batch fetch all permissions to avoid N+1 queries
        perm_placeholders = ','.join('?' * len(perm_names))
        cursor.execute(
            f'SELECT id, permission_name FROM permissions WHERE permission_name IN ({perm_placeholders})',
            perm_names
        )
        perm_id_map = {row['permission_name']: row['id'] for row in cursor.fetchall()}

        # Batch fetch existing role-permission combinations
        cursor.execute('SELECT role_id, permission_id FROM role_permissions')
        existing_role_perms = {(row['role_id'], row['permission_id']) for row in cursor.fetchall()}

        # Prepare batch insert for new role-permission mappings
        new_role_perms = []
        for role_name, permissions in role_permissions.items():
            role_id = role_id_map.get(role_name)
            if role_id:
                for perm_name in permissions:
                    perm_id = perm_id_map.get(perm_name)
                    if perm_id and (role_id, perm_id) not in existing_role_perms:
                        new_role_perms.append((role_id, perm_id))

        if new_role_perms:
            cursor.executemany(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                new_role_perms
            )

        conn.commit()
        conn.close()

        print("Shop permissions setup successfully!")
        return True

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error setting up shop permissions: {e}")
        return False
