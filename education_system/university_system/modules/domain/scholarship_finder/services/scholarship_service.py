"""
Scholarship Finder Service

Advanced scholarship discovery and management system for students.
Provides personalized recommendations, application tracking, deadline
management, and document vault integration.

Features:
- Personalized scholarship recommendations based on student profile
- External and internal scholarship database
- Application deadline tracking and reminders
- Document vault for required materials
- Eligibility matching and scoring
- Application progress tracking
- Award history and statistics
"""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.exceptions import DatabaseError, ValidationError
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.core.sql_safety import validate_identifier, escape_like

class ScholarshipDatabase:
    """Manages scholarship database and discovery"""

    @staticmethod
    def create_tables() -> None:
        """Create all required tables for scholarship finder"""
        try:
            with transaction() as conn:
                # Extended scholarships table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS scholarship_opportunities (
                        scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scholarship_name TEXT NOT NULL,
                        organization TEXT NOT NULL,
                        organization_type TEXT CHECK(organization_type IN ('university', 'government', 'private', 'corporate', 'foundation', 'nonprofit', 'community')),
                        award_amount_min REAL,
                        award_amount_max REAL,
                        award_type TEXT CHECK(award_type IN ('one-time', 'renewable', 'multi-year')),
                        description TEXT,
                        detailed_requirements TEXT,
                        eligibility_criteria TEXT,
                        academic_level TEXT CHECK(academic_level IN ('freshman', 'sophomore', 'junior', 'senior', 'graduate', 'any')),
                        min_gpa REAL,
                        max_gpa REAL,
                        required_majors TEXT,
                        excluded_majors TEXT,
                        required_enrollment_status TEXT,
                        citizenship_requirements TEXT,
                        state_residency_requirements TEXT,
                        financial_need_required BOOLEAN DEFAULT 0,
                        merit_based BOOLEAN DEFAULT 0,
                        demographic_requirements TEXT,
                        special_criteria TEXT,
                        application_url TEXT,
                        application_deadline TEXT NOT NULL,
                        notification_date TEXT,
                        award_disbursement_date TEXT,
                        renewable_terms TEXT,
                        number_of_awards INTEGER,
                        estimated_applicants INTEGER,
                        competition_level TEXT CHECK(competition_level IN ('low', 'moderate', 'high', 'very-high')),
                        required_documents TEXT,
                        essay_required BOOLEAN DEFAULT 0,
                        essay_prompts TEXT,
                        recommendation_letters_required INTEGER DEFAULT 0,
                        transcript_required BOOLEAN DEFAULT 0,
                        interview_required BOOLEAN DEFAULT 0,
                        contact_email TEXT,
                        contact_phone TEXT,
                        tags TEXT,
                        source TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        is_internal BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Student scholarship profiles
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_scholarship_profiles (
                        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL UNIQUE,
                        citizenship_status TEXT,
                        state_residency TEXT,
                        ethnicity TEXT,
                        gender TEXT,
                        first_generation BOOLEAN DEFAULT 0,
                        military_affiliation TEXT,
                        disability_status TEXT,
                        financial_need_level TEXT CHECK(financial_need_level IN ('none', 'low', 'moderate', 'high', 'exceptional')),
                        intended_career_field TEXT,
                        community_service_hours INTEGER DEFAULT 0,
                        leadership_positions TEXT,
                        academic_honors TEXT,
                        extracurricular_activities TEXT,
                        special_talents TEXT,
                        languages_spoken TEXT,
                        study_abroad_interest BOOLEAN DEFAULT 0,
                        research_interest BOOLEAN DEFAULT 0,
                        preferred_scholarship_types TEXT,
                        minimum_award_amount REAL,
                        willing_to_write_essays BOOLEAN DEFAULT 1,
                        max_recommendation_letters INTEGER DEFAULT 3,
                        profile_completeness REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id)
                    )
                ''')

                # Student scholarship applications
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_scholarship_applications (
                        application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scholarship_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        application_date TEXT DEFAULT (date('now')),
                        deadline_date TEXT NOT NULL,
                        status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'in-progress', 'submitted', 'under-review', 'finalist', 'awarded', 'denied', 'withdrawn')),
                        match_score REAL,
                        estimated_competition TEXT,
                        essay_completed BOOLEAN DEFAULT 0,
                        recommendations_obtained INTEGER DEFAULT 0,
                        recommendations_required INTEGER DEFAULT 0,
                        transcript_uploaded BOOLEAN DEFAULT 0,
                        documents_completed BOOLEAN DEFAULT 0,
                        application_progress REAL DEFAULT 0.0,
                        submission_date TEXT,
                        notification_received BOOLEAN DEFAULT 0,
                        notification_date TEXT,
                        award_amount REAL,
                        award_accepted BOOLEAN DEFAULT 0,
                        acceptance_date TEXT,
                        decline_reason TEXT,
                        notes TEXT,
                        reminder_sent BOOLEAN DEFAULT 0,
                        last_reminder_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (scholarship_id) REFERENCES scholarship_opportunities(scholarship_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        UNIQUE(scholarship_id, student_id)
                    )
                ''')

                # Document vault for scholarship materials
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS scholarship_document_vault (
                        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        document_name TEXT NOT NULL,
                        document_type TEXT CHECK(document_type IN ('essay', 'transcript', 'resume', 'recommendation', 'financial-document', 'certificate', 'portfolio', 'other')),
                        file_path TEXT NOT NULL,
                        file_size INTEGER,
                        file_format TEXT,
                        description TEXT,
                        tags TEXT,
                        version INTEGER DEFAULT 1,
                        is_current_version BOOLEAN DEFAULT 1,
                        parent_document_id INTEGER,
                        associated_scholarship_id INTEGER,
                        upload_date TEXT DEFAULT (date('now')),
                        last_modified TEXT DEFAULT (date('now')),
                        expiry_date TEXT,
                        is_verified BOOLEAN DEFAULT 0,
                        verified_by INTEGER,
                        verified_date TEXT,
                        usage_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (parent_document_id) REFERENCES scholarship_document_vault(document_id),
                        FOREIGN KEY (associated_scholarship_id) REFERENCES scholarship_opportunities(scholarship_id)
                    )
                ''')

                # Application deadlines and reminders
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS scholarship_deadline_reminders (
                        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        application_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        scholarship_id INTEGER NOT NULL,
                        deadline_date TEXT NOT NULL,
                        reminder_date TEXT NOT NULL,
                        reminder_type TEXT CHECK(reminder_type IN ('one-month', 'two-weeks', 'one-week', 'three-days', 'one-day', 'custom')),
                        days_before_deadline INTEGER,
                        reminder_sent BOOLEAN DEFAULT 0,
                        reminder_sent_date TEXT,
                        notification_method TEXT CHECK(notification_method IN ('email', 'sms', 'push', 'all')),
                        message TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (application_id) REFERENCES student_scholarship_applications(application_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (scholarship_id) REFERENCES scholarship_opportunities(scholarship_id)
                    )
                ''')

                # Scholarship awards history
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS scholarship_awards_history (
                        award_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scholarship_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        application_id INTEGER,
                        award_amount REAL NOT NULL,
                        academic_year TEXT NOT NULL,
                        semester TEXT,
                        award_date TEXT NOT NULL,
                        disbursement_date TEXT,
                        disbursement_amount REAL,
                        disbursement_status TEXT CHECK(disbursement_status IN ('pending', 'partial', 'completed', 'cancelled')),
                        is_renewable BOOLEAN DEFAULT 0,
                        renewal_deadline TEXT,
                        renewal_requirements TEXT,
                        renewal_gpa_requirement REAL,
                        thankyou_letter_sent BOOLEAN DEFAULT 0,
                        thankyou_letter_date TEXT,
                        impact_statement_submitted BOOLEAN DEFAULT 0,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (scholarship_id) REFERENCES scholarship_opportunities(scholarship_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (application_id) REFERENCES student_scholarship_applications(application_id)
                    )
                ''')

                # Eligibility matching rules
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS scholarship_matching_rules (
                        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_name TEXT NOT NULL,
                        rule_category TEXT CHECK(rule_category IN ('academic', 'demographic', 'financial', 'activity', 'geographic', 'special')),
                        rule_weight REAL DEFAULT 1.0,
                        rule_logic TEXT NOT NULL,
                        is_required BOOLEAN DEFAULT 0,
                        description TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Scholarship recommendations cache
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS scholarship_recommendations (
                        recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        scholarship_id INTEGER NOT NULL,
                        match_score REAL NOT NULL,
                        eligibility_status TEXT CHECK(eligibility_status IN ('highly-eligible', 'eligible', 'possibly-eligible', 'not-eligible')),
                        matching_criteria TEXT,
                        missing_criteria TEXT,
                        recommendation_reason TEXT,
                        estimated_competition TEXT,
                        priority_level TEXT CHECK(priority_level IN ('high', 'medium', 'low')),
                        recommended_date TEXT DEFAULT (date('now')),
                        expires_date TEXT,
                        viewed BOOLEAN DEFAULT 0,
                        viewed_date TEXT,
                        dismissed BOOLEAN DEFAULT 0,
                        dismissed_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (scholarship_id) REFERENCES scholarship_opportunities(scholarship_id),
                        UNIQUE(student_id, scholarship_id)
                    )
                ''')

                log_activity('create', 'database_tables', details={'module': 'scholarship_finder', 'action': 'create_tables'})

        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating scholarship finder tables: {e}") from e

    @staticmethod
    def add_scholarship(name: str, organization: str, organization_type: str,
                       award_amount_min: float, description: str,
                       application_deadline: str, **kwargs) -> int:
        """Add scholarship opportunity to database"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO scholarship_opportunities (
                        scholarship_name, organization, organization_type, award_amount_min,
                        award_amount_max, award_type, description, detailed_requirements,
                        eligibility_criteria, academic_level, min_gpa, max_gpa, required_majors,
                        excluded_majors, required_enrollment_status, citizenship_requirements,
                        state_residency_requirements, financial_need_required, merit_based,
                        demographic_requirements, special_criteria, application_url,
                        application_deadline, notification_date, award_disbursement_date,
                        renewable_terms, number_of_awards, estimated_applicants,
                        competition_level, required_documents, essay_required, essay_prompts,
                        recommendation_letters_required, transcript_required, interview_required,
                        contact_email, contact_phone, tags, source, is_internal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name, organization, organization_type, award_amount_min,
                    kwargs.get('award_amount_max'), kwargs.get('award_type', 'one-time'),
                    description, kwargs.get('detailed_requirements'),
                    kwargs.get('eligibility_criteria'), kwargs.get('academic_level', 'any'),
                    kwargs.get('min_gpa'), kwargs.get('max_gpa'), kwargs.get('required_majors'),
                    kwargs.get('excluded_majors'), kwargs.get('required_enrollment_status'),
                    kwargs.get('citizenship_requirements'), kwargs.get('state_residency_requirements'),
                    kwargs.get('financial_need_required', 0), kwargs.get('merit_based', 0),
                    kwargs.get('demographic_requirements'), kwargs.get('special_criteria'),
                    kwargs.get('application_url'), application_deadline,
                    kwargs.get('notification_date'), kwargs.get('award_disbursement_date'),
                    kwargs.get('renewable_terms'), kwargs.get('number_of_awards'),
                    kwargs.get('estimated_applicants'), kwargs.get('competition_level'),
                    kwargs.get('required_documents'), kwargs.get('essay_required', 0),
                    kwargs.get('essay_prompts'), kwargs.get('recommendation_letters_required', 0),
                    kwargs.get('transcript_required', 0), kwargs.get('interview_required', 0),
                    kwargs.get('contact_email'), kwargs.get('contact_phone'),
                    kwargs.get('tags'), kwargs.get('source'), kwargs.get('is_internal', 0)
                ))

                scholarship_id = cursor.lastrowid
                log_activity('create', 'scholarship_opportunity', scholarship_id=scholarship_id,
                           details={'name': name, 'organization': organization})
                return scholarship_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error adding scholarship: {e}") from e

    @staticmethod
    def search_scholarships(filters: Optional[Dict[str, Any]] = None,
                          sort_by: str = 'deadline') -> List[Dict[str, Any]]:
        """Search scholarships with filters"""
        with get_connection() as conn:
            query = "SELECT * FROM scholarship_opportunities WHERE is_active = 1"
            params = []

            if filters:
                if 'organization_type' in filters:
                    query += " AND organization_type = ?"
                    params.append(filters['organization_type'])
                if 'min_award' in filters:
                    query += " AND award_amount_min >= ?"
                    params.append(filters['min_award'])
                if 'academic_level' in filters:
                    query += " AND (academic_level = ? OR academic_level = 'any')"
                    params.append(filters['academic_level'])
                if 'major' in filters:
                    query += " AND (required_majors IS NULL OR required_majors LIKE ?)"
                    params.append(f"%{escape_like(filters['major'])}%")
                if 'merit_based' in filters:
                    query += " AND merit_based = ?"
                    params.append(filters['merit_based'])
                if 'deadline_after' in filters:
                    query += " AND application_deadline >= ?"
                    params.append(filters['deadline_after'])
                if 'tags' in filters:
                    query += " AND tags LIKE ?"
                    params.append(f"%{escape_like(filters['tags'])}%")

            # Sort
            if sort_by == 'deadline':
                query += " ORDER BY application_deadline ASC"
            elif sort_by == 'amount':
                query += " ORDER BY award_amount_min DESC"
            elif sort_by == 'competition':
                query += " ORDER BY competition_level ASC"
            else:
                query += " ORDER BY created_at DESC"

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_scholarship_details(scholarship_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed scholarship information"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM scholarship_opportunities WHERE scholarship_id = ?
            ''', (scholarship_id,))
            scholarship = cursor.fetchone()

            if scholarship:
                scholarship_dict = dict(scholarship)

                # Get application statistics
                cursor = conn.execute('''
                    SELECT
                        COUNT(*) as total_applications,
                        SUM(CASE WHEN status = 'awarded' THEN 1 ELSE 0 END) as awards_given,
                        AVG(match_score) as avg_match_score
                    FROM student_scholarship_applications
                    WHERE scholarship_id = ?
                ''', (scholarship_id,))
                stats = cursor.fetchone()
                if stats:
                    scholarship_dict['application_stats'] = dict(stats)

                return scholarship_dict
            return None

class StudentProfileManager:
    """Manages student scholarship profiles for matching"""

    @staticmethod
    def create_or_update_profile(student_id: str, **profile_data) -> int:
        """Create or update student scholarship profile"""
        try:
            with transaction() as conn:
                # Check if profile exists
                cursor = conn.execute('''
                    SELECT profile_id FROM student_scholarship_profiles WHERE student_id = ?
                ''', (student_id,))
                existing = cursor.fetchone()

                # Calculate profile completeness
                required_fields = ['citizenship_status', 'state_residency', 'financial_need_level']
                optional_fields = ['ethnicity', 'gender', 'first_generation', 'community_service_hours',
                                 'leadership_positions', 'academic_honors', 'extracurricular_activities']

                completed = sum(1 for field in required_fields if profile_data.get(field))
                completed += sum(0.5 for field in optional_fields if profile_data.get(field))
                total_possible = len(required_fields) + (len(optional_fields) * 0.5)
                completeness = round((completed / total_possible * 100), 2)

                if existing:
                    # Update
                    allowed_fields = ['citizenship_status', 'state_residency', 'ethnicity', 'gender',
                                    'first_generation', 'military_affiliation', 'disability_status',
                                    'financial_need_level', 'intended_career_field', 'community_service_hours',
                                    'leadership_positions', 'academic_honors', 'extracurricular_activities',
                                    'special_talents', 'languages_spoken', 'study_abroad_interest',
                                    'research_interest', 'preferred_scholarship_types', 'minimum_award_amount',
                                    'willing_to_write_essays', 'max_recommendation_letters']

                    update_fields = {k: v for k, v in profile_data.items() if k in allowed_fields}
                    if update_fields:
                        set_clause = ", ".join([validate_identifier(k, "column") + " = ?" for k in update_fields.keys()])
                        set_clause += ", profile_completeness = ?, updated_at = CURRENT_TIMESTAMP"
                        values = list(update_fields.values()) + [completeness, student_id]

                        conn.execute("UPDATE student_scholarship_profiles SET " + set_clause + " WHERE student_id = ?", values)
                        profile_id = existing['profile_id']
                else:
                    # Insert
                    cursor = conn.execute('''
                        INSERT INTO student_scholarship_profiles (
                            student_id, citizenship_status, state_residency, ethnicity, gender,
                            first_generation, military_affiliation, disability_status,
                            financial_need_level, intended_career_field, community_service_hours,
                            leadership_positions, academic_honors, extracurricular_activities,
                            special_talents, languages_spoken, study_abroad_interest,
                            research_interest, preferred_scholarship_types, minimum_award_amount,
                            willing_to_write_essays, max_recommendation_letters, profile_completeness
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        student_id, profile_data.get('citizenship_status'),
                        profile_data.get('state_residency'), profile_data.get('ethnicity'),
                        profile_data.get('gender'), profile_data.get('first_generation', 0),
                        profile_data.get('military_affiliation'), profile_data.get('disability_status'),
                        profile_data.get('financial_need_level'), profile_data.get('intended_career_field'),
                        profile_data.get('community_service_hours', 0), profile_data.get('leadership_positions'),
                        profile_data.get('academic_honors'), profile_data.get('extracurricular_activities'),
                        profile_data.get('special_talents'), profile_data.get('languages_spoken'),
                        profile_data.get('study_abroad_interest', 0), profile_data.get('research_interest', 0),
                        profile_data.get('preferred_scholarship_types'), profile_data.get('minimum_award_amount'),
                        profile_data.get('willing_to_write_essays', 1),
                        profile_data.get('max_recommendation_letters', 3), completeness
                    ))
                    profile_id = cursor.lastrowid

                log_activity('update', 'scholarship_profile', profile_id=profile_id,
                           details={'student_id': student_id, 'completeness': completeness})
                return profile_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error updating scholarship profile: {e}") from e

    @staticmethod
    def get_student_profile(student_id: str) -> Optional[Dict[str, Any]]:
        """Get student scholarship profile"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM student_scholarship_profiles WHERE student_id = ?
            ''', (student_id,))
            profile = cursor.fetchone()
            return dict(profile) if profile else None

class RecommendationEngine:
    """Generates personalized scholarship recommendations"""

    @staticmethod
    def generate_recommendations(student_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Generate personalized scholarship recommendations"""
        try:
            with get_connection() as conn:
                # Get student profile
                cursor = conn.execute('''
                    SELECT sp.*,
                           sdp.current_gpa AS gpa,
                           s.course AS major,
                           s.status AS enrollment_status,
                           NULL AS academic_standing
                    FROM student_scholarship_profiles sp
                    JOIN students s ON sp.student_id = s.student_id
                    LEFT JOIN student_degree_progress sdp ON s.student_id = sdp.student_id
                    WHERE sp.student_id = ?
                ''', (student_id,))
                student = cursor.fetchone()

                if not student:
                    return []

                # Get active scholarships
                cursor = conn.execute('''
                    SELECT * FROM scholarship_opportunities
                    WHERE is_active = 1 AND application_deadline >= date('now')
                ''')
                scholarships = cursor.fetchall()

                recommendations = []

                for scholarship in scholarships:
                    match_score = 0
                    matching_criteria = []
                    missing_criteria = []

                    # GPA matching
                    if scholarship['min_gpa']:
                        if student['gpa'] and student['gpa'] >= scholarship['min_gpa']:
                            match_score += 15
                            matching_criteria.append('GPA requirement met')
                        else:
                            missing_criteria.append(f"GPA below {scholarship['min_gpa']}")
                            continue  # Skip if GPA requirement not met

                    # Major matching
                    if scholarship['required_majors']:
                        if student['major'] and student['major'] in scholarship['required_majors']:
                            match_score += 20
                            matching_criteria.append('Major requirement met')
                        else:
                            missing_criteria.append('Major not eligible')
                            continue

                    # Citizenship
                    if scholarship['citizenship_requirements']:
                        if student['citizenship_status'] and student['citizenship_status'] in scholarship['citizenship_requirements']:
                            match_score += 10
                            matching_criteria.append('Citizenship requirement met')
                        else:
                            missing_criteria.append('Citizenship requirement not met')
                            continue

                    # State residency
                    if scholarship['state_residency_requirements']:
                        if student['state_residency'] and student['state_residency'] in scholarship['state_residency_requirements']:
                            match_score += 10
                            matching_criteria.append('State residency met')

                    # Financial need
                    if scholarship['financial_need_required']:
                        if student['financial_need_level'] in ['moderate', 'high', 'exceptional']:
                            match_score += 15
                            matching_criteria.append('Financial need criteria met')
                        else:
                            missing_criteria.append('Financial need not demonstrated')

                    # Merit-based
                    if scholarship['merit_based']:
                        if student['gpa'] and student['gpa'] >= 3.5:
                            match_score += 15
                            matching_criteria.append('Strong academic record')

                    # Award amount preference
                    if student['minimum_award_amount']:
                        if scholarship['award_amount_min'] >= student['minimum_award_amount']:
                            match_score += 5
                            matching_criteria.append('Meets minimum award preference')

                    # Essay willingness
                    if scholarship['essay_required']:
                        if student['willing_to_write_essays']:
                            match_score += 5
                        else:
                            match_score -= 10
                            missing_criteria.append('Essay required but student prefers not to write')

                    # Recommendation letters
                    if scholarship['recommendation_letters_required']:
                        if scholarship['recommendation_letters_required'] <= student['max_recommendation_letters']:
                            match_score += 5
                        else:
                            missing_criteria.append(f"Too many recommendation letters required ({scholarship['recommendation_letters_required']})")

                    # Bonus points for special criteria matches
                    if student['first_generation'] and scholarship['demographic_requirements'] and 'first-generation' in scholarship['demographic_requirements'].lower():
                        match_score += 10
                        matching_criteria.append('First-generation student')

                    if student['community_service_hours'] > 50 and scholarship['special_criteria'] and 'community service' in scholarship['special_criteria'].lower():
                        match_score += 10
                        matching_criteria.append('Strong community service record')

                    # Determine eligibility status
                    if match_score >= 70:
                        eligibility = 'highly-eligible'
                        priority = 'high'
                    elif match_score >= 50:
                        eligibility = 'eligible'
                        priority = 'medium'
                    elif match_score >= 30:
                        eligibility = 'possibly-eligible'
                        priority = 'low'
                    else:
                        eligibility = 'not-eligible'
                        priority = 'low'
                        continue  # Skip not eligible

                    recommendations.append({
                        'scholarship_id': scholarship['scholarship_id'],
                        'scholarship_name': scholarship['scholarship_name'],
                        'organization': scholarship['organization'],
                        'award_amount_min': scholarship['award_amount_min'],
                        'award_amount_max': scholarship['award_amount_max'],
                        'application_deadline': scholarship['application_deadline'],
                        'match_score': match_score,
                        'eligibility_status': eligibility,
                        'priority_level': priority,
                        'matching_criteria': ', '.join(matching_criteria),
                        'missing_criteria': ', '.join(missing_criteria) if missing_criteria else None,
                        'competition_level': scholarship['competition_level'],
                        'essay_required': scholarship['essay_required'],
                        'recommendation_letters_required': scholarship['recommendation_letters_required']
                    })

                # Sort by match score
                recommendations.sort(key=lambda x: x['match_score'], reverse=True)

                # Save recommendations to cache
                with transaction() as conn:
                    for rec in recommendations[:limit]:
                        conn.execute('''
                            INSERT OR REPLACE INTO scholarship_recommendations (
                                student_id, scholarship_id, match_score, eligibility_status,
                                matching_criteria, missing_criteria, estimated_competition,
                                priority_level, expires_date
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now', '+30 days'))
                        ''', (student_id, rec['scholarship_id'], rec['match_score'],
                              rec['eligibility_status'], rec['matching_criteria'],
                              rec['missing_criteria'], rec['competition_level'],
                              rec['priority_level']))

                log_activity('generate', 'scholarship_recommendations', student_id=student_id,
                           details={'count': len(recommendations[:limit])})

                return recommendations[:limit]

        except sqlite3.Error as e:
            raise DatabaseError(f"Error generating recommendations: {e}") from e

    @staticmethod
    def get_cached_recommendations(student_id: str) -> List[Dict[str, Any]]:
        """Get cached recommendations"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT r.*, s.scholarship_name, s.organization, s.award_amount_min,
                       s.award_amount_max, s.application_deadline, s.essay_required,
                       s.recommendation_letters_required
                FROM scholarship_recommendations r
                JOIN scholarship_opportunities s ON r.scholarship_id = s.scholarship_id
                WHERE r.student_id = ? AND r.expires_date >= date('now')
                  AND r.dismissed = 0 AND s.is_active = 1
                ORDER BY r.match_score DESC, r.priority_level DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

class ApplicationManager:
    """Manages scholarship applications"""

    @staticmethod
    def start_application(student_id: str, scholarship_id: int, match_score: float = None) -> int:
        """Start new scholarship application"""
        try:
            with transaction() as conn:
                # Get scholarship details
                cursor = conn.execute('''
                    SELECT application_deadline, recommendation_letters_required
                    FROM scholarship_opportunities WHERE scholarship_id = ?
                ''', (scholarship_id,))
                scholarship = cursor.fetchone()
                if not scholarship:
                    raise ValidationError("Scholarship not found")

                cursor = conn.execute('''
                    INSERT INTO student_scholarship_applications (
                        scholarship_id, student_id, deadline_date, recommendations_required, match_score
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (scholarship_id, student_id, scholarship['application_deadline'],
                      scholarship['recommendation_letters_required'], match_score))

                application_id = cursor.lastrowid

                # Create deadline reminders
                deadline = datetime.strptime(scholarship['application_deadline'], '%Y-%m-%d')
                reminders = [
                    ('one-month', 30),
                    ('two-weeks', 14),
                    ('one-week', 7),
                    ('three-days', 3),
                    ('one-day', 1)
                ]

                for reminder_type, days_before in reminders:
                    reminder_date = deadline - timedelta(days=days_before)
                    if reminder_date > datetime.now():
                        conn.execute('''
                            INSERT INTO scholarship_deadline_reminders (
                                application_id, student_id, scholarship_id, deadline_date,
                                reminder_date, reminder_type, days_before_deadline, notification_method
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'all')
                        ''', (application_id, student_id, scholarship_id,
                              scholarship['application_deadline'], reminder_date.strftime('%Y-%m-%d'),
                              reminder_type, days_before))

                log_activity('create', 'scholarship_application', application_id=application_id,
                           details={'student_id': student_id, 'scholarship_id': scholarship_id})
                return application_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error starting application: {e}") from e

    @staticmethod
    def update_application_progress(application_id: int, **updates) -> bool:
        """Update application progress"""
        try:
            with transaction() as conn:
                allowed_fields = ['status', 'essay_completed', 'recommendations_obtained',
                                'transcript_uploaded', 'documents_completed', 'notes']

                update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
                if not update_fields:
                    return False

                # Calculate progress
                cursor = conn.execute('''
                    SELECT essay_completed, recommendations_obtained, recommendations_required,
                           transcript_uploaded, documents_completed
                    FROM student_scholarship_applications WHERE application_id = ?
                ''', (application_id,))
                app = dict(cursor.fetchone())

                # Update with new values
                for key, value in update_fields.items():
                    if key in app:
                        app[key] = value

                # Calculate progress percentage
                components = []
                if app.get('essay_completed'): components.append(25)
                if app.get('transcript_uploaded'): components.append(25)
                if app.get('documents_completed'): components.append(25)
                if app['recommendations_required'] > 0:
                    rec_progress = (app.get('recommendations_obtained', 0) / app['recommendations_required']) * 25
                    components.append(rec_progress)
                else:
                    components.append(25)

                progress = sum(components)
                update_fields['application_progress'] = progress

                set_clause = ", ".join([validate_identifier(k, "column") + " = ?" for k in update_fields.keys()])
                set_clause += ", updated_at = CURRENT_TIMESTAMP"
                values = list(update_fields.values()) + [application_id]

                conn.execute("UPDATE student_scholarship_applications SET " + set_clause + " WHERE application_id = ?", values)
                log_activity('update', 'scholarship_application', application_id=application_id,
                           details={'progress': progress})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error updating application: {e}") from e

    @staticmethod
    def submit_application(application_id: int) -> bool:
        """Submit completed application"""
        try:
            with transaction() as conn:
                # Validate application is complete
                cursor = conn.execute('''
                    SELECT application_progress FROM student_scholarship_applications
                    WHERE application_id = ?
                ''', (application_id,))
                app = cursor.fetchone()
                if not app or app['application_progress'] < 100:
                    raise ValidationError("Application is not complete")

                conn.execute('''
                    UPDATE student_scholarship_applications
                    SET status = 'submitted', submission_date = date('now'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE application_id = ?
                ''', (application_id,))

                log_activity('submit', 'scholarship_application', application_id=application_id)
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error submitting application: {e}") from e

    @staticmethod
    def get_student_applications(student_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get student's scholarship applications"""
        with get_connection() as conn:
            query = '''
                SELECT a.*, s.scholarship_name, s.organization, s.award_amount_min,
                       s.award_amount_max, s.application_deadline
                FROM student_scholarship_applications a
                JOIN scholarship_opportunities s ON a.scholarship_id = s.scholarship_id
                WHERE a.student_id = ?
            '''
            params = [student_id]

            if status:
                query += " AND a.status = ?"
                params.append(status)

            query += " ORDER BY s.application_deadline ASC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_upcoming_deadlines(student_id: str, days: int = 14) -> List[Dict[str, Any]]:
        """Get applications with upcoming deadlines"""
        with get_connection() as conn:
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

            cursor = conn.execute('''
                SELECT a.*, s.scholarship_name, s.organization, s.award_amount_min
                FROM student_scholarship_applications a
                JOIN scholarship_opportunities s ON a.scholarship_id = s.scholarship_id
                WHERE a.student_id = ? AND a.status IN ('draft', 'in-progress')
                  AND a.deadline_date BETWEEN date('now') AND ?
                ORDER BY a.deadline_date ASC
            ''', (student_id, end_date))
            return [dict(row) for row in cursor.fetchall()]

class DocumentVaultManager:
    """Manages scholarship document vault"""

    @staticmethod
    def upload_document(student_id: str, document_name: str, document_type: str,
                       file_path: str, **kwargs) -> int:
        """Upload document to vault"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO scholarship_document_vault (
                        student_id, document_name, document_type, file_path, file_size,
                        file_format, description, tags, associated_scholarship_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, document_name, document_type, file_path,
                      kwargs.get('file_size'), kwargs.get('file_format'),
                      kwargs.get('description'), kwargs.get('tags'),
                      kwargs.get('associated_scholarship_id')))

                document_id = cursor.lastrowid
                log_activity('upload', 'scholarship_document', document_id=document_id,
                           details={'student_id': student_id, 'type': document_type})
                return document_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error uploading document: {e}") from e

    @staticmethod
    def get_student_documents(student_id: str, document_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get student's documents from vault"""
        with get_connection() as conn:
            query = '''
                SELECT * FROM scholarship_document_vault
                WHERE student_id = ? AND is_current_version = 1
            '''
            params = [student_id]

            if document_type:
                query += " AND document_type = ?"
                params.append(document_type)

            query += " ORDER BY upload_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def track_document_usage(document_id: int) -> bool:
        """Track document usage"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE scholarship_document_vault
                    SET usage_count = usage_count + 1
                    WHERE document_id = ?
                ''', (document_id,))
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error tracking document usage: {e}") from e

# Initialize tables on module import
try:
    ScholarshipDatabase.create_tables()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Could not create scholarship finder tables: {e}")
