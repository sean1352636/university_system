"""Cinema database initialization."""

import logging
import random
from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)


def init_cinema_db():
    """Initialize cinema database tables with comprehensive schema"""
    try:
        with transaction() as conn:
            # Movies table with extended fields
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_movies (
                    movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    genre TEXT,
                    rating TEXT,
                    duration_minutes INTEGER,
                    description TEXT,
                    director TEXT,
                    cast TEXT,
                    release_date DATE,
                    status TEXT DEFAULT 'now_showing',
                    poster_url TEXT,
                    trailer_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Screenings/showtimes table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_screenings (
                    screening_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_id INTEGER NOT NULL,
                    movie_title TEXT,
                    screen_number INTEGER,
                    screening_date DATE NOT NULL,
                    screening_time TEXT NOT NULL,
                    total_seats INTEGER DEFAULT 100,
                    available_seats INTEGER DEFAULT 100,
                    ticket_price REAL DEFAULT 12.00,
                    status TEXT DEFAULT 'available',
                    screen_type TEXT DEFAULT 'standard',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (movie_id) REFERENCES cinema_movies(movie_id)
                )
            ''')

            # Bookings table with extended fields
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_ref TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    user_email TEXT,
                    screening_id INTEGER NOT NULL,
                    movie_title TEXT,
                    screening_date DATE,
                    screening_time TEXT,
                    num_tickets INTEGER NOT NULL,
                    ticket_type TEXT,
                    seat_numbers TEXT,
                    ticket_total REAL NOT NULL,
                    snacks_total REAL DEFAULT 0.00,
                    member_discount REAL DEFAULT 0.00,
                    total_amount REAL NOT NULL,
                    payment_method TEXT,
                    points_earned INTEGER DEFAULT 0,
                    points_redeemed INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'confirmed',
                    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (screening_id) REFERENCES cinema_screenings(screening_id)
                )
            ''')

            # Snacks orders table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_snacks_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER,
                    booking_ref TEXT,
                    user_id TEXT NOT NULL,
                    snack_item TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    is_combo BOOLEAN DEFAULT 0,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES cinema_bookings(booking_id)
                )
            ''')

            # Membership table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_memberships (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    user_name TEXT,
                    user_email TEXT,
                    membership_type TEXT DEFAULT 'standard',
                    points_balance INTEGER DEFAULT 0,
                    total_points_earned INTEGER DEFAULT 0,
                    total_spent REAL DEFAULT 0.00,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    renewal_date DATE,
                    status TEXT DEFAULT 'active',
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Points transactions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_points_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    booking_ref TEXT,
                    transaction_type TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    description TEXT,
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES cinema_memberships(user_id)
                )
            ''')

            # Member-exclusive screenings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_exclusive_screenings (
                    exclusive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id INTEGER NOT NULL,
                    movie_title TEXT,
                    screening_date DATE,
                    screening_time TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (screening_id) REFERENCES cinema_screenings(screening_id)
                )
            ''')

            # Seat map table for visual seat selection
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cinema_seats (
                    seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id INTEGER NOT NULL,
                    row_letter TEXT NOT NULL,
                    seat_number INTEGER NOT NULL,
                    seat_type TEXT DEFAULT 'standard',
                    status TEXT DEFAULT 'available',
                    booking_ref TEXT,
                    FOREIGN KEY (screening_id) REFERENCES cinema_screenings(screening_id),
                    UNIQUE(screening_id, row_letter, seat_number)
                )
            ''')

            # Create sample movies if none exist
            cursor = conn.execute('SELECT COUNT(*) FROM cinema_movies')
            if cursor.fetchone()[0] == 0:
                sample_movies = [
                    ('The Academic Adventure', 'Drama', 'PG', 120,
                     'A thrilling journey through university life, exploring the challenges and triumphs of higher education.',
                     'Sarah Johnson', 'Emma Stone, Tom Holland, Viola Davis',
                     '2026-01-01', 'now_showing'),
                    ('Study Break: The Movie', 'Comedy', 'PG-13', 95,
                     'When finals week goes hilariously wrong, a group of students must find creative ways to survive.',
                     'Michael Chen', 'Awkwafina, John Cho, Kate McKinnon',
                     '2026-01-15', 'now_showing'),
                    ('Research Quest', 'Adventure', 'PG', 140,
                     'An epic tale of groundbreaking research that could change the world forever.',
                     'David Martinez', 'Chris Hemsworth, Lupita Nyongo, Mark Ruffalo',
                     '2025-12-20', 'now_showing'),
                    ('Campus Chronicles', 'Romance', 'PG-13', 110,
                     'Love blooms in the lecture halls as two students navigate academics and matters of the heart.',
                     'Jessica Williams', 'Zendaya, Timothee Chalamet, Laura Dern',
                     '2026-02-01', 'coming_soon'),
                    ('The Final Exam', 'Thriller', 'R', 105,
                     'A psychological thriller about a student who discovers a dark secret about their university.',
                     'Jordan Lee', 'Oscar Isaac, Tilda Swinton, John Boyega',
                     '2026-02-15', 'coming_soon'),
                    ('Graduation Day', 'Drama', 'PG-13', 125,
                     'The emotional journey of students facing their final days at university.',
                     'Amanda Rodriguez', 'Saoirse Ronan, Dev Patel, Frances McDormand',
                     '2026-03-01', 'coming_soon'),
                ]
                conn.executemany('''
                    INSERT INTO cinema_movies
                    (title, genre, rating, duration_minutes, description, director, cast, release_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sample_movies)

                # Create sample screenings for now_showing movies
                cursor = conn.execute('SELECT movie_id, title FROM cinema_movies WHERE status = "now_showing"')
                movies = cursor.fetchall()

                today = datetime.now().date()
                times = ['14:00', '17:00', '20:00', '22:30']
                screen_types = ['standard', 'standard', 'standard', 'premium']

                for movie_id, title in movies:
                    for day_offset in range(7):  # Next 7 days
                        screening_date = today + timedelta(days=day_offset)
                        for idx, time in enumerate(times):
                            screen_num = random.randint(1, 5)
                            conn.execute('''
                                INSERT INTO cinema_screenings
                                (movie_id, movie_title, screen_number, screening_date, screening_time,
                                 total_seats, available_seats, screen_type)
                                VALUES (?, ?, ?, ?, ?, 100, 100, ?)
                            ''', (movie_id, title, screen_num, str(screening_date), time, screen_types[idx]))

        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
        return False
