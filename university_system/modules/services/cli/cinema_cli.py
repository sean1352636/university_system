"""
Cinema CLI for University Management System

Provides comprehensive cinema services including movie listings, ticket bookings,
seat selection, concessions, membership program, and admin panel with full error handling.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import random
import string

from university_system.core.sql_safety import validate_identifier

# Import centralized database and authentication
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth

# Ticket pricing
TICKET_TYPES = {
    "Adult": 12.00,
    "Child": 7.00,
    "Senior": 9.00,
    "Student": 8.00,
}

# Snacks menu with full selection
SNACKS_MENU = {
    "Popcorn (Small)": 4.99,
    "Popcorn (Medium)": 6.49,
    "Popcorn (Large)": 7.99,
    "Soda (Small)": 2.99,
    "Soda (Medium)": 3.99,
    "Soda (Large)": 4.99,
    "Candy (M&Ms)": 3.49,
    "Candy (Skittles)": 3.49,
    "Candy (Maltesers)": 3.49,
    "Nachos": 5.99,
    "Hot Dog": 4.99,
    "Pretzel": 3.99,
    "Ice Cream": 3.49,
}

# Combo deals
COMBO_DEALS = {
    "Small Combo": {"items": ["Popcorn (Small)", "Soda (Small)"], "price": 9.99, "original": 7.98},
    "Medium Combo": {"items": ["Popcorn (Medium)", "Soda (Medium)"], "price": 12.99, "original": 10.48},
    "Large Combo": {"items": ["Popcorn (Large)", "Soda (Large)"], "price": 14.99, "original": 12.98},
    "Family Combo": {"items": ["Popcorn (Large)", "Popcorn (Large)", "Soda (Large)", "Soda (Large)"], "price": 24.99, "original": 25.96},
    "Snack Pack": {"items": ["Nachos", "Soda (Medium)", "Candy (M&Ms)"], "price": 11.99, "original": 12.47},
}

# Membership pricing
MEMBERSHIP_PRICE = 5.99
POINTS_PER_POUND = 1  # Earn 1 point per £1 spent
MEMBER_DISCOUNT = 0.10  # 10% discount on tickets

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGING = True
except ImportError:
    ACTIVITY_LOGGING = False

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


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text: str):
    """Print a formatted subheader"""
    print("\n" + "-" * 70)
    print(f"  {text}")
    print("-" * 70)


def get_current_user():
    """Get the currently logged-in user"""
    try:
        auth = get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    return None


def is_staff_or_admin(user) -> bool:
    """Check if user has staff or admin privileges"""
    if not user:
        return False
    role = user.get('role', '').lower()
    return role in ['admin', 'staff', 'instructor']


def get_user_membership(user_id: str) -> Optional[Dict]:
    """Get user's membership details"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT membership_id, membership_type, points_balance, total_points_earned,
                       total_spent, join_date, renewal_date, status
                FROM cinema_memberships
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            row = cursor.fetchone()

            if row:
                return {
                    'membership_id': row[0],
                    'membership_type': row[1],
                    'points_balance': row[2],
                    'total_points_earned': row[3],
                    'total_spent': row[4],
                    'join_date': row[5],
                    'renewal_date': row[6],
                    'status': row[7]
                }
    except Exception as e:
        logger.error(f"Error fetching membership: {e}")
    return None


def calculate_points_earned(amount: float) -> int:
    """Calculate points earned from purchase amount"""
    return int(amount * POINTS_PER_POUND)


def award_points(user_id: str, points: int, booking_ref: str, description: str):
    """Award points to user's membership"""
    try:
        with transaction() as conn:
            # Update points balance
            conn.execute('''
                UPDATE cinema_memberships
                SET points_balance = points_balance + ?,
                    total_points_earned = total_points_earned + ?,
                    last_activity = ?
                WHERE user_id = ?
            ''', (points, points, datetime.now().isoformat(), user_id))

            # Record transaction
            conn.execute('''
                INSERT INTO cinema_points_transactions
                (user_id, booking_ref, transaction_type, points, description)
                VALUES (?, ?, 'earned', ?, ?)
            ''', (user_id, booking_ref, points, description))

        logger.info(f"Awarded {points} points to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error awarding points: {e}")
        return False


def redeem_points(user_id: str, points: int, description: str) -> bool:
    """Redeem points from user's membership"""
    try:
        membership = get_user_membership(user_id)
        if not membership or membership['points_balance'] < points:
            return False

        with transaction() as conn:
            # Deduct points
            conn.execute('''
                UPDATE cinema_memberships
                SET points_balance = points_balance - ?,
                    last_activity = ?
                WHERE user_id = ?
            ''', (points, datetime.now().isoformat(), user_id))

            # Record transaction
            conn.execute('''
                INSERT INTO cinema_points_transactions
                (user_id, transaction_type, points, description)
                VALUES (?, 'redeemed', ?, ?)
            ''', (user_id, -points, description))

        logger.info(f"Redeemed {points} points for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error redeeming points: {e}")
        return False


def send_booking_confirmation_email(user_email: str, booking_details: Dict):
    """Send booking confirmation email"""
    if not EMAIL_AVAILABLE or not user_email:
        return False

    try:
        subject = f"Cinema Booking Confirmation - {booking_details['booking_ref']}"

        body = f"""
Dear {booking_details['user_name']},

Your cinema booking has been confirmed!

Booking Reference: {booking_details['booking_ref']}
Movie: {booking_details['movie_title']}
Date: {booking_details['screening_date']}
Time: {booking_details['screening_time']}
Tickets: {booking_details['num_tickets']}x {booking_details['ticket_type']}

Total Amount: £{booking_details['total_amount']:.2f}

Please arrive 15 minutes before the screening starts.
Show this confirmation at the entrance.

Enjoy the show!

University Cinema
"""

        send_email(
            to_email=user_email,
            subject=subject,
            body=body,
            template_name='cinema_booking_confirmation'
        )
        return True
    except Exception as e:
        logger.error(f"Error sending confirmation email: {e}")
        return False


# ============================================================================
# MOVIE BROWSING
# ============================================================================

def view_movies():
    """View current and upcoming movies with detailed information"""
    try:
        print_subheader("MOVIE LISTINGS")

        # Show filter options
        print("\nFilter by:")
        print("1. All Movies")
        print("2. Now Showing")
        print("3. Coming Soon")
        print("4. Filter by Genre")
        print("5. Filter by Rating")

        filter_choice = input("\nEnter choice (default: 1): ").strip() or "1"

        query = '''
            SELECT movie_id, title, genre, rating, duration_minutes, description,
                   director, cast, release_date, status
            FROM cinema_movies
            WHERE 1=1
        '''
        params = []

        if filter_choice == "2":
            query += " AND status = 'now_showing'"
        elif filter_choice == "3":
            query += " AND status = 'coming_soon'"
        elif filter_choice == "4":
            genre = input("Enter genre (Drama/Comedy/Adventure/Romance/Thriller): ").strip()
            if genre:
                query += " AND genre = ?"
                params.append(genre)
        elif filter_choice == "5":
            rating = input("Enter rating (PG/PG-13/R): ").strip()
            if rating:
                query += " AND rating = ?"
                params.append(rating)

        query += " ORDER BY status DESC, release_date"

        with get_connection() as conn:
            cursor = conn.execute(query, params)
            movies = cursor.fetchall()

            if not movies:
                print("\n❌ No movies found matching your criteria")
            else:
                print(f"\n🎬 FOUND {len(movies)} MOVIE(S):")
                print("=" * 70)
                current_status = None

                for movie in movies:
                    try:
                        (movie_id, title, genre, rating, duration, desc,
                         director, cast, release_date, status) = movie

                        if status != current_status:
                            status_label = "📺 NOW SHOWING" if status == 'now_showing' else "📅 COMING SOON"
                            print(f"\n{status_label}:")
                            print("-" * 70)
                            current_status = status

                        print(f"\n[ID: {movie_id}] {title} ({rating})")
                        print(f"Genre: {genre} | Duration: {duration} min | Release: {release_date}")

                        if director:
                            print(f"Director: {director}")
                        if cast:
                            print(f"Cast: {cast}")
                        if desc:
                            print(f"Synopsis: {desc}")

                    except Exception as e:
                        logger.error(f"Error displaying movie: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing movies: {e}", exc_info=True)
        print(f"❌ Error viewing movies: {e}")

    input("\n📌 Press Enter to continue...")


