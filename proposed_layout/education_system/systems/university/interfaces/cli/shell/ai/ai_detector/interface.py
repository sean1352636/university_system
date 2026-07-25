"""CLI interface and initialization functions for the AI Detector."""

from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.database.db import DatabaseManager
from education_system.systems.university.infrastructure.ai.ai_detector.detector.main import AIDetector

from education_system.systems.university.interfaces.cli.shell.ai.ai_detector.basic_operations import (
    analyze_text_interface_safe, view_submission_history_safe,
    view_ai_detector_statistics_safe, run_ai_detector_demo_safe,
)
from education_system.systems.university.interfaces.cli.shell.ai.ai_detector.enhanced_detection import (
    analyze_writing_style_fingerprint_cli, detect_paraphrasing_tools_cli,
    analyze_prompt_artifacts_cli, compare_draft_versions_cli,
    detect_translation_artifacts_cli, analyze_knowledge_consistency_cli,
    detect_copy_paste_patterns_cli, analyze_reference_authenticity_cli,
)
from education_system.systems.university.interfaces.cli.shell.ai.ai_detector.student_management import (
    view_student_profile_cli, compare_students_cli,
    generate_student_report_card_cli, flag_student_for_review_cli,
    view_student_progression_cli, bulk_student_analysis_cli,
)
from education_system.systems.university.interfaces.cli.shell.ai.ai_detector.analytics import (
    show_confidence_distribution_cli, generate_word_cloud_cli,
    plot_submission_timeline_cli, show_correlation_matrix_cli,
    cluster_similar_submissions_cli, generate_department_comparison_cli,
    show_weekly_trends_cli, export_visualization_pack_cli,
)

# Global AI detector instance for CLI functions
ai_detector = None

def integrate_ai_detector_with_main():
    """Initialize the AI detector system for integration with main menu"""
    global ai_detector
    try:
        # Initialize the AI detector with minimal configuration first
        ai_detector = AIDetector()

        # CRITICAL FIX: Ensure all required attributes exist
        if not hasattr(ai_detector, 'detection_threshold'):
            ai_detector.detection_threshold = 0.7

        if not hasattr(ai_detector, 'style_profiles'):
            ai_detector.style_profiles = {}

        if not hasattr(ai_detector, 'detection_methods'):
            ai_detector.detection_methods = {
                'pattern_matching': True,
                'statistical_analysis': True,
                'behavioral_analysis': True,
                'temporal_analysis': True,
                'citation_verification': True
            }

        if not hasattr(ai_detector, 'current_user'):
            ai_detector.current_user = None

        # Set authentication if available
        auth = get_auth()
        if auth:
            ai_detector.set_auth(auth)

        print("\u2705 AI detector system initialized successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize AI detector: {e}")
        print(f"\u26a0\ufe0f AI detector initialization failed: {e}")

        # Create a minimal fallback AI detector
        try:
            ai_detector = create_minimal_ai_detector()
            print("\u2705 Minimal AI detector created as fallback")
            return True
        except Exception as fallback_error:
            logger.error(f"Even fallback AI detector failed: {fallback_error}")
            print(f"\u274c Complete AI detector failure: {fallback_error}")
            return False

