"""Church schema and initialization."""
from .. import *

CHURCH_MANAGEMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS church_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    join_date TEXT,
    membership_type TEXT,
    status TEXT DEFAULT 'Active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_name TEXT,
    donor_email TEXT,
    amount REAL,
    donation_type TEXT,
    payment_method TEXT,
    transaction_ref TEXT,
    date TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_prayer_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_name TEXT,
    request TEXT,
    category TEXT,
    status TEXT DEFAULT 'Pending',
    date TEXT,
    is_anonymous INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_sermons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    speaker TEXT,
    date TEXT,
    scripture TEXT,
    summary TEXT,
    video_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    date TEXT,
    priority TEXT,
    expires TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_volunteers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    ministry TEXT,
    availability TEXT,
    skills TEXT,
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_date TEXT,
    service_type TEXT,
    attendance_count INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_small_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    leader TEXT,
    meeting_day TEXT,
    meeting_time TEXT,
    location TEXT,
    description TEXT,
    members TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS church_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT,
    amount REAL,
    category TEXT,
    date TEXT,
    vendor TEXT,
    approved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def init_church_database():
    """Initialize church management database tables."""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            conn.executescript(CHURCH_MANAGEMENT_SCHEMA)
            conn.commit()
        logger.info("Church management database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize church database: {e}")
        return False