def search_movies():
    """Search movies by title, genre, or rating"""
    try:
        print_subheader("SEARCH MOVIES")

        print("\nSearch by:")
        print("1. Title")
        print("2. Genre")
        print("3. Rating")
        print("4. Director")
        print("5. Actor/Actress")

        search_type = input("\nEnter choice: ").strip()

        if search_type == "1":
            search_term = input("Enter movie title (partial match): ").strip()
            if not search_term:
                print("❌ Search term cannot be empty")
                input("\n📌 Press Enter to continue...")
                return

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT movie_id, title, genre, rating, duration_minutes, status, release_date
                    FROM cinema_movies
                    WHERE title LIKE ?
                    ORDER BY release_date DESC
                ''', (f'%{search_term}%',))
                movies = cursor.fetchall()

        elif search_type == "2":
            genre = input("Enter genre: ").strip()
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT movie_id, title, genre, rating, duration_minutes, status, release_date
                    FROM cinema_movies
                    WHERE genre = ?
                    ORDER BY release_date DESC
                ''', (genre,))
                movies = cursor.fetchall()

        elif search_type == "3":
            rating = input("Enter rating (PG/PG-13/R): ").strip()
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT movie_id, title, genre, rating, duration_minutes, status, release_date
                    FROM cinema_movies
                    WHERE rating = ?
                    ORDER BY release_date DESC
                ''', (rating,))
                movies = cursor.fetchall()

        elif search_type == "4":
            director = input("Enter director name: ").strip()
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT movie_id, title, genre, rating, duration_minutes, status, release_date
                    FROM cinema_movies
                    WHERE director LIKE ?
                    ORDER BY release_date DESC
                ''', (f'%{director}%',))
                movies = cursor.fetchall()

        elif search_type == "5":
            actor = input("Enter actor/actress name: ").strip()
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT movie_id, title, genre, rating, duration_minutes, status, release_date
                    FROM cinema_movies
                    WHERE cast LIKE ?
                    ORDER BY release_date DESC
                ''', (f'%{actor}%',))
                movies = cursor.fetchall()
        else:
            print("❌ Invalid search type")
            input("\n📌 Press Enter to continue...")
            return

        if not movies:
            print("\n❌ No movies found matching your search")
        else:
            print(f"\n🔍 SEARCH RESULTS ({len(movies)} found):")
            print("=" * 70)
            for movie in movies:
                movie_id, title, genre, rating, duration, status, release_date = movie
                status_icon = "📺" if status == 'now_showing' else "📅"
                print(f"{status_icon} [ID: {movie_id}] {title}")
                print(f"   {genre} | {rating} | {duration} min | Release: {release_date}")
                print()

    except Exception as e:
        logger.error(f"Error searching movies: {e}", exc_info=True)
        print(f"❌ Error searching movies: {e}")

    input("\n📌 Press Enter to continue...")


def view_movie_details():
    """View detailed information about a specific movie"""
    try:
        movie_id = input("\nEnter movie ID: ").strip()

        if not movie_id.isdigit():
            print("❌ Invalid movie ID")
            input("\n📌 Press Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT title, genre, rating, duration_minutes, description,
                       director, cast, release_date, status
                FROM cinema_movies
                WHERE movie_id = ?
            ''', (movie_id,))
            movie = cursor.fetchone()

            if not movie:
                print("❌ Movie not found")
            else:
                title, genre, rating, duration, desc, director, cast, release_date, status = movie

                print_subheader(f"MOVIE DETAILS: {title}")
                print(f"\n🎬 Title: {title}")
                print(f"⭐ Rating: {rating}")
                print(f"🎭 Genre: {genre}")
                print(f"⏱️  Duration: {duration} minutes")
                print(f"🎥 Director: {director}")
                print(f"👥 Cast: {cast}")
                print(f"📅 Release Date: {release_date}")
                print(f"📊 Status: {status.replace('_', ' ').title()}")
                print(f"\n📖 Synopsis:\n{desc}")

                # Show available screenings
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM cinema_screenings
                    WHERE movie_id = ? AND status = 'available'
                          AND screening_date >= date('now')
                ''', (movie_id,))
                screening_count = cursor.fetchone()[0]

                if screening_count > 0:
                    print(f"\n🎟️  Available Screenings: {screening_count}")
                    view_option = input("\nView screenings for this movie? (yes/no): ").strip().lower()
                    if view_option == 'yes':
                        view_screenings_for_movie(movie_id, title)
                        return

    except Exception as e:
        logger.error(f"Error viewing movie details: {e}", exc_info=True)
        print(f"❌ Error viewing movie details: {e}")

    input("\n📌 Press Enter to continue...")


# ============================================================================
# SCREENINGS
# ============================================================================

def view_screenings():
    """View available screenings"""
    try:
        view_movies()

        movie_id = input("\n🎬 Enter movie ID to view screenings (0 to cancel): ").strip()
        if movie_id == "0":
            return

        if not movie_id.isdigit():
            print("❌ Invalid movie ID")
            input("\n📌 Press Enter to continue...")
            return

        with get_connection() as conn:
            # Get movie title
            movie_cursor = conn.execute('SELECT title FROM cinema_movies WHERE movie_id = ?', (movie_id,))
            movie_row = movie_cursor.fetchone()

            if not movie_row:
                print("❌ Movie not found")
                input("\n📌 Press Enter to continue...")
                return

            movie_title = movie_row[0]
            view_screenings_for_movie(movie_id, movie_title)

    except Exception as e:
        logger.error(f"Error viewing screenings: {e}", exc_info=True)
        print(f"❌ Error viewing screenings: {e}")

    input("\n📌 Press Enter to continue...")


def view_screenings_for_movie(movie_id: str, movie_title: str):
    """View screenings for a specific movie"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT screening_id, screening_date, screening_time, screen_number,
                       available_seats, total_seats, ticket_price, screen_type
                FROM cinema_screenings
                WHERE movie_id = ? AND status = 'available'
                      AND screening_date >= date('now')
                ORDER BY screening_date, screening_time
                LIMIT 50
            ''', (movie_id,))
            screenings = cursor.fetchall()

            if not screenings:
                print(f"\n❌ No screenings available for {movie_title}")
            else:
                print_subheader(f"SCREENINGS FOR: {movie_title}")
                print(f"\nShowing {len(screenings)} screening(s):")
                print("=" * 70)

                current_date = None
                for screening in screenings:
                    try:
                        scr_id, date, time, screen, avail, total, price, screen_type = screening

                        if date != current_date:
                            print(f"\n📅 {date}:")
                            current_date = date

                        availability = f"{avail}/{total}" if avail > 0 else "🔴 SOLD OUT"
                        screen_label = f"Screen {screen}"
                        if screen_type == 'premium':
                            screen_label += " (PREMIUM)"

                        occupancy_pct = ((total - avail) / total * 100) if total > 0 else 0

                        print(f"  🎟️  [ID: {scr_id}] {time} | {screen_label}")
                        print(f"      Seats: {availability} | Price: £{float(price):.2f} | Occupancy: {occupancy_pct:.0f}%")

                    except Exception as e:
                        logger.error(f"Error displaying screening: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing screenings for movie: {e}", exc_info=True)
        print(f"❌ Error viewing screenings: {e}")


# ============================================================================
# SEAT SELECTION
# ============================================================================

def initialize_seats_for_screening(screening_id: int, conn):
    """Initialize seat map for a screening if not exists"""
    try:
        # Check if seats already exist
        cursor = conn.execute('''
            SELECT COUNT(*) FROM cinema_seats WHERE screening_id = ?
        ''', (screening_id,))

        if cursor.fetchone()[0] > 0:
            return True  # Seats already initialized

        # Create seat map (10 rows x 10 seats = 100 seats)
        rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        seats_per_row = 10

        for row in rows:
            for seat_num in range(1, seats_per_row + 1):
                seat_type = 'premium' if row in ['E', 'F'] else 'standard'
                conn.execute('''
                    INSERT INTO cinema_seats (screening_id, row_letter, seat_number, seat_type, status)
                    VALUES (?, ?, ?, ?, 'available')
                ''', (screening_id, row, seat_num, seat_type))

        return True
    except Exception as e:
        logger.error(f"Error initializing seats: {e}")
        return False