def create_minimal_ai_detector():
    """Create a minimal AI detector that won't crash"""
    class MinimalAIDetector:
        def __init__(self):
            self.detection_threshold = 0.7
            self.style_profiles = {}
            self.detection_methods = {
                'pattern_matching': True,
                'statistical_analysis': True,
                'behavioral_analysis': True,
                'temporal_analysis': True,
                'citation_verification': True
            }
            self.current_user = None
            self.auth = None

        def set_auth(self, auth_obj):
            self.auth = auth_obj
            if hasattr(auth_obj, 'current_user'):
                self.current_user = auth_obj.current_user

        def get_enhanced_statistics(self):
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'recent_submissions_7_days': 0,
                'high_risk_submissions': 0,
                'detection_threshold': self.detection_threshold,
                'active_style_profiles': len(self.style_profiles),
                'active_detection_methods': len(self.detection_methods),
                'database_status': 'minimal_mode',
                'generated_at': datetime.now().isoformat(),
                'mode': 'minimal_fallback'
            }

        def get_statistics(self):
            return self.get_enhanced_statistics()

        def list_submissions(self, student_id=None, limit=10, include_text=False):
            """Safe list submissions that handles database errors"""
            try:
                db_manager = DatabaseManager()
                conn = db_manager.get_connection()
                if not conn:
                    return {
                        'submissions': [],
                        'total': 0,
                        'message': 'Database connection failed'
                    }

                cursor = conn.cursor()

                # Build query with flexible column handling
                try:
                    # First, check what columns actually exist
                    cursor.execute("PRAGMA table_info(ai_detector_submissions)")
                    columns = {row[1]: row[1] for row in cursor.fetchall()}

                    # Build select statement based on available columns
                    select_fields = [
                        'id',
                        'student_id',
                        columns.get('title', columns.get('submission_title', "'Untitled' as title")),
                        'course_code',
                        'assignment_id',
                        'submission_date',
                        'word_count',
                        'character_count'
                    ]

                    if include_text:
                        select_fields.append('submission_text')

                    query = f'''
                    SELECT {", ".join(select_fields)}
                    FROM ai_detector_submissions s
                    LEFT JOIN ai_detector_results r ON s.id = r.submission_id
                    '''

                    params = []
                    if student_id:
                        query += " WHERE s.student_id = ?"
                        params.append(student_id)

                    query += " ORDER BY s.submission_date DESC LIMIT ?"
                    params.append(limit)

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    submissions = []
                    for row in rows:
                        submission = dict(row) if hasattr(row, 'keys') else {}
                        submissions.append(submission)

                    conn.close()

                    return {
                        'submissions': submissions,
                        'total': len(submissions),
                        'student_filter': student_id,
                        'limit': limit
                    }

                except sqlite3.Error as query_error:
                    conn.close()
                    return {
                        'submissions': [],
                        'total': 0,
                        'error': f"Query error: {query_error}",
                        'message': 'Database schema issue detected'
                    }

            except sqlite3.Error as e:
                return {
                    'submissions': [],
                    'total': 0,
                    'error': str(e),
                    'message': 'Database access failed'
                }

        def analyze_text(self, text, title=None, student_id=None, course_code=None, assignment_id=None):
            """Basic text analysis that always works"""
            import random
            import time
            ai_score = random.uniform(0.1, 0.9)  # Random score for demo
            return {
                'submission_id': f"demo_{int(time.time())}",
                'ai_score': ai_score,
                'confidence': 0.5,
                'is_ai_generated': ai_score >= self.detection_threshold,
                'detection_methods': ['basic_pattern_matching'],
                'text_stats': {
                    'word_count': len(text.split()),
                    'char_count': len(text),
                    'sentence_count': len([s for s in text.split('.') if s.strip()]),
                },
                'indicators': [
                    {'name': 'demo_indicator', 'score': ai_score, 'evidence': 'Demo mode active'}
                ],
                'mode': 'minimal_demo'
            }

        def get_submission_details(self, submission_id):
            return {'error': 'Not available in minimal mode'}

    return MinimalAIDetector()

