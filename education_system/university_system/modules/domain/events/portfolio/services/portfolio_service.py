"""
Portfolio Service - Achievement & Portfolio System

Provides comprehensive digital portfolio management including projects, research,
leadership roles, verified badges, skills endorsements, and resume building.
Supports shareable public profiles for internship applications and career services.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import hashlib
import secrets

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier  # nosec B608

class PortfolioService:
    """
    Service for managing student portfolios, achievements, badges, and endorsements.

    Features:
    - Digital portfolio with multiple categories
    - Verified badges and achievements
    - Skills endorsement system
    - Resume builder with achievement integration
    - Public shareable profiles
    - LinkedIn integration support
    - Privacy controls
    """

    def __init__(self):
        """Initialize portfolio service and create database tables."""
        self.auth = get_auth()
        self._initialize_database()
        self._migrate_database()

    def _initialize_database(self):
        """Create all portfolio-related database tables."""
        with transaction() as conn:
            # Portfolios table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    bio TEXT,
                    headline TEXT,
                    profile_image_url TEXT,
                    is_public BOOLEAN DEFAULT 0,
                    public_url TEXT UNIQUE,
                    linkedin_url TEXT,
                    github_url TEXT,
                    personal_website TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Portfolio items table (projects, research, leadership, work experience)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id INTEGER NOT NULL,
                    category TEXT NOT NULL CHECK(category IN (
                        'project', 'research', 'leadership', 'work_experience',
                        'award', 'certification', 'publication', 'presentation'
                    )),
                    title TEXT NOT NULL,
                    description TEXT,
                    organization TEXT,
                    role TEXT,
                    start_date DATE,
                    end_date DATE,
                    is_current BOOLEAN DEFAULT 0,
                    technologies TEXT,
                    achievements TEXT,
                    url TEXT,
                    attachments TEXT,
                    display_order INTEGER DEFAULT 0,
                    is_featured BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id) ON DELETE CASCADE
                )
            """)

            # Badges table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS badges (
                    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    badge_type TEXT NOT NULL CHECK(badge_type IN (
                        'deans_list', 'club_officer', 'volunteer_hours',
                        'certification', 'competition_winner', 'scholarship',
                        'research_publication', 'leadership', 'academic_excellence',
                        'community_service', 'skill_mastery', 'innovation'
                    )),
                    badge_name TEXT NOT NULL,
                    description TEXT,
                    issuer TEXT NOT NULL,
                    issue_date DATE NOT NULL,
                    expiry_date DATE,
                    verification_status TEXT DEFAULT 'verified' CHECK(verification_status IN (
                        'pending', 'verified', 'expired', 'revoked'
                    )),
                    verification_code TEXT,
                    metadata TEXT,
                    icon_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Skills table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_skills (
                    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    skill_category TEXT CHECK(skill_category IN (
                        'technical', 'soft_skill', 'language', 'tool', 'domain'
                    )),
                    proficiency_level TEXT CHECK(proficiency_level IN (
                        'beginner', 'intermediate', 'advanced', 'expert'
                    )),
                    years_experience REAL,
                    is_featured BOOLEAN DEFAULT 0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id, skill_name)
                )
            """)

            # Endorsements table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_endorsements (
                    endorsement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id INTEGER NOT NULL,
                    endorser_id TEXT NOT NULL,
                    endorser_role TEXT CHECK(endorser_role IN (
                        'faculty', 'peer', 'employer', 'mentor'
                    )),
                    comment TEXT,
                    relationship TEXT,
                    endorsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (skill_id) REFERENCES student_skills(skill_id) ON DELETE CASCADE,
                    UNIQUE(skill_id, endorser_id)
                )
            """)

            # Achievements table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    achievement_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    date_achieved DATE NOT NULL,
                    points INTEGER DEFAULT 0,
                    category TEXT,
                    is_verified BOOLEAN DEFAULT 0,
                    verified_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Public profiles table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS public_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    public_url TEXT NOT NULL UNIQUE,
                    visibility TEXT DEFAULT 'private' CHECK(visibility IN (
                        'public', 'private', 'unlisted'
                    )),
                    show_contact BOOLEAN DEFAULT 0,
                    show_gpa BOOLEAN DEFAULT 0,
                    show_courses BOOLEAN DEFAULT 1,
                    show_projects BOOLEAN DEFAULT 1,
                    show_skills BOOLEAN DEFAULT 1,
                    show_endorsements BOOLEAN DEFAULT 1,
                    custom_sections TEXT,
                    theme TEXT DEFAULT 'professional',
                    view_count INTEGER DEFAULT 0,
                    last_viewed TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Resume templates table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resume_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT NOT NULL,
                    template_type TEXT CHECK(template_type IN (
                        'traditional', 'modern', 'creative', 'technical', 'academic'
                    )),
                    template_data TEXT NOT NULL,
                    is_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User resumes table (removed students FK to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_resumes (
                    resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    resume_name TEXT NOT NULL,
                    template_id INTEGER,
                    content TEXT NOT NULL,
                    last_generated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    format TEXT DEFAULT 'pdf' CHECK(format IN ('pdf', 'docx', 'html')),
                    FOREIGN KEY (template_id) REFERENCES resume_templates(template_id)
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_portfolio_student
                ON portfolios(student_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_portfolio_items_portfolio
                ON portfolio_items(portfolio_id, category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_badges_student
                ON badges(student_id, verification_status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_skills_student
                ON student_skills(student_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_endorsements_skill
                ON skill_endorsements(skill_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_public_profiles_url
                ON public_profiles(public_url)
            """)

    def _migrate_database(self):
        """Migrate database schema to add missing columns and remove foreign key constraints."""
        with transaction() as conn:
            # Check if is_featured column exists in student_skills table
            cursor = conn.execute("PRAGMA table_info(student_skills)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'is_featured' not in columns:
                # Add is_featured column to student_skills
                conn.execute("""
                    ALTER TABLE student_skills
                    ADD COLUMN is_featured BOOLEAN DEFAULT 0
                """)
                log_activity('update', 'student_skills_table',
                           details={'migration': 'Added is_featured column'})

            # Remove foreign key constraints to allow any user type
            self._remove_foreign_key_constraints(conn)

    def _remove_foreign_key_constraints(self, conn):
        """Remove foreign key constraints from portfolio tables to allow any user type."""
        try:
            # Check if portfolios table has foreign key
            cursor = conn.execute("""
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='portfolios'
            """)
            result = cursor.fetchone()

            if result and 'FOREIGN KEY' in result[0]:
                # Portfolios table needs migration
                # Create new table without FK constraint
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS portfolios_new (
                        portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        bio TEXT,
                        headline TEXT,
                        profile_image_url TEXT,
                        is_public BOOLEAN DEFAULT 0,
                        public_url TEXT UNIQUE,
                        linkedin_url TEXT,
                        github_url TEXT,
                        personal_website TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Copy data
                conn.execute("""
                    INSERT INTO portfolios_new
                    SELECT portfolio_id, student_id, title, bio, headline,
                           profile_image_url, is_public, public_url,
                           linkedin_url, github_url, personal_website,
                           created_at, updated_at
                    FROM portfolios
                """)

                # Drop old table
                conn.execute("DROP TABLE portfolios")

                # Rename new table
                conn.execute("ALTER TABLE portfolios_new RENAME TO portfolios")

            # Check student_skills table
            cursor = conn.execute("""
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='student_skills'
            """)
            result = cursor.fetchone()

            if result and 'REFERENCES students' in result[0]:
                # Check if is_featured exists first
                cursor = conn.execute("PRAGMA table_info(student_skills)")
                columns = [row[1] for row in cursor.fetchall()]
                has_featured = 'is_featured' in columns

                # Create new table
                featured_col = "is_featured BOOLEAN DEFAULT 0," if has_featured else ""
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS student_skills_new ("
                    " skill_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " student_id TEXT NOT NULL,"
                    " skill_name TEXT NOT NULL,"
                    " skill_category TEXT CHECK(skill_category IN ("
                    "  'technical', 'soft_skill', 'language', 'tool', 'domain'"
                    " )),"
                    " proficiency_level TEXT CHECK(proficiency_level IN ("
                    "  'beginner', 'intermediate', 'advanced', 'expert'"
                    " )),"
                    " years_experience REAL,"
                    " " + featured_col +
                    " added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                    " UNIQUE(student_id, skill_name)"
                    ")"
                )

                # Copy data
                if has_featured:
                    conn.execute("""
                        INSERT INTO student_skills_new
                        SELECT * FROM student_skills
                    """)
                else:
                    conn.execute("""
                        INSERT INTO student_skills_new (
                            skill_id, student_id, skill_name, skill_category,
                            proficiency_level, years_experience, added_at
                        )
                        SELECT skill_id, student_id, skill_name, skill_category,
                               proficiency_level, years_experience, added_at
                        FROM student_skills
                    """)

                conn.execute("DROP TABLE student_skills")
                conn.execute("ALTER TABLE student_skills_new RENAME TO student_skills")

            # Rebuild other tables that still carry a REFERENCES students(...) FK.
            # SQLite can't drop an FK in place, so we copy data into a new
            # FK-free table and swap it in.
            for table_name in ['badges', 'public_profiles', 'user_resumes']:
                safe_table = validate_table_name(table_name)
                cursor = conn.execute(
                    "SELECT sql FROM sqlite_master"
                    " WHERE type='table' AND name=?",
                    (safe_table,))
                result = cursor.fetchone()

                if not result or 'REFERENCES students' not in result[0]:
                    continue

                # Discover columns present on the legacy table so INSERT ... SELECT
                # matches regardless of schema drift.
                cols = [row[1] for row in conn.execute(
                    "PRAGMA table_info(" + safe_table + ")").fetchall()]
                col_list = ", ".join(cols)

                if table_name == 'badges':
                    conn.execute("""
                        CREATE TABLE badges_new (
                            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            badge_type TEXT NOT NULL CHECK(badge_type IN (
                                'deans_list', 'club_officer', 'volunteer_hours',
                                'certification', 'competition_winner', 'scholarship',
                                'research_publication', 'leadership', 'academic_excellence',
                                'community_service', 'skill_mastery', 'innovation'
                            )),
                            badge_name TEXT NOT NULL,
                            description TEXT,
                            issuer TEXT NOT NULL,
                            issue_date DATE NOT NULL,
                            expiry_date DATE,
                            verification_status TEXT DEFAULT 'verified' CHECK(verification_status IN (
                                'pending', 'verified', 'expired', 'revoked'
                            )),
                            verification_code TEXT,
                            metadata TEXT,
                            icon_url TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                elif table_name == 'public_profiles':
                    conn.execute("""
                        CREATE TABLE public_profiles_new (
                            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL UNIQUE,
                            public_url TEXT NOT NULL UNIQUE,
                            visibility TEXT DEFAULT 'private' CHECK(visibility IN (
                                'public', 'private', 'unlisted'
                            )),
                            show_contact BOOLEAN DEFAULT 0,
                            show_gpa BOOLEAN DEFAULT 0,
                            show_courses BOOLEAN DEFAULT 1,
                            show_projects BOOLEAN DEFAULT 1,
                            show_skills BOOLEAN DEFAULT 1,
                            show_endorsements BOOLEAN DEFAULT 1,
                            custom_sections TEXT,
                            theme TEXT DEFAULT 'professional',
                            view_count INTEGER DEFAULT 0,
                            last_viewed TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                else:  # user_resumes
                    conn.execute("""
                        CREATE TABLE user_resumes_new (
                            resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            resume_name TEXT NOT NULL,
                            template_id INTEGER,
                            content TEXT NOT NULL,
                            last_generated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            format TEXT DEFAULT 'pdf' CHECK(format IN ('pdf', 'docx', 'html')),
                            FOREIGN KEY (template_id) REFERENCES resume_templates(template_id)
                        )
                    """)

                conn.execute(
                    "INSERT INTO " + safe_table + "_new (" + col_list + ") "
                    "SELECT " + col_list + " FROM " + safe_table
                )
                conn.execute("DROP TABLE " + safe_table)
                conn.execute("ALTER TABLE " + safe_table + "_new RENAME TO " + safe_table)

            log_activity('update', 'portfolio_tables',
                       details={'migration': 'Removed foreign key constraints'})

        except Exception as e:
            # Log error but don't fail - table might not exist yet
            print(f"FK migration note: {e}")

    # Portfolio Management
    def create_portfolio(
        self,
        student_id: str,
        title: str,
        bio: str = None,
        headline: str = None,
        **kwargs
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new portfolio for a student.

        Args:
            student_id: Student identifier
            title: Portfolio title
            bio: Biography/about section
            headline: Professional headline
            **kwargs: Additional fields (linkedin_url, github_url, etc.)

        Returns:
            Tuple of (success, message, portfolio_id)
        """
        try:
            # Validate required fields
            if not student_id:
                return False, "Student ID is required", None
            if not title:
                return False, "Portfolio title is required", None

            # Check if portfolio already exists
            with get_connection() as conn:
                existing = conn.execute(
                    "SELECT portfolio_id FROM portfolios WHERE student_id = ?",
                    (student_id,)
                ).fetchone()

                if existing:
                    return False, "Portfolio already exists for this student", None

            # Generate unique public URL
            public_url = self._generate_public_url(student_id)

            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO portfolios (
                        student_id, title, bio, headline, public_url,
                        linkedin_url, github_url, personal_website
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    student_id, title, bio, headline, public_url,
                    kwargs.get('linkedin_url'),
                    kwargs.get('github_url'),
                    kwargs.get('personal_website')
                ))

                portfolio_id = cursor.lastrowid

                # Create associated public profile
                conn.execute("""
                    INSERT INTO public_profiles (student_id, public_url)
                    VALUES (?, ?)
                """, (student_id, public_url))

            log_activity(
                'create', 'portfolio',
                details={'portfolio_id': portfolio_id, 'student_id': student_id, 'title': title}
            )

            return True, f"Portfolio created successfully (ID: {portfolio_id})", portfolio_id

        except Exception as e:
            return False, f"Error creating portfolio: {str(e)}", None

    def update_portfolio(
        self,
        portfolio_id: int,
        **updates
    ) -> Tuple[bool, str]:
        """
        Update portfolio information.

        Args:
            portfolio_id: Portfolio identifier
            **updates: Fields to update

        Returns:
            Tuple of (success, message)
        """
        try:
            allowed_fields = [
                'title', 'bio', 'headline', 'profile_image_url',
                'is_public', 'linkedin_url', 'github_url', 'personal_website'
            ]

            update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

            if not update_fields:
                return False, "No valid fields to update"

            update_fields['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join([f"{validate_identifier(k, 'column')} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [portfolio_id]

            with transaction() as conn:
                conn.execute(
                    f"UPDATE portfolios SET {set_clause} WHERE portfolio_id = ?",
                    values
                )

            log_activity(
                'update', 'portfolio',
                details={'portfolio_id': portfolio_id, 'updates': list(update_fields.keys())}
            )

            return True, "Portfolio updated successfully"

        except Exception as e:
            return False, f"Error updating portfolio: {str(e)}"

    def get_portfolio(self, student_id: str) -> Optional[Dict]:
        """Get portfolio for a student."""
        try:
            with get_connection() as conn:
                portfolio = conn.execute("""
                    SELECT * FROM portfolios WHERE student_id = ?
                """, (student_id,)).fetchone()

                if not portfolio:
                    return None

                portfolio_dict = dict(portfolio)

                # Get portfolio items
                items = conn.execute("""
                    SELECT * FROM portfolio_items
                    WHERE portfolio_id = ?
                    ORDER BY is_featured DESC, display_order, created_at DESC
                """, (portfolio_dict['portfolio_id'],)).fetchall()

                portfolio_dict['items'] = [dict(item) for item in items]

                # Get items grouped by category
                portfolio_dict['items_by_category'] = {}
                for item in portfolio_dict['items']:
                    category = item['category']
                    if category not in portfolio_dict['items_by_category']:
                        portfolio_dict['items_by_category'][category] = []
                    portfolio_dict['items_by_category'][category].append(item)

                return portfolio_dict

        except Exception as e:
            print(f"Error getting portfolio: {e}")
            return None

    # Portfolio Items Management
    def add_portfolio_item(
        self,
        portfolio_id: int,
        category: str,
        title: str,
        description: str = None,
        **kwargs
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Add an item to portfolio (project, research, leadership, etc.).

        Args:
            portfolio_id: Portfolio identifier
            category: Item category
            title: Item title
            description: Item description
            **kwargs: Additional fields (organization, role, dates, etc.)

        Returns:
            Tuple of (success, message, item_id)
        """
        try:
            valid_categories = [
                'project', 'research', 'leadership', 'work_experience',
                'award', 'certification', 'publication', 'presentation'
            ]

            if category not in valid_categories:
                return False, f"Invalid category. Must be one of: {', '.join(valid_categories)}", None

            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO portfolio_items (
                        portfolio_id, category, title, description,
                        organization, role, start_date, end_date, is_current,
                        technologies, achievements, url, attachments,
                        display_order, is_featured
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    portfolio_id, category, title, description,
                    kwargs.get('organization'),
                    kwargs.get('role'),
                    kwargs.get('start_date'),
                    kwargs.get('end_date'),
                    kwargs.get('is_current', False),
                    kwargs.get('technologies'),
                    kwargs.get('achievements'),
                    kwargs.get('url'),
                    kwargs.get('attachments'),
                    kwargs.get('display_order', 0),
                    kwargs.get('is_featured', False)
                ))

                item_id = cursor.lastrowid

                # Update portfolio timestamp
                conn.execute("""
                    UPDATE portfolios
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE portfolio_id = ?
                """, (portfolio_id,))

            log_activity(
                'create', 'portfolio_item',
                details={'item_id': item_id, 'portfolio_id': portfolio_id, 'category': category, 'title': title}
            )

            return True, f"Portfolio item added successfully (ID: {item_id})", item_id

        except Exception as e:
            return False, f"Error adding portfolio item: {str(e)}", None

    def update_portfolio_item(
        self,
        item_id: int,
        **updates
    ) -> Tuple[bool, str]:
        """Update a portfolio item."""
        try:
            allowed_fields = [
                'title', 'description', 'organization', 'role',
                'start_date', 'end_date', 'is_current', 'technologies',
                'achievements', 'url', 'attachments', 'display_order', 'is_featured'
            ]

            update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

            if not update_fields:
                return False, "No valid fields to update"

            update_fields['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join([f"{validate_identifier(k, 'column')} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [item_id]

            with transaction() as conn:
                conn.execute(
                    f"UPDATE portfolio_items SET {set_clause} WHERE item_id = ?",
                    values
                )

            log_activity('update', 'portfolio_item', details={'item_id': item_id})

            return True, "Portfolio item updated successfully"

        except Exception as e:
            return False, f"Error updating portfolio item: {str(e)}"

    def delete_portfolio_item(self, item_id: int) -> Tuple[bool, str]:
        """Delete a portfolio item."""
        try:
            with transaction() as conn:
                conn.execute("DELETE FROM portfolio_items WHERE item_id = ?", (item_id,))

            log_activity('delete', 'portfolio_item', details={'item_id': item_id})
            return True, "Portfolio item deleted successfully"

        except Exception as e:
            return False, f"Error deleting portfolio item: {str(e)}"

    def get_portfolio_items(
        self,
        portfolio_id: int,
        category: str = None,
        featured_only: bool = False
    ) -> List[Dict]:
        """Get portfolio items with optional filtering."""
        try:
            with get_connection() as conn:
                query = "SELECT * FROM portfolio_items WHERE portfolio_id = ?"
                params = [portfolio_id]

                if category:
                    query += " AND category = ?"
                    params.append(category)

                if featured_only:
                    query += " AND is_featured = 1"

                query += " ORDER BY is_featured DESC, display_order, created_at DESC"

                items = conn.execute(query, params).fetchall()
                return [dict(item) for item in items]

        except Exception as e:
            print(f"Error getting portfolio items: {e}")
            return []

    # Badge Management
    def award_badge(
        self,
        student_id: str,
        badge_type: str,
        badge_name: str,
        issuer: str,
        description: str = None,
        issue_date: str = None,
        **kwargs
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Award a verified badge to a student.

        Args:
            student_id: Student identifier
            badge_type: Type of badge
            badge_name: Badge name
            issuer: Issuing authority
            description: Badge description
            issue_date: Date of issue
            **kwargs: Additional fields

        Returns:
            Tuple of (success, message, badge_id)
        """
        try:
            if not issue_date:
                issue_date = datetime.now().date().isoformat()

            # Generate verification code
            verification_code = self._generate_verification_code()

            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO badges (
                        student_id, badge_type, badge_name, description,
                        issuer, issue_date, expiry_date, verification_code,
                        metadata, icon_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    student_id, badge_type, badge_name, description,
                    issuer, issue_date, kwargs.get('expiry_date'),
                    verification_code, kwargs.get('metadata'), kwargs.get('icon_url')
                ))

                badge_id = cursor.lastrowid

            log_activity(
                'award', 'badge',
                badge_id=badge_id,
                details={'student_id': student_id, 'badge_type': badge_type, 'badge_name': badge_name}
            )

            return True, f"Badge awarded successfully (ID: {badge_id})", badge_id

        except Exception as e:
            return False, f"Error awarding badge: {str(e)}", None

    def get_student_badges(
        self,
        student_id: str,
        verified_only: bool = True
    ) -> List[Dict]:
        """Get all badges for a student."""
        try:
            with get_connection() as conn:
                query = "SELECT * FROM badges WHERE student_id = ?"
                params = [student_id]

                if verified_only:
                    query += " AND verification_status = 'verified'"

                query += " ORDER BY issue_date DESC"

                badges = conn.execute(query, params).fetchall()
                return [dict(badge) for badge in badges]

        except Exception as e:
            print(f"Error getting badges: {e}")
            return []

    def verify_badge(self, verification_code: str) -> Optional[Dict]:
        """Verify a badge using verification code."""
        try:
            with get_connection() as conn:
                badge = conn.execute("""
                    SELECT * FROM badges WHERE verification_code = ?
                """, (verification_code,)).fetchone()

                return dict(badge) if badge else None

        except Exception as e:
            print(f"Error verifying badge: {e}")
            return None

    # Skills Management
    def add_skill(
        self,
        student_id: str,
        skill_name: str,
        skill_category: str = None,
        proficiency_level: str = None,
        years_experience: float = None,
        is_featured: bool = False
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Add a skill to student's profile.

        Args:
            student_id: Student identifier
            skill_name: Name of the skill
            skill_category: Category (technical, soft_skill, language, tool, domain)
            proficiency_level: Proficiency (beginner, intermediate, advanced, expert)
            years_experience: Years of experience
            is_featured: Whether to feature this skill

        Returns:
            Tuple of (success, message, skill_id)
        """
        try:
            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO student_skills (
                        student_id, skill_name, skill_category,
                        proficiency_level, years_experience, is_featured
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    student_id, skill_name, skill_category,
                    proficiency_level, years_experience, is_featured
                ))

                skill_id = cursor.lastrowid

            log_activity(
                'add', 'skill',
                skill_id=skill_id,
                details={'student_id': student_id, 'skill_name': skill_name}
            )

            return True, f"Skill added successfully (ID: {skill_id})", skill_id

        except sqlite3.IntegrityError:
            return False, "Skill already exists for this student", None
        except Exception as e:
            return False, f"Error adding skill: {str(e)}", None

    def update_skill(
        self,
        skill_id: int,
        **updates
    ) -> Tuple[bool, str]:
        """Update skill information."""
        try:
            allowed_fields = [
                'skill_category', 'proficiency_level', 'years_experience', 'is_featured'
            ]

            update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

            if not update_fields:
                return False, "No valid fields to update"

            set_clause = ', '.join([f"{validate_identifier(k, 'column')} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [skill_id]

            with transaction() as conn:
                conn.execute(
                    f"UPDATE student_skills SET {set_clause} WHERE skill_id = ?",
                    values
                )

            log_activity('update', 'skill', details={'skill_id': skill_id})
            return True, "Skill updated successfully"

        except Exception as e:
            return False, f"Error updating skill: {str(e)}"

    def remove_skill(self, skill_id: int) -> Tuple[bool, str]:
        """Remove a skill from student's profile."""
        try:
            with transaction() as conn:
                conn.execute("DELETE FROM student_skills WHERE skill_id = ?", (skill_id,))

            log_activity('remove', 'skill', details={'skill_id': skill_id})
            return True, "Skill removed successfully"

        except Exception as e:
            return False, f"Error removing skill: {str(e)}"

    def get_student_skills(self, student_id: str) -> List[Dict]:
        """Get all skills for a student with endorsement counts."""
        try:
            with get_connection() as conn:
                skills = conn.execute("""
                    SELECT
                        s.*,
                        COUNT(DISTINCT e.endorsement_id) as endorsement_count,
                        COUNT(DISTINCT CASE WHEN e.endorser_role = 'faculty'
                              THEN e.endorsement_id END) as faculty_endorsements,
                        COUNT(DISTINCT CASE WHEN e.endorser_role = 'peer'
                              THEN e.endorsement_id END) as peer_endorsements
                    FROM student_skills s
                    LEFT JOIN skill_endorsements e ON s.skill_id = e.skill_id
                    WHERE s.student_id = ?
                    GROUP BY s.skill_id
                    ORDER BY s.is_featured DESC, endorsement_count DESC, s.skill_name
                """, (student_id,)).fetchall()

                return [dict(skill) for skill in skills]

        except Exception as e:
            print(f"Error getting skills: {e}")
            return []

    # Endorsement Management
    def request_endorsement(
        self,
        skill_id: int,
        endorser_id: str,
        message: str = None
    ) -> Tuple[bool, str]:
        """
        Request a skill endorsement from another user.

        Note: This creates a pending request that would be handled
        by a notification system in production.
        """
        # In a real system, this would send a notification/email
        # For now, we'll just log the request
        log_activity(
            'request', 'skill_endorsement',
            skill_id=skill_id,
            details={'endorser_id': endorser_id, 'message': message}
        )

        return True, f"Endorsement request sent to {endorser_id}"

    def endorse_skill(
        self,
        skill_id: int,
        endorser_id: str,
        endorser_role: str,
        comment: str = None,
        relationship: str = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Endorse a student's skill.

        Args:
            skill_id: Skill identifier
            endorser_id: User providing endorsement
            endorser_role: Role of endorser (faculty, peer, employer, mentor)
            comment: Optional comment
            relationship: Relationship to student

        Returns:
            Tuple of (success, message, endorsement_id)
        """
        try:
            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO skill_endorsements (
                        skill_id, endorser_id, endorser_role, comment, relationship
                    ) VALUES (?, ?, ?, ?, ?)
                """, (skill_id, endorser_id, endorser_role, comment, relationship))

                endorsement_id = cursor.lastrowid

            log_activity(
                'endorse', 'skill',
                endorsement_id=endorsement_id,
                details={'skill_id': skill_id, 'endorser_id': endorser_id}
            )

            return True, "Skill endorsed successfully", endorsement_id

        except sqlite3.IntegrityError:
            return False, "You have already endorsed this skill", None
        except Exception as e:
            return False, f"Error endorsing skill: {str(e)}", None

    def get_skill_endorsements(self, skill_id: int) -> List[Dict]:
        """Get all endorsements for a skill."""
        try:
            with get_connection() as conn:
                endorsements = conn.execute("""
                    SELECT * FROM skill_endorsements
                    WHERE skill_id = ?
                    ORDER BY endorsed_at DESC
                """, (skill_id,)).fetchall()

                return [dict(e) for e in endorsements]

        except Exception as e:
            print(f"Error getting endorsements: {e}")
            return []

    def get_student_endorsements(self, student_id: str) -> List[Dict]:
        """Get all endorsements received by a student."""
        try:
            with get_connection() as conn:
                endorsements = conn.execute("""
                    SELECT
                        e.*,
                        s.skill_name,
                        s.skill_category
                    FROM skill_endorsements e
                    JOIN student_skills s ON e.skill_id = s.skill_id
                    WHERE s.student_id = ?
                    ORDER BY e.endorsed_at DESC
                """, (student_id,)).fetchall()

                return [dict(e) for e in endorsements]

        except Exception as e:
            print(f"Error getting student endorsements: {e}")
            return []

    # Achievement Management
    def add_achievement(
        self,
        student_id: str,
        achievement_type: str,
        title: str,
        description: str = None,
        date_achieved: str = None,
        points: int = 0,
        category: str = None
    ) -> Tuple[bool, str, Optional[int]]:
        """Add an achievement to student's record."""
        try:
            if not date_achieved:
                date_achieved = datetime.now().date().isoformat()

            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO achievements (
                        student_id, achievement_type, title, description,
                        date_achieved, points, category
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    student_id, achievement_type, title, description,
                    date_achieved, points, category
                ))

                achievement_id = cursor.lastrowid

            log_activity(
                'add', 'achievement',
                achievement_id=achievement_id,
                details={'student_id': student_id, 'title': title}
            )

            return True, f"Achievement added (ID: {achievement_id})", achievement_id

        except Exception as e:
            return False, f"Error adding achievement: {str(e)}", None

    def get_student_achievements(self, student_id: str) -> List[Dict]:
        """Get all achievements for a student."""
        try:
            with get_connection() as conn:
                achievements = conn.execute("""
                    SELECT * FROM achievements
                    WHERE student_id = ?
                    ORDER BY date_achieved DESC
                """, (student_id,)).fetchall()

                return [dict(a) for a in achievements]

        except Exception as e:
            print(f"Error getting achievements: {e}")
            return []

    # Public Profile Management
    def update_public_profile(
        self,
        student_id: str,
        **settings
    ) -> Tuple[bool, str]:
        """
        Update public profile settings and visibility.

        Args:
            student_id: Student identifier
            **settings: Profile settings (visibility, show_contact, etc.)

        Returns:
            Tuple of (success, message)
        """
        try:
            allowed_fields = [
                'visibility', 'show_contact', 'show_gpa', 'show_courses',
                'show_projects', 'show_skills', 'show_endorsements',
                'custom_sections', 'theme'
            ]

            update_fields = {k: v for k, v in settings.items() if k in allowed_fields}

            if not update_fields:
                return False, "No valid settings to update"

            update_fields['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join([f"{validate_identifier(k, 'column')} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [student_id]

            with transaction() as conn:
                conn.execute(
                    f"UPDATE public_profiles SET {set_clause} WHERE student_id = ?",
                    values
                )

            log_activity(
                'update', 'public_profile',
                student_id=student_id,
                details={'settings': list(update_fields.keys())}
            )

            return True, "Public profile updated successfully"

        except Exception as e:
            return False, f"Error updating public profile: {str(e)}"

    def get_public_profile(self, student_id: str) -> Optional[Dict]:
        """Get public profile settings for a student."""
        try:
            with get_connection() as conn:
                profile = conn.execute("""
                    SELECT * FROM public_profiles WHERE student_id = ?
                """, (student_id,)).fetchone()

                return dict(profile) if profile else None

        except Exception as e:
            print(f"Error getting public profile: {e}")
            return None

    def get_public_portfolio(self, public_url: str) -> Optional[Dict]:
        """
        Get publicly accessible portfolio data using public URL.
        Respects privacy settings.
        """
        try:
            with transaction() as conn:
                # Update view count
                conn.execute("""
                    UPDATE public_profiles
                    SET view_count = view_count + 1, last_viewed = CURRENT_TIMESTAMP
                    WHERE public_url = ? AND visibility IN ('public', 'unlisted')
                """, (public_url,))

            with get_connection() as conn:
                # Get profile settings
                profile = conn.execute("""
                    SELECT * FROM public_profiles
                    WHERE public_url = ? AND visibility IN ('public', 'unlisted')
                """, (public_url,)).fetchone()

                if not profile:
                    return None

                profile_dict = dict(profile)
                student_id = profile_dict['student_id']

                # Get portfolio
                portfolio = conn.execute("""
                    SELECT * FROM portfolios WHERE student_id = ?
                """, (student_id,)).fetchone()

                if not portfolio:
                    return None

                result = dict(portfolio)
                result['profile_settings'] = profile_dict

                # Get data based on privacy settings
                if profile_dict['show_projects']:
                    items = conn.execute("""
                        SELECT * FROM portfolio_items
                        WHERE portfolio_id = ?
                        ORDER BY is_featured DESC, display_order
                    """, (result['portfolio_id'],)).fetchall()
                    result['items'] = [dict(item) for item in items]

                if profile_dict['show_skills']:
                    result['skills'] = self.get_student_skills(student_id)

                if profile_dict['show_endorsements']:
                    result['endorsements'] = self.get_student_endorsements(student_id)

                # Always show badges (they're verified)
                result['badges'] = self.get_student_badges(student_id)

                return result

        except Exception as e:
            print(f"Error getting public portfolio: {e}")
            return None

    def get_portfolio_url(self, student_id: str) -> Optional[str]:
        """Get the public URL for a student's portfolio."""
        try:
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT public_url FROM public_profiles WHERE student_id = ?
                """, (student_id,)).fetchone()

                return result['public_url'] if result else None

        except Exception as e:
            print(f"Error getting portfolio URL: {e}")
            return None

    # Resume Building
    def generate_resume(
        self,
        student_id: str,
        resume_name: str,
        template_type: str = 'traditional',
        sections: List[str] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Generate a resume from portfolio data.

        Args:
            student_id: Student identifier
            resume_name: Name for the resume
            template_type: Type of template
            sections: Sections to include

        Returns:
            Tuple of (success, message, resume_data)
        """
        try:
            # Default sections if not specified
            if sections is None:
                sections = [
                    'education', 'experience', 'projects', 'skills',
                    'achievements', 'certifications'
                ]

            # Gather data for resume
            resume_data = {
                'student_id': student_id,
                'generated_at': datetime.now().isoformat(),
                'template_type': template_type,
                'sections': {}
            }

            with get_connection() as conn:
                # Try the students table first; fall back to users so portfolios
                # work for any logged-in account (admin, staff, alumni, etc.).
                student = conn.execute(
                    "SELECT * FROM students WHERE student_id = ?",
                    (student_id,),
                ).fetchone()
                if student:
                    resume_data['student_info'] = dict(student)
                else:
                    user = conn.execute(
                        "SELECT username, first_name, last_name, email, role"
                        " FROM users WHERE username = ? OR student_id = ?",
                        (student_id, student_id),
                    ).fetchone()
                    if user:
                        resume_data['student_info'] = dict(user)
                    else:
                        # Last resort: synthesise a minimal info block so resume
                        # generation never fails purely because the user record
                        # lives in a different table.
                        resume_data['student_info'] = {
                            'student_id': student_id,
                            'first_name': '',
                            'last_name': '',
                            'email': '',
                        }

                # Get portfolio
                portfolio = self.get_portfolio(student_id)
                if portfolio:
                    resume_data['portfolio'] = portfolio

                # Get skills
                if 'skills' in sections:
                    resume_data['sections']['skills'] = self.get_student_skills(student_id)

                # Get achievements
                if 'achievements' in sections:
                    resume_data['sections']['achievements'] = self.get_student_achievements(student_id)

                # Get badges
                if 'certifications' in sections:
                    resume_data['sections']['badges'] = self.get_student_badges(student_id)

                # Get experience items
                if 'experience' in sections and portfolio:
                    resume_data['sections']['experience'] = [
                        item for item in portfolio['items']
                        if item['category'] in ['work_experience', 'leadership']
                    ]

                # Get projects
                if 'projects' in sections and portfolio:
                    resume_data['sections']['projects'] = [
                        item for item in portfolio['items']
                        if item['category'] in ['project', 'research']
                    ]

            # Save resume
            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO user_resumes (
                        student_id, resume_name, content
                    ) VALUES (?, ?, ?)
                """, (student_id, resume_name, json.dumps(resume_data)))

                resume_id = cursor.lastrowid

            resume_data['resume_id'] = resume_id

            log_activity(
                'generate', 'resume',
                resume_id=resume_id,
                details={'student_id': student_id, 'template_type': template_type}
            )

            return True, f"Resume generated successfully (ID: {resume_id})", resume_data

        except Exception as e:
            return False, f"Error generating resume: {str(e)}", None

    def get_student_resumes(self, student_id: str) -> List[Dict]:
        """Get all resumes for a student."""
        try:
            with get_connection() as conn:
                resumes = conn.execute("""
                    SELECT
                        resume_id, student_id, resume_name,
                        last_generated, format
                    FROM user_resumes
                    WHERE student_id = ?
                    ORDER BY last_generated DESC
                """, (student_id,)).fetchall()

                return [dict(r) for r in resumes]

        except Exception as e:
            print(f"Error getting resumes: {e}")
            return []

    def get_resume(self, resume_id: int) -> Optional[Dict]:
        """Get a specific resume with full content."""
        try:
            with get_connection() as conn:
                resume = conn.execute("""
                    SELECT * FROM user_resumes WHERE resume_id = ?
                """, (resume_id,)).fetchone()

                if not resume:
                    return None

                resume_dict = dict(resume)
                resume_dict['content'] = json.loads(resume_dict['content'])
                return resume_dict

        except Exception as e:
            print(f"Error getting resume: {e}")
            return None

    # Statistics and Analytics
    def get_portfolio_stats(self, student_id: str) -> Dict:
        """Get comprehensive portfolio statistics."""
        try:
            with get_connection() as conn:
                stats = {}

                # Portfolio items count by category
                items_count = conn.execute("""
                    SELECT category, COUNT(*) as count
                    FROM portfolio_items pi
                    JOIN portfolios p ON pi.portfolio_id = p.portfolio_id
                    WHERE p.student_id = ?
                    GROUP BY category
                """, (student_id,)).fetchall()

                stats['items_by_category'] = {row['category']: row['count'] for row in items_count}

                # Total items
                stats['total_items'] = sum(stats['items_by_category'].values())

                # Badge count
                badge_count = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM badges
                    WHERE student_id = ? AND verification_status = 'verified'
                """, (student_id,)).fetchone()

                stats['verified_badges'] = badge_count['count']

                # Skills count
                skills_count = conn.execute("""
                    SELECT COUNT(*) as count FROM student_skills WHERE student_id = ?
                """, (student_id,)).fetchone()

                stats['total_skills'] = skills_count['count']

                # Endorsements received
                endorsements_count = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM skill_endorsements e
                    JOIN student_skills s ON e.skill_id = s.skill_id
                    WHERE s.student_id = ?
                """, (student_id,)).fetchone()

                stats['total_endorsements'] = endorsements_count['count']

                # Profile views
                profile = conn.execute("""
                    SELECT view_count, visibility
                    FROM public_profiles
                    WHERE student_id = ?
                """, (student_id,)).fetchone()

                if profile:
                    stats['profile_views'] = profile['view_count']
                    stats['profile_visibility'] = profile['visibility']
                else:
                    stats['profile_views'] = 0
                    stats['profile_visibility'] = 'private'

                # Achievement points
                points = conn.execute("""
                    SELECT SUM(points) as total_points
                    FROM achievements
                    WHERE student_id = ?
                """, (student_id,)).fetchone()

                stats['achievement_points'] = points['total_points'] or 0

                # Completeness score (0-100)
                completeness = 0
                if stats['total_items'] > 0:
                    completeness += 30
                if stats['total_skills'] >= 5:
                    completeness += 20
                if stats['verified_badges'] > 0:
                    completeness += 20
                if stats['total_endorsements'] > 0:
                    completeness += 15

                # Check if portfolio has bio
                portfolio = conn.execute("""
                    SELECT bio FROM portfolios WHERE student_id = ?
                """, (student_id,)).fetchone()

                if portfolio and portfolio['bio']:
                    completeness += 15

                stats['completeness_score'] = completeness

                return stats

        except Exception as e:
            print(f"Error getting portfolio stats: {e}")
            return {}

    # Helper Methods
    def _generate_public_url(self, student_id: str) -> str:
        """Generate a unique public URL for portfolio."""
        if not student_id:
            # Fallback if student_id is None or empty
            student_id = f"student-{secrets.token_hex(4)}"

        # Create URL-friendly string from student_id
        base = str(student_id).lower().replace(' ', '-')
        # Add random suffix for uniqueness
        suffix = secrets.token_hex(4)
        return f"{base}-{suffix}"

    def _generate_verification_code(self) -> str:
        """Generate a verification code for badges."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(8)
        return f"{timestamp}-{random_part}"