def display_seat_map(screening_id: int) -> List[Dict]:
    """Display visual seat map and return seat data"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT row_letter, seat_number, status, seat_type
                FROM cinema_seats
                WHERE screening_id = ?
                ORDER BY row_letter, seat_number
            ''', (screening_id,))
            seats = cursor.fetchall()

            if not seats:
                return []

            print("\n🎬 SCREEN")
            print("=" * 42)
            print("\n   1  2  3  4  5  6  7  8  9  10")

            current_row = None
            seat_data = []

            for seat in seats:
                row, num, status, seat_type = seat
                seat_data.append({
                    'row': row,
                    'number': num,
                    'status': status,
                    'type': seat_type
                })

                if row != current_row:
                    if current_row is not None:
                        print()
                    current_row = row
                    print(f"{row} ", end='')

                # Display seat status
                if status == 'available':
                    if seat_type == 'premium':
                        print(" ♦️ ", end='')
                    else:
                        print(" ⬜", end='')
                else:
                    print(" ⬛", end='')

            print("\n\n⬜ Available  ⬛ Taken  ♦️  Premium")
            print("=" * 42)

            return seat_data

    except Exception as e:
        logger.error(f"Error displaying seat map: {e}")
        return []


def select_seats(screening_id: int, num_tickets: int) -> List[str]:
    """Interactive seat selection"""
    try:
        with transaction() as conn:
            # Initialize seats if needed
            initialize_seats_for_screening(screening_id, conn)

        selected_seats = []

        while len(selected_seats) < num_tickets:
            seats_data = display_seat_map(screening_id)

            if not seats_data:
                print("❌ Error loading seat map")
                return []

            remaining = num_tickets - len(selected_seats)
            print(f"\n🎟️  Select {remaining} more seat(s)")

            if selected_seats:
                print(f"Selected: {', '.join(selected_seats)}")

            row = input("\nEnter row (A-J) or 'auto' for automatic selection: ").strip().upper()

            if row == 'AUTO':
                # Auto-select best available seats
                auto_seats = auto_select_seats(screening_id, num_tickets - len(selected_seats))
                if auto_seats:
                    selected_seats.extend(auto_seats)
                    print(f"✅ Auto-selected: {', '.join(auto_seats)}")
                    break
                else:
                    print("❌ Could not find enough consecutive seats")
                    continue

            if row not in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                print("❌ Invalid row. Please enter A-J")
                continue

            seat_num = input("Enter seat number (1-10): ").strip()

            if not seat_num.isdigit() or int(seat_num) < 1 or int(seat_num) > 10:
                print("❌ Invalid seat number. Please enter 1-10")
                continue

            seat_id = f"{row}{seat_num}"

            # Check if seat is available
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT status FROM cinema_seats
                    WHERE screening_id = ? AND row_letter = ? AND seat_number = ?
                ''', (screening_id, row, int(seat_num)))
                result = cursor.fetchone()

                if not result:
                    print("❌ Seat not found")
                    continue

                if result[0] != 'available':
                    print("❌ Seat already taken")
                    continue

                if seat_id in selected_seats:
                    print("❌ Seat already selected")
                    continue

            selected_seats.append(seat_id)
            print(f"✅ Added seat {seat_id}")

        return selected_seats

    except Exception as e:
        logger.error(f"Error in seat selection: {e}")
        return []


def auto_select_seats(screening_id: int, num_seats: int) -> List[str]:
    """Automatically select best available consecutive seats"""
    try:
        with get_connection() as conn:
            # Try to find consecutive seats in middle rows first
            preferred_rows = ['E', 'F', 'D', 'G', 'C', 'H', 'B', 'I', 'A', 'J']

            for row in preferred_rows:
                cursor = conn.execute('''
                    SELECT seat_number FROM cinema_seats
                    WHERE screening_id = ? AND row_letter = ? AND status = 'available'
                    ORDER BY seat_number
                ''', (screening_id, row))
                available = [r[0] for r in cursor.fetchall()]

                # Find consecutive seats
                for i in range(len(available) - num_seats + 1):
                    consecutive = available[i:i+num_seats]
                    if len(consecutive) == num_seats and consecutive[-1] - consecutive[0] == num_seats - 1:
                        return [f"{row}{num}" for num in consecutive]

        # If no consecutive seats, just pick any available
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT row_letter, seat_number FROM cinema_seats
                WHERE screening_id = ? AND status = 'available'
                ORDER BY row_letter, seat_number
                LIMIT ?
            ''', (screening_id, num_seats))
            seats = cursor.fetchall()
            return [f"{row}{num}" for row, num in seats]

    except Exception as e:
        logger.error(f"Error auto-selecting seats: {e}")
        return []


def mark_seats_as_booked(screening_id: int, seats: List[str], booking_ref: str):
    """Mark selected seats as booked"""
    try:
        with transaction() as conn:
            for seat_id in seats:
                row = seat_id[0]
                num = int(seat_id[1:])
                conn.execute('''
                    UPDATE cinema_seats
                    SET status = 'booked', booking_ref = ?
                    WHERE screening_id = ? AND row_letter = ? AND seat_number = ?
                ''', (booking_ref, screening_id, row, num))
        return True
    except Exception as e:
        logger.error(f"Error marking seats as booked: {e}")
        return False


# ============================================================================
# SNACKS & COMBOS
# ============================================================================

def display_snacks_menu():
    """Display snacks menu with combo deals"""
    print_subheader("🍿 SNACKS & CONCESSIONS")

    print("\n🎁 COMBO DEALS (Best Value!):")
    print("-" * 70)
    for idx, (combo_name, combo_data) in enumerate(COMBO_DEALS.items(), 1):
        savings = combo_data['original'] - combo_data['price']
        print(f"{idx}. {combo_name} - £{combo_data['price']:.2f} (Save £{savings:.2f})")
        print(f"   Includes: {', '.join(combo_data['items'])}")

    print("\n🍿 INDIVIDUAL ITEMS:")
    print("-" * 70)
    start_idx = len(COMBO_DEALS) + 1
    for idx, (item, price) in enumerate(SNACKS_MENU.items(), start_idx):
        print(f"{idx}. {item} - £{price:.2f}")


def suggest_combo_for_party(num_tickets: int):
    """Suggest appropriate combo based on party size"""
    suggestions = []

    if num_tickets == 1:
        suggestions.append("Small Combo")
    elif num_tickets == 2:
        suggestions.append("Medium Combo")
    elif num_tickets >= 3:
        suggestions.append("Family Combo")
        if num_tickets >= 4:
            suggestions.append("Large Combo")

    if suggestions:
        print(f"\n💡 Recommended for {num_tickets} person(s): {', '.join(suggestions)}")


def add_snacks_to_order() -> Tuple[float, List[Dict]]:
    """Interactive snacks ordering with combo support"""
    try:
        snacks_total = 0.0
        snacks_list = []

        display_snacks_menu()

        total_items = len(COMBO_DEALS) + len(SNACKS_MENU)

        while True:
            choice = input(f"\n🍿 Select item (1-{total_items}, 0 to finish): ").strip()

            if choice == "0":
                break

            if not choice.isdigit():
                print("❌ Invalid selection")
                continue

            item_idx = int(choice)

            # Check if it's a combo
            if item_idx <= len(COMBO_DEALS):
                combo_name = list(COMBO_DEALS.keys())[item_idx - 1]
                combo_data = COMBO_DEALS[combo_name]

                qty_str = input(f"Quantity of {combo_name}: ").strip()

                try:
                    qty = int(qty_str)
                    if qty < 1 or qty > 5:
                        print("❌ Quantity must be between 1 and 5 for combos")
                        continue
                except ValueError:
                    print("❌ Invalid quantity")
                    continue

                subtotal = combo_data['price'] * qty
                snacks_list.append({
                    'name': combo_name,
                    'price': combo_data['price'],
                    'quantity': qty,
                    'subtotal': subtotal,
                    'is_combo': True
                })
                snacks_total += subtotal

                savings = (combo_data['original'] - combo_data['price']) * qty
                print(f"✅ Added {qty}x {combo_name} (Saved £{savings:.2f})")

            # Individual item
            elif item_idx <= total_items:
                snack_idx = item_idx - len(COMBO_DEALS) - 1
                snacks_menu_list = list(SNACKS_MENU.items())

                if snack_idx < 0 or snack_idx >= len(snacks_menu_list):
                    print("❌ Invalid selection")
                    continue

                snack_name, snack_price = snacks_menu_list[snack_idx]

                qty_str = input(f"Quantity of {snack_name}: ").strip()

                try:
                    qty = int(qty_str)
                    if qty < 1 or qty > 10:
                        print("❌ Quantity must be between 1 and 10")
                        continue
                except ValueError:
                    print("❌ Invalid quantity")
                    continue

                subtotal = snack_price * qty
                snacks_list.append({
                    'name': snack_name,
                    'price': snack_price,
                    'quantity': qty,
                    'subtotal': subtotal,
                    'is_combo': False
                })
                snacks_total += subtotal

                print(f"✅ Added {qty}x {snack_name}")
            else:
                print("❌ Invalid selection")

        return snacks_total, snacks_list

    except Exception as e:
        logger.error(f"Error adding snacks: {e}")
        return 0.0, []


# ============================================================================
# TICKET BOOKING
# ============================================================================

def book_tickets():
    """Book movie tickets with full features"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to book tickets")
        input("\n📌 Press Enter to continue...")
        return

    try:
        # Check membership
        membership = get_user_membership(user.get('username'))
        if membership:
            print(f"\n💳 Member Benefits Active!")
            print(f"   Points Balance: {membership['points_balance']}")
            print(f"   Member Discount: {int(MEMBER_DISCOUNT * 100)}% off tickets")

        view_screenings()

        screening_id = input("\n🎟️  Enter screening ID to book (0 to cancel): ").strip()
        if screening_id == "0":
            return

        if not screening_id.isdigit():
            print("❌ Invalid screening ID")
            input("\n📌 Press Enter to continue...")
            return

        # Get screening details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT movie_title, screening_date, screening_time, screen_number,
                       available_seats, ticket_price, screen_type
                FROM cinema_screenings
                WHERE screening_id = ? AND status = 'available'
            ''', (screening_id,))
            screening = cursor.fetchone()

            if not screening:
                print("❌ Screening not found or not available")
                input("\n📌 Press Enter to continue...")
                return

            movie_title, date, time, screen, available, base_price, screen_type = screening

            print_subheader(f"BOOKING: {movie_title}")
            print(f"\n🎬 Movie: {movie_title}")
            print(f"📅 Date: {date}")
            print(f"🕐 Time: {time}")
            print(f"📺 Screen: {screen}" + (" (PREMIUM)" if screen_type == 'premium' else ""))
            print(f"💺 Available Seats: {available}")

            # Get number of tickets
            num_tickets_str = input(f"\nEnter number of tickets (1-{min(available, 10)}): ").strip()

            try:
                num_tickets = int(num_tickets_str)
            except ValueError:
                print("❌ Invalid number of tickets")
                input("\n📌 Press Enter to continue...")
                return

            if num_tickets < 1 or num_tickets > min(available, 10):
                print(f"❌ Number of tickets must be between 1 and {min(available, 10)}")
                input("\n📌 Press Enter to continue...")
                return

            # Select ticket type
            print("\n🎫 TICKET TYPES:")
            for idx, (ttype, tprice) in enumerate(TICKET_TYPES.items(), 1):
                # Apply member discount if applicable
                final_price = tprice * (1 - MEMBER_DISCOUNT) if membership else tprice
                discount_label = f" (Member: £{final_price:.2f})" if membership else ""
                print(f"{idx}. {ttype} - £{tprice:.2f}{discount_label}")

            ticket_choice = input("\nSelect ticket type (1-4): ").strip()
            ticket_types_list = list(TICKET_TYPES.items())

            try:
                ticket_idx = int(ticket_choice) - 1
                if ticket_idx < 0 or ticket_idx >= len(ticket_types_list):
                    raise ValueError
                ticket_type, ticket_price = ticket_types_list[ticket_idx]
            except (ValueError, IndexError):
                print("❌ Invalid ticket type")
                input("\n📌 Press Enter to continue...")
                return

            # Apply member discount
            member_discount_amount = 0.0
            if membership:
                member_discount_amount = ticket_price * num_tickets * MEMBER_DISCOUNT
                ticket_price = ticket_price * (1 - MEMBER_DISCOUNT)

            ticket_total = num_tickets * ticket_price

            # Seat selection
            print("\n💺 SEAT SELECTION")
            use_seat_selection = input("Select specific seats? (yes/no, default: auto): ").strip().lower()

            if use_seat_selection == 'yes':
                selected_seats = select_seats(int(screening_id), num_tickets)
                if not selected_seats:
                    print("❌ Seat selection cancelled")
                    input("\n📌 Press Enter to continue...")
                    return
            else:
                # Auto-assign seats
                selected_seats = auto_select_seats(int(screening_id), num_tickets)
                if selected_seats:
                    print(f"✅ Auto-assigned seats: {', '.join(selected_seats)}")
                else:
                    selected_seats = [f"Auto-{i+1}" for i in range(num_tickets)]

            # Snacks
            snacks_total = 0.0
            snacks_list = []

            suggest_combo_for_party(num_tickets)
            add_snacks = input("\n🍿 Add snacks to your order? (yes/no): ").strip().lower()

            if add_snacks == 'yes':
                snacks_total, snacks_list = add_snacks_to_order()

            # Points redemption
            points_redeemed = 0
            points_discount = 0.0

            if membership and membership['points_balance'] >= 100:
                print(f"\n⭐ You have {membership['points_balance']} points")
                print("   100 points = £5 off | 200 points = £10 off | 500 points = £25 off")

                redeem = input("Redeem points? (yes/no): ").strip().lower()
                if redeem == 'yes':
                    points_to_redeem = input("Enter points to redeem (100/200/500): ").strip()

                    if points_to_redeem in ['100', '200', '500']:
                        points_val = int(points_to_redeem)
                        if membership['points_balance'] >= points_val:
                            points_redeemed = points_val
                            points_discount = points_val / 20  # 100 points = £5
                            print(f"✅ Redeeming {points_redeemed} points for £{points_discount:.2f} off")

            total_amount = ticket_total + snacks_total - member_discount_amount - points_discount

            # Generate booking reference
            booking_ref = f"CINEMA-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"

            # Booking summary
            print_subheader("BOOKING SUMMARY")
            print(f"\n🎬 Movie: {movie_title}")
            print(f"📅 Date/Time: {date} at {time}")
            print(f"💺 Seats: {', '.join(selected_seats)}")
            print(f"🎟️  Tickets: {num_tickets}x {ticket_type} @ £{TICKET_TYPES[ticket_type]:.2f} = £{num_tickets * TICKET_TYPES[ticket_type]:.2f}")

            if member_discount_amount > 0:
                print(f"   💳 Member Discount ({int(MEMBER_DISCOUNT * 100)}%): -£{member_discount_amount:.2f}")
                print(f"   Ticket Total: £{ticket_total:.2f}")

            if snacks_list:
                print("\n🍿 Snacks:")
                for snack in snacks_list:
                    combo_label = " [COMBO]" if snack.get('is_combo') else ""
                    print(f"   {snack['quantity']}x {snack['name']}{combo_label} @ £{snack['price']:.2f} = £{snack['subtotal']:.2f}")
                print(f"   Snacks Total: £{snacks_total:.2f}")

            if points_redeemed > 0:
                print(f"\n⭐ Points Redeemed: {points_redeemed} points (-£{points_discount:.2f})")

            print(f"\n💰 TOTAL AMOUNT: £{total_amount:.2f}")

            # Calculate points to be earned
            points_to_earn = calculate_points_earned(total_amount) if membership else 0
            if points_to_earn > 0:
                print(f"   ⭐ Points to earn: {points_to_earn}")

            confirm = input("\n✅ Confirm booking? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Booking cancelled")
                input("\n📌 Press Enter to continue...")
                return

            # Create booking
            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO cinema_bookings
                    (booking_ref, user_id, user_name, user_email, screening_id, movie_title,
                     screening_date, screening_time, num_tickets, ticket_type, seat_numbers,
                     ticket_total, snacks_total, member_discount, total_amount,
                     points_earned, points_redeemed, status, booking_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)
                ''', (booking_ref, user.get('username'), user.get('full_name', user.get('username')),
                      user.get('email', ''), screening_id, movie_title, date, time,
                      num_tickets, ticket_type, ','.join(selected_seats),
                      ticket_total, snacks_total, member_discount_amount, total_amount,
                      points_to_earn, points_redeemed, datetime.now().isoformat()))

                booking_id = conn_tx.execute('SELECT last_insert_rowid()').fetchone()[0]

                # Add snacks
                for snack in snacks_list:
                    conn_tx.execute('''
                        INSERT INTO cinema_snacks_orders
                        (booking_id, booking_ref, user_id, snack_item, quantity, unit_price, subtotal, is_combo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (booking_id, booking_ref, user.get('username'), snack['name'],
                          snack['quantity'], snack['price'], snack['subtotal'],
                          snack.get('is_combo', False)))

                # Update available seats
                conn_tx.execute('''
                    UPDATE cinema_screenings
                    SET available_seats = available_seats - ?
                    WHERE screening_id = ?
                ''', (num_tickets, screening_id))

                # Mark seats as booked
                mark_seats_as_booked(int(screening_id), selected_seats, booking_ref)

                # Handle membership points
                if membership:
                    if points_redeemed > 0:
                        redeem_points(user.get('username'), points_redeemed,
                                    f"Redeemed for booking {booking_ref}")

                    if points_to_earn > 0:
                        award_points(user.get('username'), points_to_earn, booking_ref,
                                   f"Earned from booking {booking_ref}")

                    # Update total spent
                    conn_tx.execute('''
                        UPDATE cinema_memberships
                        SET total_spent = total_spent + ?
                        WHERE user_id = ?
                    ''', (total_amount, user.get('username')))

            print_subheader("BOOKING CONFIRMED!")
            print(f"\n✅ Booking Reference: {booking_ref}")
            print(f"🎬 Movie: {movie_title}")
            print(f"📅 Date: {date} at {time}")
            print(f"💺 Seats: {', '.join(selected_seats)}")
            print(f"💰 Total Paid: £{total_amount:.2f}")

            if points_to_earn > 0:
                new_balance = membership['points_balance'] - points_redeemed + points_to_earn
                print(f"⭐ New Points Balance: {new_balance}")

            print("\n📧 Confirmation email sent (if email configured)")
            print("\n⚠️  Please arrive 15 minutes before the screening")
            print("    Show this booking reference at the entrance")

            # Send confirmation email
            booking_details = {
                'booking_ref': booking_ref,
                'user_name': user.get('full_name', user.get('username')),
                'movie_title': movie_title,
                'screening_date': date,
                'screening_time': time,
                'num_tickets': num_tickets,
                'ticket_type': ticket_type,
                'total_amount': total_amount
            }
            send_booking_confirmation_email(user.get('email', ''), booking_details)

            # Log activity
            if ACTIVITY_LOGGING:
                log_activity('create', 'cinema_booking',
                           booking_ref=booking_ref,
                           details={'movie': movie_title, 'amount': total_amount})

            logger.info(f"User {user.get('username')} booked cinema tickets {booking_ref} for £{total_amount:.2f}")

    except Exception as e:
        logger.error(f"Error booking tickets: {e}", exc_info=True)
        print(f"❌ Error booking tickets: {e}")

    input("\n📌 Press Enter to continue...")


def view_my_bookings():
    """View user's booking history with detailed information"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view bookings")
        input("\n📌 Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT booking_ref, movie_title, screening_date, screening_time,
                       num_tickets, ticket_type, seat_numbers, total_amount,
                       points_earned, status, booking_date
                FROM cinema_bookings
                WHERE user_id = ?
                ORDER BY booking_date DESC
                LIMIT 50
            ''', (user.get('username'),))
            bookings = cursor.fetchall()

            if not bookings:
                print("\n❌ No bookings found")
            else:
                print_subheader(f"YOUR BOOKINGS ({len(bookings)} found)")

                for booking in bookings:
                    try:
                        (ref, movie, date, time, tickets, ttype, seats,
                         total, points, status, booked) = booking

                        print(f"\n{'='*70}")
                        print(f"🎟️  Booking: {ref}")
                        print(f"🎬 Movie: {movie}")
                        print(f"📅 Date/Time: {date} at {time}")
                        print(f"💺 Seats: {seats}")
                        print(f"🎫 Tickets: {tickets}x {ttype}")
                        print(f"💰 Total: £{float(total):.2f}")
                        if points > 0:
                            print(f"⭐ Points Earned: {points}")
                        print(f"📊 Status: {status.upper()}")
                        print(f"📆 Booked: {booked}")

                        # Show snacks if any
                        snacks_cursor = conn.execute('''
                            SELECT snack_item, quantity, subtotal, is_combo
                            FROM cinema_snacks_orders
                            WHERE booking_ref = ?
                        ''', (ref,))
                        snacks = snacks_cursor.fetchall()

                        if snacks:
                            print("🍿 Snacks:")
                            for snack_item, qty, subtotal, is_combo in snacks:
                                combo_label = " [COMBO]" if is_combo else ""
                                print(f"   {qty}x {snack_item}{combo_label} - £{float(subtotal):.2f}")

                    except Exception as e:
                        logger.error(f"Error displaying booking: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing bookings: {e}", exc_info=True)
        print(f"❌ Error viewing bookings: {e}")

    input("\n📌 Press Enter to continue...")


