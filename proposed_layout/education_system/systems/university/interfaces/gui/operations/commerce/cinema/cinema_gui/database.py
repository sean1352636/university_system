"""
Cinema Booking System - Database initialization and utilities
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import os
import random
import string
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.sql_safety import validate_table_name, validate_identifier  # nosec B608

# Database setup - use centralized university system database
try:
    from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
    DB_FILE = str(DEFAULT_DB_PATH)
except ImportError:
    # Fallback if running standalone
    DB_FILE = os.path.join(os.path.dirname(__file__), "../../../../../data/db_files/student_records.db")

# Logs directory for audit
LOGS_DIR = os.path.join(os.path.dirname(__file__), "../../../../../logs")

def init_database():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        _init_database_tables(conn, cursor)
    finally:
        cursor.close()
        conn.close()


def _init_database_tables(conn, cursor):
    """Create all database tables and seed data (called by init_database)."""

    # Movies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            duration INTEGER NOT NULL,
            genre TEXT,
            rating TEXT,
            description TEXT,
            release_date TEXT,
            director TEXT,
            poster_url TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Screenings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screenings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            screen_number INTEGER NOT NULL,
            show_time TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')

    # Seats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screening_id INTEGER NOT NULL,
            row TEXT NOT NULL,
            seat_number INTEGER NOT NULL,
            seat_type TEXT DEFAULT 'standard',
            status TEXT DEFAULT 'available',
            FOREIGN KEY (screening_id) REFERENCES screenings(id),
            UNIQUE(screening_id, row, seat_number)
        )
    ''')

    # Bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_ref TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            screening_id INTEGER NOT NULL,
            ticket_types TEXT,
            subtotal REAL NOT NULL,
            discount_amount REAL DEFAULT 0,
            promo_code TEXT,
            snacks_total REAL DEFAULT 0,
            snacks_items TEXT,
            total_amount REAL NOT NULL,
            payment_status TEXT DEFAULT 'pending',
            payment_method TEXT,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            notes TEXT,
            FOREIGN KEY (screening_id) REFERENCES screenings(id)
        )
    ''')

    # Booked seats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS booked_seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            seat_id INTEGER NOT NULL,
            ticket_type TEXT DEFAULT 'Adult',
            FOREIGN KEY (booking_id) REFERENCES bookings(id),
            FOREIGN KEY (seat_id) REFERENCES seats(id)
        )
    ''')

    # Promo codes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT NOT NULL,
            discount_value REAL NOT NULL,
            min_purchase REAL DEFAULT 0,
            max_uses INTEGER DEFAULT NULL,
            times_used INTEGER DEFAULT 0,
            valid_from TEXT,
            valid_until TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Members/Customers table for loyalty program
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            points INTEGER DEFAULT 0,
            tier TEXT DEFAULT 'Bronze',
            total_spent REAL DEFAULT 0,
            bookings_count INTEGER DEFAULT 0,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP,
            birthday TEXT,
            preferences TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')

    # Movie reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            member_id INTEGER,
            customer_name TEXT,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            helpful_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    ''')

    # Waiting list table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screening_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT,
            seats_wanted INTEGER DEFAULT 1,
            notified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'waiting',
            FOREIGN KEY (screening_id) REFERENCES screenings(id)
        )
    ''')

    # Gift cards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            initial_value REAL NOT NULL,
            current_balance REAL NOT NULL,
            purchaser_name TEXT,
            purchaser_email TEXT,
            recipient_name TEXT,
            recipient_email TEXT,
            message TEXT,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
            expiry_date TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')

    # Favorites/Watchlist table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER,
            customer_email TEXT,
            movie_id INTEGER NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notify_screenings INTEGER DEFAULT 1,
            FOREIGN KEY (member_id) REFERENCES members(id),
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            UNIQUE(customer_email, movie_id)
        )
    ''')

    # Movie Series/Franchise table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movie_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Movie to Series linking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movie_series_link (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            series_id INTEGER NOT NULL,
            sequence_number INTEGER DEFAULT 1,
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            FOREIGN KEY (series_id) REFERENCES movie_series(id),
            UNIQUE(movie_id, series_id)
        )
    ''')

    # Coming Soon movies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coming_soon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            genre TEXT,
            rating TEXT,
            director TEXT,
            release_date TEXT NOT NULL,
            trailer_url TEXT,
            poster_url TEXT,
            notify_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'upcoming',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Season Passes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS season_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_code TEXT UNIQUE NOT NULL,
            member_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            pass_type TEXT NOT NULL,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            movies_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    ''')

    # Seat Holds table (temporary during checkout)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seat_holds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            held_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (seat_id) REFERENCES seats(id)
        )
    ''')

    # Cinema Referrals table (separate from health services referrals)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cinema_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referral_code TEXT UNIQUE NOT NULL,
            referrer_email TEXT NOT NULL,
            referee_email TEXT,
            status TEXT DEFAULT 'pending',
            reward_given INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Staff Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            role TEXT NOT NULL,
            hire_date TEXT,
            last_login TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Add salt column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE staff ADD COLUMN salt TEXT")
        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
            raise

    # Audit Log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Private Rentals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS private_rentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT,
            screen_number INTEGER NOT NULL,
            rental_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            guest_count INTEGER DEFAULT 0,
            movie_id INTEGER,
            custom_content TEXT,
            catering_notes TEXT,
            base_price REAL NOT NULL,
            extras_price REAL DEFAULT 0,
            total_price REAL NOT NULL,
            deposit_paid REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')

    # Special Events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS special_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            screen_number INTEGER,
            movie_id INTEGER,
            ticket_price REAL,
            max_capacity INTEGER,
            tickets_sold INTEGER DEFAULT 0,
            special_guests TEXT,
            status TEXT DEFAULT 'upcoming',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')

    # Themed Nights table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS themed_nights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            theme_type TEXT NOT NULL,
            description TEXT,
            day_of_week INTEGER,
            discount_percent REAL DEFAULT 0,
            genre_filter TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Polls/Voting table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            poll_type TEXT DEFAULT 'movie_choice',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            max_votes_per_user INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Poll Options table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS poll_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL,
            option_text TEXT NOT NULL,
            movie_id INTEGER,
            votes INTEGER DEFAULT 0,
            FOREIGN KEY (poll_id) REFERENCES polls(id),
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')

    # Poll Votes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS poll_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL,
            option_id INTEGER NOT NULL,
            member_id INTEGER,
            customer_email TEXT,
            voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (poll_id) REFERENCES polls(id),
            FOREIGN KEY (option_id) REFERENCES poll_options(id),
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    ''')

    # Inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            current_stock INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 10,
            unit_cost REAL,
            supplier TEXT,
            last_restock TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Unified orders table (snack orders have source_type='snack')
    # NOTE: snack_orders migrated to unified 'orders' table with source_type = 'snack'
    # Column mappings: id -> auto, order_ref -> order_number, items -> notes, order_status stays, payment_status stays
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'snack',
            source_order_id INTEGER,
            student_id TEXT,
            customer_name TEXT,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_amount REAL NOT NULL,
            payment_method TEXT,
            age_verified INTEGER DEFAULT 0,
            order_status TEXT DEFAULT 'pending',
            notes TEXT,
            order_number TEXT,
            payment_status TEXT DEFAULT 'pending'
        )
    ''')

    # Corporate Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corporate_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            contact_phone TEXT,
            billing_address TEXT,
            tax_id TEXT,
            credit_limit REAL DEFAULT 1000,
            current_balance REAL DEFAULT 0,
            payment_terms INTEGER DEFAULT 30,
            discount_percent REAL DEFAULT 10,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Corporate Invoices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corporate_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            corporate_id INTEGER NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            items TEXT NOT NULL,
            subtotal REAL NOT NULL,
            tax_amount REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            amount_paid REAL DEFAULT 0,
            status TEXT DEFAULT 'unpaid',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (corporate_id) REFERENCES corporate_accounts(id)
        )
    ''')

    # Screen Maintenance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screen_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screen_number INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT,
            technician TEXT,
            cost REAL,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Customer Profiles table (extended member info)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER UNIQUE NOT NULL,
            avatar_url TEXT,
            favorite_genre TEXT,
            favorite_seats TEXT,
            preferred_snacks TEXT,
            notifications_email INTEGER DEFAULT 1,
            notifications_sms INTEGER DEFAULT 0,
            language_preference TEXT DEFAULT 'en',
            accessibility_needs TEXT,
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    ''')

    # Movie Translations table (multilingual support)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movie_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            language_code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            UNIQUE(movie_id, language_code)
        )
    ''')

    # ==================== OPERATIONS MODULE TABLES ====================

    # Staff Shifts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            shift_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            position TEXT DEFAULT 'general',
            screen_assigned INTEGER,
            break_start TEXT,
            break_end TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    ''')

    # Staff Availability table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            available_from TEXT,
            available_until TEXT,
            is_available INTEGER DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id),
            UNIQUE(staff_id, day_of_week)
        )
    ''')

    # Shift Swap Requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shift_swap_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            original_shift_id INTEGER NOT NULL,
            requested_with_id INTEGER,
            target_shift_id INTEGER,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (requester_id) REFERENCES staff(id),
            FOREIGN KEY (original_shift_id) REFERENCES shifts(id),
            FOREIGN KEY (requested_with_id) REFERENCES staff(id),
            FOREIGN KEY (target_shift_id) REFERENCES shifts(id),
            FOREIGN KEY (reviewed_by) REFERENCES staff(id)
        )
    ''')

    # Equipment table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            screen_number INTEGER,
            brand TEXT,
            model TEXT,
            serial_number TEXT,
            install_date TEXT,
            warranty_until TEXT,
            last_service_date TEXT,
            next_service_due TEXT,
            hours_used INTEGER DEFAULT 0,
            max_hours_before_service INTEGER DEFAULT 2000,
            status TEXT DEFAULT 'operational',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Equipment Maintenance Log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment_maintenance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT,
            performed_by TEXT,
            cost REAL DEFAULT 0,
            parts_replaced TEXT,
            hours_at_service INTEGER,
            next_service_hours INTEGER,
            service_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES equipment(id)
        )
    ''')

    # Lost and Found table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lost_found (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_description TEXT NOT NULL,
            category TEXT DEFAULT 'other',
            location_found TEXT,
            screen_number INTEGER,
            found_date TEXT NOT NULL,
            found_time TEXT,
            found_by_staff_id INTEGER,
            storage_location TEXT,
            claimed INTEGER DEFAULT 0,
            claimed_by_name TEXT,
            claimed_by_email TEXT,
            claimed_by_phone TEXT,
            claim_date TEXT,
            verified_by_staff_id INTEGER,
            identification_method TEXT,
            status TEXT DEFAULT 'unclaimed',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (found_by_staff_id) REFERENCES staff(id),
            FOREIGN KEY (verified_by_staff_id) REFERENCES staff(id)
        )
    ''')

    # Incidents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_type TEXT NOT NULL,
            severity TEXT DEFAULT 'low',
            description TEXT NOT NULL,
            location TEXT,
            screen_number INTEGER,
            incident_datetime TEXT NOT NULL,
            reported_by_staff_id INTEGER,
            witnesses TEXT,
            immediate_action_taken TEXT,
            resolution TEXT,
            resolved_by_staff_id INTEGER,
            resolved_datetime TEXT,
            customer_involved INTEGER DEFAULT 0,
            customer_name TEXT,
            customer_contact TEXT,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_notes TEXT,
            follow_up_completed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reported_by_staff_id) REFERENCES staff(id),
            FOREIGN KEY (resolved_by_staff_id) REFERENCES staff(id)
        )
    ''')

    # Screen layouts table (per-screen configuration)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screen_layouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screen_number INTEGER UNIQUE NOT NULL,
            name TEXT,
            rows INTEGER NOT NULL DEFAULT 8,
            seats_per_row INTEGER NOT NULL DEFAULT 12,
            vip_rows TEXT,
            wheelchair_positions TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Cinema settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cinema_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add new columns if they don't exist (for upgrades)
    new_columns = [
        ("movies", "description", "TEXT"),
        ("movies", "release_date", "TEXT"),
        ("movies", "director", "TEXT"),
        ("movies", "poster_url", "TEXT"),
        ("movies", "status", "TEXT DEFAULT 'active'"),
        ("movies", "trailer_url", "TEXT"),
        ("movies", "age_rating", "TEXT"),
        ("movies", "language", "TEXT DEFAULT 'en'"),
        ("bookings", "notes", "TEXT"),
        ("bookings", "ticket_types", "TEXT"),
        ("bookings", "subtotal", "REAL"),
        ("bookings", "discount_amount", "REAL DEFAULT 0"),
        ("bookings", "promo_code", "TEXT"),
        ("bookings", "snacks_total", "REAL DEFAULT 0"),
        ("bookings", "snacks_items", "TEXT"),
        ("bookings", "group_discount", "REAL DEFAULT 0"),
        ("bookings", "early_bird_discount", "REAL DEFAULT 0"),
        ("bookings", "dynamic_pricing_applied", "REAL DEFAULT 0"),
        ("bookings", "season_pass_id", "INTEGER"),
        ("bookings", "corporate_id", "INTEGER"),
        ("bookings", "qr_code", "TEXT"),
        ("bookings", "snack_pickup_time", "TEXT"),
        ("screenings", "status", "TEXT DEFAULT 'active'"),
        ("screenings", "is_3d", "INTEGER DEFAULT 0"),
        ("screenings", "is_imax", "INTEGER DEFAULT 0"),
        ("screenings", "social_distancing", "INTEGER DEFAULT 0"),
        ("seats", "seat_type", "TEXT DEFAULT 'standard'"),
        ("seats", "is_wheelchair", "INTEGER DEFAULT 0"),
        ("seats", "is_companion", "INTEGER DEFAULT 0"),
        ("seats", "is_couple", "INTEGER DEFAULT 0"),
        ("booked_seats", "ticket_type", "TEXT DEFAULT 'Adult'"),
        ("members", "referral_code", "TEXT"),
        ("members", "credit_balance", "REAL DEFAULT 0"),
        ("members", "favorite_seats", "TEXT"),
        ("members", "avatar", "TEXT"),
    ]

    for table, column, col_type in new_columns:
        try:
            safe_table = validate_table_name(table)
            safe_column = validate_identifier(column, "column")
            cursor.execute("ALTER TABLE [" + safe_table + "] ADD COLUMN [" + safe_column + "] " + col_type)
        except Exception:
            pass

    # Insert sample promo codes if empty
    cursor.execute("SELECT COUNT(*) FROM promo_codes")
    if cursor.fetchone()[0] == 0:
        sample_promos = [
            ("WELCOME10", "percentage", 10, 0, 100, "2024-01-01", "2025-12-31"),
            ("SAVE5", "fixed", 5, 20, 50, "2024-01-01", "2025-12-31"),
            ("FAMILY20", "percentage", 20, 50, 30, "2024-01-01", "2025-12-31"),
        ]
        cursor.executemany('''
            INSERT INTO promo_codes (code, discount_type, discount_value, min_purchase, max_uses, valid_from, valid_until)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_promos)

    # Insert sample data if empty
    cursor.execute("SELECT COUNT(*) FROM movies")
    if cursor.fetchone()[0] == 0:
        sample_movies = [
            ("The Dark Knight", 152, "Action", "PG-13", "Batman faces the Joker", "2008-07-18", "Christopher Nolan"),
            ("Inception", 148, "Sci-Fi", "PG-13", "Dreams within dreams", "2010-07-16", "Christopher Nolan"),
            ("The Shawshank Redemption", 142, "Drama", "R", "Hope through prison walls", "1994-09-23", "Frank Darabont"),
            ("Pulp Fiction", 154, "Crime", "R", "Interconnected crime stories", "1994-10-14", "Quentin Tarantino"),
            ("Interstellar", 169, "Sci-Fi", "PG-13", "Journey through space and time", "2014-11-07", "Christopher Nolan"),
        ]
        cursor.executemany(
            "INSERT INTO movies (title, duration, genre, rating, description, release_date, director) VALUES (?, ?, ?, ?, ?, ?, ?)",
            sample_movies
        )

        # Create screenings for next 7 days
        times = ["10:00", "13:00", "16:00", "19:00", "22:00"]
        for movie_id in range(1, 6):
            for day_offset in range(7):
                date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                for time in times[:3]:
                    screen = random.randint(1, 5)
                    price = random.choice([12.99, 14.99, 16.99])
                    cursor.execute(
                        "INSERT INTO screenings (movie_id, screen_number, show_time, price) VALUES (?, ?, ?, ?)",
                        (movie_id, screen, f"{date} {time}", price)
                    )

        # Create seats for each screening
        cursor.execute("SELECT id FROM screenings")
        screening_ids = cursor.fetchall()
        rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        for (screening_id,) in screening_ids:
            for row in rows:
                for seat_num in range(1, 13):
                    # VIP seats in rows A-B
                    seat_type = 'vip' if row in ['A', 'B'] else 'standard'
                    cursor.execute(
                        "INSERT INTO seats (screening_id, row, seat_number, seat_type, status) VALUES (?, ?, ?, ?, 'available')",
                        (screening_id, row, seat_num, seat_type)
                    )

    conn.commit()

def generate_booking_ref():
    """Generate a unique booking reference."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
