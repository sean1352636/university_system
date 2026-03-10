"""
Database initialization for Social Matching module.

Creates tables for user interests, matches, buddy requests, teams, clubs, and activities.
"""

from education_system.university_system.infrastructure.database.db import get_connection, transaction


def initialize_social_matching_tables():
    """
    Initialize all database tables for the social matching system.

    Tables created:
    - user_interests: User interest profiles with categories
    - interest_matches: Calculated compatibility matches
    - buddy_requests: Study abroad and social buddy requests
    - team_formations: Intramural sports team formations
    - club_suggestions: Personalized club recommendations
    - social_activities: Suggested social activities
    - user_personality: Personality type assessments
    - user_privacy_settings: Privacy controls for matching
    """
    with transaction() as conn:
        # User interests table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_interests (
                interest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                interest_category TEXT NOT NULL,
                interest_name TEXT NOT NULL,
                interest_level INTEGER DEFAULT 5,
                is_public INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username),
                UNIQUE(user_id, interest_category, interest_name)
            )
        """)

        # Interest matches table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interest_matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                compatibility_score REAL NOT NULL,
                shared_interests TEXT,
                match_reason TEXT,
                match_status TEXT DEFAULT 'suggested',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users(username),
                FOREIGN KEY (user2_id) REFERENCES users(username),
                UNIQUE(user1_id, user2_id)
            )
        """)

        # Buddy requests table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buddy_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                destination TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username),
                FOREIGN KEY (receiver_id) REFERENCES users(username)
            )
        """)

        # Team formations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_formations (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL UNIQUE,
                sport_type TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                team_size INTEGER NOT NULL,
                current_members INTEGER DEFAULT 1,
                skill_level TEXT,
                description TEXT,
                status TEXT DEFAULT 'recruiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES users(username)
            )
        """)

        # Team members table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES team_formations(team_id),
                FOREIGN KEY (user_id) REFERENCES users(username),
                UNIQUE(team_id, user_id)
            )
        """)

        # Club suggestions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS club_suggestions (
                suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                club_name TEXT NOT NULL,
                club_category TEXT NOT NULL,
                match_score REAL NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'suggested',
                suggested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)

        # Social activities table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS social_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT,
                location TEXT,
                activity_date DATE,
                activity_time TIME,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                interests_matched TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(username)
            )
        """)

        # Activity participants table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_participants (
                participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                rsvp_status TEXT DEFAULT 'interested',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES social_activities(activity_id),
                FOREIGN KEY (user_id) REFERENCES users(username),
                UNIQUE(activity_id, user_id)
            )
        """)

        # User personality table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_personality (
                personality_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                personality_type TEXT,
                extroversion_score INTEGER,
                openness_score INTEGER,
                social_preference TEXT,
                group_size_preference TEXT,
                activity_level TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)

        # Privacy settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_privacy_settings (
                privacy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                allow_matching INTEGER DEFAULT 1,
                show_profile INTEGER DEFAULT 1,
                allow_messages INTEGER DEFAULT 1,
                show_interests INTEGER DEFAULT 1,
                show_in_search INTEGER DEFAULT 1,
                match_same_major INTEGER DEFAULT 0,
                match_same_year INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)

        # Create indexes for performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_interests_user
            ON user_interests(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_interests_category
            ON user_interests(interest_category)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interest_matches_users
            ON interest_matches(user1_id, user2_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interest_matches_score
            ON interest_matches(compatibility_score DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_buddy_requests_receiver
            ON buddy_requests(receiver_id, status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_team_formations_sport
            ON team_formations(sport_type, status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_social_activities_date
            ON social_activities(activity_date)
        """)


def seed_sample_data():
    """Seed sample data for testing and demonstration."""
    with transaction() as conn:
        # Sample interest categories and popular interests
        sample_interests = [
            ('Sports', ['Basketball', 'Soccer', 'Tennis', 'Swimming', 'Volleyball', 'Running']),
            ('Music', ['Rock', 'Pop', 'Hip-Hop', 'Classical', 'Jazz', 'Electronic']),
            ('Arts', ['Painting', 'Photography', 'Theater', 'Dance', 'Sculpture', 'Film']),
            ('Gaming', ['Video Games', 'Board Games', 'Card Games', 'eSports', 'RPGs']),
            ('Outdoor', ['Hiking', 'Camping', 'Cycling', 'Rock Climbing', 'Kayaking']),
            ('Technology', ['Programming', 'AI/ML', 'Robotics', 'Web Dev', 'Cybersecurity']),
            ('Academic', ['Research', 'Study Groups', 'Academic Clubs', 'Tutoring', 'Debate']),
            ('Career', ['Networking', 'Entrepreneurship', 'Internships', 'Professional Dev']),
            ('Travel', ['Study Abroad', 'Backpacking', 'Cultural Exchange', 'Adventure Travel'])
        ]

        # Sample clubs based on interests
        sample_clubs = [
            ('Sports', 'Intramural Basketball League'),
            ('Sports', 'Campus Running Club'),
            ('Music', 'Acapella Group'),
            ('Music', 'DJ Club'),
            ('Arts', 'Photography Society'),
            ('Arts', 'Drama Club'),
            ('Gaming', 'eSports Team'),
            ('Gaming', 'Board Game Society'),
            ('Technology', 'Coding Club'),
            ('Technology', 'Robotics Team'),
            ('Academic', 'Debate Society'),
            ('Academic', 'Research Symposium'),
            ('Career', 'Entrepreneurship Club'),
            ('Career', 'Professional Network'),
            ('Travel', 'Study Abroad Alumni'),
            ('Outdoor', 'Adventure Club')
        ]


if __name__ == "__main__":
    print("Initializing social matching database tables...")
    initialize_social_matching_tables()
    print("Database initialization complete!")
    print("\nSample data seeding available via seed_sample_data()")