# ============================================================================
# MEMBERSHIP PROGRAM
# ============================================================================

def membership_menu():
    """Membership program menu"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access membership features")
        input("\n📌 Press Enter to continue...")
        return

    while True:
        try:
            print_header("CINEMA MEMBERSHIP PROGRAM")

            membership = get_user_membership(user.get('username'))

            if membership:
                print(f"\n💳 MEMBERSHIP STATUS: {membership['status'].upper()}")
                print(f"Member Since: {membership['join_date']}")
                print(f"Renewal Date: {membership['renewal_date']}")
                print(f"\n⭐ Points Balance: {membership['points_balance']}")
                print(f"   Total Points Earned: {membership['total_points_earned']}")
                print(f"   Total Spent: £{membership['total_spent']:.2f}")

                print("\n🎁 MEMBER BENEFITS:")
                print(f"   • {int(MEMBER_DISCOUNT * 100)}% discount on all tickets")
                print(f"   • Earn {POINTS_PER_POUND} point per £1 spent")
                print("   • Redeem points for free tickets and snacks")
                print("   • Access to member-exclusive screenings")
                print("   • Priority booking")
            else:
                print("\n📋 NOT A MEMBER YET")
                print(f"\nJoin for only £{MEMBERSHIP_PRICE:.2f}/month!")
                print("\n🎁 MEMBERSHIP BENEFITS:")
                print(f"   • {int(MEMBER_DISCOUNT * 100)}% discount on all tickets")
                print(f"   • Earn {POINTS_PER_POUND} point per £1 spent")
                print("   • Redeem points for free tickets and snacks")
                print("   • Access to member-exclusive screenings")
                print("   • Priority booking")

            print("\n" + "="*70)

            if membership:
                print("\n1. View Points History")
                print("2. Redeem Points")
                print("3. View Exclusive Screenings")
                print("4. Membership Details")
                print("5. Cancel Membership")
            else:
                print("\n1. Join Membership")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if membership:
                if choice == "1":
                    view_points_history()
                elif choice == "2":
                    redeem_points_menu()
                elif choice == "3":
                    view_exclusive_screenings()
                elif choice == "4":
                    view_membership_details()
                elif choice == "5":
                    cancel_membership()
                elif choice == "0":
                    break
                else:
                    print("❌ Invalid choice")
                    input("\n📌 Press Enter to continue...")
            else:
                if choice == "1":
                    join_membership()
                elif choice == "0":
                    break
                else:
                    print("❌ Invalid choice")
                    input("\n📌 Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in membership menu: {e}", exc_info=True)
            print(f"❌ An error occurred: {e}")
            input("\n📌 Press Enter to continue...")


def join_membership():
    """Join cinema membership"""
    user = get_current_user()
    if not user:
        return

    try:
        # Check if already a member
        if get_user_membership(user.get('username')):
            print("❌ You are already a member!")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("JOIN CINEMA MEMBERSHIP")

        print(f"\n💳 Membership Fee: £{MEMBERSHIP_PRICE:.2f}/month")
        print("\n🎁 Benefits:")
        print(f"   • {int(MEMBER_DISCOUNT * 100)}% discount on all tickets")
        print(f"   • Earn {POINTS_PER_POUND} point per £1 spent")
        print("   • Redeem points for rewards")
        print("   • Access to exclusive screenings")

        confirm = input("\n✅ Join now? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("❌ Membership signup cancelled")
            input("\n📌 Press Enter to continue...")
            return

        # Process membership
        with transaction() as conn:
            join_date = datetime.now()
            renewal_date = join_date + timedelta(days=30)

            conn.execute('''
                INSERT INTO cinema_memberships
                (user_id, user_name, user_email, membership_type, points_balance,
                 join_date, renewal_date, status)
                VALUES (?, ?, ?, 'standard', 0, ?, ?, 'active')
            ''', (user.get('username'), user.get('full_name', user.get('username')),
                  user.get('email', ''), join_date.isoformat(),
                  renewal_date.date().isoformat()))

            # Award welcome bonus points
            conn.execute('''
                INSERT INTO cinema_points_transactions
                (user_id, transaction_type, points, description)
                VALUES (?, 'bonus', 100, 'Welcome bonus')
            ''', (user.get('username'),))

            conn.execute('''
                UPDATE cinema_memberships
                SET points_balance = 100
                WHERE user_id = ?
            ''', (user.get('username'),))

        print("\n✅ MEMBERSHIP ACTIVATED!")
        print(f"   Join Date: {join_date.date()}")
        print(f"   Renewal Date: {renewal_date.date()}")
        print("   🎁 Welcome Bonus: 100 points")
        print("\n   Start enjoying your benefits today!")

        if ACTIVITY_LOGGING:
            log_activity('create', 'cinema_membership',
                       user_id=user.get('username'),
                       details={'membership_type': 'standard'})

        logger.info(f"User {user.get('username')} joined cinema membership")

    except Exception as e:
        logger.error(f"Error joining membership: {e}", exc_info=True)
        print(f"❌ Error joining membership: {e}")

    input("\n📌 Press Enter to continue...")


def view_points_history():
    """View points transaction history"""
    user = get_current_user()
    if not user:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT transaction_type, points, description, transaction_date
                FROM cinema_points_transactions
                WHERE user_id = ?
                ORDER BY transaction_date DESC
                LIMIT 50
            ''', (user.get('username'),))
            transactions = cursor.fetchall()

            if not transactions:
                print("\n❌ No points history found")
            else:
                print_subheader("POINTS HISTORY")

                for trans in transactions:
                    trans_type, points, desc, date = trans

                    sign = "+" if points > 0 else ""
                    icon = "⭐" if points > 0 else "🎁"

                    print(f"\n{icon} {sign}{points} points - {trans_type.upper()}")
                    print(f"   {desc}")
                    print(f"   Date: {date}")

    except Exception as e:
        logger.error(f"Error viewing points history: {e}", exc_info=True)
        print(f"❌ Error viewing points history: {e}")

    input("\n📌 Press Enter to continue...")


def redeem_points_menu():
    """Points redemption menu"""
    user = get_current_user()
    if not user:
        return

    try:
        membership = get_user_membership(user.get('username'))
        if not membership:
            print("❌ Membership not found")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("REDEEM POINTS")
        print(f"\n⭐ Your Points Balance: {membership['points_balance']}")

        print("\n🎁 REDEMPTION OPTIONS:")
        print("1. £5 Discount - 100 points")
        print("2. £10 Discount - 200 points")
        print("3. £25 Discount - 500 points")
        print("4. Free Small Popcorn - 50 points")
        print("5. Free Medium Drink - 30 points")
        print("\n0. Cancel")

        choice = input("\nEnter choice: ").strip()

        redemptions = {
            '1': (100, '£5 discount voucher'),
            '2': (200, '£10 discount voucher'),
            '3': (500, '£25 discount voucher'),
            '4': (50, 'Free Small Popcorn'),
            '5': (30, 'Free Medium Drink'),
        }

        if choice == '0':
            return

        if choice not in redemptions:
            print("❌ Invalid choice")
            input("\n📌 Press Enter to continue...")
            return

        points_needed, reward = redemptions[choice]

        if membership['points_balance'] < points_needed:
            print(f"❌ Insufficient points. You need {points_needed} points but have {membership['points_balance']}")
            input("\n📌 Press Enter to continue...")
            return

        confirm = input(f"\nRedeem {points_needed} points for {reward}? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("❌ Redemption cancelled")
            input("\n📌 Press Enter to continue...")
            return

        # Redeem points
        if redeem_points(user.get('username'), points_needed, f"Redeemed for {reward}"):
            new_balance = membership['points_balance'] - points_needed
            print(f"\n✅ Successfully redeemed {points_needed} points for {reward}")
            print(f"   New Balance: {new_balance} points")
            print("\n   Your reward will be available on your next booking")
        else:
            print("❌ Redemption failed")

    except Exception as e:
        logger.error(f"Error redeeming points: {e}", exc_info=True)
        print(f"❌ Error redeeming points: {e}")

    input("\n📌 Press Enter to continue...")


def view_exclusive_screenings():
    """View member-exclusive screenings"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT e.screening_id, e.movie_title, e.screening_date,
                       e.screening_time, e.description, s.available_seats
                FROM cinema_exclusive_screenings e
                JOIN cinema_screenings s ON e.screening_id = s.screening_id
                WHERE s.screening_date >= date('now') AND s.status = 'available'
                ORDER BY s.screening_date, s.screening_time
            ''')
            exclusives = cursor.fetchall()

            if not exclusives:
                print("\n❌ No exclusive screenings available at this time")
            else:
                print_subheader("MEMBER-EXCLUSIVE SCREENINGS")
                print(f"\n👑 {len(exclusives)} exclusive screening(s) available:")

                for exc in exclusives:
                    scr_id, movie, date, time, desc, seats = exc
                    print(f"\n🎬 {movie}")
                    print(f"   📅 {date} at {time}")
                    print(f"   💺 {seats} seats available")
                    print(f"   Screening ID: {scr_id}")
                    if desc:
                        print(f"   ℹ️  {desc}")

    except Exception as e:
        logger.error(f"Error viewing exclusive screenings: {e}", exc_info=True)
        print(f"❌ Error viewing exclusive screenings: {e}")

    input("\n📌 Press Enter to continue...")


def view_membership_details():
    """View detailed membership information"""
    user = get_current_user()
    if not user:
        return

    try:
        membership = get_user_membership(user.get('username'))
        if not membership:
            print("❌ Membership not found")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("MEMBERSHIP DETAILS")

        print(f"\n💳 Member ID: {membership['membership_id']}")
        print(f"👤 Name: {user.get('full_name', user.get('username'))}")
        print(f"📧 Email: {user.get('email', 'N/A')}")
        print(f"🎫 Membership Type: {membership['membership_type'].title()}")
        print(f"📊 Status: {membership['status'].upper()}")

        print(f"\n📅 Membership Dates:")
        print(f"   Join Date: {membership['join_date']}")
        print(f"   Renewal Date: {membership['renewal_date']}")
        print(f"   Last Activity: {membership.get('last_activity', 'N/A')}")

        print(f"\n⭐ Points Summary:")
        print(f"   Current Balance: {membership['points_balance']}")
        print(f"   Total Earned: {membership['total_points_earned']}")
        print(f"   Total Spent: £{membership['total_spent']:.2f}")

        # Calculate savings
        savings = membership['total_spent'] * MEMBER_DISCOUNT
        print(f"\n💰 Total Savings: £{savings:.2f}")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM cinema_bookings
                WHERE user_id = ? AND member_discount > 0
            ''', (user.get('username'),))
            booking_count = cursor.fetchone()[0]
            print(f"   Bookings with Discount: {booking_count}")

    except Exception as e:
        logger.error(f"Error viewing membership details: {e}", exc_info=True)
        print(f"❌ Error viewing membership details: {e}")

    input("\n📌 Press Enter to continue...")


