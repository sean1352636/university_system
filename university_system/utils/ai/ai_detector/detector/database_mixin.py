"""Database initialization and management mixin for AIDetector."""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from university_system.utils.ai.ai_detector.core.constants import (
    logger, ML_AVAILABLE, sqlite3, DEFAULT_DB_PATH,
)
from university_system.utils.ai.ai_detector.core.exceptions import DatabaseError
from university_system.utils.ai.ai_detector.analyzers import (
    TemporalAnalyzer, CitationVerifier, BehavioralAnalyzer,
    MultiModalAnalyzer, AdversarialDetector,
)
from university_system.utils.ai.ai_detector.features import (
    FederatedLearning, PrivacyManager, BiasDetector, BlockchainAuditTrail,
    PredictiveAnalytics, RealTimeProcessor, InstitutionBenchmarking, StudentSelfCheckTool,
)
from university_system.utils.ai.ai_detector.ml import AdvancedMLTrainer
from university_system.utils.ai.ai_detector.visualization import VisualAnalyzer
from university_system.utils.ai.ai_detector.integration import APIGateway, ComplianceManager


class DatabaseMixin:
    """Mixin providing __init__, database connection, and schema management."""

    def __init__(self, db_path=str(DEFAULT_DB_PATH), detection_threshold=0.7):
        """Enhanced initialization with proper attribute setup - FIXED VERSION"""

        # CRITICAL: Initialize base attributes FIRST - this is the key fix!
        self.db_path = db_path
        self.detection_threshold = detection_threshold  # MUST be set early!
        self.current_user = None

        # Initialize missing attributes that other methods depend on
        self.detection_methods = {
            'pattern_matching': True,
            'statistical_analysis': True,
            'behavioral_analysis': True,
            'temporal_analysis': True,
            'citation_verification': True
        }
        self.style_profiles = {}

        # Initialize all the advanced components (these can come after base attributes)
        try:
            self.temporal_analyzer = TemporalAnalyzer(self)
            self.citation_verifier = CitationVerifier(self)
            self.behavioral_analyzer = BehavioralAnalyzer(self)
            self.multimodal_analyzer = MultiModalAnalyzer(self)
            self.adversarial_detector = AdversarialDetector(self)
            self.federated_learning = FederatedLearning(self)
            self.privacy_manager = PrivacyManager(self)
            self.bias_detector = BiasDetector(self)
            self.blockchain_audit = BlockchainAuditTrail(self)
            self.predictive_analytics = PredictiveAnalytics(self)
            self.realtime_processor = RealTimeProcessor(self)
            self.institution_benchmarking = InstitutionBenchmarking(self)
            self.student_self_check = StudentSelfCheckTool(self)
            self.advanced_ml_trainer = AdvancedMLTrainer(self)
            self.visual_analyzer = VisualAnalyzer(self)
            self.api_gateway = APIGateway(self)
            self.compliance_manager = ComplianceManager(self)

            print("All AI detector components initialized successfully")

        except Exception as component_error:
            # Don't fail completely if advanced components fail
            print(f"Some advanced components failed to initialize: {component_error}")
            # Set minimal fallbacks
            self.temporal_analyzer = None
            self.citation_verifier = None
            # ... etc for other components

        # Initialize database and setup
        try:
            self._init_database()
            self._init_advanced_db_tables()

            # Initialize privacy and compliance frameworks
            if hasattr(self, 'privacy_manager') and self.privacy_manager:
                self.privacy_manager.initialize_privacy_tables()
            if hasattr(self, 'compliance_manager') and self.compliance_manager:
                self.compliance_manager.initialize_compliance_framework(['GDPR', 'FERPA'])

            # Fix database schema issues
            self.fix_database_schema()

            print("AI detector database initialization completed")

        except Exception as db_error:
            print(f"Database initialization had issues: {db_error}")
            # Continue with basic functionality even if advanced features fail

    def _init_database(self):
        """Initialize the main database tables"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Main submissions table
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

            # Results table
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

            # Users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            ''')

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")

    def _init_advanced_db_tables(self):
        """Initialize additional database tables for new features"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Submission metadata table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_detector_metadata (
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

            # Institution data
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS institutions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,
                country TEXT,
                created_at TEXT NOT NULL
            )
            ''')

            # Student demographics (for bias analysis)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_demographics (
                student_id TEXT PRIMARY KEY,
                age_group TEXT,
                gender TEXT,
                ethnicity TEXT,
                native_language TEXT,
                academic_level TEXT,
                accommodations TEXT
            )
            ''')

            # Main submissions table
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

            # Results table
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

            # Real-time processing queue
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_queue (
                id TEXT PRIMARY KEY,
                submission_data TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT DEFAULT 'queued',
                created_at TEXT NOT NULL,
                processed_at TEXT
            )
            ''')

            # Advanced detection results
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS advanced_detection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                temporal_analysis TEXT,
                citation_analysis TEXT,
                behavioral_analysis TEXT,
                multimodal_analysis TEXT,
                adversarial_analysis TEXT,
                ensemble_prediction TEXT,
                risk_prediction TEXT,
                bias_adjusted_score REAL,
                blockchain_hash TEXT,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            )
            ''')

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error initializing advanced database tables: {e}")

    def _safe_db_connect(self):
        """Safely connect to database with proper error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            raise DatabaseError(f"Failed to connect to database: {e}")

    def _get_fallback_statistics(self) -> Dict[str, Any]:
        """Fallback statistics when database is unavailable"""
        return {
            'total_submissions': 0,
            'unique_students': 0,
            'average_ai_score': 0.0,
            'recent_submissions_7_days': 0,
            'high_risk_submissions': 0,
            'detection_threshold': getattr(self, 'detection_threshold', 0.7),
            'active_style_profiles': 0,
            'active_detection_methods': 0,
            'database_status': 'error',
            'error': 'Database unavailable',
            'generated_at': datetime.now().isoformat()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Basic statistics method (wrapper for get_enhanced_statistics)
        This fixes the missing get_statistics method error
        """
        try:
            return self.get_enhanced_statistics()
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'active_style_profiles': 0,
                'error': str(e)
            }

    def fix_detector_instance(detector):
        """Quick fix for an existing detector instance"""
        if not hasattr(detector, 'detection_threshold'):
            detector.detection_threshold = 0.7

        if not hasattr(detector, 'detection_methods'):
            detector.detection_methods = {
                'pattern_matching': True,
                'statistical_analysis': True,
                'behavioral_analysis': True,
                'temporal_analysis': True,
                'citation_verification': True
            }

        if not hasattr(detector, 'style_profiles'):
            detector.style_profiles = {}

        # Try to fix database schema
        try:
            detector.fix_database_schema()
        except Exception:
            pass

        return detector

    def get_statistics_fallback(self) -> Dict[str, Any]:
        """Fallback statistics method that doesn't break"""
        try:
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'active_style_profiles': 0,
                'detection_threshold': getattr(self, 'detection_threshold', 0.7),
                'status': 'basic_mode',
                'message': 'Running in basic mode due to initialization issues'
            }
        except Exception:
            return {
                'error': 'Statistics unavailable',
                'status': 'error'
            }

    def get_submission_history(self, student_id: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Fixed submission history method that handles missing column names
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Build query with proper column handling
            base_query = '''
            SELECT
                s.id,
                s.student_id,
                s.submission_text,
                COALESCE(s.title, 'Untitled') as title,
                s.course_code,
                s.assignment_id,
                s.submission_date,
                s.word_count,
                s.character_count,
                s.institution_id,
                r.ai_score,
                r.confidence,
                r.created_at as analysis_date
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            '''

            if student_id:
                query = base_query + " WHERE s.student_id = ? ORDER BY s.submission_date DESC LIMIT ?"
                params = (student_id, limit)
            else:
                query = base_query + " ORDER BY s.submission_date DESC LIMIT ?"
                params = (limit,)

            cursor.execute(query, params)
            submissions = []

            for row in cursor.fetchall():
                try:
                    submission = {
                        'id': row['id'],
                        'student_id': row['student_id'],
                        'title': row['title'] or 'Untitled',
                        'course_code': row['course_code'],
                        'assignment_id': row['assignment_id'],
                        'submission_date': row['submission_date'],
                        'word_count': row['word_count'],
                        'character_count': row['character_count'],
                        'institution_id': row['institution_id'],
                        'ai_score': row['ai_score'],
                        'confidence': row['confidence'],
                        'analysis_date': row['analysis_date'],
                        'is_ai_generated': (row['ai_score'] or 0) >= self.detection_threshold,
                        'text_preview': (row['submission_text'] or '')[:200] + "..." if len(row['submission_text'] or '') > 200 else (row['submission_text'] or '')
                    }
                    submissions.append(submission)
                except Exception as row_error:
                    logger.warning(f"Error processing submission row: {row_error}")
                    continue

            conn.close()

            return {
                'submissions': submissions,
                'total_count': len(submissions),
                'student_filter': student_id,
                'limit': limit
            }

        except Exception as e:
            logger.error(f"Error getting submission history: {e}")
            return {
                'submissions': [],
                'total_count': 0,
                'error': str(e),
                'student_filter': student_id,
                'limit': limit
            }

    def fix_database_schema(self):
        """
        Fix database schema issues by adding missing columns
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Check if title column exists, if not add it
            cursor.execute("PRAGMA table_info(ai_detector_submissions)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'title' not in columns and 'submission_title' in columns:
                # Rename submission_title to title
                cursor.execute('''
                ALTER TABLE ai_detector_submissions
                RENAME COLUMN submission_title TO title
                ''')
                logger.info("Renamed submission_title column to title")

            elif 'title' not in columns:
                # Add title column
                cursor.execute('''
                ALTER TABLE ai_detector_submissions
                ADD COLUMN title TEXT
                ''')
                logger.info("Added missing title column")

            # Ensure other common columns exist
            # Define allowed column names and types for validation
            ALLOWED_COLUMN_TYPES = {'TEXT', 'INTEGER', 'REAL', 'BLOB'}
            ALLOWED_COLUMN_NAMES = {'institution_id', 'word_count', 'character_count'}

            missing_columns = {
                'institution_id': 'TEXT',
                'word_count': 'INTEGER',
                'character_count': 'INTEGER'
            }

            for col_name, col_type in missing_columns.items():
                # Validate column name and type to prevent SQL injection
                if col_name not in ALLOWED_COLUMN_NAMES:
                    logger.error(f"Invalid column name: {col_name}")
                    continue
                if col_type not in ALLOWED_COLUMN_TYPES:
                    logger.error(f"Invalid column type: {col_type}")
                    continue

                if col_name not in columns:
                    cursor.execute(f'''
                    ALTER TABLE ai_detector_submissions
                    ADD COLUMN {col_name} {col_type}
                    ''')
                    logger.info(f"Added missing {col_name} column")

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error fixing database schema: {e}")
