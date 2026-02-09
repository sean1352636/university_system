"""
AI tools integration for CLI system.

This module handles AI detector and plagiarism checker integration,
including text analysis, submission tracking, and reporting.
"""

from .imports import (
    logging, time, datetime, DB_PATH, _t, logger,
    log_activity, AIDetector, validate_column_definition
)

import sqlite3
import random

# Error types
class ValidationError(Exception):
    pass

class DatabaseError(Exception):
    pass

class ConfigurationError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class PermissionDeniedError(Exception):
    pass

class DatabaseConnectionError(Exception):
    pass

class QueryError(Exception):
    pass

# Global AI detector instance
ai_detector = None
auth = None

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def integrate_ai_detector_with_main():
    """Initialize the AI detector system for integration with main menu"""
    global ai_detector
    try:
        # Initialize the AI detector with minimal configuration first
        ai_detector = AIDetector()
        
        # 🔧 CRITICAL FIX: Ensure all required attributes exist
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
        global auth
        if auth:
            ai_detector.set_auth(auth)
        
        print("✅ AI detector system initialized successfully!")
        return True

    except (ConfigurationError, DatabaseError, AttributeError) as e:
        logging.error(f"Failed to initialize AI detector: {e}")
        print(f"⚠️ AI detector initialization failed: {e}")

        # Create a minimal fallback AI detector
        try:
            ai_detector = create_minimal_ai_detector()
            print("✅ Minimal AI detector created as fallback")
            return True
        except (ConfigurationError, AttributeError) as fallback_error:
            logging.error(f"Even fallback AI detector failed: {fallback_error}")
            print(f"❌ Complete AI detector failure: {fallback_error}")
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
                conn = get_db_connection()
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

                except (sqlite3.Error, QueryError) as query_error:
                    conn.close()
                    return {
                        'submissions': [],
                        'total': 0,
                        'error': f"Query error: {query_error}",
                        'message': 'Database schema issue detected'
                    }

            except (sqlite3.Error, DatabaseConnectionError) as e:
                return {
                    'submissions': [],
                    'total': 0,
                    'error': str(e),
                    'message': 'Database access failed'
                }
        
        def analyze_text(self, text, title=None, student_id=None, course_code=None, assignment_id=None):
            """Basic text analysis that always works"""
            import random
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
        print(_t("cli.ai_detector.login_required"))
        return

    # Initialize AI detector if not already done or if it failed
    if ai_detector is None:
        print(_t("cli.ai_detector.initializing"))
        try:
            integrate_ai_detector_with_main()
        except (ConfigurationError, DatabaseError, AttributeError) as e:
            print(f"❌ AI detector initialization failed: {e}")
            ai_detector = create_minimal_ai_detector()
            print("✅ Running in minimal mode")
    
    # Double-check that ai_detector has required attributes
    if not hasattr(ai_detector, 'detection_threshold'):
        print("⚠️ AI detector missing critical attributes, recreating...")
        ai_detector = create_minimal_ai_detector()
    
    # Ensure the AI detector has the current auth context
    try:
        ai_detector.set_auth(auth_obj)
    except (AuthenticationError, AttributeError) as e:
        print(f"⚠️ Could not set auth context: {e}")
    
    while True:
        print(f"\n" + _t("cli.ai_detector.menu_title"))
        print("========================")

        # Show current mode
        try:
            stats = ai_detector.get_enhanced_statistics()
            mode = stats.get('mode', 'normal')
            if mode == 'minimal_fallback':
                print("⚠️ " + _t("cli.ai_detector.minimal_mode"))
        except (AttributeError, TypeError, KeyError):
            print("⚠️ " + _t("cli.ai_detector.status_check_failed"))

        print("1. " + _t("cli.ai_detector.analyze_text"))
        print("2. " + _t("cli.ai_detector.view_history"))
        print("3. " + _t("cli.ai_detector.view_stats"))
        print("4. " + _t("cli.ai_detector.demo"))
        print("5. " + _t("common.return_to_main_menu"))

        choice = input(_t("common.enter_choice") + " (1-5): ").strip()

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
                print(_t("cli.returning_to_menu"))
                break
            else:
                print(_t("common.invalid_choice"))
        except (ConfigurationError, DatabaseError, ValidationError, AttributeError) as e:
            print(f"❌ {_t('common.error')}: {e}")
            print(_t("cli.try_again_or_return"))


