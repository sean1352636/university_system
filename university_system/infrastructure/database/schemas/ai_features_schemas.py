from __future__ import annotations
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, sqlite3
from university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_ai_features_system_db():
    """Initialize the AI-Powered Features database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="AI-Powered Features"))

        # Chatbot conversations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chatbot_conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            end_time TEXT,
            message_count INTEGER DEFAULT 0,
            satisfaction_rating INTEGER,
            was_helpful BOOLEAN,
            escalated_to_human BOOLEAN DEFAULT 0
        )
        ''')

        # Chatbot messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chatbot_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            message_text TEXT NOT NULL,
            intent_detected TEXT,
            confidence_score REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES ai_chatbot_conversations (conversation_id)
        )
        ''')

        # AI recommendations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            recommendation_content TEXT NOT NULL,
            algorithm_used TEXT,
            confidence_score REAL,
            context_data TEXT,
            was_accepted BOOLEAN,
            feedback_rating INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Auto-grading results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_grading_results (
            grading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            assignment_type TEXT NOT NULL,
            auto_score REAL,
            max_score REAL,
            grading_criteria TEXT,
            feedback_generated TEXT,
            confidence_score REAL,
            requires_manual_review BOOLEAN DEFAULT 0,
            manual_override_score REAL,
            graded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Smart content suggestions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_content_suggestions (
            suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            context TEXT NOT NULL,
            suggested_content TEXT NOT NULL,
            relevance_score REAL,
            source TEXT,
            was_used BOOLEAN DEFAULT 0,
            created_for TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Sentiment analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_sentiment_analysis (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_text TEXT NOT NULL,
            sentiment_score REAL,
            sentiment_category TEXT,
            emotions_detected TEXT,
            key_phrases TEXT,
            analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Plagiarism detection
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_plagiarism_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            document_text TEXT NOT NULL,
            similarity_score REAL,
            matched_sources TEXT,
            flagged BOOLEAN DEFAULT 0,
            review_status TEXT DEFAULT 'pending',
            checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # AI model performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_model_performance (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            test_dataset TEXT,
            measured_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="AI-Powered Features"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="AI Features", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# INTEGRATION MARKETPLACE SCHEMAS
# ============================================================================


def init_ai_tables():
    """Initialize ai system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="ai"))

        # Create ai_detector_metadata table
        cursor.execute('''
        CREATE TABLE ai_detector_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        time_taken INTEGER,
                        browser_info TEXT,
                        device_fingerprint TEXT,
                        ip_address TEXT,
                        location_data TEXT,
                        keystroke_data TEXT,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create ai_detector_results table
        cursor.execute('''
        CREATE TABLE ai_detector_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        ai_score REAL NOT NULL,
                        confidence REAL NOT NULL,
                        detailed_results TEXT,
                        created_at TEXT NOT NULL,
                        style_deviation REAL,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create ai_detector_submissions table
        cursor.execute('''
        CREATE TABLE ai_detector_submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        submission_text TEXT NOT NULL,
                        title TEXT,
                        course_code TEXT,
                        assignment_id TEXT,
                        submission_date TEXT NOT NULL,
                        word_count INTEGER,
                        character_count INTEGER,
                        institution_id TEXT
                    )
        ''')

        # Create campaign_expenses table
        cursor.execute('''
        CREATE TABLE campaign_expenses (
                    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER,
                    amount REAL,
                    description TEXT,
                    receipt_path TEXT,
                    expense_date TEXT,
                    approved BOOLEAN DEFAULT 0,
                    FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
                )
        ''')

        # Create campaign_materials table
        cursor.execute('''
        CREATE TABLE campaign_materials (
                    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER,
                    material_type TEXT,
                    content TEXT,
                    file_path TEXT,
                    upload_date TEXT,
                    status TEXT DEFAULT 'pending_approval',
                    FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
                )
        ''')

        # Create chatbot_conversations table
        cursor.execute('''
        CREATE TABLE chatbot_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    intent TEXT,
                    confidence REAL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create fundraising_campaigns table
        cursor.execute('''
        CREATE TABLE fundraising_campaigns (
                    campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_name TEXT,
                    description TEXT,
                    goal_amount REAL,
                    current_amount REAL DEFAULT 0.0,
                    start_date TEXT,
                    end_date TEXT,
                    created_by TEXT,
                    created_date TEXT,
                    status TEXT DEFAULT 'active',
                    category TEXT,
                    is_featured BOOLEAN DEFAULT 0
                )
        ''')

        # Create plagiarism_results table
        cursor.execute('''
        CREATE TABLE plagiarism_results (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            document_id INTEGER NOT NULL,
                            matched_document_id INTEGER,
                            similarity_score REAL NOT NULL CHECK(similarity_score >= 0 AND similarity_score <= 1),
                            check_date TEXT NOT NULL,
                            checked_by INTEGER,
                            status TEXT NOT NULL,
                            report TEXT,
                            threshold_used REAL DEFAULT 0.3,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (document_id) REFERENCES document_repository (id) ON DELETE CASCADE,
                            FOREIGN KEY (matched_document_id) REFERENCES document_repository (id) ON DELETE SET NULL,
                            FOREIGN KEY (checked_by) REFERENCES users (id) ON DELETE SET NULL
                        )
        ''')

        # Create risk_details table
        cursor.execute('''
        CREATE TABLE risk_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    risk_factor_id INTEGER,
                    detail TEXT,
                    weight REAL,
                    created_at TEXT,
                    FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id)
                )
        ''')

        # Create sustainability_tracking table
        cursor.execute('''
        CREATE TABLE sustainability_tracking (
                    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    club_id INTEGER,
                    carbon_footprint REAL,
                    waste_generated REAL,
                    waste_recycled REAL,
                    transport_method TEXT,
                    sustainability_score REAL,
                    notes TEXT,
                    recorded_date TEXT,
                    FOREIGN KEY (event_id) REFERENCES union_events (event_id),
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
                )
        ''')

        # Create teacher_availability table
        cursor.execute('''
        CREATE TABLE teacher_availability (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        teacher_id INTEGER,
                        day_of_week TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        meeting_type TEXT,
                        location TEXT,
                        active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (teacher_id) REFERENCES users (id)
                    )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="ai"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="ai", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ALUMNI TABLES (8 tables)
# ============================================================================


