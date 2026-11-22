"""Database initialization and management mixin for AIDetector."""

from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import (
    logger, ML_AVAILABLE, sqlite3, DEFAULT_DB_PATH,
)
from education_system.systems.university.shared.ai.ai_detector.core.exceptions import DatabaseError
from education_system.systems.university.shared.ai.ai_detector.analyzers import (
    TemporalAnalyzer, CitationVerifier, BehavioralAnalyzer,
    MultiModalAnalyzer, AdversarialDetector,
)
from education_system.systems.university.shared.ai.ai_detector.features import (
    FederatedLearning, PrivacyManager, BiasDetector, BlockchainAuditTrail,
    PredictiveAnalytics, RealTimeProcessor, InstitutionBenchmarking, StudentSelfCheckTool,
)
from education_system.systems.university.shared.ai.ai_detector.ml import AdvancedMLTrainer
from education_system.systems.university.shared.ai.ai_detector.visualization import VisualAnalyzer
from education_system.systems.university.shared.ai.ai_detector.integration import APIGateway, ComplianceManager
from education_system.systems.university.infrastructure.database.schemas.users_table import ensure_users_table


_COMPONENTS = (
    ("temporal_analyzer", TemporalAnalyzer), ("citation_verifier", CitationVerifier),
    ("behavioral_analyzer", BehavioralAnalyzer), ("multimodal_analyzer", MultiModalAnalyzer),
    ("adversarial_detector", AdversarialDetector), ("federated_learning", FederatedLearning),
    ("privacy_manager", PrivacyManager), ("bias_detector", BiasDetector),
    ("blockchain_audit", BlockchainAuditTrail), ("predictive_analytics", PredictiveAnalytics),
    ("realtime_processor", RealTimeProcessor), ("institution_benchmarking", InstitutionBenchmarking),
    ("student_self_check", StudentSelfCheckTool), ("advanced_ml_trainer", AdvancedMLTrainer),
    ("visual_analyzer", VisualAnalyzer), ("api_gateway", APIGateway),
    ("compliance_manager", ComplianceManager),
)