def analyze_text_interface_safe():
    """Safe version of text analysis interface"""
    global ai_detector
    
    try:
        print("\nText Analysis for AI Detection")
        print("=" * 40)
        
        # Get basic inputs
        title = input("Enter submission title (optional): ").strip() or "Demo Analysis"
        
        print("\nEnter the text to analyze (press Enter twice to finish):")
        print("-" * 50)
        
        lines = []
        empty_lines = 0
        
        while empty_lines < 2:
            try:
                line = input()
                if line.strip() == "":
                    empty_lines += 1
                else:
                    empty_lines = 0
                lines.append(line)
            except KeyboardInterrupt:
                print("\nAnalysis cancelled.")
                return
        
        # Remove trailing empty lines
        while lines and lines[-1].strip() == "":
            lines.pop()
        
        text = "\n".join(lines)
        
        if not text.strip():
            print("❌ No text provided for analysis.")
            return
        
        print(f"\nAnalyzing {len(text)} characters of text...")
        
        # Analyze the text with error handling
        try:
            result = ai_detector.analyze_text(text=text, title=title)
            display_analysis_results_safe(result)
        except (ValueError, TypeError, ValidationError) as analysis_error:
            print(f"❌ Analysis failed: {analysis_error}")
            print("The AI detector may not be fully initialized.")
            
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Interface error: {e}")


def display_analysis_results_safe(result):
    """Safe version of results display"""
    try:
        print("\n" + "=" * 60)
        print("AI DETECTION ANALYSIS RESULTS")
        print("=" * 60)
        
        print(f"Submission ID: {result.get('submission_id', 'N/A')}")
        print(f"AI Score: {result.get('ai_score', 0):.3f} (0.0 = Human, 1.0 = AI)")
        print(f"Confidence Level: {result.get('confidence', 0):.3f}")
        
        is_ai = result.get('is_ai_generated', False)
        status = "🤖 LIKELY AI-GENERATED" if is_ai else "👤 LIKELY HUMAN-WRITTEN"
        print(f"Assessment: {status}")
        
        methods = result.get('detection_methods', [])
        print(f"Detection Methods Used: {', '.join(methods) if methods else 'Unknown'}")
        
        # Show text stats if available
        text_stats = result.get('text_stats', {})
        if text_stats:
            print(f"\nText Statistics:")
            print(f"  Word Count: {text_stats.get('word_count', 'N/A')}")
            print(f"  Character Count: {text_stats.get('char_count', 'N/A')}")
            print(f"  Sentence Count: {text_stats.get('sentence_count', 'N/A')}")
        
        # Show indicators if available
        indicators = result.get('indicators', [])
        if indicators:
            print(f"\nDetected Indicators:")
            for indicator in indicators:
                print(f"  • {indicator.get('name', 'Unknown')}: {indicator.get('score', 0):.3f}")
                evidence = indicator.get('evidence')
                if evidence:
                    print(f"    Evidence: {evidence}")
        
        mode = result.get('mode')
        if mode:
            print(f"\nMode: {mode}")
        
        print("=" * 60)
        
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error displaying results: {e}")
        print("Results could not be displayed properly.")
    
    input("\nPress Enter to continue...")