def cancel_membership():
    """Cancel cinema membership"""
    user = get_current_user()
    if not user:
        return

    try:
        membership = get_user_membership(user.get('username'))
        if not membership:
            print("❌ Membership not found")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("CANCEL MEMBERSHIP")

        print(f"\n⚠️  WARNING: You are about to cancel your membership")
        print(f"\n   Current Points Balance: {membership['points_balance']}")
        print("   These points will be forfeited upon cancellation")
        print("\n   You will lose access to:")
        print(f"   • {int(MEMBER_DISCOUNT * 100)}% ticket discount")
        print("   • Points earning and redemption")
        print("   • Exclusive screenings")

        confirm = input("\n❌ Are you sure you want to cancel? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("✅ Cancellation aborted")
            input("\n📌 Press Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE cinema_memberships
                SET status = 'cancelled'
                WHERE user_id = ?
            ''', (user.get('username'),))

        print("\n✅ Membership cancelled successfully")
        print("   We're sorry to see you go!")
        print("   You can rejoin anytime.")

        if ACTIVITY_LOGGING:
            log_activity('delete', 'cinema_membership',
                       user_id=user.get('username'),
                       details={'reason': 'user_requested'})

        logger.info(f"User {user.get('username')} cancelled cinema membership")

    except Exception as e:
        logger.error(f"Error cancelling membership: {e}", exc_info=True)
        print(f"❌ Error cancelling membership: {e}")

    input("\n📌 Press Enter to continue...")


# ============================================================================
# ADMIN PANEL
# ============================================================================

def admin_panel():
    """Admin panel for cinema management"""
    user = get_current_user()
    if not user or not is_staff_or_admin(user):
        print("❌ Access denied. Staff/Admin privileges required.")
        input("\n📌 Press Enter to continue...")
        return

    while True:
        try:
            print_header("CINEMA ADMIN PANEL")
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

            print("\n🎬 MOVIE MANAGEMENT:")
            print("1. Add New Movie")
            print("2. Update Movie")
            print("3. View All Movies")

            print("\n📅 SCREENING MANAGEMENT:")
            print("4. Add Screening")
            print("5. Update Screening")
            print("6. View All Screenings")

            print("\n📊 REPORTS & ANALYTICS:")
            print("7. Booking Reports")
            print("8. Revenue Analytics")
            print("9. Occupancy Report")
            print("10. Member Statistics")

            print("\n👑 EXCLUSIVE SCREENINGS:")
            print("11. Create Exclusive Screening")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                admin_add_movie()
            elif choice == "2":
                admin_update_movie()
            elif choice == "3":
                admin_view_all_movies()
            elif choice == "4":
                admin_add_screening()
            elif choice == "5":
                admin_update_screening()
            elif choice == "6":
                admin_view_all_screenings()
            elif choice == "7":
                admin_booking_reports()
            elif choice == "8":
                admin_revenue_analytics()
            elif choice == "9":
                admin_occupancy_report()
            elif choice == "10":
                admin_member_statistics()
            elif choice == "11":
                admin_create_exclusive_screening()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("\n📌 Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in admin panel: {e}", exc_info=True)
            print(f"❌ An error occurred: {e}")
            input("\n📌 Press Enter to continue...")


def admin_add_movie():
    """Add new movie to the system"""
    try:
        print_subheader("ADD NEW MOVIE")

        title = input("\n🎬 Movie Title: ").strip()
        if not title:
            print("❌ Title cannot be empty")
            input("\n📌 Press Enter to continue...")
            return

        genre = input("🎭 Genre (Drama/Comedy/Adventure/Romance/Thriller): ").strip()
        rating = input("⭐ Rating (PG/PG-13/R): ").strip()

        duration_str = input("⏱️  Duration (minutes): ").strip()
        try:
            duration = int(duration_str)
        except ValueError:
            print("❌ Invalid duration")
            input("\n📌 Press Enter to continue...")
            return

        description = input("📖 Description: ").strip()
        director = input("🎥 Director: ").strip()
        cast = input("👥 Cast (comma-separated): ").strip()
        release_date = input("📅 Release Date (YYYY-MM-DD): ").strip()

        status = input("📊 Status (now_showing/coming_soon): ").strip().lower()
        if status not in ['now_showing', 'coming_soon']:
            status = 'coming_soon'

        with transaction() as conn:
            conn.execute('''
                INSERT INTO cinema_movies
                (title, genre, rating, duration_minutes, description, director, cast, release_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, genre, rating, duration, description, director, cast, release_date, status))

            movie_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        print(f"\n✅ Movie added successfully! (ID: {movie_id})")

        if ACTIVITY_LOGGING:
            log_activity('create', 'cinema_movie',
                       movie_id=movie_id,
                       details={'title': title, 'status': status})

        logger.info(f"Admin added movie: {title} (ID: {movie_id})")

    except Exception as e:
        logger.error(f"Error adding movie: {e}", exc_info=True)
        print(f"❌ Error adding movie: {e}")

    input("\n📌 Press Enter to continue...")


def admin_update_movie():
    """Update existing movie"""
    try:
        admin_view_all_movies()

        movie_id = input("\n🎬 Enter Movie ID to update (0 to cancel): ").strip()
        if movie_id == "0":
            return

        if not movie_id.isdigit():
            print("❌ Invalid movie ID")
            input("\n📌 Press Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('SELECT title, status FROM cinema_movies WHERE movie_id = ?', (movie_id,))
            movie = cursor.fetchone()

            if not movie:
                print("❌ Movie not found")
                input("\n📌 Press Enter to continue...")
                return

            title, current_status = movie

            print(f"\nUpdating: {title}")
            print("\nLeave blank to keep current value")

            new_status = input(f"New Status (current: {current_status}) [now_showing/coming_soon]: ").strip().lower()

            if new_status and new_status in ['now_showing', 'coming_soon']:
                with transaction() as conn_tx:
                    conn_tx.execute('''
                        UPDATE cinema_movies
                        SET status = ?, updated_at = ?
                        WHERE movie_id = ?
                    ''', (new_status, datetime.now().isoformat(), movie_id))

                print(f"✅ Movie updated successfully!")

                if ACTIVITY_LOGGING:
                    log_activity('update', 'cinema_movie',
                               movie_id=movie_id,
                               details={'status_changed': f'{current_status} -> {new_status}'})
            else:
                print("❌ No changes made")

    except Exception as e:
        logger.error(f"Error updating movie: {e}", exc_info=True)
        print(f"❌ Error updating movie: {e}")

    input("\n📌 Press Enter to continue...")


def admin_view_all_movies():
    """View all movies in the system"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT movie_id, title, genre, rating, duration_minutes, status, release_date
                FROM cinema_movies
                ORDER BY release_date DESC
            ''')
            movies = cursor.fetchall()

            if not movies:
                print("\n❌ No movies in the system")
            else:
                print_subheader(f"ALL MOVIES ({len(movies)} total)")

                for movie in movies:
                    movie_id, title, genre, rating, duration, status, release_date = movie
                    status_icon = "📺" if status == 'now_showing' else "📅"
                    print(f"\n{status_icon} [ID: {movie_id}] {title}")
                    print(f"   {genre} | {rating} | {duration} min | Release: {release_date}")
                    print(f"   Status: {status.replace('_', ' ').title()}")

    except Exception as e:
        logger.error(f"Error viewing all movies: {e}", exc_info=True)
        print(f"❌ Error viewing all movies: {e}")


def admin_add_screening():
    """Add new screening"""
    try:
        admin_view_all_movies()

        movie_id = input("\n🎬 Enter Movie ID for screening: ").strip()
        if not movie_id.isdigit():
            print("❌ Invalid movie ID")
            input("\n📌 Press Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('SELECT title FROM cinema_movies WHERE movie_id = ?', (movie_id,))
            movie = cursor.fetchone()

            if not movie:
                print("❌ Movie not found")
                input("\n📌 Press Enter to continue...")
                return

            movie_title = movie[0]

            print(f"\nCreating screening for: {movie_title}")

            screen_num = input("📺 Screen Number (1-10): ").strip()
            screening_date = input("📅 Screening Date (YYYY-MM-DD): ").strip()
            screening_time = input("🕐 Screening Time (HH:MM): ").strip()

            total_seats = input("💺 Total Seats (default: 100): ").strip() or "100"
            try:
                total_seats = int(total_seats)
            except ValueError:
                total_seats = 100

            screen_type = input("🎭 Screen Type (standard/premium): ").strip().lower() or "standard"

            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO cinema_screenings
                    (movie_id, movie_title, screen_number, screening_date, screening_time,
                     total_seats, available_seats, screen_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available')
                ''', (movie_id, movie_title, screen_num, screening_date, screening_time,
                      total_seats, total_seats, screen_type))

                screening_id = conn_tx.execute('SELECT last_insert_rowid()').fetchone()[0]

            print(f"\n✅ Screening added successfully! (ID: {screening_id})")

            if ACTIVITY_LOGGING:
                log_activity('create', 'cinema_screening',
                           screening_id=screening_id,
                           details={'movie': movie_title, 'date': screening_date})

            logger.info(f"Admin added screening for {movie_title} on {screening_date}")

    except Exception as e:
        logger.error(f"Error adding screening: {e}", exc_info=True)
        print(f"❌ Error adding screening: {e}")

    input("\n📌 Press Enter to continue...")


def admin_update_screening():
    """Update screening status or capacity"""
    try:
        print_subheader("UPDATE SCREENING")

        screening_id = input("\n🎟️  Enter Screening ID: ").strip()
        if not screening_id.isdigit():
            print("❌ Invalid screening ID")
            input("\n📌 Press Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT movie_title, screening_date, screening_time, status, available_seats
                FROM cinema_screenings
                WHERE screening_id = ?
            ''', (screening_id,))
            screening = cursor.fetchone()

            if not screening:
                print("❌ Screening not found")
                input("\n📌 Press Enter to continue...")
                return

            movie, date, time, status, seats = screening

            print(f"\nScreening: {movie}")
            print(f"Date/Time: {date} at {time}")
            print(f"Status: {status}")
            print(f"Available Seats: {seats}")

            new_status = input("\nNew Status (available/cancelled): ").strip().lower()

            if new_status in ['available', 'cancelled']:
                with transaction() as conn_tx:
                    conn_tx.execute('''
                        UPDATE cinema_screenings
                        SET status = ?
                        WHERE screening_id = ?
                    ''', (new_status, screening_id))

                print(f"✅ Screening status updated to: {new_status}")

                if ACTIVITY_LOGGING:
                    log_activity('update', 'cinema_screening',
                               screening_id=screening_id,
                               details={'status': new_status})
            else:
                print("❌ Invalid status")

    except Exception as e:
        logger.error(f"Error updating screening: {e}", exc_info=True)
        print(f"❌ Error updating screening: {e}")

    input("\n📌 Press Enter to continue...")


def admin_view_all_screenings():
    """View all screenings"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT screening_id, movie_title, screening_date, screening_time,
                       screen_number, available_seats, total_seats, status
                FROM cinema_screenings
                WHERE screening_date >= date('now', '-7 days')
                ORDER BY screening_date DESC, screening_time DESC
                LIMIT 100
            ''')
            screenings = cursor.fetchall()

            if not screenings:
                print("\n❌ No screenings found")
            else:
                print_subheader(f"ALL SCREENINGS ({len(screenings)} found)")

                current_date = None
                for screening in screenings:
                    scr_id, movie, date, time, screen, avail, total, status = screening

                    if date != current_date:
                        print(f"\n📅 {date}:")
                        current_date = date

                    occupancy = ((total - avail) / total * 100) if total > 0 else 0
                    status_icon = "✅" if status == 'available' else "❌"

                    print(f"  {status_icon} [ID: {scr_id}] {time} - {movie}")
                    print(f"      Screen {screen} | {avail}/{total} seats | {occupancy:.0f}% full | {status}")

    except Exception as e:
        logger.error(f"Error viewing all screenings: {e}", exc_info=True)
        print(f"❌ Error viewing all screenings: {e}")

    input("\n📌 Press Enter to continue...")


def admin_booking_reports():
    """View booking reports"""
    try:
        print_subheader("BOOKING REPORTS")

        print("\n1. Today's Bookings")
        print("2. This Week's Bookings")
        print("3. This Month's Bookings")
        print("4. All Bookings")

        choice = input("\nEnter choice: ").strip()

        _DATE_FILTERS = {
            "1": "AND DATE(booking_date) = DATE('now')",
            "2": "AND DATE(booking_date) >= DATE('now', '-7 days')",
            "3": "AND DATE(booking_date) >= DATE('now', 'start of month')",
        }
        date_filter = _DATE_FILTERS.get(choice, "")

        with get_connection() as conn:
            cursor = conn.execute(f'''
                SELECT booking_ref, user_name, movie_title, screening_date,
                       num_tickets, total_amount, status, booking_date
                FROM cinema_bookings
                WHERE 1=1 {date_filter}
                ORDER BY booking_date DESC
                LIMIT 100
            ''')
            bookings = cursor.fetchall()

            if not bookings:
                print("\n❌ No bookings found")
            else:
                total_revenue = sum(float(b[5]) for b in bookings)
                total_tickets = sum(int(b[4]) for b in bookings)

                print(f"\n📊 BOOKING SUMMARY:")
                print(f"   Total Bookings: {len(bookings)}")
                print(f"   Total Tickets: {total_tickets}")
                print(f"   Total Revenue: £{total_revenue:.2f}")
                print(f"   Average Order: £{total_revenue/len(bookings):.2f}")

                print(f"\n📋 BOOKINGS:")
                print("="*70)

                for booking in bookings[:20]:  # Show first 20
                    ref, user, movie, date, tickets, amount, status, booked = booking
                    print(f"\n{ref} | {user}")
                    print(f"   {movie} on {date}")
                    print(f"   {tickets} tickets | £{float(amount):.2f} | {status}")
                    print(f"   Booked: {booked}")

    except Exception as e:
        logger.error(f"Error viewing booking reports: {e}", exc_info=True)
        print(f"❌ Error viewing booking reports: {e}")

    input("\n📌 Press Enter to continue...")


def admin_revenue_analytics():
    """View revenue analytics"""
    try:
        print_subheader("REVENUE ANALYTICS")

        with get_connection() as conn:
            # Total revenue
            cursor = conn.execute('''
                SELECT
                    SUM(total_amount) as total_revenue,
                    SUM(ticket_total) as ticket_revenue,
                    SUM(snacks_total) as snacks_revenue,
                    COUNT(*) as total_bookings
                FROM cinema_bookings
                WHERE status = 'confirmed'
            ''')
            totals = cursor.fetchone()

            total_rev, ticket_rev, snacks_rev, bookings = totals

            print(f"\n💰 OVERALL REVENUE:")
            print(f"   Total Revenue: £{float(total_rev or 0):.2f}")
            print(f"   Ticket Sales: £{float(ticket_rev or 0):.2f} ({float(ticket_rev or 0)/float(total_rev or 1)*100:.1f}%)")
            print(f"   Snacks Sales: £{float(snacks_rev or 0):.2f} ({float(snacks_rev or 0)/float(total_rev or 1)*100:.1f}%)")
            print(f"   Total Bookings: {bookings}")

            # Revenue by movie
            cursor = conn.execute('''
                SELECT movie_title, SUM(total_amount) as revenue, COUNT(*) as bookings
                FROM cinema_bookings
                WHERE status = 'confirmed'
                GROUP BY movie_title
                ORDER BY revenue DESC
                LIMIT 10
            ''')
            by_movie = cursor.fetchall()

            if by_movie:
                print(f"\n🎬 TOP MOVIES BY REVENUE:")
                for movie, rev, book_count in by_movie:
                    print(f"   {movie}: £{float(rev):.2f} ({book_count} bookings)")

            # Revenue by date
            cursor = conn.execute('''
                SELECT DATE(booking_date) as date, SUM(total_amount) as revenue
                FROM cinema_bookings
                WHERE status = 'confirmed' AND DATE(booking_date) >= DATE('now', '-7 days')
                GROUP BY DATE(booking_date)
                ORDER BY date DESC
            ''')
            by_date = cursor.fetchall()

            if by_date:
                print(f"\n📅 REVENUE BY DATE (Last 7 Days):")
                for date, rev in by_date:
                    print(f"   {date}: £{float(rev):.2f}")

            # Membership stats
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as member_bookings,
                    SUM(total_amount) as member_revenue,
                    SUM(member_discount) as total_discounts
                FROM cinema_bookings
                WHERE status = 'confirmed' AND member_discount > 0
            ''')
            member_stats = cursor.fetchone()

            if member_stats and member_stats[0] > 0:
                mem_bookings, mem_rev, discounts = member_stats
                print(f"\n💳 MEMBERSHIP IMPACT:")
                print(f"   Member Bookings: {mem_bookings}")
                print(f"   Member Revenue: £{float(mem_rev or 0):.2f}")
                print(f"   Total Discounts: £{float(discounts or 0):.2f}")

    except Exception as e:
        logger.error(f"Error viewing revenue analytics: {e}", exc_info=True)
        print(f"❌ Error viewing revenue analytics: {e}")

    input("\n📌 Press Enter to continue...")


def admin_occupancy_report():
    """View screening occupancy rates"""
    try:
        print_subheader("OCCUPANCY REPORT")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    movie_title,
                    screening_date,
                    screening_time,
                    total_seats,
                    available_seats,
                    screen_number,
                    status
                FROM cinema_screenings
                WHERE screening_date >= DATE('now', '-7 days')
                ORDER BY screening_date DESC, screening_time DESC
                LIMIT 50
            ''')
            screenings = cursor.fetchall()

            if not screenings:
                print("\n❌ No screenings found")
            else:
                print(f"\n📊 SHOWING {len(screenings)} SCREENING(S):")
                print("="*70)

                total_capacity = 0
                total_sold = 0

                current_date = None
                for screening in screenings:
                    movie, date, time, total, avail, screen, status = screening

                    if date != current_date:
                        print(f"\n📅 {date}:")
                        current_date = date

                    sold = total - avail
                    occupancy = (sold / total * 100) if total > 0 else 0

                    total_capacity += total
                    total_sold += sold

                    # Color code occupancy
                    if occupancy >= 90:
                        icon = "🔴"
                    elif occupancy >= 70:
                        icon = "🟡"
                    elif occupancy >= 50:
                        icon = "🟢"
                    else:
                        icon = "⚪"

                    print(f"  {icon} {time} - {movie}")
                    print(f"      Screen {screen} | {sold}/{total} seats ({occupancy:.0f}% full) | {status}")

                overall_occupancy = (total_sold / total_capacity * 100) if total_capacity > 0 else 0
                print(f"\n📊 OVERALL OCCUPANCY: {overall_occupancy:.1f}%")
                print(f"   Total Capacity: {total_capacity} seats")
                print(f"   Total Sold: {total_sold} seats")
                print(f"   Available: {total_capacity - total_sold} seats")

    except Exception as e:
        logger.error(f"Error viewing occupancy report: {e}", exc_info=True)
        print(f"❌ Error viewing occupancy report: {e}")

    input("\n📌 Press Enter to continue...")


def admin_member_statistics():
    """View membership statistics"""
    try:
        print_subheader("MEMBERSHIP STATISTICS")

        with get_connection() as conn:
            # Total members
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(points_balance), SUM(total_spent)
                FROM cinema_memberships
                WHERE status = 'active'
            ''')
            stats = cursor.fetchone()

            if stats:
                total_members, total_points, total_spent = stats

                print(f"\n💳 MEMBERSHIP OVERVIEW:")
                print(f"   Active Members: {total_members or 0}")
                print(f"   Total Points in Circulation: {total_points or 0}")
                print(f"   Total Member Spending: £{float(total_spent or 0):.2f}")

                if total_members and total_members > 0:
                    avg_points = (total_points or 0) / total_members
                    avg_spent = (total_spent or 0) / total_members
                    print(f"   Avg Points per Member: {avg_points:.0f}")
                    print(f"   Avg Spending per Member: £{avg_spent:.2f}")

            # Top members
            cursor = conn.execute('''
                SELECT user_name, total_points_earned, total_spent, points_balance
                FROM cinema_memberships
                WHERE status = 'active'
                ORDER BY total_spent DESC
                LIMIT 10
            ''')
            top_members = cursor.fetchall()

            if top_members:
                print(f"\n🏆 TOP MEMBERS BY SPENDING:")
                for name, points_earned, spent, balance in top_members:
                    print(f"   {name}: £{float(spent):.2f} spent | {points_earned} points earned | {balance} balance")

            # Recent joins
            cursor = conn.execute('''
                SELECT user_name, join_date, points_balance
                FROM cinema_memberships
                WHERE status = 'active'
                ORDER BY join_date DESC
                LIMIT 5
            ''')
            recent = cursor.fetchall()

            if recent:
                print(f"\n🆕 RECENT MEMBERS:")
                for name, join_date, balance in recent:
                    print(f"   {name} joined {join_date} | {balance} points")

    except Exception as e:
        logger.error(f"Error viewing member statistics: {e}", exc_info=True)
        print(f"❌ Error viewing member statistics: {e}")

    input("\n📌 Press Enter to continue...")


