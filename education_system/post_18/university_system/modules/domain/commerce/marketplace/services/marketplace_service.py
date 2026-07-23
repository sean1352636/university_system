"""
Student Marketplace Service

Facilitates buying/selling, subletting, and free stuff exchange among students.
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import os

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core import paths
from education_system.post_18.university_system.core.sql_safety import validate_identifier, escape_like  # nosec B608

class MarketplaceService:
    """Service for student marketplace and exchanges."""

    def __init__(self):
        """Initialize the Marketplace Service."""
        self._ensure_tables_exist()
        self._remove_foreign_key_constraints()
        self._ensure_upload_directory()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Marketplace Listings table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS marketplace_listings (
                    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller_id TEXT NOT NULL,
                    listing_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL,
                    condition_status TEXT,
                    location TEXT,
                    contact_method TEXT DEFAULT 'Message',
                    contact_info TEXT,
                    is_negotiable BOOLEAN DEFAULT 1,
                    status TEXT DEFAULT 'Active',
                    view_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    metadata TEXT
                )
            """)

            # Sublet Listings table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sublet_listings (
                    sublet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    landlord_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    address TEXT NOT NULL,
                    monthly_rent REAL NOT NULL,
                    utilities_included BOOLEAN DEFAULT 0,
                    bedrooms INTEGER,
                    bathrooms REAL,
                    square_feet INTEGER,
                    furnished BOOLEAN DEFAULT 0,
                    pets_allowed BOOLEAN DEFAULT 0,
                    parking_available BOOLEAN DEFAULT 0,
                    available_from TEXT NOT NULL,
                    available_to TEXT NOT NULL,
                    min_lease_months INTEGER DEFAULT 1,
                    security_deposit REAL,
                    amenities TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    status TEXT DEFAULT 'Available',
                    view_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Free Stuff Board table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS free_stuff (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giver_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    condition_status TEXT DEFAULT 'Used',
                    location TEXT NOT NULL,
                    pickup_instructions TEXT,
                    available_until TEXT,
                    contact_info TEXT,
                    status TEXT DEFAULT 'Available',
                    claimed_by TEXT,
                    claimed_at TEXT,
                    view_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Listing Photos table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listing_photos (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    photo_path TEXT NOT NULL,
                    is_primary BOOLEAN DEFAULT 0,
                    caption TEXT,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Saved Listings table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_listings (
                    saved_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Messages table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS marketplace_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Reviews/Ratings table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS marketplace_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    seller_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    review_text TEXT,
                    transaction_completed BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Reports table (no FK constraint to allow any user type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS marketplace_reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    reporter_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'Pending',
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    resolution TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            log_activity('create', 'marketplace_tables',
                        details={'status': 'Marketplace tables created'})

    def _remove_foreign_key_constraints(self):
        """Remove foreign key constraints from marketplace tables to allow any user type."""
        with transaction() as conn:
            # Check if we need to migrate tables
            cursor = conn.execute("""
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='marketplace_listings'
            """)
            result = cursor.fetchone()

            if result and 'FOREIGN KEY' in result[0]:
                # Table has FK constraint, need to recreate
                # Step 1: Create temporary table without FK
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS marketplace_listings_new (
                        listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        seller_id TEXT NOT NULL,
                        listing_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        category TEXT NOT NULL,
                        price REAL,
                        condition_status TEXT,
                        location TEXT,
                        contact_method TEXT DEFAULT 'Message',
                        contact_info TEXT,
                        is_negotiable BOOLEAN DEFAULT 1,
                        status TEXT DEFAULT 'Active',
                        view_count INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        expires_at TEXT,
                        metadata TEXT
                    )
                """)

                # Step 2: Copy data (check if metadata column exists)
                cursor = conn.execute("PRAGMA table_info(marketplace_listings)")
                columns = [row[1] for row in cursor.fetchall()]

                if 'metadata' in columns:
                    # Old table has metadata column
                    conn.execute("""
                        INSERT INTO marketplace_listings_new
                        SELECT * FROM marketplace_listings
                    """)
                else:
                    # Old table doesn't have metadata column
                    conn.execute("""
                        INSERT INTO marketplace_listings_new
                        SELECT listing_id, seller_id, listing_type, title, description,
                               category, price, condition_status, location, contact_method,
                               contact_info, is_negotiable, status, view_count,
                               created_at, updated_at, expires_at,
                               NULL as metadata
                        FROM marketplace_listings
                    """)

                # Step 3: Drop old table
                conn.execute("DROP TABLE marketplace_listings")

                # Step 4: Rename new table
                conn.execute("ALTER TABLE marketplace_listings_new RENAME TO marketplace_listings")

                log_activity('update', 'marketplace_tables',
                           details={'action': 'Removed foreign key constraints'})

    def _ensure_upload_directory(self):
        """Ensure upload directory exists for listing photos."""
        upload_dir = os.path.join(paths.UPLOAD_DIR, 'marketplace')
        os.makedirs(upload_dir, exist_ok=True)

    # ========== Marketplace Listings (Buy/Sell) ==========

    def create_listing(self, seller_id: str, listing_type: str, title: str,
                      description: str, category: str, price: float = 0.0,
                      condition_status: str = "Used", location: str = "",
                      contact_method: str = "Message", contact_info: str = "",
                      is_negotiable: bool = True,
                      expires_days: int = 30, metadata: Optional[Dict] = None) -> int:
        """
        Create a marketplace listing.

        Args:
            seller_id: Seller's ID
            listing_type: 'For Sale', 'Wanted', 'Service', 'Trade'
            title: Listing title
            description: Detailed description
            category: Category (Electronics, Books, Furniture, etc.)
            price: Price (0 for free or negotiable)
            condition_status: 'New', 'Like New', 'Good', 'Fair', 'Poor'
            location: Pickup/delivery location
            contact_method: Preferred contact method
            contact_info: Contact information
            is_negotiable: Whether price is negotiable
            expires_days: Days until listing expires
            metadata: Optional metadata (e.g., ISBN, course_code for textbooks)

        Returns:
            Listing ID
        """
        expires_at = (datetime.now() + timedelta(days=expires_days)).strftime('%Y-%m-%d')

        # Ensure metadata column exists
        self._ensure_metadata_column()

        # Convert metadata dict to JSON string
        metadata_json = json.dumps(metadata) if metadata else None

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO marketplace_listings
                (seller_id, listing_type, title, description, category,
                 price, condition_status, location, contact_method, contact_info,
                 is_negotiable, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (seller_id, listing_type, title, description, category,
                  price, condition_status, location, contact_method, contact_info,
                  is_negotiable, expires_at, metadata_json))

            listing_id = cursor.lastrowid

            log_activity('create', 'marketplace_listing',
                        details={'listing_id': listing_id, 'seller_id': seller_id,
                                'type': listing_type, 'title': title, 'metadata': metadata})

            return listing_id

    def _ensure_metadata_column(self):
        """Ensure metadata column exists in marketplace_listings table."""
        with transaction() as conn:
            # Check if column exists
            cursor = conn.execute("""
                PRAGMA table_info(marketplace_listings)
            """)
            columns = [row[1] for row in cursor.fetchall()]

            if 'metadata' not in columns:
                # Add metadata column
                conn.execute("""
                    ALTER TABLE marketplace_listings
                    ADD COLUMN metadata TEXT
                """)

    def get_listing(self, listing_id: int, increment_views: bool = True) -> Optional[Dict]:
        """Get marketplace listing by ID."""
        with get_connection() as conn:
            # Increment view count
            if increment_views:
                with transaction() as trans_conn:
                    trans_conn.execute("""
                        UPDATE marketplace_listings
                        SET view_count = view_count + 1
                        WHERE listing_id = ?
                    """, (listing_id,))

            listing = conn.execute("""
                SELECT * FROM marketplace_listings WHERE listing_id = ?
            """, (listing_id,)).fetchone()

            if not listing:
                return None

            result = dict(listing)

            # Get photos
            photos = conn.execute("""
                SELECT * FROM listing_photos
                WHERE listing_type = 'marketplace' AND listing_id = ?
                ORDER BY is_primary DESC, uploaded_at
            """, (listing_id,)).fetchall()

            result['photos'] = [dict(p) for p in photos]

            # Get seller rating
            seller_rating = conn.execute("""
                SELECT AVG(rating) as avg_rating, COUNT(*) as review_count
                FROM marketplace_reviews
                WHERE seller_id = ?
            """, (listing['seller_id'],)).fetchone()

            result['seller_rating'] = dict(seller_rating) if seller_rating else {}

            # Parse metadata JSON if present
            if result.get('metadata'):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except (json.JSONDecodeError, TypeError):
                    result['metadata'] = {}

            return result

    def get_listings(self, seller_id: Optional[str] = None,
                    listing_type: Optional[str] = None,
                    category: Optional[str] = None,
                    status: str = 'Active',
                    min_price: Optional[float] = None,
                    max_price: Optional[float] = None,
                    search_term: Optional[str] = None,
                    limit: int = 50) -> List[Dict]:
        """Get marketplace listings with filters."""
        with get_connection() as conn:
            query = "SELECT * FROM marketplace_listings WHERE 1=1"
            params = []

            if seller_id:
                query += " AND seller_id = ?"
                params.append(seller_id)

            if listing_type:
                query += " AND listing_type = ?"
                params.append(listing_type)

            if category:
                query += " AND category = ?"
                params.append(category)

            if status:
                query += " AND status = ?"
                params.append(status)

            if min_price is not None:
                query += " AND price >= ?"
                params.append(min_price)

            if max_price is not None:
                query += " AND price <= ?"
                params.append(max_price)

            if search_term:
                query += " AND (title LIKE ? OR description LIKE ?)"
                params.extend([f"%{escape_like(search_term)}%", f"%{escape_like(search_term)}%"])

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            listings = conn.execute(query, params).fetchall()
            result_listings = []
            for listing in listings:
                listing_dict = dict(listing)
                # Parse metadata JSON if present
                if listing_dict.get('metadata'):
                    try:
                        listing_dict['metadata'] = json.loads(listing_dict['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        listing_dict['metadata'] = {}
                result_listings.append(listing_dict)
            return result_listings

    def get_user_listings(self, user_id: str, status: Optional[str] = None) -> List[Dict]:
        """Get all listings for a specific user."""
        return self.get_listings(seller_id=user_id, status=status, limit=1000)

    def search_listings(self, search_term: Optional[str] = None,
                       min_price: Optional[float] = None,
                       max_price: Optional[float] = None,
                       category: Optional[str] = None,
                       status: str = 'Active') -> List[Dict]:
        """Search listings with filters."""
        return self.get_listings(
            search_term=search_term,
            min_price=min_price,
            max_price=max_price,
            category=category,
            status=status,
            limit=100
        )

    def get_categories(self) -> List[str]:
        """Get list of available categories."""
        return [
            "Textbooks",
            "Electronics",
            "Furniture",
            "Housing",
            "Services",
            "Free",
            "Other"
        ]

    def update_listing(self, listing_id: int, **updates) -> bool:
        """Update marketplace listing fields."""
        if not updates:
            return False

        allowed_fields = {
            'title', 'description', 'category', 'price', 'condition_status',
            'location', 'contact_method', 'contact_info', 'is_negotiable', 'status'
        }

        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            return False

        set_clause = ", ".join([validate_identifier(field, "column") + " = ?" for field in valid_updates.keys()])
        set_clause += ", updated_at = ?"

        values = list(valid_updates.values())
        values.append(datetime.now().isoformat())
        values.append(listing_id)

        with transaction() as conn:
            conn.execute(
                "UPDATE marketplace_listings"
                " SET " + set_clause +
                " WHERE listing_id = ?",
                values)

            log_activity('update', 'marketplace_listing',
                        details={'listing_id': listing_id, 'updated_fields': list(valid_updates.keys())})

        return True

    def delete_listing(self, listing_id: int, user_id: Optional[str] = None) -> bool:
        """Delete a marketplace listing."""
        with transaction() as conn:
            # Verify ownership if user_id provided
            if user_id:
                listing = conn.execute("""
                    SELECT seller_id FROM marketplace_listings WHERE listing_id = ?
                """, (listing_id,)).fetchone()

                if not listing or listing['seller_id'] != user_id:
                    return False

            conn.execute("""
                UPDATE marketplace_listings
                SET status = 'Deleted', updated_at = ?
                WHERE listing_id = ?
            """, (datetime.now().isoformat(), listing_id))

            log_activity('delete', 'marketplace_listing',
                        details={'listing_id': listing_id})

        return True

    def mark_listing_sold(self, listing_id: int, user_id: str) -> bool:
        """Mark a listing as sold."""
        with transaction() as conn:
            # Verify ownership
            listing = conn.execute("""
                SELECT seller_id FROM marketplace_listings WHERE listing_id = ?
            """, (listing_id,)).fetchone()

            if not listing or listing['seller_id'] != user_id:
                return False

            conn.execute("""
                UPDATE marketplace_listings
                SET status = 'Sold', updated_at = ?
                WHERE listing_id = ?
            """, (datetime.now().isoformat(), listing_id))

            log_activity('update', 'marketplace_listing',
                        details={'listing_id': listing_id, 'status': 'Sold'})

        return True

    # ========== Sublet Listings ==========

    def create_sublet(self, landlord_id: str, title: str, description: str,
                     address: str, monthly_rent: float,
                     available_from: str, available_to: str,
                     utilities_included: bool = False,
                     bedrooms: int = 1, bathrooms: float = 1.0,
                     square_feet: int = 0, furnished: bool = False,
                     pets_allowed: bool = False, parking_available: bool = False,
                     min_lease_months: int = 1, security_deposit: float = 0.0,
                     amenities: str = "", contact_email: str = "",
                     contact_phone: str = "") -> int:
        """
        Create a sublet listing.

        Args:
            landlord_id: Landlord's ID
            title: Listing title
            description: Detailed description
            address: Property address
            monthly_rent: Monthly rent amount
            available_from: Start date (YYYY-MM-DD)
            available_to: End date (YYYY-MM-DD)
            utilities_included: Whether utilities are included
            bedrooms: Number of bedrooms
            bathrooms: Number of bathrooms
            square_feet: Square footage
            furnished: Whether furnished
            pets_allowed: Whether pets are allowed
            parking_available: Whether parking is available
            min_lease_months: Minimum lease duration
            security_deposit: Security deposit amount
            amenities: Comma-separated amenities
            contact_email: Contact email
            contact_phone: Contact phone

        Returns:
            Sublet listing ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO sublet_listings
                (landlord_id, title, description, address, monthly_rent,
                 utilities_included, bedrooms, bathrooms, square_feet,
                 furnished, pets_allowed, parking_available,
                 available_from, available_to, min_lease_months,
                 security_deposit, amenities, contact_email, contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (landlord_id, title, description, address, monthly_rent,
                  utilities_included, bedrooms, bathrooms, square_feet,
                  furnished, pets_allowed, parking_available,
                  available_from, available_to, min_lease_months,
                  security_deposit, amenities, contact_email, contact_phone))

            sublet_id = cursor.lastrowid

            log_activity('create', 'sublet_listing',
                        details={'sublet_id': sublet_id, 'landlord_id': landlord_id, 'address': address})

            return sublet_id

    def get_sublet(self, sublet_id: int, increment_views: bool = True) -> Optional[Dict]:
        """Get sublet listing by ID."""
        with get_connection() as conn:
            if increment_views:
                with transaction() as trans_conn:
                    trans_conn.execute("""
                        UPDATE sublet_listings
                        SET view_count = view_count + 1
                        WHERE sublet_id = ?
                    """, (sublet_id,))

            sublet = conn.execute("""
                SELECT * FROM sublet_listings WHERE sublet_id = ?
            """, (sublet_id,)).fetchone()

            if not sublet:
                return None

            result = dict(sublet)

            # Get photos
            photos = conn.execute("""
                SELECT * FROM listing_photos
                WHERE listing_type = 'sublet' AND listing_id = ?
                ORDER BY is_primary DESC, uploaded_at
            """, (sublet_id,)).fetchall()

            result['photos'] = [dict(p) for p in photos]

            return result

    def get_sublets(self, landlord_id: Optional[str] = None,
                   status: str = 'Available',
                   min_rent: Optional[float] = None,
                   max_rent: Optional[float] = None,
                   min_bedrooms: Optional[int] = None,
                   furnished: Optional[bool] = None,
                   pets_allowed: Optional[bool] = None,
                   available_from: Optional[str] = None,
                   search_term: Optional[str] = None,
                   limit: int = 50) -> List[Dict]:
        """Get sublet listings with filters."""
        with get_connection() as conn:
            query = "SELECT * FROM sublet_listings WHERE 1=1"
            params = []

            if landlord_id:
                query += " AND landlord_id = ?"
                params.append(landlord_id)

            if status:
                query += " AND status = ?"
                params.append(status)

            if min_rent is not None:
                query += " AND monthly_rent >= ?"
                params.append(min_rent)

            if max_rent is not None:
                query += " AND monthly_rent <= ?"
                params.append(max_rent)

            if min_bedrooms is not None:
                query += " AND bedrooms >= ?"
                params.append(min_bedrooms)

            if furnished is not None:
                query += " AND furnished = ?"
                params.append(furnished)

            if pets_allowed is not None:
                query += " AND pets_allowed = ?"
                params.append(pets_allowed)

            if available_from:
                query += " AND available_from <= ?"
                params.append(available_from)

            if search_term:
                query += " AND (title LIKE ? OR description LIKE ? OR address LIKE ?)"
                params.extend([f"%{escape_like(search_term)}%"] * 3)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            sublets = conn.execute(query, params).fetchall()
            return [dict(s) for s in sublets]

    def update_sublet(self, sublet_id: int, **updates) -> bool:
        """Update sublet listing fields."""
        if not updates:
            return False

        allowed_fields = {
            'title', 'description', 'monthly_rent', 'utilities_included',
            'furnished', 'pets_allowed', 'parking_available', 'amenities',
            'contact_email', 'contact_phone', 'status'
        }

        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            return False

        set_clause = ", ".join([validate_identifier(field, "column") + " = ?" for field in valid_updates.keys()])
        set_clause += ", updated_at = ?"

        values = list(valid_updates.values())
        values.append(datetime.now().isoformat())
        values.append(sublet_id)

        with transaction() as conn:
            conn.execute(
                "UPDATE sublet_listings"
                " SET " + set_clause +
                " WHERE sublet_id = ?",
                values)

            log_activity('update', 'sublet_listing',
                        details={'sublet_id': sublet_id, 'updated_fields': list(valid_updates.keys())})

        return True

    # ========== Free Stuff Board ==========

    def post_free_item(self, giver_id: str, item_name: str, description: str,
                      category: str, condition_status: str = "Used",
                      location: str = "", pickup_instructions: str = "",
                      available_days: int = 7, contact_info: str = "") -> int:
        """
        Post a free item to the free stuff board.

        Args:
            giver_id: ID of person giving away item
            item_name: Name of item
            description: Item description
            category: Category
            condition_status: Condition
            location: Pickup location
            pickup_instructions: How to pick up
            available_days: Days until item removed if not claimed
            contact_info: Contact information

        Returns:
            Free item ID
        """
        available_until = (datetime.now() + timedelta(days=available_days)).strftime('%Y-%m-%d')

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO free_stuff
                (giver_id, item_name, description, category, condition_status,
                 location, pickup_instructions, available_until, contact_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (giver_id, item_name, description, category, condition_status,
                  location, pickup_instructions, available_until, contact_info))

            item_id = cursor.lastrowid

            log_activity('create', 'free_stuff_post',
                        details={'item_id': item_id, 'giver_id': giver_id, 'item': item_name})

            return item_id

    def get_free_item(self, item_id: int, increment_views: bool = True) -> Optional[Dict]:
        """Get free item by ID."""
        with get_connection() as conn:
            if increment_views:
                with transaction() as trans_conn:
                    trans_conn.execute("""
                        UPDATE free_stuff
                        SET view_count = view_count + 1
                        WHERE item_id = ?
                    """, (item_id,))

            item = conn.execute("""
                SELECT * FROM free_stuff WHERE item_id = ?
            """, (item_id,)).fetchone()

            if not item:
                return None

            result = dict(item)

            # Get photos
            photos = conn.execute("""
                SELECT * FROM listing_photos
                WHERE listing_type = 'free_stuff' AND listing_id = ?
                ORDER BY uploaded_at
            """, (item_id,)).fetchall()

            result['photos'] = [dict(p) for p in photos]

            return result

    def get_free_items(self, giver_id: Optional[str] = None,
                      category: Optional[str] = None,
                      status: str = 'Available',
                      search_term: Optional[str] = None,
                      limit: int = 50) -> List[Dict]:
        """Get free stuff items with filters."""
        with get_connection() as conn:
            query = "SELECT * FROM free_stuff WHERE 1=1"
            params = []

            if giver_id:
                query += " AND giver_id = ?"
                params.append(giver_id)

            if category:
                query += " AND category = ?"
                params.append(category)

            if status:
                query += " AND status = ?"
                params.append(status)

            if search_term:
                query += " AND (item_name LIKE ? OR description LIKE ?)"
                params.extend([f"%{escape_like(search_term)}%", f"%{escape_like(search_term)}%"])

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            items = conn.execute(query, params).fetchall()
            return [dict(i) for i in items]

    def claim_free_item(self, item_id: int, claimer_id: str) -> bool:
        """Claim a free item."""
        with transaction() as conn:
            # Check if still available
            item = conn.execute("""
                SELECT status FROM free_stuff WHERE item_id = ?
            """, (item_id,)).fetchone()

            if not item or item['status'] != 'Available':
                return False

            # Claim it
            conn.execute("""
                UPDATE free_stuff
                SET status = 'Claimed', claimed_by = ?, claimed_at = ?
                WHERE item_id = ?
            """, (claimer_id, datetime.now().isoformat(), item_id))

            log_activity('update', 'free_stuff_claim',
                        details={'item_id': item_id, 'claimed_by': claimer_id})

        return True

    # ========== Photo Management ==========

    def add_listing_photo(self, listing_type: str, listing_id: int,
                         photo_data: bytes, is_primary: bool = False,
                         caption: str = "") -> int:
        """
        Add a photo to a listing.

        Args:
            listing_type: 'marketplace', 'sublet', or 'free_stuff'
            listing_id: Listing ID
            photo_data: Photo binary data
            is_primary: Whether this is the primary photo
            caption: Photo caption

        Returns:
            Photo ID
        """
        # Save photo to disk
        upload_dir = os.path.join(paths.UPLOAD_DIR, 'marketplace')
        filename = f"{listing_type}_{listing_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        photo_path = os.path.join(upload_dir, filename)

        with open(photo_path, 'wb') as f:
            f.write(photo_data)

        # If this is primary, unset other primary photos
        if is_primary:
            with transaction() as conn:
                conn.execute("""
                    UPDATE listing_photos
                    SET is_primary = 0
                    WHERE listing_type = ? AND listing_id = ?
                """, (listing_type, listing_id))

        # Save to database
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO listing_photos
                (listing_type, listing_id, photo_path, is_primary, caption)
                VALUES (?, ?, ?, ?, ?)
            """, (listing_type, listing_id, photo_path, is_primary, caption))

            photo_id = cursor.lastrowid

            log_activity('create', 'listing_photo',
                        details={'photo_id': photo_id, 'listing_type': listing_type, 'listing_id': listing_id})

            return photo_id

    def get_listing_photos(self, listing_type: str, listing_id: int) -> List[Dict]:
        """Get all photos for a listing."""
        with get_connection() as conn:
            photos = conn.execute("""
                SELECT * FROM listing_photos
                WHERE listing_type = ? AND listing_id = ?
                ORDER BY is_primary DESC, uploaded_at
            """, (listing_type, listing_id)).fetchall()

            return [dict(p) for p in photos]

    # ========== Saved Listings (Watchlist) ==========

    def save_listing(self, user_id: str, listing_type: str,
                    listing_id: int, notes: str = "") -> int:
        """Add a listing to user's saved items."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO saved_listings
                (user_id, listing_type, listing_id, notes)
                VALUES (?, ?, ?, ?)
            """, (user_id, listing_type, listing_id, notes))

            saved_id = cursor.lastrowid

            log_activity('create', 'saved_listing',
                        details={'saved_id': saved_id, 'user_id': user_id, 'type': listing_type})

            return saved_id

    def get_saved_listings(self, user_id: str) -> List[Dict]:
        """Get all saved listings for a user."""
        with get_connection() as conn:
            saved = conn.execute("""
                SELECT sl.*,
                    CASE sl.listing_type
                        WHEN 'marketplace' THEN ml.title
                        WHEN 'sublet' THEN sub.title
                        WHEN 'free_stuff' THEN fs.item_name
                    END as listing_title
                FROM saved_listings sl
                LEFT JOIN marketplace_listings ml ON sl.listing_type = 'marketplace'
                    AND sl.listing_id = ml.listing_id
                LEFT JOIN sublet_listings sub ON sl.listing_type = 'sublet'
                    AND sl.listing_id = sub.sublet_id
                LEFT JOIN free_stuff fs ON sl.listing_type = 'free_stuff'
                    AND sl.listing_id = fs.item_id
                WHERE sl.user_id = ?
                ORDER BY sl.created_at DESC
            """, (user_id,)).fetchall()

            return [dict(s) for s in saved]

    def remove_saved_listing(self, saved_id: int) -> bool:
        """Remove a listing from saved items."""
        with transaction() as conn:
            conn.execute("""
                DELETE FROM saved_listings WHERE saved_id = ?
            """, (saved_id,))

            log_activity('delete', 'saved_listing',
                        details={'saved_id': saved_id})

        return True

    def add_favorite(self, user_id: str, listing_id: int) -> bool:
        """Add a listing to user's favorites (wrapper for save_listing)."""
        try:
            self.save_listing(user_id, 'marketplace', listing_id)
            return True
        except Exception:
            return False

    def get_user_favorites(self, user_id: str) -> List[Dict]:
        """Get user's favorite listings (wrapper for get_saved_listings)."""
        saved_listings = self.get_saved_listings(user_id)

        # Fetch full listing details for marketplace listings
        favorites = []
        with get_connection() as conn:
            for saved in saved_listings:
                if saved['listing_type'] == 'marketplace':
                    listing = self.get_listing(saved['listing_id'], increment_views=False)
                    if listing:
                        favorites.append(listing)

        return favorites

    # ========== Messaging ==========

    def send_message(self, listing_id: int, sender_id: str,
                    message_text: str, listing_type: str = 'marketplace',
                    receiver_id: Optional[str] = None) -> int:
        """
        Send a message about a listing.

        If receiver_id is not provided, it will be looked up from the listing's seller.
        """
        # If receiver_id not provided, look up the seller
        if not receiver_id:
            with get_connection() as conn:
                listing = conn.execute("""
                    SELECT seller_id FROM marketplace_listings WHERE listing_id = ?
                """, (listing_id,)).fetchone()

                if not listing:
                    raise ValueError(f"Listing {listing_id} not found")

                receiver_id = listing['seller_id']

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO marketplace_messages
                (listing_type, listing_id, sender_id, receiver_id, message_text)
                VALUES (?, ?, ?, ?, ?)
            """, (listing_type, listing_id, sender_id, receiver_id, message_text))

            message_id = cursor.lastrowid

            log_activity('create', 'marketplace_message',
                        details={'message_id': message_id, 'listing_type': listing_type, 'listing_id': listing_id})

            return message_id

    def get_user_messages(self, user_id: str) -> List[Dict]:
        """Get all messages for a user (sent or received)."""
        with get_connection() as conn:
            messages = conn.execute("""
                SELECT *,
                    CASE WHEN sender_id = ? THEN 'sent' ELSE 'received' END as direction
                FROM marketplace_messages
                WHERE sender_id = ? OR receiver_id = ?
                ORDER BY sent_at DESC
            """, (user_id, user_id, user_id)).fetchall()

            return [dict(m) for m in messages]

    def get_messages(self, listing_type: str, listing_id: int,
                    user_id: str) -> List[Dict]:
        """Get all messages for a listing involving user."""
        with get_connection() as conn:
            messages = conn.execute("""
                SELECT *,
                    CASE WHEN sender_id = ? THEN 'sent' ELSE 'received' END as direction
                FROM marketplace_messages
                WHERE listing_type = ? AND listing_id = ?
                  AND (sender_id = ? OR receiver_id = ?)
                ORDER BY sent_at ASC
            """, (user_id, listing_type, listing_id, user_id, user_id)).fetchall()

            return [dict(m) for m in messages]

    def mark_messages_read(self, listing_type: str, listing_id: int,
                          user_id: str) -> int:
        """Mark all messages as read for a user."""
        with transaction() as conn:
            cursor = conn.execute("""
                UPDATE marketplace_messages
                SET is_read = 1
                WHERE listing_type = ? AND listing_id = ?
                  AND receiver_id = ? AND is_read = 0
            """, (listing_type, listing_id, user_id))

            return cursor.rowcount

    # ========== Reviews and Ratings ==========

    def add_review(self, listing_type: str, listing_id: int,
                  reviewer_id: str, seller_id: str, rating: int,
                  review_text: str = "",
                  transaction_completed: bool = True) -> int:
        """Add a review for a seller."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO marketplace_reviews
                (listing_type, listing_id, reviewer_id, seller_id,
                 rating, review_text, transaction_completed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (listing_type, listing_id, reviewer_id, seller_id,
                  rating, review_text, transaction_completed))

            review_id = cursor.lastrowid

            log_activity('create', 'marketplace_review',
                        details={'review_id': review_id, 'seller_id': seller_id, 'rating': rating})

            return review_id

    def get_seller_reviews(self, seller_id: str) -> List[Dict]:
        """Get all reviews for a seller."""
        with get_connection() as conn:
            reviews = conn.execute("""
                SELECT * FROM marketplace_reviews
                WHERE seller_id = ?
                ORDER BY created_at DESC
            """, (seller_id,)).fetchall()

            return [dict(r) for r in reviews]

    def get_seller_rating(self, seller_id: str) -> Dict:
        """Get average rating and review count for a seller."""
        with get_connection() as conn:
            stats = conn.execute("""
                SELECT
                    AVG(rating) as avg_rating,
                    COUNT(*) as review_count,
                    SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as positive_reviews
                FROM marketplace_reviews
                WHERE seller_id = ?
            """, (seller_id,)).fetchone()

            return dict(stats) if stats else {}

    # ========== Reports ==========

    def report_listing(self, listing_type: str, listing_id: int,
                      reporter_id: str, reason: str,
                      description: str = "") -> int:
        """Report a listing for inappropriate content."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO marketplace_reports
                (listing_type, listing_id, reporter_id, reason, description)
                VALUES (?, ?, ?, ?, ?)
            """, (listing_type, listing_id, reporter_id, reason, description))

            report_id = cursor.lastrowid

            log_activity('create', 'marketplace_report',
                        details={'report_id': report_id, 'listing_type': listing_type,
                                'listing_id': listing_id, 'reason': reason})

            return report_id

    def review_report(self, report_id: int, reviewer_id: str,
                     resolution: str) -> bool:
        """Review and resolve a report."""
        with transaction() as conn:
            conn.execute("""
                UPDATE marketplace_reports
                SET status = 'Resolved', reviewed_at = ?,
                    reviewed_by = ?, resolution = ?
                WHERE report_id = ?
            """, (datetime.now().isoformat(), reviewer_id, resolution, report_id))

            log_activity('update', 'marketplace_report',
                        details={'report_id': report_id, 'resolution': resolution})

        return True

    # ========== Analytics ==========

    def get_statistics(self) -> Dict:
        """Get overall marketplace statistics."""
        with get_connection() as conn:
            listing_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                    AVG(view_count) as avg_views
                FROM marketplace_listings
            """).fetchone()

            sublet_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available,
                    AVG(monthly_rent) as avg_rent,
                    AVG(view_count) as avg_views
                FROM sublet_listings
            """).fetchone()

            free_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available,
                    SUM(CASE WHEN status = 'Claimed' THEN 1 ELSE 0 END) as claimed
                FROM free_stuff
            """).fetchone()

            return {
                'marketplace': dict(listing_stats) if listing_stats else {},
                'sublets': dict(sublet_stats) if sublet_stats else {},
                'free_stuff': dict(free_stats) if free_stats else {}
            }

    def get_popular_categories(self) -> Dict:
        """Get most popular categories."""
        with get_connection() as conn:
            marketplace_categories = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM marketplace_listings
                WHERE status = 'Active'
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()

            free_categories = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM free_stuff
                WHERE status = 'Available'
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()

            return {
                'marketplace': [dict(c) for c in marketplace_categories],
                'free_stuff': [dict(c) for c in free_categories]
            }
