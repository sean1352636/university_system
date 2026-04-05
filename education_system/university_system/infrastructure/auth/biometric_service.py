"""
Biometric Authentication Service

Provides biometric authentication capabilities including facial recognition
and fingerprint verification for the University Management System.

Features:
- Face enrollment and verification using 128-D encoding vectors
- Fingerprint template enrollment and verification
- Biometric enrollment management (list, revoke)
- Authentication attempt logging with device info
- Secure template storage (NEVER stores raw images)
- Template integrity verification via SHA-256 hashing

Optional Dependencies:
    - ``face_recognition``: Required for facial recognition features.
      Install with: ``pip install face_recognition``
    - ``numpy``: Required for array operations on face encodings.
      Install with: ``pip install numpy``

    If these libraries are not installed, face-related methods return
    error dicts explaining the missing dependencies. Fingerprint methods
    work independently of these libraries.

Database Tables:
    - biometric_enrollments: Stores enrolled biometric templates
    - biometric_auth_log: Audit log of all authentication attempts

Security:
    - Raw biometric images are NEVER stored in the database
    - Face images are immediately converted to 128-D float encodings
    - Templates are stored as pickled binary blobs
    - SHA-256 hashes are stored for template integrity verification
    - All authentication attempts are logged regardless of outcome

Usage:
    from education_system.university_system.infrastructure.auth.biometric_service import BiometricService

    service = BiometricService(db_manager=db_manager, face_threshold=0.6)
    result = service.enroll_face(user_id='user1', image_data=image_bytes)
    if result['success']:
        print("Face enrolled:", result['enrollment_id'])
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import pickle
import secrets
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from education_system.university_system.infrastructure.database.db import sqlite3

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Optional dependency: face_recognition
try:
    import face_recognition as _face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    _face_recognition = None
    FACE_RECOGNITION_AVAILABLE = False

# Optional dependency: numpy
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Biometric type constants
BIOMETRIC_TYPE_FACE = 'face'
BIOMETRIC_TYPE_FINGERPRINT = 'fingerprint'

# Default thresholds for biometric matching
DEFAULT_FACE_THRESHOLD = 0.6
DEFAULT_FINGERPRINT_THRESHOLD = 0.7

# Maximum number of enrollments per user per biometric type
MAX_ENROLLMENTS_PER_TYPE = 5


class BiometricService:
    """Biometric authentication service for face and fingerprint verification.

    Handles the full lifecycle of biometric authentication including
    enrollment, verification, and management of biometric templates.

    Raw biometric data (images, scans) is NEVER stored. Only derived
    templates (encodings, hashes) are persisted in the database.

    Parameters
    ----------
    db_manager : DatabaseConnectionManager
        Database connection manager instance providing ``get_connection()``
        context manager.
    face_threshold : float, optional
        Maximum distance threshold for face matching. Lower values are
        stricter. A match is successful when the computed distance is
        below this threshold. Defaults to ``0.6``.
    fingerprint_threshold : float, optional
        Minimum similarity score threshold for fingerprint matching.
        Higher values are stricter. A match is successful when the
        computed similarity exceeds this threshold. Defaults to ``0.7``.

    Attributes
    ----------
    db_manager : DatabaseConnectionManager
        The database connection manager.
    face_threshold : float
        The face matching distance threshold.
    fingerprint_threshold : float
        The fingerprint matching similarity threshold.

    Examples
    --------
    >>> from education_system.university_system.infrastructure.auth.managers import DatabaseConnectionManager
    >>> db_mgr = DatabaseConnectionManager('path/to/db.db')
    >>> bio = BiometricService(db_manager=db_mgr, face_threshold=0.5)
    >>> result = bio.enroll_face('user1', image_bytes)
    >>> if result['success']:
    ...     print("Enrolled:", result['enrollment_id'])
    """

    def __init__(
        self,
        db_manager,
        face_threshold: float = DEFAULT_FACE_THRESHOLD,
        fingerprint_threshold: float = DEFAULT_FINGERPRINT_THRESHOLD,
    ):
        self.db_manager = db_manager
        self.face_threshold = face_threshold
        self.fingerprint_threshold = fingerprint_threshold
        self._ensure_tables()

    # =========================================================================
    # Schema Initialization
    # =========================================================================

    def _ensure_tables(self) -> None:
        """Create biometric database tables if they do not exist.

        Creates the ``biometric_enrollments`` and ``biometric_auth_log``
        tables with appropriate schema for storing biometric templates
        and authentication audit records.

        If the table already exists with an older schema (missing columns
        like ``enrollment_id`` or ``template_data``), the missing columns
        are added via ALTER TABLE to avoid breaking index creation.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Biometric enrollment storage table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS biometric_enrollments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        enrollment_id TEXT UNIQUE,
                        user_id TEXT NOT NULL,
                        biometric_type TEXT NOT NULL,
                        template_data BLOB,
                        template_hash TEXT,
                        device_name TEXT DEFAULT 'Unknown Device',
                        quality_score REAL,
                        created_at TEXT NOT NULL,
                        last_verified_at TEXT,
                        is_active INTEGER DEFAULT 1,
                        verification_count INTEGER DEFAULT 0,
                        failure_count INTEGER DEFAULT 0,
                        metadata TEXT DEFAULT '{}',
                        revoked_at TEXT
                    )
                """)

                # Migrate older schemas that may be missing columns
                cursor.execute("PRAGMA table_info(biometric_enrollments)")
                existing_columns = {row[1] for row in cursor.fetchall()}

                migrations = {
                    'enrollment_id': 'TEXT',
                    'template_data': 'BLOB',
                    'template_hash': 'TEXT',
                    'device_name': "TEXT DEFAULT 'Unknown Device'",
                    'quality_score': 'REAL',
                    'last_verified_at': 'TEXT',
                    'verification_count': 'INTEGER DEFAULT 0',
                    'failure_count': 'INTEGER DEFAULT 0',
                    'metadata': "TEXT DEFAULT '{}'",
                    'revoked_at': 'TEXT',
                }
                for col_name, col_def in migrations.items():
                    if col_name not in existing_columns:
                        cursor.execute(
                            f"ALTER TABLE biometric_enrollments ADD COLUMN {col_name} {col_def}"
                        )

                # Index for user and type lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_biometric_enroll_user
                    ON biometric_enrollments(user_id, biometric_type, is_active)
                """)

                # Unique index for enrollment_id lookups
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_biometric_enroll_id
                    ON biometric_enrollments(enrollment_id)
                """)

                # Authentication attempt log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS biometric_auth_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        biometric_type TEXT NOT NULL,
                        match_score REAL,
                        success INTEGER NOT NULL,
                        device_info TEXT,
                        ip_address TEXT,
                        enrollment_id TEXT,
                        error_message TEXT,
                        attempt_at TEXT NOT NULL
                    )
                """)

                # Index for auth log user lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_biometric_auth_log_user
                    ON biometric_auth_log(user_id, biometric_type)
                """)

                # Index for auth log time-based queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_biometric_auth_log_time
                    ON biometric_auth_log(attempt_at)
                """)

                conn.commit()
                logger.debug("Biometric database tables ensured")

        except sqlite3.Error as e:
            logger.error("Failed to create biometric tables")

    # =========================================================================
    # Face Enrollment and Verification
    # =========================================================================

    def enroll_face(
        self,
        user_id: str,
        image_data: bytes,
        device_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enroll a face biometric for a user.

        Extracts a 128-dimensional face encoding from the provided image
        data and stores only the encoding template. The raw image is
        NEVER stored in the database.

        Parameters
        ----------
        user_id : str
            Unique identifier for the user.
        image_data : bytes
            Raw image data (JPEG, PNG, etc.) containing a single face.
        device_name : str, optional
            Human-readable name for the enrollment device.
            Defaults to ``'Face Camera'``.

        Returns
        -------
        dict
            On success: ``{'success': True, 'enrollment_id': ...}``
            On failure: ``{'success': False, 'error': ...}``

        Notes
        -----
        - Only one face should be present in the image.
        - The image is discarded immediately after encoding extraction.
        - The 128-D encoding is stored as a pickled numpy array.
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return {
                'success': False,
                'error': 'Face recognition requires the face_recognition library. '
                         'Install with: pip install face_recognition',
            }

        if not NUMPY_AVAILABLE:
            return {
                'success': False,
                'error': 'Face recognition requires numpy. '
                         'Install with: pip install numpy',
            }

        if not user_id:
            return {'success': False, 'error': 'user_id is required'}

        if not image_data or not isinstance(image_data, bytes):
            return {'success': False, 'error': 'image_data must be non-empty bytes'}

        if device_name is None:
            device_name = 'Face Camera'

        try:
            # Check enrollment limit
            existing_count = self._count_enrollments(user_id, BIOMETRIC_TYPE_FACE)
            if existing_count >= MAX_ENROLLMENTS_PER_TYPE:
                return {
                    'success': False,
                    'error': f'Maximum face enrollments ({MAX_ENROLLMENTS_PER_TYPE}) '
                             f'reached for this user. Revoke an existing enrollment first.',
                }

            # Load the image from bytes - raw image is only in memory temporarily
            image_array = _face_recognition.load_image_file(io.BytesIO(image_data))

            # Detect face locations in the image
            face_locations = _face_recognition.face_locations(image_array)

            if len(face_locations) == 0:
                return {
                    'success': False,
                    'error': 'No face detected in the provided image. '
                             'Please provide a clear, well-lit photo with a visible face.',
                }

            if len(face_locations) > 1:
                return {
                    'success': False,
                    'error': f'Multiple faces ({len(face_locations)}) detected in the image. '
                             f'Please provide an image with exactly one face.',
                }

            # Extract the 128-D face encoding
            face_encodings = _face_recognition.face_encodings(
                image_array, known_face_locations=face_locations
            )

            if len(face_encodings) == 0:
                return {
                    'success': False,
                    'error': 'Could not extract face encoding from the image. '
                             'Please try with a different, clearer photo.',
                }

            face_encoding = face_encodings[0]  # 128-D numpy float array

            # Compute a quality score based on face bounding box size
            top, right, bottom, left = face_locations[0]
            face_area = (bottom - top) * (right - left)
            image_area = image_array.shape[0] * image_array.shape[1]
            quality_score = min(1.0, face_area / max(image_area * 0.05, 1))

            # Serialize the encoding template (NEVER the raw image)
            template_bytes = pickle.dumps(face_encoding)
            template_hash = self._compute_template_hash(template_bytes)

            # Generate a unique enrollment ID
            enrollment_id = f"face_{secrets.token_urlsafe(16)}"
            now = datetime.utcnow().isoformat()

            # Store the template in the database
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO biometric_enrollments (
                        enrollment_id, user_id, biometric_type,
                        template_data, template_hash, device_name,
                        quality_score, created_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    enrollment_id,
                    user_id,
                    BIOMETRIC_TYPE_FACE,
                    template_bytes,
                    template_hash,
                    device_name,
                    round(quality_score, 4),
                    now,
                ))
                conn.commit()

            # Clear sensitive data from memory
            del image_array
            del face_encodings
            del face_encoding

            logger.info(
                "Face enrolled for user '%s' (enrollment: %s, quality: %.2f)",
                user_id, enrollment_id, quality_score,
            )

            # Audit log the enrollment
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_ENABLED,
                    user_id=user_id,
                    resource_type='biometric_face',
                    details={
                        'enrollment_id': enrollment_id,
                        'quality_score': round(quality_score, 4),
                    },
                )

            return {
                'success': True,
                'enrollment_id': enrollment_id,
                'quality_score': round(quality_score, 4),
                'biometric_type': BIOMETRIC_TYPE_FACE,
            }

        except Exception as e:
            logger.error(
                "Failed to enroll face for user '%s': %s", user_id, e,
            )
            return {
                'success': False,
                'error': f'Face enrollment failed: {e}',
            }

    def verify_face(
        self,
        user_id: str,
        image_data: bytes,
        device_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a face against the user's enrolled face template(s).

        Extracts a face encoding from the provided image and compares
        it against all active face enrollments for the user.

        Parameters
        ----------
        user_id : str
            The user whose enrolled face to verify against.
        image_data : bytes
            Raw image data (JPEG, PNG, etc.) containing the face to verify.
        device_info : str, optional
            Information about the verification device for logging.

        Returns
        -------
        dict
            On success: ``{'success': True, 'match_score': float, 'enrollment_id': ...}``
            On failure: ``{'success': False, 'match_score': float, 'error': ...}``

        Notes
        -----
        The ``match_score`` represents 1.0 minus the face distance. Higher
        scores indicate better matches. The verification succeeds when the
        face distance is below ``self.face_threshold``.
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return {
                'success': False,
                'match_score': 0.0,
                'error': 'Face recognition requires the face_recognition library. '
                         'Install with: pip install face_recognition',
            }

        if not NUMPY_AVAILABLE:
            return {
                'success': False,
                'match_score': 0.0,
                'error': 'Face recognition requires numpy. '
                         'Install with: pip install numpy',
            }

        if not user_id:
            return {'success': False, 'match_score': 0.0, 'error': 'user_id is required'}

        if not image_data or not isinstance(image_data, bytes):
            return {
                'success': False,
                'match_score': 0.0,
                'error': 'image_data must be non-empty bytes',
            }

        try:
            # Load enrolled face templates for this user
            enrollments = self._get_active_enrollments(user_id, BIOMETRIC_TYPE_FACE)
            if not enrollments:
                self._log_auth_attempt(
                    user_id=user_id,
                    biometric_type=BIOMETRIC_TYPE_FACE,
                    match_score=0.0,
                    success=False,
                    device_info=device_info,
                    error_message='No face enrollments found',
                )
                return {
                    'success': False,
                    'match_score': 0.0,
                    'error': 'No active face enrollments found for this user',
                }

            # Load and process the verification image
            image_array = _face_recognition.load_image_file(io.BytesIO(image_data))
            face_locations = _face_recognition.face_locations(image_array)

            if len(face_locations) == 0:
                self._log_auth_attempt(
                    user_id=user_id,
                    biometric_type=BIOMETRIC_TYPE_FACE,
                    match_score=0.0,
                    success=False,
                    device_info=device_info,
                    error_message='No face detected in verification image',
                )
                return {
                    'success': False,
                    'match_score': 0.0,
                    'error': 'No face detected in the provided image',
                }

            if len(face_locations) > 1:
                self._log_auth_attempt(
                    user_id=user_id,
                    biometric_type=BIOMETRIC_TYPE_FACE,
                    match_score=0.0,
                    success=False,
                    device_info=device_info,
                    error_message='Multiple faces detected',
                )
                return {
                    'success': False,
                    'match_score': 0.0,
                    'error': 'Multiple faces detected. Please provide an image with one face.',
                }

            # Extract the face encoding from the verification image
            face_encodings = _face_recognition.face_encodings(
                image_array, known_face_locations=face_locations
            )

            if len(face_encodings) == 0:
                self._log_auth_attempt(
                    user_id=user_id,
                    biometric_type=BIOMETRIC_TYPE_FACE,
                    match_score=0.0,
                    success=False,
                    device_info=device_info,
                    error_message='Could not extract face encoding',
                )
                return {
                    'success': False,
                    'match_score': 0.0,
                    'error': 'Could not extract face encoding from the image',
                }

            verification_encoding = face_encodings[0]

            # Compare against all enrolled templates, find best match
            best_match_score = 0.0
            best_enrollment_id = None
            best_distance = float('inf')

            for enrollment in enrollments:
                try:
                    enrolled_encoding = pickle.loads(enrollment['template_data'])  # nosec B301  # data from our own DB, not untrusted input

                    # Compute face distance (lower = better match)
                    distances = _face_recognition.face_distance(
                        [enrolled_encoding], verification_encoding
                    )
                    distance = float(distances[0])

                    # Convert distance to a similarity score (higher = better)
                    score = max(0.0, 1.0 - distance)

                    if distance < best_distance:
                        best_distance = distance
                        best_match_score = score
                        best_enrollment_id = enrollment['enrollment_id']

                except (pickle.UnpicklingError, ValueError, TypeError) as e:
                    logger.warning(
                        "Failed to deserialize face template '%s': %s",
                        enrollment['enrollment_id'], e,
                    )
                    continue

            # Determine if the match meets the threshold
            is_match = best_distance < self.face_threshold

            # Log the authentication attempt
            self._log_auth_attempt(
                user_id=user_id,
                biometric_type=BIOMETRIC_TYPE_FACE,
                match_score=round(best_match_score, 4),
                success=is_match,
                device_info=device_info,
                enrollment_id=best_enrollment_id,
            )

            # Update enrollment statistics
            if best_enrollment_id:
                self._update_enrollment_stats(
                    enrollment_id=best_enrollment_id,
                    success=is_match,
                )

            # Clear sensitive data from memory
            del image_array
            del face_encodings
            del verification_encoding

            if is_match:
                logger.info(
                    "Face verification successful for user '%s' (score: %.4f)",
                    user_id, best_match_score,
                )
                return {
                    'success': True,
                    'match_score': round(best_match_score, 4),
                    'enrollment_id': best_enrollment_id,
                    'biometric_type': BIOMETRIC_TYPE_FACE,
                }
            else:
                logger.info(
                    "Face verification failed for user '%s' (score: %.4f, threshold: %.2f)",
                    user_id, best_match_score, self.face_threshold,
                )
                return {
                    'success': False,
                    'match_score': round(best_match_score, 4),
                    'error': 'Face does not match enrolled template',
                    'biometric_type': BIOMETRIC_TYPE_FACE,
                }

        except Exception as e:
            logger.error(
                "Face verification error for user '%s': %s", user_id, e,
            )
            self._log_auth_attempt(
                user_id=user_id,
                biometric_type=BIOMETRIC_TYPE_FACE,
                match_score=0.0,
                success=False,
                device_info=device_info,
                error_message=str(e),
            )
            return {
                'success': False,
                'match_score': 0.0,
                'error': f'Face verification failed: {e}',
            }

    # =========================================================================
    # Fingerprint Enrollment and Verification
    # =========================================================================

    def enroll_fingerprint(
        self,
        user_id: str,
        template_data: bytes,
        device_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enroll a fingerprint biometric for a user.

        Stores a pre-computed fingerprint template. The template is
        expected to be generated by a fingerprint sensor/SDK and
        provided as raw bytes.

        Parameters
        ----------
        user_id : str
            Unique identifier for the user.
        template_data : bytes
            Pre-computed fingerprint template data from a sensor/SDK.
        device_name : str, optional
            Human-readable name for the enrollment device.
            Defaults to ``'Fingerprint Scanner'``.

        Returns
        -------
        dict
            On success: ``{'success': True, 'enrollment_id': ...}``
            On failure: ``{'success': False, 'error': ...}``
        """
        if not user_id:
            return {'success': False, 'error': 'user_id is required'}

        if not template_data or not isinstance(template_data, bytes):
            return {
                'success': False,
                'error': 'template_data must be non-empty bytes',
            }

        if device_name is None:
            device_name = 'Fingerprint Scanner'

        try:
            # Check enrollment limit
            existing_count = self._count_enrollments(user_id, BIOMETRIC_TYPE_FINGERPRINT)
            if existing_count >= MAX_ENROLLMENTS_PER_TYPE:
                return {
                    'success': False,
                    'error': f'Maximum fingerprint enrollments ({MAX_ENROLLMENTS_PER_TYPE}) '
                             f'reached for this user. Revoke an existing enrollment first.',
                }

            # Compute template hash for integrity verification
            template_hash = self._compute_template_hash(template_data)

            # Check for duplicate templates (same fingerprint already enrolled)
            if self._is_duplicate_template(user_id, BIOMETRIC_TYPE_FINGERPRINT, template_hash):
                return {
                    'success': False,
                    'error': 'This fingerprint appears to already be enrolled',
                }

            # Serialize the template for storage
            stored_template = pickle.dumps(template_data)

            # Generate a unique enrollment ID
            enrollment_id = f"fp_{secrets.token_urlsafe(16)}"
            now = datetime.utcnow().isoformat()

            # Store the template in the database
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO biometric_enrollments (
                        enrollment_id, user_id, biometric_type,
                        template_data, template_hash, device_name,
                        quality_score, created_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    enrollment_id,
                    user_id,
                    BIOMETRIC_TYPE_FINGERPRINT,
                    stored_template,
                    template_hash,
                    device_name,
                    None,  # Quality score not available for raw templates
                    now,
                ))
                conn.commit()

            logger.info(
                "Fingerprint enrolled for user '%s' (enrollment: %s)",
                user_id, enrollment_id,
            )

            # Audit log the enrollment
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_ENABLED,
                    user_id=user_id,
                    resource_type='biometric_fingerprint',
                    details={'enrollment_id': enrollment_id},
                )

            return {
                'success': True,
                'enrollment_id': enrollment_id,
                'biometric_type': BIOMETRIC_TYPE_FINGERPRINT,
            }

        except Exception as e:
            logger.error(
                "Failed to enroll fingerprint for user '%s': %s", user_id, e,
            )
            return {
                'success': False,
                'error': f'Fingerprint enrollment failed: {e}',
            }

    def verify_fingerprint(
        self,
        user_id: str,
        template_data: bytes,
        device_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a fingerprint against the user's enrolled template(s).

        Compares the provided fingerprint template against all active
        fingerprint enrollments for the user using byte-level comparison
        and hash matching.

        Parameters
        ----------
        user_id : str
            The user whose enrolled fingerprint to verify against.
        template_data : bytes
            The fingerprint template data to verify.
        device_info : str, optional
            Information about the verification device for logging.

        Returns
        -------
        dict
            On success: ``{'success': True, 'match_score': float, 'enrollment_id': ...}``
            On failure: ``{'success': False, 'match_score': float, 'error': ...}``

        Notes
        -----
        Fingerprint matching uses hash comparison for exact matches and
        byte-level similarity for partial matches. The ``match_score``
        ranges from 0.0 (no match) to 1.0 (exact match).
        """
        if not user_id:
            return {'success': False, 'match_score': 0.0, 'error': 'user_id is required'}

        if not template_data or not isinstance(template_data, bytes):
            return {
                'success': False,
                'match_score': 0.0,
                'error': 'template_data must be non-empty bytes',
            }

        try:
            # Load enrolled fingerprint templates for this user
            enrollments = self._get_active_enrollments(user_id, BIOMETRIC_TYPE_FINGERPRINT)
            if not enrollments:
                self._log_auth_attempt(
                    user_id=user_id,
                    biometric_type=BIOMETRIC_TYPE_FINGERPRINT,
                    match_score=0.0,
                    success=False,
                    device_info=device_info,
                    error_message='No fingerprint enrollments found',
                )
                return {
                    'success': False,
                    'match_score': 0.0,
                    'error': 'No active fingerprint enrollments found for this user',
                }

            # Compute hash of the verification template
            verification_hash = self._compute_template_hash(template_data)

            best_match_score = 0.0
            best_enrollment_id = None

            for enrollment in enrollments:
                try:
                    stored_template = pickle.loads(enrollment['template_data'])  # nosec B301  # data from our own DB, not untrusted input

                    # First check: exact hash match (fast path)
                    if enrollment['template_hash'] == verification_hash:
                        best_match_score = 1.0
                        best_enrollment_id = enrollment['enrollment_id']
                        break

                    # Second check: byte-level similarity comparison
                    similarity = self._compute_byte_similarity(
                        stored_template, template_data
                    )

                    if similarity > best_match_score:
                        best_match_score = similarity
                        best_enrollment_id = enrollment['enrollment_id']

                except (pickle.UnpicklingError, ValueError, TypeError) as e:
                    logger.warning(
                        "Failed to deserialize fingerprint template '%s': %s",
                        enrollment['enrollment_id'], e,
                    )
                    continue

            # Determine if the match meets the threshold
            is_match = best_match_score >= self.fingerprint_threshold

            # Log the authentication attempt
            self._log_auth_attempt(
                user_id=user_id,
                biometric_type=BIOMETRIC_TYPE_FINGERPRINT,
                match_score=round(best_match_score, 4),
                success=is_match,
                device_info=device_info,
                enrollment_id=best_enrollment_id,
            )

            # Update enrollment statistics
            if best_enrollment_id:
                self._update_enrollment_stats(
                    enrollment_id=best_enrollment_id,
                    success=is_match,
                )

            if is_match:
                logger.info(
                    "Fingerprint verification successful for user '%s' (score: %.4f)",
                    user_id, best_match_score,
                )
                return {
                    'success': True,
                    'match_score': round(best_match_score, 4),
                    'enrollment_id': best_enrollment_id,
                    'biometric_type': BIOMETRIC_TYPE_FINGERPRINT,
                }
            else:
                logger.info(
                    "Fingerprint verification failed for user '%s' "
                    "(score: %.4f, threshold: %.2f)",
                    user_id, best_match_score, self.fingerprint_threshold,
                )
                return {
                    'success': False,
                    'match_score': round(best_match_score, 4),
                    'error': 'Fingerprint does not match enrolled template',
                    'biometric_type': BIOMETRIC_TYPE_FINGERPRINT,
                }

        except Exception as e:
            logger.error(
                "Fingerprint verification error for user '%s': %s", user_id, e,
            )
            self._log_auth_attempt(
                user_id=user_id,
                biometric_type=BIOMETRIC_TYPE_FINGERPRINT,
                match_score=0.0,
                success=False,
                device_info=device_info,
                error_message=str(e),
            )
            return {
                'success': False,
                'match_score': 0.0,
                'error': f'Fingerprint verification failed: {e}',
            }

    # =========================================================================
    # Enrollment Management
    # =========================================================================

    def list_enrollments(self, user_id: str) -> List[Dict[str, Any]]:
        """List all active biometric enrollments for a user.

        Parameters
        ----------
        user_id : str
            The user whose enrollments to list.

        Returns
        -------
        list of dict
            Each dict contains enrollment metadata (enrollment_id,
            biometric_type, device_name, created_at, etc.).
            Returns empty list on error.
        """
        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT enrollment_id, biometric_type, device_name,
                           quality_score, created_at, last_verified_at,
                           verification_count, failure_count
                    FROM biometric_enrollments
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY biometric_type, created_at DESC
                """, (user_id,))

                rows = cursor.fetchall()
                enrollments = []
                for row in rows:
                    enrollments.append({
                        'enrollment_id': row['enrollment_id'],
                        'biometric_type': row['biometric_type'],
                        'device_name': row['device_name'],
                        'quality_score': row['quality_score'],
                        'created_at': row['created_at'],
                        'last_verified_at': row['last_verified_at'],
                        'verification_count': row['verification_count'],
                        'failure_count': row['failure_count'],
                    })

                logger.debug(
                    "Listed %d biometric enrollments for user '%s'",
                    len(enrollments), user_id,
                )
                return enrollments

        except sqlite3.Error as e:
            logger.error(
                "Failed to list biometric enrollments for user '%s': %s",
                user_id, e,
            )
            return []

    def revoke_enrollment(self, enrollment_id: str) -> Dict[str, Any]:
        """Revoke (deactivate) a biometric enrollment.

        The enrollment is soft-deleted by setting ``is_active = 0``.
        The template data is retained for audit purposes but can no
        longer be used for verification.

        Parameters
        ----------
        enrollment_id : str
            The unique enrollment ID to revoke.

        Returns
        -------
        dict
            ``{'success': True}`` on success, ``{'success': False, 'error': ...}``
            on failure.
        """
        if not enrollment_id:
            return {'success': False, 'error': 'enrollment_id is required'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Fetch enrollment details before revoking
                cursor.execute("""
                    SELECT user_id, biometric_type, device_name
                    FROM biometric_enrollments
                    WHERE enrollment_id = ? AND is_active = 1
                """, (enrollment_id,))
                row = cursor.fetchone()

                if row is None:
                    return {
                        'success': False,
                        'error': 'Enrollment not found or already revoked',
                    }

                user_id = row[0]
                biometric_type = row[1]
                device_name = row[2]

                # Deactivate the enrollment
                cursor.execute("""
                    UPDATE biometric_enrollments
                    SET is_active = 0
                    WHERE enrollment_id = ?
                """, (enrollment_id,))
                conn.commit()

            logger.info(
                "Biometric enrollment revoked: %s (user: %s, type: %s)",
                enrollment_id, user_id, biometric_type,
            )

            # Audit log the revocation
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_DISABLED,
                    user_id=user_id,
                    resource_type=f'biometric_{biometric_type}',
                    details={
                        'enrollment_id': enrollment_id,
                        'device_name': device_name,
                    },
                )

            return {
                'success': True,
                'enrollment_id': enrollment_id,
                'biometric_type': biometric_type,
            }

        except sqlite3.Error as e:
            logger.error("Failed to revoke biometric enrollment")
            return {
                'success': False,
                'error': f'Database error while revoking enrollment: {e}',
            }

    # =========================================================================
    # Logging and Audit
    # =========================================================================

    def _log_auth_attempt(
        self,
        user_id: str,
        biometric_type: str,
        match_score: float,
        success: bool,
        device_info: Optional[str] = None,
        enrollment_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Log a biometric authentication attempt to the audit table.

        Every authentication attempt is logged regardless of outcome
        to maintain a complete audit trail.

        Parameters
        ----------
        user_id : str
            The user who attempted authentication.
        biometric_type : str
            The type of biometric used (``'face'`` or ``'fingerprint'``).
        match_score : float
            The computed match score (0.0 to 1.0).
        success : bool
            Whether the authentication was successful.
        device_info : str, optional
            Information about the device used for the attempt.
        enrollment_id : str, optional
            The enrollment ID that was matched against.
        error_message : str, optional
            Error message if the attempt failed due to an error.
        """
        now = datetime.utcnow().isoformat()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO biometric_auth_log (
                        user_id, biometric_type, match_score, success,
                        device_info, enrollment_id, error_message, attempt_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    biometric_type,
                    round(match_score, 4),
                    int(success),
                    device_info,
                    enrollment_id,
                    error_message,
                    now,
                ))
                conn.commit()

            logger.debug(
                "Biometric auth attempt logged: user=%s, type=%s, success=%s, score=%.4f",
                user_id, biometric_type, success, match_score,
            )

        except sqlite3.Error as e:
            # Logging failures should never break authentication flow
            logger.error("Failed to log biometric auth attempt")

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _compute_template_hash(self, template_data: bytes) -> str:
        """Compute a SHA-256 hash of biometric template data.

        Used for template integrity verification and duplicate detection.

        Parameters
        ----------
        template_data : bytes
            The raw template data to hash.

        Returns
        -------
        str
            Hexadecimal SHA-256 hash string.
        """
        return hashlib.sha256(template_data).hexdigest()

    def _compute_byte_similarity(
        self,
        template_a: bytes,
        template_b: bytes,
    ) -> float:
        """Compute byte-level similarity between two templates.

        Uses normalized byte comparison to produce a similarity score
        between 0.0 (completely different) and 1.0 (identical).

        Parameters
        ----------
        template_a : bytes
            First template.
        template_b : bytes
            Second template.

        Returns
        -------
        float
            Similarity score between 0.0 and 1.0.
        """
        if not template_a or not template_b:
            return 0.0

        # If the templates are identical, return perfect match
        if template_a == template_b:
            return 1.0

        # Pad shorter template to match length for comparison
        max_len = max(len(template_a), len(template_b))
        if max_len == 0:
            return 0.0

        # Compare byte-by-byte, counting matches
        min_len = min(len(template_a), len(template_b))
        matching_bytes = sum(
            1 for i in range(min_len)
            if template_a[i] == template_b[i]
        )

        # Penalize length differences
        similarity = matching_bytes / max_len
        return similarity

    def _get_active_enrollments(
        self,
        user_id: str,
        biometric_type: str,
    ) -> List[Dict[str, Any]]:
        """Retrieve active enrollments for a user and biometric type.

        Parameters
        ----------
        user_id : str
            The user whose enrollments to retrieve.
        biometric_type : str
            The biometric type (``'face'`` or ``'fingerprint'``).

        Returns
        -------
        list of dict
            Each dict contains enrollment_id, template_data, and template_hash.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT enrollment_id, template_data, template_hash
                    FROM biometric_enrollments
                    WHERE user_id = ? AND biometric_type = ? AND is_active = 1
                    ORDER BY created_at DESC
                """, (user_id, biometric_type))

                enrollments = []
                for row in cursor.fetchall():
                    enrollments.append({
                        'enrollment_id': row[0],
                        'template_data': row[1],
                        'template_hash': row[2],
                    })
                return enrollments

        except sqlite3.Error as e:
            logger.error(
                "Failed to get enrollments for user '%s' (type: %s): %s",
                user_id, biometric_type, e,
            )
            return []

    def _count_enrollments(self, user_id: str, biometric_type: str) -> int:
        """Count the number of active enrollments for a user and type.

        Parameters
        ----------
        user_id : str
            The user whose enrollments to count.
        biometric_type : str
            The biometric type to count.

        Returns
        -------
        int
            Number of active enrollments, or 0 on error.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM biometric_enrollments
                    WHERE user_id = ? AND biometric_type = ? AND is_active = 1
                """, (user_id, biometric_type))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(
                "Failed to count enrollments for user '%s': %s",
                user_id, e,
            )
            return 0

    def _is_duplicate_template(
        self,
        user_id: str,
        biometric_type: str,
        template_hash: str,
    ) -> bool:
        """Check if a template with the same hash already exists.

        Parameters
        ----------
        user_id : str
            The user to check.
        biometric_type : str
            The biometric type.
        template_hash : str
            SHA-256 hash of the template.

        Returns
        -------
        bool
            ``True`` if a matching active enrollment exists.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM biometric_enrollments
                    WHERE user_id = ? AND biometric_type = ?
                      AND template_hash = ? AND is_active = 1
                """, (user_id, biometric_type, template_hash))
                return cursor.fetchone()[0] > 0
        except sqlite3.Error as e:
            logger.error("Failed to check duplicate template")
            return False

    def _update_enrollment_stats(
        self,
        enrollment_id: str,
        success: bool,
    ) -> None:
        """Update verification statistics for an enrollment.

        Parameters
        ----------
        enrollment_id : str
            The enrollment to update.
        success : bool
            Whether the verification was successful.
        """
        now = datetime.utcnow().isoformat()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                if success:
                    cursor.execute("""
                        UPDATE biometric_enrollments
                        SET verification_count = verification_count + 1,
                            last_verified_at = ?
                        WHERE enrollment_id = ?
                    """, (now, enrollment_id))
                else:
                    cursor.execute("""
                        UPDATE biometric_enrollments
                        SET failure_count = failure_count + 1
                        WHERE enrollment_id = ?
                    """, (enrollment_id,))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(
                "Failed to update enrollment stats for '%s': %s",
                enrollment_id, e,
            )

    def get_auth_history(
        self,
        user_id: str,
        biometric_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent authentication attempt history for a user.

        Parameters
        ----------
        user_id : str
            The user whose history to retrieve.
        biometric_type : str, optional
            Filter by biometric type. If ``None``, returns all types.
        limit : int, optional
            Maximum number of records to return. Defaults to 50.

        Returns
        -------
        list of dict
            Recent authentication attempts, most recent first.
        """
        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if biometric_type:
                    cursor.execute("""
                        SELECT biometric_type, match_score, success,
                               device_info, enrollment_id, error_message,
                               attempt_at
                        FROM biometric_auth_log
                        WHERE user_id = ? AND biometric_type = ?
                        ORDER BY attempt_at DESC
                        LIMIT ?
                    """, (user_id, biometric_type, limit))
                else:
                    cursor.execute("""
                        SELECT biometric_type, match_score, success,
                               device_info, enrollment_id, error_message,
                               attempt_at
                        FROM biometric_auth_log
                        WHERE user_id = ?
                        ORDER BY attempt_at DESC
                        LIMIT ?
                    """, (user_id, limit))

                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(
                "Failed to get auth history for user '%s': %s", user_id, e,
            )
            return []

    def is_available(self, biometric_type: Optional[str] = None) -> bool:
        """Check if the biometric service is operational.

        Parameters
        ----------
        biometric_type : str, optional
            Check availability for a specific type (``'face'`` or
            ``'fingerprint'``). If ``None``, checks general availability.

        Returns
        -------
        bool
            ``True`` if the service and required dependencies are available.
        """
        # Fingerprint is always available (no external dependencies)
        if biometric_type == BIOMETRIC_TYPE_FINGERPRINT:
            try:
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM biometric_enrollments WHERE 1=0"
                    )
                    return True
            except sqlite3.Error:
                return False

        # Face requires face_recognition and numpy
        if biometric_type == BIOMETRIC_TYPE_FACE:
            return FACE_RECOGNITION_AVAILABLE and NUMPY_AVAILABLE

        # General availability: at least fingerprint works
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM biometric_enrollments WHERE 1=0"
                )
                return True
        except sqlite3.Error:
            return False


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'BiometricService',
    'FACE_RECOGNITION_AVAILABLE',
    'NUMPY_AVAILABLE',
    'BIOMETRIC_TYPE_FACE',
    'BIOMETRIC_TYPE_FINGERPRINT',
]
