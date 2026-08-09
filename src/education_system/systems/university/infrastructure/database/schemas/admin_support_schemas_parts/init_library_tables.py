"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_library_tables():
    """Initialize library system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="library"))

        # Create book_loans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    checkout_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    return_date TEXT,
                    status TEXT DEFAULT 'active',
                    fine_amount REAL DEFAULT 0.0,
                    renewal_count INTEGER DEFAULT 0,
                    reading_progress INTEGER DEFAULT 0,
                    checkout_method TEXT DEFAULT 'manual',
                    staff_id TEXT,
                    notes TEXT
                )
        ''')

        # Create book_recommendations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.0,
                    generated_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    clicked BOOLEAN DEFAULT FALSE
                )
        ''')

        # Create book_requests table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    isbn TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    requested_date TEXT NOT NULL,
                    processed_date TEXT,
                    processed_by TEXT,
                    notes TEXT
                )
        ''')

        # Create book_reservations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    reservation_date TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    priority_order INTEGER DEFAULT 1,
                    notification_sent BOOLEAN DEFAULT FALSE
                )
        ''')

        # Create book_reviews table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    review_text TEXT,
                    review_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    helpful_votes INTEGER DEFAULT 0,
                    moderated_by TEXT,
                    moderation_date TEXT
                )
        ''')

        # Create books table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
                    book_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    isbn TEXT UNIQUE,
                    publisher TEXT,
                    category TEXT,
                    year_published INTEGER,
                    description TEXT,
                    location TEXT,
                    status TEXT DEFAULT 'available',
                    added_date TEXT,
                    last_updated TEXT,
                    reading_level TEXT,
                    tags TEXT,
                    cover_image_path TEXT,
                    digital_copy_path TEXT,
                    acquisition_cost REAL DEFAULT 0.0,
                    barcode TEXT UNIQUE,
                    qr_code_path TEXT,
                    total_pages INTEGER,
                    language TEXT DEFAULT 'English',
                    edition TEXT,
                    condition_notes TEXT
                )
        ''')

        # Create digital_library table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS digital_library (
                    digital_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER,
                    category TEXT,
                    description TEXT,
                    access_level TEXT DEFAULT 'public',
                    download_count INTEGER DEFAULT 0,
                    added_date TEXT NOT NULL
                )
        ''')

        # Create interlibrary_loans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS interlibrary_loans (
                    ill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    isbn TEXT,
                    source_library TEXT,
                    request_date TEXT NOT NULL,
                    expected_arrival TEXT,
                    actual_arrival TEXT,
                    due_date TEXT,
                    return_date TEXT,
                    status TEXT DEFAULT 'requested',
                    cost REAL DEFAULT 0.0
                )
        ''')

        # Create library_accounts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS library_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        book_title TEXT,
                        author TEXT,
                        isbn TEXT,
                        checkout_date TEXT,
                        due_date TEXT,
                        return_date TEXT,
                        fine_amount DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'checked_out',
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create library_settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS library_settings (
                        setting_name TEXT PRIMARY KEY,
                        setting_value TEXT NOT NULL,
                        description TEXT,
                        setting_type TEXT DEFAULT 'string',
                        min_value REAL,
                        max_value REAL,
                        allowed_values TEXT
                    )
        ''')

        # Create reading_goals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    current_value INTEGER DEFAULT 0,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_date TEXT NOT NULL
                )
        ''')

        # Create reading_list_items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_list_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    added_date TEXT NOT NULL,
                    added_by TEXT NOT NULL,
                    notes TEXT,
                    order_index INTEGER DEFAULT 0
                )
        ''')

        # Create reading_lists table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_lists (
                    list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    creator_id TEXT NOT NULL,
                    created_date TEXT NOT NULL,
                    is_public BOOLEAN DEFAULT FALSE,
                    is_collaborative BOOLEAN DEFAULT FALSE,
                    category TEXT,
                    target_reading_level TEXT
                )
        ''')

        # Create resource_bookings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS resource_bookings (
                            id TEXT PRIMARY KEY,
                            resource_id TEXT NOT NULL,
                            event_id TEXT,
                            start_time TEXT NOT NULL,
                            end_time TEXT NOT NULL,
                            status TEXT DEFAULT 'confirmed',
                            notes TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="library"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="library", error=str(e)))
        if 'conn' in locals():
            conn.close()