def admin_create_exclusive_screening():
    """Create member-exclusive screening"""
    try:
        print_subheader("CREATE EXCLUSIVE SCREENING")

        admin_view_all_screenings()

        screening_id = input("\n🎟️  Enter Screening ID to make exclusive: ").strip()
        if not screening_id.isdigit():
            print("❌ Invalid screening ID")
            input("\n📌 Press Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT movie_title, screening_date, screening_time
                FROM cinema_screenings
                WHERE screening_id = ?
            ''', (screening_id,))
            screening = cursor.fetchone()

            if not screening:
                print("❌ Screening not found")
                input("\n📌 Press Enter to continue...")
                return

            movie, date, time = screening

            description = input(f"\n📝 Description for this exclusive screening: ").strip()

            with transaction() as conn_tx:
                # Check if already exclusive
                cursor = conn_tx.execute('''
                    SELECT exclusive_id FROM cinema_exclusive_screenings
                    WHERE screening_id = ?
                ''', (screening_id,))

                if cursor.fetchone():
                    print("❌ This screening is already exclusive")
                else:
                    conn_tx.execute('''
                        INSERT INTO cinema_exclusive_screenings
                        (screening_id, movie_title, screening_date, screening_time, description)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (screening_id, movie, date, time, description))

                    print(f"\n✅ Exclusive screening created!")
                    print(f"   Movie: {movie}")
                    print(f"   Date/Time: {date} at {time}")
                    print(f"   Description: {description}")

                    if ACTIVITY_LOGGING:
                        log_activity('create', 'cinema_exclusive_screening',
                                   screening_id=screening_id,
                                   details={'movie': movie})

    except Exception as e:
        logger.error(f"Error creating exclusive screening: {e}", exc_info=True)
        print(f"❌ Error creating exclusive screening: {e}")

    input("\n📌 Press Enter to continue...")