def display_ai_detector_menu_from_main(auth_obj):
    """Display AI detector menu with comprehensive error handling"""
    global ai_detector

    # Check if user is authenticated
    if not auth_obj or not auth_obj.current_user:
        print("You must be logged in to access the AI detector.")
        return

    # Initialize AI detector if not already done or if it failed
    if ai_detector is None:
        print("Initializing AI detector...")
        try:
            integrate_ai_detector_with_main()
        except Exception as e:
            print(f"\u274c AI detector initialization failed: {e}")
            ai_detector = create_minimal_ai_detector()
            print("\u2705 Running in minimal mode")

    # Double-check that ai_detector has required attributes
    if not hasattr(ai_detector, 'detection_threshold'):
        print("\u26a0\ufe0f AI detector missing critical attributes, recreating...")
        ai_detector = create_minimal_ai_detector()

    # Ensure the AI detector has the current auth context
    try:
        ai_detector.set_auth(auth_obj)
    except Exception as e:
        print(f"\u26a0\ufe0f Could not set auth context: {e}")

    while True:
        print("\nAI Content Detector Menu:")
        print("=" * 50)

        # Show current mode
        try:
            stats = ai_detector.get_enhanced_statistics()
            mode = stats.get('mode', 'normal')
            if mode == 'minimal_fallback':
                print("\u26a0\ufe0f Running in MINIMAL MODE - limited functionality")
        except (AttributeError, TypeError, KeyError):
            print("\u26a0\ufe0f Status check failed - proceeding with caution")

        print("\n\U0001f4dd Basic Analysis:")
        print("  1. Analyze text for AI-generated content")
        print("  2. View submission history")
        print("  3. View system statistics")
        print("  4. Demo AI detector")

        print("\n\U0001f52c Enhanced Detection Analysis:")
        print("  5. Analyze writing style fingerprint")
        print("  6. Detect paraphrasing tools (Quillbot, etc.)")
        print("  7. Analyze prompt artifacts (ChatGPT/Claude)")
        print("  8. Compare draft versions")
        print("  9. Detect translation artifacts")
        print(" 10. Analyze knowledge consistency")
        print(" 11. Detect copy-paste patterns")
        print(" 12. Analyze reference authenticity")

        print("\n\U0001f465 Student Management:")
        print(" 13. View student profile")
        print(" 14. Compare two students")
        print(" 15. Generate student report card")
        print(" 16. Flag student for review")
        print(" 17. View student progression")
        print(" 18. Bulk student analysis")

        print("\n\U0001f4ca Analytics & Visualization:")
        print(" 19. Show confidence distribution")
        print(" 20. Generate word cloud data")
        print(" 21. Plot submission timeline")
        print(" 22. Show correlation matrix")
        print(" 23. Cluster similar submissions")
        print(" 24. Department comparison")
        print(" 25. Show weekly trends")
        print(" 26. Export visualization pack")

        print("\n 0. Return to Main Menu")

        choice = input("\nEnter your choice (0-26): ").strip()

        try:
            if choice == '1':
                analyze_text_interface_safe()
            elif choice == '2':
                view_submission_history_safe()
            elif choice == '3':
                view_ai_detector_statistics_safe()
            elif choice == '4':
                run_ai_detector_demo_safe()
            elif choice == '5':
                analyze_writing_style_fingerprint_cli()
            elif choice == '6':
                detect_paraphrasing_tools_cli()
            elif choice == '7':
                analyze_prompt_artifacts_cli()
            elif choice == '8':
                compare_draft_versions_cli()
            elif choice == '9':
                detect_translation_artifacts_cli()
            elif choice == '10':
                analyze_knowledge_consistency_cli()
            elif choice == '11':
                detect_copy_paste_patterns_cli()
            elif choice == '12':
                analyze_reference_authenticity_cli()
            elif choice == '13':
                view_student_profile_cli()
            elif choice == '14':
                compare_students_cli()
            elif choice == '15':
                generate_student_report_card_cli()
            elif choice == '16':
                flag_student_for_review_cli()
            elif choice == '17':
                view_student_progression_cli()
            elif choice == '18':
                bulk_student_analysis_cli()
            elif choice == '19':
                show_confidence_distribution_cli()
            elif choice == '20':
                generate_word_cloud_cli()
            elif choice == '21':
                plot_submission_timeline_cli()
            elif choice == '22':
                show_correlation_matrix_cli()
            elif choice == '23':
                cluster_similar_submissions_cli()
            elif choice == '24':
                generate_department_comparison_cli()
            elif choice == '25':
                show_weekly_trends_cli()
            elif choice == '26':
                export_visualization_pack_cli()
            elif choice == '0':
                print("Returning to main menu...")
                break
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"\u274c Error: {e}")
            print("Please try again or return to main menu.")

def fix_ai_detector_database_schema():
    """Fix AI detector database schema by creating proper tables"""
    try:
        db_manager = DatabaseManager()
        conn = db_manager.get_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        print("\U0001f527 Fixing AI detector database schema...")

        # Create AI detector submissions table with correct column names
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_detector_submissions (
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

        # Create AI detector results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_detector_results (
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

        # Check if we need to migrate old data or add missing columns
        cursor.execute("PRAGMA table_info(ai_detector_submissions)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        # Add missing columns if they don't exist
        required_columns = {
            'title': 'TEXT',
            'course_code': 'TEXT',
            'assignment_id': 'TEXT',
            'word_count': 'INTEGER',
            'character_count': 'INTEGER',
            'institution_id': 'TEXT'
        }

        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE ai_detector_submissions ADD COLUMN [{column_name}] {column_type}')
                    print(f"\u2705 Added column '{column_name}' to ai_detector_submissions table")
                except sqlite3.Error as e:
                    print(f"\u26a0\ufe0f Could not add column '{column_name}': {e}")

        # Check if we have the wrong column name and need to rename
        if 'submission_title' in existing_columns and 'title' not in existing_columns:
            try:
                # SQLite doesn't support RENAME COLUMN directly in older versions
                # So we'll create a new table and copy data
                cursor.execute('''
                CREATE TABLE ai_detector_submissions_new (
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

                # Copy data from old table to new table
                cursor.execute('''
                INSERT INTO ai_detector_submissions_new
                (id, student_id, submission_text, title, course_code, assignment_id,
                 submission_date, word_count, character_count, institution_id)
                SELECT id, student_id, submission_text, submission_title, course_code, assignment_id,
                       submission_date, word_count, character_count, institution_id
                FROM ai_detector_submissions
                ''')

                # Drop old table and rename new one
                cursor.execute('DROP TABLE ai_detector_submissions')
                cursor.execute('ALTER TABLE ai_detector_submissions_new RENAME TO ai_detector_submissions')

                print("\u2705 Migrated 'submission_title' column to 'title'")

            except sqlite3.Error as e:
                print(f"\u26a0\ufe0f Could not migrate submission_title column: {e}")

        conn.commit()
        conn.close()

        print("\u2705 AI detector database schema fix completed!")
        return True

    except sqlite3.Error as e:
        print(f"\u274c Error fixing AI detector database schema: {e}")
        return False
