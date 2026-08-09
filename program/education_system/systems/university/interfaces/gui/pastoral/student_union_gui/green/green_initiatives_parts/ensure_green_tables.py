"""Extracted function implementation."""

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _ensure_green_tables():
    """Create green-initiative tables if they do not yet exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS green_initiatives (
                initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                status TEXT DEFAULT 'active',
                created_by TEXT,
                created_date TEXT,
                target_date TEXT,
                carbon_target REAL,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carbon_tracking (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                transport_carbon REAL DEFAULT 0,
                energy_carbon REAL DEFAULT 0,
                catering_carbon REAL DEFAULT 0,
                total_carbon REAL DEFAULT 0,
                attendees INTEGER DEFAULT 0,
                carbon_per_person REAL DEFAULT 0,
                sustainability_score REAL DEFAULT 0,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waste_reduction_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                waste_generated REAL DEFAULT 0,
                waste_recycled REAL DEFAULT 0,
                waste_composted REAL DEFAULT 0,
                waste_landfill REAL DEFAULT 0,
                recycling_rate REAL DEFAULT 0,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS green_transport_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transport_method TEXT,
                distance_km REAL DEFAULT 0,
                carbon_saved REAL DEFAULT 0,
                trip_date TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eco_suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                certifications TEXT,
                description TEXT,
                contact_email TEXT,
                rating REAL DEFAULT 0,
                added_by TEXT,
                added_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS green_certifications (
                cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_name TEXT,
                entity_type TEXT,
                certification_level TEXT,
                score REAL DEFAULT 0,
                awarded_date TEXT,
                expires_date TEXT,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carbon_offsets (
                offset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_name TEXT NOT NULL,
                description TEXT,
                offset_kg REAL DEFAULT 0,
                cost REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                purchased_by TEXT,
                purchase_date TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error creating green tables: {e}")
