"""
Database initialization and permission setup for the charity shop.
"""

from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports import (
    sqlite3, logger, get_connection, safe_alter_table_add_column, get_auth,
    TABLE_NAME, CUSTOMERS_TABLE, DONATIONS_TABLE, DONORS_TABLE, STAFF_TABLE,
    GIFT_CARDS_TABLE, PRICE_HISTORY_TABLE, SALES_TABLE, BUNDLES_TABLE,
    PROMOTIONS_TABLE, LAYAWAY_TABLE, LOYALTY_TABLE, ARCHIVED_TABLE,
    LOCATIONS_TABLE, SHIFTS_TABLE, TASKS_TABLE, WISHLISTS_TABLE,
    FEEDBACK_TABLE, REFERRALS_TABLE,
    auth,
)
import education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports as _imp


def init_charity_shop_db() -> bool:
    """Initialize the charity shop database tables."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if main table exists and has the correct columns
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns = [col[1] for col in cursor.fetchall()]

        if 'sold' not in columns:
            if 'id' in columns:
                # Migration: add new columns to existing table
                safe_alter_table_add_column(TABLE_NAME, "sold", "INTEGER DEFAULT 0", conn)
                safe_alter_table_add_column(TABLE_NAME, "sold_date", "TEXT", conn)
                safe_alter_table_add_column(TABLE_NAME, "sold_quantity", "INTEGER DEFAULT 0", conn)
            else:
                # Create new table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        price REAL NOT NULL,
                        quantity INTEGER NOT NULL,
                        condition TEXT DEFAULT 'Good',
                        date_added TEXT NOT NULL,
                        sold INTEGER DEFAULT 0,
                        sold_date TEXT,
                        sold_quantity INTEGER DEFAULT 0
                    )
                """)

        # Add new columns to main stock table if missing
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns = [col[1] for col in cursor.fetchall()]

        new_columns = [
            ("low_stock_threshold", "INTEGER DEFAULT 5"),
            ("barcode", "TEXT"),
            ("location_id", "INTEGER"),
            ("discount_percent", "REAL DEFAULT 0"),
            ("donation_cost", "REAL DEFAULT 0"),
        ]
        for col_name, col_def in new_columns:
            if col_name not in columns:
                safe_alter_table_add_column(TABLE_NAME, col_name, col_def, conn)

        # Create customers table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {CUSTOMERS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                date_registered TEXT NOT NULL,
                birthday TEXT,
                is_vip INTEGER DEFAULT 0,
                loyalty_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                notes TEXT
            )
        """)

        # Create donors table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {DONORS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                date_registered TEXT NOT NULL,
                total_donations INTEGER DEFAULT 0,
                total_value REAL DEFAULT 0,
                notes TEXT
            )
        """)

        # Create donations table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {DONATIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donor_id INTEGER,
                item_description TEXT NOT NULL,
                category TEXT,
                quantity INTEGER DEFAULT 1,
                estimated_value REAL,
                date_received TEXT NOT NULL,
                receipt_number TEXT,
                donation_drive_id TEXT,
                notes TEXT,
                FOREIGN KEY (donor_id) REFERENCES {DONORS_TABLE}(id)
            )
        """)

        # Create staff table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {STAFF_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                role TEXT DEFAULT 'volunteer',
                date_joined TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                total_hours REAL DEFAULT 0,
                total_sales REAL DEFAULT 0,
                sales_count INTEGER DEFAULT 0
            )
        """)

        # Create gift cards table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {GIFT_CARDS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                initial_balance REAL NOT NULL,
                current_balance REAL NOT NULL,
                date_issued TEXT NOT NULL,
                expiry_date TEXT,
                issued_to INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (issued_to) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create price history table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {PRICE_HISTORY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                old_price REAL,
                new_price REAL NOT NULL,
                change_date TEXT NOT NULL,
                changed_by TEXT,
                reason TEXT,
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id)
            )
        """)

        # Create sales table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SALES_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                customer_id INTEGER,
                staff_id INTEGER,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                discount_applied REAL DEFAULT 0,
                total_amount REAL NOT NULL,
                payment_method TEXT DEFAULT 'cash',
                sale_date TEXT NOT NULL,
                refunded INTEGER DEFAULT 0,
                refund_date TEXT,
                refund_reason TEXT,
                gift_card_id INTEGER,
                loyalty_points_earned INTEGER DEFAULT 0,
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id),
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id),
                FOREIGN KEY (staff_id) REFERENCES {STAFF_TABLE}(id)
            )
        """)

        # Create bundles table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {BUNDLES_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                bundle_price REAL NOT NULL,
                item_ids TEXT NOT NULL,
                date_created TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                times_sold INTEGER DEFAULT 0
            )
        """)

        # Create promotions table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {PROMOTIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                discount_type TEXT NOT NULL,
                discount_value REAL NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                category TEXT,
                min_purchase REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Create layaway table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {LAYAWAY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                total_price REAL NOT NULL,
                deposit_paid REAL NOT NULL,
                remaining_balance REAL NOT NULL,
                start_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id),
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create loyalty points log table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {LOYALTY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                points_change INTEGER NOT NULL,
                reason TEXT,
                transaction_date TEXT NOT NULL,
                sale_id INTEGER,
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create archived items table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {ARCHIVED_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                condition TEXT,
                date_added TEXT,
                date_archived TEXT NOT NULL,
                archive_reason TEXT
            )
        """)

        # Create locations table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {LOCATIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                address TEXT,
                phone TEXT,
                manager TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Create shifts table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SHIFTS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                shift_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                hours_worked REAL,
                notes TEXT,
                FOREIGN KEY (staff_id) REFERENCES {STAFF_TABLE}(id)
            )
        """)

        # Create tasks table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TASKS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                assigned_to INTEGER,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                due_date TEXT,
                created_date TEXT NOT NULL,
                completed_date TEXT,
                FOREIGN KEY (assigned_to) REFERENCES {STAFF_TABLE}(id)
            )
        """)

        # Create wishlists table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {WISHLISTS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                item_description TEXT NOT NULL,
                category TEXT,
                max_price REAL,
                date_added TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create feedback table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {FEEDBACK_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                item_id INTEGER,
                rating INTEGER NOT NULL,
                comment TEXT,
                feedback_date TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id),
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id)
            )
        """)

        # Create referrals table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {REFERRALS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                referral_date TEXT NOT NULL,
                reward_given INTEGER DEFAULT 0,
                reward_amount REAL DEFAULT 0,
                FOREIGN KEY (referrer_id) REFERENCES {CUSTOMERS_TABLE}(id),
                FOREIGN KEY (referred_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        conn.commit()
        conn.close()
        logger.info("Charity shop database initialized successfully")
        return True

    except sqlite3.Error as e:
        logger.error(f"Error initializing charity shop database: {e}")
        print(f"Database error: {e}")
        return False


def setup_charity_shop_permissions(auth_instance=None) -> None:
    """Setup permissions for the charity shop module."""
    if auth_instance is None:
        auth_instance = _imp.auth or get_auth()

    if auth_instance is None:
        logger.warning("No auth instance available for setting up charity shop permissions")
        return

    # Define charity shop permissions
    permissions = [
        'view_charity_shop_stock',
        'add_charity_shop_item',
        'edit_charity_shop_item',
        'delete_charity_shop_item',
        'sell_charity_shop_item',
        'view_charity_shop_reports',
        'manage_charity_shop',
    ]

    # Add permissions to roles
    try:
        if hasattr(auth_instance, 'add_permission_to_role'):
            # Admin gets all permissions
            for perm in permissions:
                try:
                    auth_instance.add_permission_to_role('admin', perm)
                except Exception:
                    pass

            # Staff gets most permissions
            staff_perms = [p for p in permissions if 'delete' not in p]
            for perm in staff_perms:
                try:
                    auth_instance.add_permission_to_role('staff', perm)
                except Exception:
                    pass

            # Students and instructors can view
            for role in ['student', 'instructor']:
                try:
                    auth_instance.add_permission_to_role(role, 'view_charity_shop_stock')
                except Exception:
                    pass

            logger.info("Charity shop permissions setup complete")
    except Exception as e:
        logger.warning(f"Could not setup charity shop permissions: {e}")