# ============================================================================
# MAIN MENU
# ============================================================================

def cinema_menu():
    """Main cinema menu"""
    try:
        # Initialize database
        init_cinema_db()
    except Exception as e:
        logger.error(f"Failed to initialize cinema database: {e}", exc_info=True)
        print(f"❌ Failed to initialize cinema system: {e}")
        input("\n📌 Press Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Cinema")
        input("\n📌 Press Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY CINEMA")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

                # Show membership status
                membership = get_user_membership(user.get('username'))
                if membership:
                    print(f"💳 Member Status: ACTIVE | Points: {membership['points_balance']}")

            print("\n🎬 MOVIE BROWSING:")
            print("1. View Movies (Now Showing & Coming Soon)")
            print("2. Search Movies")
            print("3. View Movie Details")

            print("\n🎟️  TICKET BOOKING:")
            print("4. View Screenings")
            print("5. Book Tickets")
            print("6. View My Bookings")

            print("\n💳 MEMBERSHIP PROGRAM:")
            print("7. Membership Menu")

            # Show admin options for staff/admin
            if is_staff_or_admin(user):
                print("\n👑 ADMIN PANEL:")
                print("8. Cinema Administration")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_movies()
            elif choice == "2":
                search_movies()
            elif choice == "3":
                view_movie_details()
            elif choice == "4":
                view_screenings()
            elif choice == "5":
                book_tickets()
            elif choice == "6":
                view_my_bookings()
            elif choice == "7":
                membership_menu()
            elif choice == "8" and is_staff_or_admin(user):
                admin_panel()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("\n📌 Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in cinema menu: {e}", exc_info=True)
            print(f"❌ An error occurred: {e}")
            input("\n📌 Press Enter to continue...")


def launch_cinema_cli(auth=None):
    """Launch cinema CLI (called from main menu)"""
    cinema_menu()


if __name__ == "__main__":
    cinema_menu()
