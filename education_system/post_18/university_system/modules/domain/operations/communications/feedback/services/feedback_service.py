"""
Feedback & Suggestion Box Service

Provides comprehensive feedback and suggestion management with:
- Anonymous and attributed feedback submission
- Upvoting system for suggestions
- Status tracking and administrative responses
- Impact metrics for implemented suggestions
- Public suggestion board with trending ideas
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.sql_safety import escape_like
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

class FeedbackService:
    """Service for managing feedback and suggestions"""

    # Feedback/Suggestion Status Types
    STATUS_SUBMITTED = "Submitted"
    STATUS_UNDER_REVIEW = "Under Review"
    STATUS_PLANNED = "Planned"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_IMPLEMENTED = "Implemented"
    STATUS_DECLINED = "Declined"

    # Categories
    CATEGORIES = [
        "Academic",
        "Housing",
        "Dining",
        "Technology",
        "Campus Life",
        "Safety",
        "Other"
    ]

    def __init__(self):
        """Initialize the feedback service and create tables"""
        self._create_tables()

    def _create_tables(self):
        """Create all necessary tables for feedback system"""
        with transaction() as conn:
            # Categories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    icon TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Main feedback/suggestions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    category_id INTEGER NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('feedback', 'suggestion')),
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    is_anonymous BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT 'Submitted',
                    priority TEXT DEFAULT 'Normal' CHECK(priority IN ('Low', 'Normal', 'High', 'Critical')),
                    votes INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES feedback_categories(id)
                )
            """)

            # Votes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    vote_type TEXT DEFAULT 'upvote' CHECK(vote_type IN ('upvote', 'downvote')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(submission_id, user_id),
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                )
            """)

            # Administrative responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    responder_id TEXT NOT NULL,
                    responder_name TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                )
            """)

            # Status update history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_status_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                )
            """)

            # Impact tracking for implemented suggestions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_impacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    implementation_date DATE,
                    users_affected INTEGER,
                    satisfaction_increase REAL,
                    cost_savings REAL,
                    description TEXT,
                    metrics TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                )
            """)

            # Attachments (optional files/images)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT,
                    file_size INTEGER,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_status
                ON feedback_submissions(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_category
                ON feedback_submissions(category_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_votes_count
                ON feedback_submissions(votes DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON feedback_submissions(user_id)
            """)

            # Initialize categories if empty
            self._initialize_categories(conn)

    def _initialize_categories(self, conn):
        """Initialize default categories"""
        category_data = [
            ("Academic", "Course content, teaching quality, curriculum", "📚"),
            ("Housing", "Dormitories, apartments, maintenance", "🏠"),
            ("Dining", "Cafeteria, meal plans, food quality", "🍽️"),
            ("Technology", "IT services, WiFi, software, computers", "💻"),
            ("Campus Life", "Events, clubs, activities, facilities", "🎉"),
            ("Safety", "Security, emergency services, lighting", "🔒"),
            ("Other", "General feedback and suggestions", "💡")
        ]

        for name, desc, icon in category_data:
            conn.execute("""
                INSERT OR IGNORE INTO feedback_categories (name, description, icon)
                VALUES (?, ?, ?)
            """, (name, desc, icon))

    def submit_feedback(
        self,
        user_id: Optional[str],
        category: str,
        title: str,
        description: str,
        is_anonymous: bool = False,
        feedback_type: str = "feedback"
    ) -> int:
        """
        Submit new feedback or suggestion

        Args:
            user_id: User ID (None if anonymous)
            category: Category name
            title: Brief title/summary
            description: Detailed description
            is_anonymous: Whether to hide user identity
            feedback_type: 'feedback' or 'suggestion'

        Returns:
            Submission ID
        """
        with transaction() as conn:
            # Get category ID
            category_id = conn.execute(
                "SELECT id FROM feedback_categories WHERE name = ?",
                (category,)
            ).fetchone()

            if not category_id:
                raise ValueError(f"Invalid category: {category}")

            category_id = category_id[0]

            # Insert submission
            cursor = conn.execute("""
                INSERT INTO feedback_submissions
                (user_id, category_id, type, title, description, is_anonymous, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id if not is_anonymous else None,
                category_id,
                feedback_type,
                title,
                description,
                is_anonymous,
                self.STATUS_SUBMITTED
            ))

            submission_id = cursor.lastrowid

            # Log activity
            log_activity(
                'create',
                'feedback_submission',
                submission_id=submission_id,
                details={
                    'type': feedback_type,
                    'category': category,
                    'is_anonymous': is_anonymous,
                    'user_id': user_id if not is_anonymous else 'anonymous'
                }
            )

            return submission_id

    def submit_suggestion(
        self,
        user_id: Optional[str],
        category: str,
        title: str,
        description: str,
        is_anonymous: bool = False
    ) -> int:
        """Convenience method for submitting suggestions"""
        return self.submit_feedback(
            user_id, category, title, description, is_anonymous, "suggestion"
        )

    def upvote_submission(self, submission_id: int, user_id: str) -> bool:
        """
        Upvote a submission

        Args:
            submission_id: Submission to upvote
            user_id: User casting the vote

        Returns:
            True if vote was added, False if already voted
        """
        with transaction() as conn:
            # Check if already voted
            existing = conn.execute("""
                SELECT id FROM feedback_votes
                WHERE submission_id = ? AND user_id = ?
            """, (submission_id, user_id)).fetchone()

            if existing:
                return False

            # Add vote
            conn.execute("""
                INSERT INTO feedback_votes (submission_id, user_id, vote_type)
                VALUES (?, ?, 'upvote')
            """, (submission_id, user_id))

            # Update vote count
            conn.execute("""
                UPDATE feedback_submissions
                SET votes = votes + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (submission_id,))

            log_activity(
                'create',
                'feedback_vote',
                submission_id=submission_id,
                details={'user_id': user_id, 'type': 'upvote'}
            )

            return True

    def remove_vote(self, submission_id: int, user_id: str) -> bool:
        """
        Remove a vote from a submission

        Args:
            submission_id: Submission ID
            user_id: User ID

        Returns:
            True if vote was removed
        """
        with transaction() as conn:
            # Check if vote exists
            existing = conn.execute("""
                SELECT id FROM feedback_votes
                WHERE submission_id = ? AND user_id = ?
            """, (submission_id, user_id)).fetchone()

            if not existing:
                return False

            # Remove vote
            conn.execute("""
                DELETE FROM feedback_votes
                WHERE submission_id = ? AND user_id = ?
            """, (submission_id, user_id))

            # Update vote count
            conn.execute("""
                UPDATE feedback_submissions
                SET votes = votes - 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (submission_id,))

            log_activity(
                'delete',
                'feedback_vote',
                submission_id=submission_id,
                details={'user_id': user_id}
            )

            return True

    def get_submissions(
        self,
        submission_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        sort_by: str = "votes",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get submissions with filtering and sorting

        Args:
            submission_type: Filter by 'feedback' or 'suggestion'
            category: Filter by category name
            status: Filter by status
            user_id: Filter by user (show only their submissions)
            sort_by: Sort by 'votes', 'date', 'updated'
            limit: Number of results
            offset: Pagination offset

        Returns:
            List of submissions
        """
        query = """
            SELECT
                fs.id,
                fs.user_id,
                fs.type,
                fs.title,
                fs.description,
                fs.is_anonymous,
                fs.status,
                fs.priority,
                fs.votes,
                fs.created_at,
                fs.updated_at,
                fc.name as category,
                fc.icon as category_icon,
                CASE
                    WHEN fs.is_anonymous = 1 THEN 'Anonymous'
                    ELSE fs.user_id
                END as display_user
            FROM feedback_submissions fs
            JOIN feedback_categories fc ON fs.category_id = fc.id
            WHERE 1=1
        """
        params = []

        if submission_type:
            query += " AND fs.type = ?"
            params.append(submission_type)

        if category:
            query += " AND fc.name = ?"
            params.append(category)

        if status:
            query += " AND fs.status = ?"
            params.append(status)

        if user_id:
            query += " AND fs.user_id = ?"
            params.append(user_id)

        # Sorting
        if sort_by == "votes":
            query += " ORDER BY fs.votes DESC, fs.created_at DESC"
        elif sort_by == "date":
            query += " ORDER BY fs.created_at DESC"
        elif sort_by == "updated":
            query += " ORDER BY fs.updated_at DESC"
        else:
            query += " ORDER BY fs.created_at DESC"

        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_connection() as conn:
            results = conn.execute(query, params).fetchall()
            return [dict(row) for row in results]

    def get_submission_details(self, submission_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a submission"""
        with get_connection() as conn:
            # Get submission
            submission = conn.execute("""
                SELECT
                    fs.*,
                    fc.name as category,
                    fc.icon as category_icon,
                    fc.description as category_description
                FROM feedback_submissions fs
                JOIN feedback_categories fc ON fs.category_id = fc.id
                WHERE fs.id = ?
            """, (submission_id,)).fetchone()

            if not submission:
                return None

            result = dict(submission)

            # Get responses
            responses = conn.execute("""
                SELECT * FROM feedback_responses
                WHERE submission_id = ?
                ORDER BY created_at DESC
            """, (submission_id,)).fetchall()
            result['responses'] = [dict(r) for r in responses]

            # Get status history
            status_history = conn.execute("""
                SELECT * FROM feedback_status_updates
                WHERE submission_id = ?
                ORDER BY created_at DESC
            """, (submission_id,)).fetchall()
            result['status_history'] = [dict(s) for s in status_history]

            # Get impact data if implemented
            if result['status'] == self.STATUS_IMPLEMENTED:
                impact = conn.execute("""
                    SELECT * FROM feedback_impacts
                    WHERE submission_id = ?
                """, (submission_id,)).fetchone()
                result['impact'] = dict(impact) if impact else None

            # Get vote count and check if user voted
            result['vote_count'] = result['votes']

            return result

    def add_response(
        self,
        submission_id: int,
        responder_id: str,
        responder_name: str,
        response_text: str
    ) -> int:
        """
        Add administrative response to a submission

        Args:
            submission_id: Submission ID
            responder_id: Administrator ID
            responder_name: Administrator name
            response_text: Response message

        Returns:
            Response ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO feedback_responses
                (submission_id, responder_id, responder_name, response_text)
                VALUES (?, ?, ?, ?)
            """, (submission_id, responder_id, responder_name, response_text))

            response_id = cursor.lastrowid

            # Update submission timestamp
            conn.execute("""
                UPDATE feedback_submissions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (submission_id,))

            log_activity(
                'create',
                'feedback_response',
                response_id=response_id,
                details={
                    'submission_id': submission_id,
                    'responder': responder_name
                }
            )

            return response_id

    def update_status(
        self,
        submission_id: int,
        new_status: str,
        updated_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update submission status

        Args:
            submission_id: Submission ID
            new_status: New status value
            updated_by: User making the change
            notes: Optional notes about the change

        Returns:
            True if successful
        """
        with transaction() as conn:
            # Get current status
            current = conn.execute("""
                SELECT status FROM feedback_submissions WHERE id = ?
            """, (submission_id,)).fetchone()

            if not current:
                return False

            old_status = current[0]

            # Update status
            conn.execute("""
                UPDATE feedback_submissions
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_status, submission_id))

            # Record status change
            conn.execute("""
                INSERT INTO feedback_status_updates
                (submission_id, old_status, new_status, updated_by, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (submission_id, old_status, new_status, updated_by, notes))

            log_activity(
                'update',
                'feedback_status',
                submission_id=submission_id,
                details={
                    'old_status': old_status,
                    'new_status': new_status,
                    'updated_by': updated_by
                }
            )

            return True

    def add_impact_data(
        self,
        submission_id: int,
        implementation_date: str,
        users_affected: int,
        satisfaction_increase: float,
        cost_savings: float,
        description: str,
        metrics: Optional[str] = None
    ) -> int:
        """
        Add impact tracking data for implemented suggestions

        Args:
            submission_id: Submission ID
            implementation_date: Date of implementation
            users_affected: Number of users impacted
            satisfaction_increase: Satisfaction increase percentage
            cost_savings: Cost savings amount
            description: Impact description
            metrics: Additional metrics (JSON string)

        Returns:
            Impact record ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO feedback_impacts
                (submission_id, implementation_date, users_affected,
                 satisfaction_increase, cost_savings, description, metrics)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                submission_id, implementation_date, users_affected,
                satisfaction_increase, cost_savings, description, metrics
            ))

            impact_id = cursor.lastrowid

            log_activity(
                'create',
                'feedback_impact',
                impact_id=impact_id,
                details={'submission_id': submission_id}
            )

            return impact_id

    def get_trending_suggestions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending suggestions (high votes, recent activity)

        Args:
            limit: Number of results

        Returns:
            List of trending suggestions
        """
        query = """
            SELECT
                fs.id,
                fs.title,
                fs.description,
                fs.votes,
                fs.status,
                fs.created_at,
                fs.updated_at,
                fc.name as category,
                fc.icon as category_icon,
                COUNT(fr.id) as response_count
            FROM feedback_submissions fs
            JOIN feedback_categories fc ON fs.category_id = fc.id
            LEFT JOIN feedback_responses fr ON fs.id = fr.submission_id
            WHERE fs.type = 'suggestion'
            AND fs.status NOT IN ('Declined', 'Implemented')
            GROUP BY fs.id
            ORDER BY
                fs.votes DESC,
                fs.updated_at DESC,
                response_count DESC
            LIMIT ?
        """

        with get_connection() as conn:
            results = conn.execute(query, (limit,)).fetchall()
            return [dict(row) for row in results]

    def get_implemented_suggestions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get implemented suggestions with impact data

        Args:
            limit: Number of results

        Returns:
            List of implemented suggestions
        """
        query = """
            SELECT
                fs.id,
                fs.title,
                fs.description,
                fs.votes,
                fs.created_at,
                fc.name as category,
                fc.icon as category_icon,
                fi.implementation_date,
                fi.users_affected,
                fi.satisfaction_increase,
                fi.cost_savings,
                fi.description as impact_description
            FROM feedback_submissions fs
            JOIN feedback_categories fc ON fs.category_id = fc.id
            LEFT JOIN feedback_impacts fi ON fs.id = fi.submission_id
            WHERE fs.status = 'Implemented'
            ORDER BY fi.implementation_date DESC, fs.votes DESC
            LIMIT ?
        """

        with get_connection() as conn:
            results = conn.execute(query, (limit,)).fetchall()
            return [dict(row) for row in results]

    def get_user_submissions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all submissions by a specific user"""
        return self.get_submissions(user_id=user_id, limit=100)

    def get_user_votes(self, user_id: str) -> List[int]:
        """Get list of submission IDs that user has voted on"""
        with get_connection() as conn:
            results = conn.execute("""
                SELECT submission_id FROM feedback_votes
                WHERE user_id = ?
            """, (user_id,)).fetchall()
            return [row[0] for row in results]

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall feedback system statistics"""
        with get_connection() as conn:
            stats = {
                'total_submissions': 0,
                'total_feedback': 0,
                'total_suggestions': 0,
                'total_votes': 0,
                'total_responses': 0,
                'by_status': {},
                'by_category': {},
                'implemented_count': 0,
                'average_votes': 0
            }

            # Total submissions
            result = conn.execute(
                "SELECT COUNT(*) FROM feedback_submissions"
            ).fetchone()
            stats['total_submissions'] = result[0]

            # By type
            result = conn.execute("""
                SELECT type, COUNT(*) FROM feedback_submissions
                GROUP BY type
            """).fetchall()
            for row in result:
                if row[0] == 'feedback':
                    stats['total_feedback'] = row[1]
                elif row[0] == 'suggestion':
                    stats['total_suggestions'] = row[1]

            # Total votes
            result = conn.execute("SELECT COUNT(*) FROM feedback_votes").fetchone()
            stats['total_votes'] = result[0]

            # Total responses
            result = conn.execute("SELECT COUNT(*) FROM feedback_responses").fetchone()
            stats['total_responses'] = result[0]

            # By status
            result = conn.execute("""
                SELECT status, COUNT(*) FROM feedback_submissions
                GROUP BY status
            """).fetchall()
            stats['by_status'] = {row[0]: row[1] for row in result}

            # By category
            result = conn.execute("""
                SELECT fc.name, COUNT(fs.id)
                FROM feedback_categories fc
                LEFT JOIN feedback_submissions fs ON fc.id = fs.category_id
                GROUP BY fc.name
            """).fetchall()
            stats['by_category'] = {row[0]: row[1] for row in result}

            # Implemented count
            stats['implemented_count'] = stats['by_status'].get('Implemented', 0)

            # Average votes
            result = conn.execute("""
                SELECT AVG(votes) FROM feedback_submissions
            """).fetchone()
            stats['average_votes'] = round(result[0], 2) if result[0] else 0

            return stats

    def search_submissions(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search submissions by title or description

        Args:
            search_term: Search query
            limit: Number of results

        Returns:
            List of matching submissions
        """
        query = """
            SELECT
                fs.id,
                fs.type,
                fs.title,
                fs.description,
                fs.status,
                fs.votes,
                fs.created_at,
                fc.name as category,
                fc.icon as category_icon
            FROM feedback_submissions fs
            JOIN feedback_categories fc ON fs.category_id = fc.id
            WHERE fs.title LIKE ? OR fs.description LIKE ?
            ORDER BY fs.votes DESC, fs.created_at DESC
            LIMIT ?
        """

        search_pattern = f"%{escape_like(search_term)}%"

        with get_connection() as conn:
            results = conn.execute(
                query, (search_pattern, search_pattern, limit)
            ).fetchall()
            return [dict(row) for row in results]

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories"""
        with get_connection() as conn:
            results = conn.execute("""
                SELECT
                    fc.*,
                    COUNT(fs.id) as submission_count
                FROM feedback_categories fc
                LEFT JOIN feedback_submissions fs ON fc.id = fs.category_id
                GROUP BY fc.id
                ORDER BY fc.name
            """).fetchall()
            return [dict(row) for row in results]

    def has_user_voted(self, submission_id: int, user_id: str) -> bool:
        """Check if user has voted on a submission"""
        with get_connection() as conn:
            result = conn.execute("""
                SELECT 1 FROM feedback_votes
                WHERE submission_id = ? AND user_id = ?
            """, (submission_id, user_id)).fetchone()
            return result is not None

    def delete_submission(self, submission_id: int, user_id: str) -> bool:
        """
        Delete a submission (only by owner or admin)

        Args:
            submission_id: Submission ID
            user_id: User attempting deletion

        Returns:
            True if deleted
        """
        with transaction() as conn:
            # Check ownership
            submission = conn.execute("""
                SELECT user_id FROM feedback_submissions WHERE id = ?
            """, (submission_id,)).fetchone()

            if not submission or submission[0] != user_id:
                return False

            # Delete submission (cascades to votes, responses, etc.)
            conn.execute(
                "DELETE FROM feedback_submissions WHERE id = ?",
                (submission_id,)
            )

            log_activity(
                'delete',
                'feedback_submission',
                submission_id=submission_id,
                details={'user_id': user_id}
            )

            return True
