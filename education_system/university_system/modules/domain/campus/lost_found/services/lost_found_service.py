"""
Lost & Found Service

Manages lost and found items with photo uploads, claim verification, and matching.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.sql_safety import escape_like
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import os
import hashlib

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core import paths

class LostFoundService:
    """Service for lost and found item management."""

    def __init__(self):
        """Initialize the Lost & Found Service."""
        self._ensure_tables_exist()
        self._ensure_upload_directory()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Lost Items table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lost_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    lost_date TEXT NOT NULL,
                    lost_location TEXT NOT NULL,
                    lost_time TEXT,
                    distinctive_features TEXT,
                    color TEXT,
                    brand TEXT,
                    estimated_value REAL,
                    contact_email TEXT,
                    contact_phone TEXT,
                    status TEXT DEFAULT 'Active',
                    reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reporter_id) REFERENCES students(student_id)
                )
            """)

            # Found Items table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS found_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    finder_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    found_date TEXT NOT NULL,
                    found_location TEXT NOT NULL,
                    found_time TEXT,
                    distinctive_features TEXT,
                    color TEXT,
                    brand TEXT,
                    current_location TEXT,
                    storage_info TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    status TEXT DEFAULT 'Available',
                    reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (finder_id) REFERENCES students(student_id)
                )
            """)

            # Item Photos table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_photos (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    photo_path TEXT NOT NULL,
                    photo_hash TEXT,
                    caption TEXT,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Claims table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    found_item_id INTEGER NOT NULL,
                    claimant_id TEXT NOT NULL,
                    claim_description TEXT NOT NULL,
                    verification_questions TEXT,
                    verification_answers TEXT,
                    supporting_evidence TEXT,
                    status TEXT DEFAULT 'Pending',
                    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    resolution_notes TEXT,
                    FOREIGN KEY (found_item_id) REFERENCES found_items(item_id) ON DELETE CASCADE,
                    FOREIGN KEY (claimant_id) REFERENCES students(student_id)
                )
            """)

            # Matches table (automatic matching between lost and found)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lost_item_id INTEGER NOT NULL,
                    found_item_id INTEGER NOT NULL,
                    match_score REAL NOT NULL,
                    match_reasons TEXT,
                    status TEXT DEFAULT 'Suggested',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lost_item_id) REFERENCES lost_items(item_id) ON DELETE CASCADE,
                    FOREIGN KEY (found_item_id) REFERENCES found_items(item_id) ON DELETE CASCADE
                )
            """)

            # Verification Questions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    found_item_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    expected_answer_type TEXT DEFAULT 'text',
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (found_item_id) REFERENCES found_items(item_id) ON DELETE CASCADE
                )
            """)

            log_activity('create', 'lost_found_tables',
                        details={'status': 'Lost & Found tables created'})

    def _ensure_upload_directory(self):
        """Ensure upload directory exists for item photos."""
        upload_dir = os.path.join(paths.UPLOAD_DIR, 'lost_found')
        os.makedirs(upload_dir, exist_ok=True)

    # ========== Lost Items ==========

    def report_lost_item(self, reporter_id: str, item_name: str, category: str,
                        description: str, lost_date: str, lost_location: str,
                        lost_time: str = "", distinctive_features: str = "",
                        color: str = "", brand: str = "",
                        estimated_value: float = 0.0,
                        contact_email: str = "",
                        contact_phone: str = "") -> int:
        """
        Report a lost item.

        Args:
            reporter_id: ID of person reporting lost item
            item_name: Name/type of item
            category: Category (Electronics, Clothing, Books, etc.)
            description: Detailed description
            lost_date: Date item was lost (YYYY-MM-DD)
            lost_location: Location where item was lost
            lost_time: Approximate time lost
            distinctive_features: Unique identifying features
            color: Primary color
            brand: Brand/manufacturer
            estimated_value: Estimated monetary value
            contact_email: Contact email
            contact_phone: Contact phone number

        Returns:
            Lost item ID
        """
        with transaction() as conn:
            # Check if reporter exists in students table
            reporter_exists = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (reporter_id,)
            ).fetchone()

            # If reporter doesn't exist, create a basic student record
            if not reporter_exists:
                conn.execute("""
                    INSERT INTO students (student_id, status, registration_datetime)
                    VALUES (?, 'Active', ?)
                """, (reporter_id, datetime.now().isoformat()))

            cursor = conn.execute("""
                INSERT INTO lost_items
                (reporter_id, item_name, category, description, lost_date,
                 lost_location, lost_time, distinctive_features, color, brand,
                 estimated_value, contact_email, contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (reporter_id, item_name, category, description, lost_date,
                  lost_location, lost_time, distinctive_features, color, brand,
                  estimated_value, contact_email, contact_phone))

            item_id = cursor.lastrowid

            log_activity('create', 'lost_item',
                        details={'item_id': item_id, 'reporter_id': reporter_id, 'item': item_name})

            # Automatically search for potential matches
            self._find_potential_matches_for_lost(item_id)

            return item_id

    def get_lost_item(self, item_id: int) -> Optional[Dict]:
        """Get lost item by ID."""
        with get_connection() as conn:
            item = conn.execute("""
                SELECT * FROM lost_items WHERE item_id = ?
            """, (item_id,)).fetchone()

            if not item:
                return None

            result = dict(item)

            # Get photos
            photos = conn.execute("""
                SELECT * FROM item_photos
                WHERE item_type = 'lost' AND item_id = ?
            """, (item_id,)).fetchall()

            result['photos'] = [dict(p) for p in photos]

            return result

    def get_lost_items(self, reporter_id: Optional[str] = None,
                      category: Optional[str] = None,
                      status: str = 'Active') -> List[Dict]:
        """Get lost items with optional filters."""
        with get_connection() as conn:
            query = "SELECT * FROM lost_items WHERE 1=1"
            params = []

            if reporter_id:
                query += " AND reporter_id = ?"
                params.append(reporter_id)

            if category:
                query += " AND category = ?"
                params.append(category)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY reported_at DESC"

            items = conn.execute(query, params).fetchall()
            return [dict(i) for i in items]

    def update_lost_item_status(self, item_id: int, status: str,
                               notes: str = "") -> bool:
        """Update lost item status (Active, Found, Closed)."""
        valid_statuses = ['Active', 'Found', 'Closed']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of {valid_statuses}")

        with transaction() as conn:
            conn.execute("""
                UPDATE lost_items
                SET status = ?, updated_at = ?
                WHERE item_id = ?
            """, (status, datetime.now().isoformat(), item_id))

            log_activity('update', 'lost_item_status',
                        details={'item_id': item_id, 'status': status, 'notes': notes})

        return True

    # ========== Found Items ==========

    def report_found_item(self, finder_id: str, item_name: str, category: str,
                         description: str, found_date: str, found_location: str,
                         found_time: str = "", distinctive_features: str = "",
                         color: str = "", brand: str = "",
                         current_location: str = "", storage_info: str = "",
                         contact_email: str = "",
                         contact_phone: str = "") -> int:
        """
        Report a found item.

        Args:
            finder_id: ID of person who found item
            item_name: Name/type of item
            category: Category (Electronics, Clothing, Books, etc.)
            description: Detailed description
            found_date: Date item was found (YYYY-MM-DD)
            found_location: Location where item was found
            found_time: Approximate time found
            distinctive_features: Unique identifying features
            color: Primary color
            brand: Brand/manufacturer
            current_location: Where item is currently stored
            storage_info: Additional storage details
            contact_email: Contact email
            contact_phone: Contact phone number

        Returns:
            Found item ID
        """
        with transaction() as conn:
            # Check if finder exists in students table
            finder_exists = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (finder_id,)
            ).fetchone()

            # If finder doesn't exist, create a basic student record
            if not finder_exists:
                conn.execute("""
                    INSERT INTO students (student_id, status, registration_datetime)
                    VALUES (?, 'Active', ?)
                """, (finder_id, datetime.now().isoformat()))

            cursor = conn.execute("""
                INSERT INTO found_items
                (finder_id, item_name, category, description, found_date,
                 found_location, found_time, distinctive_features, color, brand,
                 current_location, storage_info, contact_email, contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (finder_id, item_name, category, description, found_date,
                  found_location, found_time, distinctive_features, color, brand,
                  current_location, storage_info, contact_email, contact_phone))

            item_id = cursor.lastrowid

            log_activity('create', 'found_item',
                        details={'item_id': item_id, 'finder_id': finder_id, 'item': item_name})

            # Automatically search for potential matches
            self._find_potential_matches_for_found(item_id)

            return item_id

    def get_found_item(self, item_id: int) -> Optional[Dict]:
        """Get found item by ID with photos."""
        with get_connection() as conn:
            item = conn.execute("""
                SELECT * FROM found_items WHERE item_id = ?
            """, (item_id,)).fetchone()

            if not item:
                return None

            result = dict(item)

            # Get photos
            photos = conn.execute("""
                SELECT * FROM item_photos
                WHERE item_type = 'found' AND item_id = ?
            """, (item_id,)).fetchall()

            result['photos'] = [dict(p) for p in photos]

            # Get verification questions
            questions = conn.execute("""
                SELECT * FROM verification_questions
                WHERE found_item_id = ?
            """, (item_id,)).fetchall()

            result['verification_questions'] = [dict(q) for q in questions]

            return result

    def get_found_items(self, finder_id: Optional[str] = None,
                       category: Optional[str] = None,
                       status: str = 'Available') -> List[Dict]:
        """Get found items with optional filters."""
        with get_connection() as conn:
            query = "SELECT * FROM found_items WHERE 1=1"
            params = []

            if finder_id:
                query += " AND finder_id = ?"
                params.append(finder_id)

            if category:
                query += " AND category = ?"
                params.append(category)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY reported_at DESC"

            items = conn.execute(query, params).fetchall()
            return [dict(i) for i in items]

    def update_found_item_status(self, item_id: int, status: str,
                                notes: str = "") -> bool:
        """Update found item status (Available, Claimed, Donated, Discarded)."""
        valid_statuses = ['Available', 'Claimed', 'Donated', 'Discarded']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of {valid_statuses}")

        with transaction() as conn:
            conn.execute("""
                UPDATE found_items
                SET status = ?, updated_at = ?
                WHERE item_id = ?
            """, (status, datetime.now().isoformat(), item_id))

            log_activity('update', 'found_item_status',
                        details={'item_id': item_id, 'status': status, 'notes': notes})

        return True

    # ========== Photo Management ==========

    def add_item_photo(self, item_type: str, item_id: int,
                      photo_data: bytes, caption: str = "") -> int:
        """
        Add a photo to a lost or found item.

        Args:
            item_type: 'lost' or 'found'
            item_id: Item ID
            photo_data: Photo binary data
            caption: Optional photo caption

        Returns:
            Photo ID
        """
        if item_type not in ['lost', 'found']:
            raise ValueError("item_type must be 'lost' or 'found'")

        # Generate photo hash for duplicate detection
        photo_hash = hashlib.sha256(photo_data).hexdigest()

        # Save photo to disk
        upload_dir = os.path.join(paths.UPLOAD_DIR, 'lost_found')
        filename = f"{item_type}_{item_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        photo_path = os.path.join(upload_dir, filename)

        with open(photo_path, 'wb') as f:
            f.write(photo_data)

        # Save to database
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO item_photos
                (item_type, item_id, photo_path, photo_hash, caption)
                VALUES (?, ?, ?, ?, ?)
            """, (item_type, item_id, photo_path, photo_hash, caption))

            photo_id = cursor.lastrowid

            log_activity('create', 'item_photo',
                        details={'photo_id': photo_id, 'item_type': item_type, 'item_id': item_id})

            return photo_id

    def get_item_photos(self, item_type: str, item_id: int) -> List[Dict]:
        """Get all photos for an item."""
        with get_connection() as conn:
            photos = conn.execute("""
                SELECT * FROM item_photos
                WHERE item_type = ? AND item_id = ?
                ORDER BY uploaded_at
            """, (item_type, item_id)).fetchall()

            return [dict(p) for p in photos]

    def delete_item_photo(self, photo_id: int) -> bool:
        """Delete an item photo."""
        with get_connection() as conn:
            photo = conn.execute("""
                SELECT photo_path FROM item_photos WHERE photo_id = ?
            """, (photo_id,)).fetchone()

            if not photo:
                return False

            # Delete file from disk
            try:
                if os.path.exists(photo['photo_path']):
                    os.remove(photo['photo_path'])
            except Exception as e:
                log_activity('error', 'delete_photo_file',
                           details={'photo_id': photo_id, 'error': str(e)})

        # Delete from database
        with transaction() as conn:
            conn.execute("DELETE FROM item_photos WHERE photo_id = ?", (photo_id,))

            log_activity('delete', 'item_photo', details={'photo_id': photo_id})

        return True

    # ========== Search and Matching ==========

    def search_items(self, item_type: str, search_term: str,
                    category: Optional[str] = None,
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> List[Dict]:
        """
        Search lost or found items.

        Args:
            item_type: 'lost' or 'found'
            search_term: Search term for name, description, features
            category: Filter by category
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)

        Returns:
            List of matching items
        """
        table = 'lost_items' if item_type == 'lost' else 'found_items'
        date_field = 'lost_date' if item_type == 'lost' else 'found_date'

        with get_connection() as conn:
            query = f"""
                SELECT * FROM {table}
                WHERE (item_name LIKE ? OR description LIKE ?
                       OR distinctive_features LIKE ? OR brand LIKE ?)
            """
            params = [f"%{escape_like(search_term)}%"] * 4

            if category:
                query += " AND category = ?"
                params.append(category)

            if date_from:
                query += f" AND {date_field} >= ?"
                params.append(date_from)

            if date_to:
                query += f" AND {date_field} <= ?"
                params.append(date_to)

            query += " ORDER BY reported_at DESC"

            items = conn.execute(query, params).fetchall()
            return [dict(i) for i in items]

    def _find_potential_matches_for_lost(self, lost_item_id: int):
        """Find potential matches in found items for a lost item."""
        with get_connection() as conn:
            lost = conn.execute(
                "SELECT * FROM lost_items WHERE item_id = ?",
                (lost_item_id,)
            ).fetchone()

            if not lost:
                return

            # Search found items
            found_items = conn.execute("""
                SELECT * FROM found_items
                WHERE status = 'Available'
                AND category = ?
            """, (lost['category'],)).fetchall()

            matches = []
            for found in found_items:
                score, reasons = self._calculate_match_score(dict(lost), dict(found))
                if score >= 50:  # Threshold for potential match
                    matches.append({
                        'found_item_id': found['item_id'],
                        'score': score,
                        'reasons': reasons
                    })

            # Save matches
            with transaction() as conn:
                for match in matches:
                    conn.execute("""
                        INSERT INTO item_matches
                        (lost_item_id, found_item_id, match_score, match_reasons)
                        VALUES (?, ?, ?, ?)
                    """, (lost_item_id, match['found_item_id'],
                          match['score'], json.dumps(match['reasons'])))

    def _find_potential_matches_for_found(self, found_item_id: int):
        """Find potential matches in lost items for a found item."""
        with get_connection() as conn:
            found = conn.execute(
                "SELECT * FROM found_items WHERE item_id = ?",
                (found_item_id,)
            ).fetchone()

            if not found:
                return

            # Search lost items
            lost_items = conn.execute("""
                SELECT * FROM lost_items
                WHERE status = 'Active'
                AND category = ?
            """, (found['category'],)).fetchall()

            matches = []
            for lost in lost_items:
                score, reasons = self._calculate_match_score(dict(lost), dict(found))
                if score >= 50:  # Threshold for potential match
                    matches.append({
                        'lost_item_id': lost['item_id'],
                        'score': score,
                        'reasons': reasons
                    })

            # Save matches
            with transaction() as conn:
                for match in matches:
                    conn.execute("""
                        INSERT INTO item_matches
                        (lost_item_id, found_item_id, match_score, match_reasons)
                        VALUES (?, ?, ?, ?)
                    """, (match['lost_item_id'], found_item_id,
                          match['score'], json.dumps(match['reasons'])))

    def _calculate_match_score(self, lost_item: Dict, found_item: Dict) -> Tuple[float, List[str]]:
        """Calculate match score between lost and found items."""
        score = 0.0
        reasons = []

        # Category match (required)
        if lost_item['category'] != found_item['category']:
            return 0.0, []

        # Item name similarity (30 points)
        if lost_item['item_name'].lower() in found_item['item_name'].lower() or \
           found_item['item_name'].lower() in lost_item['item_name'].lower():
            score += 30
            reasons.append("Similar item name")

        # Color match (20 points)
        if lost_item['color'] and found_item['color']:
            if lost_item['color'].lower() == found_item['color'].lower():
                score += 20
                reasons.append(f"Same color: {lost_item['color']}")

        # Brand match (20 points)
        if lost_item['brand'] and found_item['brand']:
            if lost_item['brand'].lower() == found_item['brand'].lower():
                score += 20
                reasons.append(f"Same brand: {lost_item['brand']}")

        # Location proximity (15 points)
        if lost_item['lost_location'].lower() in found_item['found_location'].lower() or \
           found_item['found_location'].lower() in lost_item['lost_location'].lower():
            score += 15
            reasons.append("Similar location")

        # Date proximity (15 points)
        try:
            lost_date = datetime.strptime(lost_item['lost_date'], '%Y-%m-%d')
            found_date = datetime.strptime(found_item['found_date'], '%Y-%m-%d')
            date_diff = abs((lost_date - found_date).days)

            if date_diff <= 3:
                score += 15
                reasons.append(f"Dates within {date_diff} days")
            elif date_diff <= 7:
                score += 10
                reasons.append(f"Dates within {date_diff} days")
        except (ValueError, TypeError):
            pass

        return score, reasons

    def get_matches(self, item_type: str, item_id: int) -> List[Dict]:
        """Get potential matches for a lost or found item."""
        with get_connection() as conn:
            if item_type == 'lost':
                matches = conn.execute("""
                    SELECT im.*, fi.item_name, fi.description, fi.found_location, fi.found_date
                    FROM item_matches im
                    JOIN found_items fi ON im.found_item_id = fi.item_id
                    WHERE im.lost_item_id = ?
                    ORDER BY im.match_score DESC
                """, (item_id,)).fetchall()
            else:  # found
                matches = conn.execute("""
                    SELECT im.*, li.item_name, li.description, li.lost_location, li.lost_date
                    FROM item_matches im
                    JOIN lost_items li ON im.lost_item_id = li.item_id
                    WHERE im.found_item_id = ?
                    ORDER BY im.match_score DESC
                """, (item_id,)).fetchall()

            return [dict(m) for m in matches]

    # ========== Claims and Verification ==========

    def create_verification_questions(self, found_item_id: int,
                                      created_by: str,
                                      questions: List[str]) -> List[int]:
        """Create verification questions for a found item."""
        question_ids = []

        with transaction() as conn:
            for question_text in questions:
                cursor = conn.execute("""
                    INSERT INTO verification_questions
                    (found_item_id, question_text, created_by)
                    VALUES (?, ?, ?)
                """, (found_item_id, question_text, created_by))

                question_ids.append(cursor.lastrowid)

            log_activity('create', 'verification_questions',
                        details={'found_item_id': found_item_id,
                                'count': len(questions)})

        return question_ids

    def submit_claim(self, found_item_id: int, claimant_id: str,
                    claim_description: str,
                    verification_answers: Optional[Dict[int, str]] = None,
                    supporting_evidence: str = "") -> int:
        """
        Submit a claim for a found item.

        Args:
            found_item_id: Found item ID
            claimant_id: ID of person claiming item
            claim_description: Why they believe it's their item
            verification_answers: Dict of question_id -> answer
            supporting_evidence: Additional evidence

        Returns:
            Claim ID
        """
        # Get verification questions
        with get_connection() as conn:
            questions = conn.execute("""
                SELECT * FROM verification_questions
                WHERE found_item_id = ?
            """, (found_item_id,)).fetchall()

            question_ids = [q['question_id'] for q in questions]

        # Submit claim
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO item_claims
                (found_item_id, claimant_id, claim_description,
                 verification_questions, verification_answers, supporting_evidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (found_item_id, claimant_id, claim_description,
                  json.dumps(question_ids),
                  json.dumps(verification_answers) if verification_answers else None,
                  supporting_evidence))

            claim_id = cursor.lastrowid

            log_activity('create', 'item_claim',
                        details={'claim_id': claim_id, 'found_item_id': found_item_id,
                                'claimant_id': claimant_id})

            return claim_id

    def review_claim(self, claim_id: int, reviewer_id: str,
                    approved: bool, resolution_notes: str = "") -> bool:
        """Review and approve/reject a claim."""
        status = 'Approved' if approved else 'Rejected'

        with transaction() as conn:
            # Update claim
            conn.execute("""
                UPDATE item_claims
                SET status = ?, reviewed_at = ?, reviewed_by = ?,
                    resolution_notes = ?
                WHERE claim_id = ?
            """, (status, datetime.now().isoformat(), reviewer_id,
                  resolution_notes, claim_id))

            # If approved, update found item status
            if approved:
                claim = conn.execute(
                    "SELECT found_item_id FROM item_claims WHERE claim_id = ?",
                    (claim_id,)
                ).fetchone()

                if claim:
                    conn.execute("""
                        UPDATE found_items
                        SET status = 'Claimed', updated_at = ?
                        WHERE item_id = ?
                    """, (datetime.now().isoformat(), claim['found_item_id']))

            log_activity('update', 'item_claim_review',
                        details={'claim_id': claim_id, 'status': status, 'reviewer': reviewer_id})

        return True

    def get_claims(self, found_item_id: Optional[int] = None,
                  claimant_id: Optional[str] = None,
                  status: Optional[str] = None) -> List[Dict]:
        """Get claims with optional filters."""
        with get_connection() as conn:
            query = "SELECT * FROM item_claims WHERE 1=1"
            params = []

            if found_item_id:
                query += " AND found_item_id = ?"
                params.append(found_item_id)

            if claimant_id:
                query += " AND claimant_id = ?"
                params.append(claimant_id)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY submitted_at DESC"

            claims = conn.execute(query, params).fetchall()
            return [dict(c) for c in claims]

    # ========== Analytics ==========

    def get_statistics(self) -> Dict:
        """Get overall lost and found statistics."""
        with get_connection() as conn:
            lost_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status = 'Found' THEN 1 ELSE 0 END) as found
                FROM lost_items
            """).fetchone()

            found_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available,
                    SUM(CASE WHEN status = 'Claimed' THEN 1 ELSE 0 END) as claimed
                FROM found_items
            """).fetchone()

            claim_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as rejected
                FROM item_claims
            """).fetchone()

            match_stats = conn.execute("""
                SELECT COUNT(*) as total_matches, AVG(match_score) as avg_score
                FROM item_matches
                WHERE match_score >= 50
            """).fetchone()

            return {
                'lost_items': dict(lost_stats) if lost_stats else {},
                'found_items': dict(found_stats) if found_stats else {},
                'claims': dict(claim_stats) if claim_stats else {},
                'matches': dict(match_stats) if match_stats else {}
            }

    def get_category_breakdown(self) -> Dict:
        """Get item breakdown by category."""
        with get_connection() as conn:
            lost_by_category = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM lost_items
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()

            found_by_category = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM found_items
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()

            return {
                'lost': [dict(c) for c in lost_by_category],
                'found': [dict(c) for c in found_by_category]
            }
