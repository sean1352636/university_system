"""
Accessibility Services Portal - Service Layer

This module provides comprehensive accessibility services for students with disabilities,
ensuring FERPA compliance and privacy throughout all operations.

Features:
- Accommodation request workflow
- Real-time status tracking
- Document management for medical documentation
- Direct messaging with disability services staff
- Faculty notification system
- Accommodation renewal tracking
"""

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
import shutil

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.shared.constants import paths

class AccessibilityService:
    """Service class for managing accessibility accommodations and services."""

    # Accommodation types
    ACCOMMODATION_TYPES = [
        'Extended Time',
        'Note-Taking',
        'Sign Language',
        'Accessible Seating',
        'Adaptive Technology',
        'Other'
    ]

    # Request statuses
    STATUS_SUBMITTED = 'Submitted'
    STATUS_UNDER_REVIEW = 'Under Review'
    STATUS_APPROVED = 'Approved'
    STATUS_DENIED = 'Denied'
    STATUS_ACTIVE = 'Active'

    def __init__(self):
        """Initialize the accessibility service and ensure database tables exist."""
        self._initialize_database()

    def _initialize_database(self):
        """Create all necessary database tables for accessibility services."""
        with transaction() as conn:
            # Accommodation requests table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accommodation_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    student_email TEXT NOT NULL,
                    accommodation_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_date TIMESTAMP,
                    reviewer_id TEXT,
                    reviewer_notes TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Migrate existing accommodation_requests table if needed
            cursor = conn.execute("PRAGMA table_info(accommodation_requests)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # Add missing columns
            if 'student_name' not in existing_columns:
                try:
                    conn.execute('ALTER TABLE accommodation_requests ADD COLUMN student_name TEXT')
                except Exception:
                    pass

            if 'student_email' not in existing_columns:
                try:
                    conn.execute('ALTER TABLE accommodation_requests ADD COLUMN student_email TEXT')
                except Exception:
                    pass

            if 'submitted_date' not in existing_columns:
                try:
                    conn.execute('ALTER TABLE accommodation_requests ADD COLUMN submitted_date TIMESTAMP')
                    conn.execute('UPDATE accommodation_requests SET submitted_date = CURRENT_TIMESTAMP WHERE submitted_date IS NULL')
                except Exception:
                    pass

            if 'reviewer_notes' not in existing_columns:
                try:
                    conn.execute('ALTER TABLE accommodation_requests ADD COLUMN reviewer_notes TEXT')
                except Exception:
                    pass

            # Active accommodations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accommodations (
                    accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    accommodation_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    expiration_date DATE NOT NULL,
                    approved_by TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id),
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Documentation table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accommodation_documentation (
                    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    document_type TEXT,
                    FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id)
                )
            """)

            # Messages table for communication with disability services
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accessibility_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read INTEGER DEFAULT 0,
                    FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id)
                )
            """)

            # Faculty notifications table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS faculty_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accommodation_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    faculty_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    accommodation_summary TEXT NOT NULL,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged INTEGER DEFAULT 0,
                    FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id)
                )
            """)

            # Renewal tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accommodation_renewals (
                    renewal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accommodation_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    renewal_request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    processed_date TIMESTAMP,
                    processed_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id)
                )
            """)

            conn.commit()

    def submit_accommodation_request(
        self,
        student_id: str,
        student_name: str,
        student_email: str,
        accommodation_type: str,
        description: str
    ) -> int:
        """
        Submit a new accommodation request.

        Args:
            student_id: Student identifier
            student_name: Student's full name
            student_email: Student's email for notifications
            accommodation_type: Type of accommodation requested
            description: Detailed description of accommodation needs

        Returns:
            request_id: ID of the created request
        """
        if accommodation_type not in self.ACCOMMODATION_TYPES:
            raise ValueError(f"Invalid accommodation type. Must be one of: {', '.join(self.ACCOMMODATION_TYPES)}")

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO accommodation_requests
                (student_id, student_name, student_email, accommodation_type, description, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, student_name, student_email, accommodation_type, description, self.STATUS_SUBMITTED))

            request_id = cursor.lastrowid
            conn.commit()

        log_activity(
            'create',
            'accommodation_request',
            request_id=request_id,
            details={'student_id': student_id, 'type': accommodation_type}
        )

        return request_id

    def upload_documentation(
        self,
        request_id: int,
        student_id: str,
        filename: str,
        file_content: bytes,
        document_type: str = 'Medical Documentation'
    ) -> int:
        """
        Upload supporting documentation for an accommodation request.

        Args:
            request_id: ID of the accommodation request
            student_id: Student identifier
            filename: Original filename
            file_content: File content as bytes
            document_type: Type of document

        Returns:
            doc_id: ID of the uploaded document
        """
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(paths.UPLOAD_DIR, 'accessibility', student_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(upload_dir, safe_filename)

        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_content)

        # Record in database
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO accommodation_documentation
                (request_id, student_id, filename, file_path, document_type)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, student_id, filename, file_path, document_type))

            doc_id = cursor.lastrowid
            conn.commit()

        log_activity(
            'upload',
            'accommodation_documentation',
            doc_id=doc_id,
            details={'request_id': request_id, 'filename': filename}
        )

        return doc_id

    def get_student_requests(self, student_id: str) -> List[Dict]:
        """
        Get all accommodation requests for a student.

        Args:
            student_id: Student identifier

        Returns:
            List of request dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT request_id, accommodation_type, description, status,
                       requested_date as submitted_date, review_date as reviewed_date, review_notes as reviewer_notes
                FROM accommodation_requests
                WHERE student_id = ?
                ORDER BY requested_date DESC
            """, (student_id,))

            columns = [desc[0] for desc in cursor.description]
            requests = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return requests

    def get_request_details(self, request_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific request.

        Args:
            request_id: Request identifier

        Returns:
            Request details dictionary or None if not found
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM accommodation_requests
                WHERE request_id = ?
            """, (request_id,))

            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            request_details = dict(zip(columns, row))

        return request_details

    def update_request_status(
        self,
        request_id: int,
        new_status: str,
        reviewer_id: str,
        reviewer_notes: Optional[str] = None
    ) -> bool:
        """
        Update the status of an accommodation request.

        Args:
            request_id: Request identifier
            new_status: New status value
            reviewer_id: ID of the staff member reviewing
            reviewer_notes: Optional notes from reviewer

        Returns:
            True if successful, False otherwise
        """
        valid_statuses = [
            self.STATUS_SUBMITTED,
            self.STATUS_UNDER_REVIEW,
            self.STATUS_APPROVED,
            self.STATUS_DENIED,
            self.STATUS_ACTIVE
        ]

        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

        with transaction() as conn:
            conn.execute("""
                UPDATE accommodation_requests
                SET status = ?, reviewer_id = ?, reviewer_notes = ?, reviewed_date = CURRENT_TIMESTAMP
                WHERE request_id = ?
            """, (new_status, reviewer_id, reviewer_notes, request_id))

            conn.commit()

        log_activity(
            'update',
            'accommodation_request',
            request_id=request_id,
            details={'status': new_status, 'reviewer': reviewer_id}
        )

        return True

    def approve_and_activate_accommodation(
        self,
        request_id: int,
        approved_by: str,
        start_date: Optional[str] = None,
        duration_months: int = 12
    ) -> int:
        """
        Approve a request and create an active accommodation.

        Args:
            request_id: Request identifier
            approved_by: Staff member approving the accommodation
            start_date: Start date (defaults to today)
            duration_months: Duration in months (default 12)

        Returns:
            accommodation_id: ID of the created accommodation
        """
        # Get request details
        request = self.get_request_details(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        # Set dates
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')

        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        expiration_dt = start_dt + timedelta(days=duration_months * 30)
        expiration_date = expiration_dt.strftime('%Y-%m-%d')

        with transaction() as conn:
            # Update request status
            conn.execute("""
                UPDATE accommodation_requests
                SET status = ?, reviewer_id = ?, reviewed_date = CURRENT_TIMESTAMP
                WHERE request_id = ?
            """, (self.STATUS_APPROVED, approved_by, request_id))

            # Create active accommodation
            current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor = conn.execute("""
                INSERT INTO accommodations
                (student_id, accommodation_type, description,
                 start_date, end_date, status, approved_by, approval_date,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """, (
                request['student_id'],
                request['accommodation_type'],
                request['description'],
                start_date,
                expiration_date,
                approved_by,
                current_timestamp,
                current_timestamp,
                current_timestamp
            ))

            accommodation_id = cursor.lastrowid
            conn.commit()

        log_activity(
            'approve',
            'accommodation',
            accommodation_id=accommodation_id,
            details={'request_id': request_id, 'approved_by': approved_by}
        )

        return accommodation_id

    def get_active_accommodations(self, student_id: str) -> List[Dict]:
        """
        Get all active accommodations for a student.

        Args:
            student_id: Student identifier

        Returns:
            List of active accommodation dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id as accommodation_id, accommodation_type, description,
                       start_date, end_date as expiration_date, approved_by,
                       (status = 'active') as is_active
                FROM accommodations
                WHERE student_id = ? AND status = 'active'
                ORDER BY start_date DESC
            """, (student_id,))

            columns = [desc[0] for desc in cursor.description]
            accommodations = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return accommodations

    def get_expiring_accommodations(self, student_id: str, days_threshold: int = 30) -> List[Dict]:
        """
        Get accommodations expiring within a specified number of days.

        Args:
            student_id: Student identifier
            days_threshold: Number of days to look ahead (default 30)

        Returns:
            List of expiring accommodation dictionaries
        """
        threshold_date = (datetime.now() + timedelta(days=days_threshold)).strftime('%Y-%m-%d')

        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id as accommodation_id, accommodation_type, description,
                       start_date, end_date as expiration_date, approved_by
                FROM accommodations
                WHERE student_id = ? AND status = 'active'
                  AND end_date <= ?
                ORDER BY end_date ASC
            """, (student_id, threshold_date))

            columns = [desc[0] for desc in cursor.description]
            accommodations = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return accommodations

    def send_message(
        self,
        request_id: int,
        sender_id: str,
        sender_type: str,
        message: str
    ) -> int:
        """
        Send a message regarding an accommodation request.

        Args:
            request_id: Request identifier
            sender_id: ID of the sender
            sender_type: Type of sender ('student' or 'staff')
            message: Message content

        Returns:
            message_id: ID of the sent message
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO accessibility_messages
                (request_id, sender_id, sender_type, message)
                VALUES (?, ?, ?, ?)
            """, (request_id, sender_id, sender_type, message))

            message_id = cursor.lastrowid
            conn.commit()

        log_activity(
            'send',
            'accessibility_message',
            message_id=message_id,
            details={'request_id': request_id, 'sender_type': sender_type}
        )

        return message_id

    def get_messages(self, request_id: int) -> List[Dict]:
        """
        Get all messages for a specific request.

        Args:
            request_id: Request identifier

        Returns:
            List of message dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT message_id, sender_id, sender_type, message, sent_date, is_read
                FROM accessibility_messages
                WHERE request_id = ?
                ORDER BY sent_date ASC
            """, (request_id,))

            columns = [desc[0] for desc in cursor.description]
            messages = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return messages

    def mark_message_as_read(self, message_id: int) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: Message identifier

        Returns:
            True if successful
        """
        with transaction() as conn:
            conn.execute("""
                UPDATE accessibility_messages
                SET is_read = 1
                WHERE message_id = ?
            """, (message_id,))

            conn.commit()

        return True

    def notify_faculty(
        self,
        accommodation_id: int,
        student_id: str,
        faculty_id: str,
        course_id: str,
        accommodation_summary: str
    ) -> int:
        """
        Send a notification to faculty about a student's accommodations.

        Args:
            accommodation_id: Accommodation identifier
            student_id: Student identifier
            faculty_id: Faculty member identifier
            course_id: Course identifier
            accommodation_summary: Summary of accommodations (privacy-aware)

        Returns:
            notification_id: ID of the notification
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO faculty_notifications
                (accommodation_id, student_id, faculty_id, course_id, accommodation_summary)
                VALUES (?, ?, ?, ?, ?)
            """, (accommodation_id, student_id, faculty_id, course_id, accommodation_summary))

            notification_id = cursor.lastrowid
            conn.commit()

        log_activity(
            'notify',
            'faculty_accommodation',
            notification_id=notification_id,
            details={'faculty_id': faculty_id, 'course_id': course_id}
        )

        return notification_id

    def get_faculty_notifications(self, student_id: str) -> List[Dict]:
        """
        Get all faculty notifications sent for a student.

        Args:
            student_id: Student identifier

        Returns:
            List of notification dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT fn.notification_id, fn.faculty_id, fn.course_id,
                       fn.accommodation_summary, fn.sent_date, fn.acknowledged
                FROM faculty_notifications fn
                WHERE fn.student_id = ?
                ORDER BY fn.sent_date DESC
            """, (student_id,))

            columns = [desc[0] for desc in cursor.description]
            notifications = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return notifications

    def request_renewal(
        self,
        accommodation_id: int,
        student_id: str,
        notes: Optional[str] = None
    ) -> int:
        """
        Submit a renewal request for an existing accommodation.

        Args:
            accommodation_id: Accommodation identifier
            student_id: Student identifier
            notes: Optional notes about renewal

        Returns:
            renewal_id: ID of the renewal request
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO accommodation_renewals
                (accommodation_id, student_id, status, notes)
                VALUES (?, ?, ?, ?)
            """, (accommodation_id, student_id, 'Pending', notes))

            renewal_id = cursor.lastrowid
            conn.commit()

        log_activity(
            'request',
            'accommodation_renewal',
            renewal_id=renewal_id,
            details={'accommodation_id': accommodation_id, 'student_id': student_id}
        )

        return renewal_id

    def get_renewal_requests(self, student_id: str) -> List[Dict]:
        """
        Get all renewal requests for a student.

        Args:
            student_id: Student identifier

        Returns:
            List of renewal request dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT ar.renewal_id, ar.accommodation_id, a.accommodation_type,
                       ar.renewal_request_date, ar.status, ar.processed_date, ar.notes
                FROM accommodation_renewals ar
                JOIN accommodations a ON ar.accommodation_id = a.id
                WHERE ar.student_id = ?
                ORDER BY ar.renewal_request_date DESC
            """, (student_id,))

            columns = [desc[0] for desc in cursor.description]
            renewals = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return renewals

    def process_renewal(
        self,
        renewal_id: int,
        status: str,
        processed_by: str,
        notes: Optional[str] = None,
        extend_months: int = 12
    ) -> bool:
        """
        Process a renewal request.

        Args:
            renewal_id: Renewal request identifier
            status: New status ('Approved' or 'Denied')
            processed_by: Staff member processing the renewal
            notes: Optional processing notes
            extend_months: Months to extend if approved

        Returns:
            True if successful
        """
        with transaction() as conn:
            # Update renewal record
            conn.execute("""
                UPDATE accommodation_renewals
                SET status = ?, processed_date = CURRENT_TIMESTAMP,
                    processed_by = ?, notes = ?
                WHERE renewal_id = ?
            """, (status, processed_by, notes, renewal_id))

            # If approved, extend the accommodation
            if status == 'Approved':
                cursor = conn.execute("""
                    SELECT accommodation_id FROM accommodation_renewals
                    WHERE renewal_id = ?
                """, (renewal_id,))

                result = cursor.fetchone()
                if result:
                    accommodation_id = result[0]

                    # Get current expiration date
                    cursor = conn.execute("""
                        SELECT end_date FROM accommodations
                        WHERE id = ?
                    """, (accommodation_id,))

                    current_exp = cursor.fetchone()[0]
                    current_exp_dt = datetime.strptime(current_exp, '%Y-%m-%d')
                    new_exp_dt = current_exp_dt + timedelta(days=extend_months * 30)
                    new_exp = new_exp_dt.strftime('%Y-%m-%d')

                    # Update expiration date
                    conn.execute("""
                        UPDATE accommodations
                        SET end_date = ?
                        WHERE id = ?
                    """, (new_exp, accommodation_id))

            conn.commit()

        log_activity(
            'process',
            'accommodation_renewal',
            renewal_id=renewal_id,
            details={'status': status, 'processed_by': processed_by}
        )

        return True

    def get_documentation(self, request_id: int) -> List[Dict]:
        """
        Get all documentation for a request.

        Args:
            request_id: Request identifier

        Returns:
            List of document dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT doc_id, filename, file_path, upload_date, document_type
                FROM accommodation_documentation
                WHERE request_id = ?
                ORDER BY upload_date DESC
            """, (request_id,))

            columns = [desc[0] for desc in cursor.description]
            documents = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return documents

    def deactivate_accommodation(self, accommodation_id: int, reason: str) -> bool:
        """
        Deactivate an accommodation.

        Args:
            accommodation_id: Accommodation identifier
            reason: Reason for deactivation

        Returns:
            True if successful
        """
        with transaction() as conn:
            conn.execute("""
                UPDATE accommodations
                SET status = 'inactive'
                WHERE id = ?
            """, (accommodation_id,))

            conn.commit()

        log_activity(
            'deactivate',
            'accommodation',
            accommodation_id=accommodation_id,
            details={'reason': reason}
        )

        return True

    def get_all_pending_requests(self) -> List[Dict]:
        """
        Get all pending accommodation requests (for staff view).

        Returns:
            List of pending request dictionaries
        """
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT request_id, student_id, accommodation_type,
                       description, status, requested_date as submitted_date
                FROM accommodation_requests
                WHERE status IN (?, ?)
                ORDER BY requested_date ASC
            """, (self.STATUS_SUBMITTED, self.STATUS_UNDER_REVIEW))

            columns = [desc[0] for desc in cursor.description]
            requests = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return requests

    def get_statistics(self) -> Dict:
        """
        Get statistics about accessibility services.

        Returns:
            Dictionary containing various statistics
        """
        with get_connection() as conn:
            # Total requests
            cursor = conn.execute("SELECT COUNT(*) FROM accommodation_requests")
            total_requests = cursor.fetchone()[0]

            # Pending requests
            cursor = conn.execute("""
                SELECT COUNT(*) FROM accommodation_requests
                WHERE status IN (?, ?)
            """, (self.STATUS_SUBMITTED, self.STATUS_UNDER_REVIEW))
            pending_requests = cursor.fetchone()[0]

            # Active accommodations
            cursor = conn.execute("""
                SELECT COUNT(*) FROM accommodations WHERE status = 'active'
            """)
            active_accommodations = cursor.fetchone()[0]

            # By accommodation type
            cursor = conn.execute("""
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                WHERE status = 'active'
                GROUP BY accommodation_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Expiring soon (30 days)
            threshold_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor = conn.execute("""
                SELECT COUNT(*) FROM accommodations
                WHERE status = 'active' AND end_date <= ?
            """, (threshold_date,))
            expiring_soon = cursor.fetchone()[0]

        return {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'active_accommodations': active_accommodations,
            'by_type': by_type,
            'expiring_soon': expiring_soon
        }
