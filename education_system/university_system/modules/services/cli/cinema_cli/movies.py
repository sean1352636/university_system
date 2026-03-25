"""Cinema CLI movie browsing functions."""

import logging

from education_system.university_system.infrastructure.database.db import get_connection

from education_system.university_system.modules.services.cli.cinema_cli.utils import print_subheader
from education_system.university_system.modules.services.cli.cinema_cli.screenings import view_screenings_for_movie

logger = logging.getLogger(__name__)


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
