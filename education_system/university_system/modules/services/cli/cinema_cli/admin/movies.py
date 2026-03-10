"""Cinema CLI admin movie management functions."""

import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection, transaction

from ..constants import ACTIVITY_LOGGING
from ..utils import print_subheader

logger = logging.getLogger(__name__)


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
            from ..constants import log_activity
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
                    from ..constants import log_activity
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