class DatabaseMixin:
    """Mixin providing __init__, database connection, schema, the signed-in
    person and the review threshold.

    The detector always runs as a real signed-in person (:meth:`set_auth`);
    there is no fallback user. Results are scoped by the integrity rules
    (``application/integrity/access``): module staff see readings on modules
    they teach, reviewers and integrity officers all of them; students use
    their own readings in the Academic Integrity window instead.
    """

    def __init__(self, db_path=str(DEFAULT_DB_PATH), detection_threshold=None, auth=None):
        self.db_path = db_path
        self.current_user = None
        self.auth = None
        if detection_threshold is not None:
            logger.info("AIDetector(detection_threshold=...) is ignored: the review threshold "
                        "is the integrity setting ai_review_threshold")
        # Which informational checks a full reading runs, for this session.
        # The indicators themselves always run: they are the reading.
        self.detection_methods = {
            'citation_verification': True,
            'disguised_characters': True,
            'paraphrase_tools': True,
            'prompt_artifacts': True,
            'behavioral_analysis': True,
            'temporal_analysis': True,
        }
        self.style_profiles = {}
        self.component_errors = {}

        # Each component on its own, so one failing does not leave the rest
        # unset; a failed one is None and its error is kept for the status view.
        for name, cls in _COMPONENTS:
            try:
                setattr(self, name, cls(self))
            except Exception as exc:
                logger.exception("AI detector component %s failed to start", name)
                setattr(self, name, None)
                self.component_errors[name] = str(exc)

        self._init_database()
        if self.privacy_manager is not None:
            self.privacy_manager.initialize_privacy_tables()
        if self.compliance_manager is not None:
            self.compliance_manager.initialize_compliance_framework(['GDPR', 'FERPA'])
        if auth is not None:
            self.set_auth(auth)

    # ── who is using the detector ────────────────────────────────────────

    def set_auth(self, auth):
        """The signed-in person: an auth object with ``current_user`` or a
        user dict with ``username``."""
        self.auth = auth
        user = auth if isinstance(auth, dict) else getattr(auth, 'current_user', None)
        if callable(user):
            user = user()
        self.current_user = user if isinstance(user, dict) and user.get('username') else None

    def _person(self, conn):
        """The signed-in person as the integrity rules see them."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        if not self.current_user:
            raise PermissionError("Sign in to use the AI Content Detector")
        who = integrity_access.from_user(conn, self.current_user)
        if who is None:
            raise PermissionError("Sign in to use the AI Content Detector")
        return who

    def _username(self) -> str:
        return (self.current_user or {}).get('username') or 'system'

    def require_staff(self, conn=None):
        """The signed-in member of staff, or ``PermissionError``."""
        own = conn is None
        conn = conn or self._safe_db_connect()
        try:
            who = self._person(conn)
            if not who.is_staff:
                raise PermissionError("The AI Content Detector is for staff")
            return who
        finally:
            if own:
                conn.close()

    def require_officer(self, conn=None):
        """An integrity officer or administrator, or ``PermissionError``."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        own = conn is None
        conn = conn or self._safe_db_connect()
        try:
            who = self._person(conn)
            if not integrity_access.is_officer(conn, who):
                raise PermissionError("Only an integrity officer can do this")
            return who
        finally:
            if own:
                conn.close()

    def _module_scope(self, conn):
        """Modules the signed-in person may see readings on; ``None`` = all."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        return integrity_access.taught_modules(conn, self.require_staff(conn))

    @staticmethod
    def _scope_sql(modules, column="s.course_code"):
        if modules is None:
            return "", []
        return f" AND {column} IN ({','.join('?' * len(modules)) or 'NULL'})", list(modules)

    # ── the review threshold ────────────────────────────────────────────

    @property
    def detection_threshold(self) -> float:
        """The one review threshold: integrity setting ``ai_review_threshold``."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        conn = self._safe_db_connect()
        try:
            return integrity_access.number(conn, "ai_review_threshold")
        finally:
            conn.close()

    @detection_threshold.setter
    def detection_threshold(self, value):
        """Change the integrity setting (integrity officers only)."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        conn = self._safe_db_connect()
        try:
            integrity_access.set_setting(conn, self._person(conn), "ai_review_threshold", value)
            conn.commit()
        finally:
            conn.close()

    # ── schema and connections ──────────────────────────────────────────

    def _init_database(self):
        """The detector's tables (declared in ``ai_detector_schema``)."""
        from education_system.systems.university.infrastructure.database.schemas import (
            ai_detector_schema,
        )
        conn = self._safe_db_connect()
        try:
            ensure_users_table(conn.cursor())
            ai_detector_schema.apply_to_connection(conn)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Failed to initialize database: {e}") from e
        finally:
            conn.close()

    def _init_advanced_db_tables(self):
        """Kept for callers: the tables are all in ``ai_detector_schema``."""
        self._init_database()

    def _safe_db_connect(self):
        """A connection (rows by name, the university's pragmas)."""
        from education_system.systems.university.infrastructure.database.db import get_connection
        try:
            return get_connection(self.db_path)
        except Exception as e:
            raise DatabaseError(f"Failed to connect to database: {e}") from e

    def _get_connection(self):
        """The name the alert, audit, batch, course and model mixins use."""
        return self._safe_db_connect()

    def _get_fallback_statistics(self) -> Dict[str, Any]:
        """Fallback statistics when database is unavailable"""
        return {
            'total_submissions': 0,
            'unique_students': 0,
            'average_ai_score': 0.0,
            'recent_submissions_7_days': 0,
            'high_risk_submissions': 0,
            'detection_threshold': None,
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
        """Kept for callers: bring an existing detector's tables up to date."""
        detector.fix_database_schema()
        return detector

    def get_statistics_fallback(self) -> Dict[str, Any]:
        """Fallback statistics method that doesn't break"""
        try:
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'active_style_profiles': 0,
                'detection_threshold': None,
                'status': 'basic_mode',
                'message': 'Running in basic mode due to initialization issues'
            }
        except Exception:
            return {
                'error': 'Statistics unavailable',
                'status': 'error'
            }

    def get_submission_history(self, student_id: str = None, limit: int = 50) -> Dict[str, Any]:
        """Readings the signed-in member of staff may see (modules they
        review; all for reviewers and integrity officers), newest first."""
        conn = self._safe_db_connect()
        try:
            modules = self._module_scope(conn)
            limit_at = self.detection_threshold
            scope, params = self._scope_sql(modules)
            sql = (
                "SELECT s.id, s.student_id, s.submission_text, COALESCE(s.title, 'Untitled') AS "
                "title, s.course_code, s.assignment_id, s.submission_date, s.word_count, "
                "s.character_count, s.institution_id, s.assignment_submission_id, s.checked_by, "
                "r.id AS result_id, r.ai_score, r.confidence, r.level, r.method, "
                "r.created_at AS analysis_date FROM ai_detector_submissions s "
                "LEFT JOIN ai_detector_results r ON s.id = r.submission_id WHERE 1 = 1" + scope)
            if student_id:
                sql += " AND s.student_id = ?"
                params.append(str(student_id))
            sql += " ORDER BY s.submission_date DESC LIMIT ?"
            params.append(int(limit))
            submissions = []
            for row in conn.execute(sql, params).fetchall():
                text = row['submission_text'] or ''
                score = row['ai_score'] or 0
                submissions.append({
                    'id': row['id'], 'result_id': row['result_id'],
                    'student_id': row['student_id'], 'title': row['title'] or 'Untitled',
                    'course_code': row['course_code'], 'assignment_id': row['assignment_id'],
                    'assignment_submission_id': row['assignment_submission_id'],
                    'submission_date': row['submission_date'], 'word_count': row['word_count'],
                    'character_count': row['character_count'],
                    'institution_id': row['institution_id'], 'ai_score': row['ai_score'],
                    'confidence': row['confidence'], 'level': row['level'],
                    'method': row['method'], 'checked_by': row['checked_by'],
                    'analysis_date': row['analysis_date'],
                    'needs_review': score >= limit_at,
                    'is_ai_generated': score >= limit_at,   # kept for screens: = needs_review
                    'text_preview': text[:200] + "..." if len(text) > 200 else text,
                })
            return {'submissions': submissions, 'total_count': len(submissions),
                    'student_filter': student_id, 'limit': limit}
        finally:
            conn.close()

    def fix_database_schema(self):
        """Bring the detector's tables up to date (``ai_detector_schema``,
        which also owns the columns this used to add at runtime)."""
        self._init_database()
