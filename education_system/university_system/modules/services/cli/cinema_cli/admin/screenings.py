"""Cinema CLI admin screening management functions."""

import logging

from education_system.university_system.infrastructure.database.db import get_connection, transaction

from education_system.university_system.modules.services.cli.cinema_cli.constants import ACTIVITY_LOGGING
from education_system.university_system.modules.services.cli.cinema_cli.utils import print_subheader
from education_system.university_system.modules.services.cli.cinema_cli.admin.movies import admin_view_all_movies

logger = logging.getLogger(__name__)


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
                from education_system.university_system.modules.services.cli.cinema_cli.constants import log_activity
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
                    from education_system.university_system.modules.services.cli.cinema_cli.constants import log_activity
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
                        from education_system.university_system.modules.services.cli.cinema_cli.constants import log_activity
                        log_activity('create', 'cinema_exclusive_screening',
                                   screening_id=screening_id,
                                   details={'movie': movie})

    except Exception as e:
        logger.error(f"Error creating exclusive screening: {e}", exc_info=True)
        print(f"❌ Error creating exclusive screening: {e}")

    input("\n📌 Press Enter to continue...")