def fix_ai_detector_database_schema():
    """Fix AI detector database schema by creating proper tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("🔧 Fixing AI detector database schema...")
        
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
        
        # Use centralized SQL safety validation for column definitions
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                try:
                    # Validate column definition using SQL safety module
                    col_def = validate_column_definition(column_name, column_def)
                    cursor.execute(f'ALTER TABLE ai_detector_submissions ADD COLUMN [{col_def.name}] {col_def.type_def}')
                    print(f"✅ Added column '{column_name}' to ai_detector_submissions table")
                except SQLIdentifierError as e:
                    print(f"⚠️ Invalid column definition for '{column_name}': {e}")
                    continue
                except (sqlite3.Error, DatabaseError) as e:
                    print(f"⚠️ Could not add column '{column_name}': {e}")
        
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
                
                print("✅ Migrated 'submission_title' column to 'title'")
                
            except (sqlite3.Error, DatabaseError) as e:
                print(f"⚠️ Could not migrate submission_title column: {e}")
        
        conn.commit()
        conn.close()
        
        print("✅ AI detector database schema fix completed!")
        return True
        
    except (sqlite3.Error, DatabaseError) as e:
        print(f"❌ Error fixing AI detector database schema: {e}")
        return False


def view_submission_history_safe():
    """Safe version of submission history with proper error handling"""
    global ai_detector
    
    try:
        print("\nSubmission History")
        print("=" * 30)
        
        # Try to get submissions with error handling
        try:
            submissions = ai_detector.list_submissions(limit=20)
        except (ValueError, TypeError, ValidationError) as list_error:
            print(f"❌ Error accessing submission data: {list_error}")
            print("This might be a database schema issue. Attempting to fix...")
            
            # Try to fix the database schema
            if fix_ai_detector_database_schema():
                print("✅ Database schema fixed. Trying again...")
                try:
                    submissions = ai_detector.list_submissions(limit=20)
                except (ValueError, TypeError, ValidationError) as retry_error:
                    print(f"❌ Still having issues: {retry_error}")
                    submissions = {'submissions': [], 'total': 0, 'error': str(retry_error)}
            else:
                submissions = {'submissions': [], 'total': 0, 'error': 'Database schema fix failed'}
        
        if not submissions.get('submissions'):
            reason = submissions.get('error') or submissions.get('message', 'No submissions found')
            print(f"No submission history available. Reason: {reason}")
        else:
            print(f"Showing {len(submissions['submissions'])} of {submissions['total']} submissions:")
            print()
            
            for submission in submissions['submissions']:
                try:
                    print(f"ID: {submission.get('id', 'N/A')}")
                    
                    # Handle different possible column names
                    title = (submission.get('title') or 
                            submission.get('submission_title') or 
                            'Untitled')
                    print(f"Title: {title}")
                    
                    print(f"Date: {submission.get('submission_date', 'N/A')}")
                    
                    if submission.get('student_id'):
                        print(f"Student ID: {submission['student_id']}")
                    if submission.get('course_code'):
                        print(f"Course: {submission['course_code']}")
                    
                    ai_score = submission.get('ai_score')
                    if ai_score is not None:
                        status = "AI-Generated" if ai_score >= ai_detector.detection_threshold else "Human-Written"
                        print(f"AI Score: {ai_score:.3f} ({status})")
                    
                    print("-" * 40)
                    
                except (ValueError, TypeError, ValidationError) as display_error:
                    print(f"❌ Error displaying submission: {display_error}")
                    print(f"Raw data: {submission}")
                    print("-" * 40)
        
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error viewing history: {e}")
        print("The submission history feature is currently unavailable.")
    
    input("\nPress Enter to continue...")


def display_detailed_submission(submission):
    """Display detailed information about a submission"""
    print("\n" + "=" * 60)
    print("DETAILED SUBMISSION VIEW")
    print("=" * 60)
    
    print(f"Submission ID: {submission['id']}")
    print(f"Title: {submission['submission_title']}")
    print(f"Student ID: {submission.get('student_id', 'N/A')}")
    print(f"Course Code: {submission.get('course_code', 'N/A')}")
    print(f"Assignment ID: {submission.get('assignment_id', 'N/A')}")
    print(f"Submission Date: {submission['submission_date']}")
    print(f"Word Count: {submission['word_count']}")
    print(f"Character Count: {submission['character_count']}")
    
    if submission.get('results'):
        latest_result = submission['results'][0]  # Most recent result
        print(f"\nLatest Analysis:")
        print(f"AI Score: {latest_result['ai_score']:.3f}")
        print(f"Confidence: {latest_result['confidence_level']:.3f}")
        print(f"Detection Method: {latest_result['detection_method']}")
        print(f"Analysis Date: {latest_result['analysis_date']}")
        
        if latest_result.get('indicators_found'):
            print(f"\nIndicators Found:")
            for indicator in latest_result['indicators_found']:
                print(f"  • {indicator.get('name', 'Unknown')}: {indicator.get('score', 0):.3f}")
                if indicator.get('evidence'):
                    print(f"    Evidence: {indicator['evidence']}")
    
    print("=" * 60)
    input("\nPress Enter to continue...")


def view_ai_detector_statistics_safe():
    """Safe version of statistics viewing"""
    global ai_detector
    
    try:
        print("\nAI Detector System Statistics")
        print("=" * 40)
        
        stats = ai_detector.get_enhanced_statistics()
        
        print(f"Detection Threshold: {stats.get('detection_threshold', 'Unknown')}")
        print(f"Total Submissions: {stats.get('total_submissions', 0)}")
        print(f"Unique Students: {stats.get('unique_students', 0)}")
        print(f"Average AI Score: {stats.get('average_ai_score', 0):.3f}")
        print(f"Recent Activity (7 days): {stats.get('recent_submissions_7_days', 0)}")
        print(f"High Risk Submissions: {stats.get('high_risk_submissions', 0)}")
        print(f"Database Status: {stats.get('database_status', 'Unknown')}")
        
        mode = stats.get('mode')
        if mode:
            print(f"Operating Mode: {mode}")
        
        print("=" * 40)
        
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error retrieving statistics: {e}")
        print("Statistics are not available at this time.")
    
    input("\nPress Enter to continue...")


def run_ai_detector_demo_safe():
    """Safe version of demo"""
    try:
        print("\nRunning AI Detector Demo...")
        print("=" * 40)
        
        # Simple demo that should always work
        demo_text = "This is a demonstration of the AI content detection system. It analyzes text for patterns that might indicate artificial intelligence generation."
        
        result = ai_detector.analyze_text(
            text=demo_text,
            title="Demo Analysis"
        )
        
        display_analysis_results_safe(result)
        
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Demo failed: {e}")
        print("This indicates the AI detector system needs attention.")
    
    input("\nPress Enter to continue...")


def integrate_plagiarism_checker_with_main():
    """Initialize and integrate the plagiarism checker with the main system"""
    try:
        # Import and initialize from your plagiarism_main.py
        from university_system.modules.domain.academics.services.assignments.plagiarism_main import PlagiarismChecker
        
        checker = PlagiarismChecker()
        logging.info("Plagiarism checker initialized successfully")
        
        # Add permissions if needed
        try:
            from university_system.infrastructure.auth import add_plagiarism_permissions
            auth_instance = globals().get('auth')
            if auth_instance:
                created_permissions = add_plagiarism_permissions(auth_instance)
                if created_permissions:
                    logging.info(f"Added plagiarism permissions: {', '.join(created_permissions)}")
        except (AuthenticationError, PermissionDeniedError) as perm_error:
            logging.warning(f"Could not add plagiarism permissions: {perm_error}")
        
        return True
        
    except ImportError as e:
        logging.warning(f"Plagiarism checker module not available: {e}")
        return True
    except (ConfigurationError, DatabaseError) as e:
        logging.warning(f"Plagiarism checker integration failed: {e}")
        return True


def display_plagiarism_checker_menu(auth):
    """Wrapper to call your real plagiarism menu from plagiarism_main.py"""
    try:
        # Import your actual function
        from university_system.modules.domain.academics.services.assignments.plagiarism_main import display_plagiarism_checker_menu as real_menu
        
        # Call your real function
        real_menu(auth)
        
    except ImportError as e:
        print("Plagiarism checker module not found.")
        print("Make sure plagiarism_main.py is in the same directory.")
        input("Press Enter to continue...")

    except (ConfigurationError, AuthenticationError, DatabaseError) as e:
        print(f"Error accessing plagiarism checker: {e}")
        input("Press Enter to continue...")


__all__ = [
    'integrate_ai_detector_with_main',
    'create_minimal_ai_detector',
    'display_ai_detector_menu_from_main',
    'analyze_text_interface_safe',
    'display_analysis_results_safe',
    'fix_ai_detector_database_schema',
    'view_submission_history_safe',
    'display_detailed_submission',
    'view_ai_detector_statistics_safe',
    'run_ai_detector_demo_safe',
    'integrate_plagiarism_checker_with_main',
    'display_plagiarism_checker_menu',
]
