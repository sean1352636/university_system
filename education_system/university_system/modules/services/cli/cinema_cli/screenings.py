"""Cinema CLI screening display functions."""

import logging

from education_system.university_system.infrastructure.database.db import get_connection

from education_system.university_system.modules.services.cli.cinema_cli.utils import print_subheader

logger = logging.getLogger(__name__)


def view_screenings():
    """View available screenings"""
    try:
        from education_system.university_system.modules.services.cli.cinema_cli.movies import view_movies
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
