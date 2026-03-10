"""
Consolidated schema for remaining features 4-8
Creates all tables for: Mobile App, Accessibility, Parent Portal, Transportation, Blockchain
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.paths import DEFAULT_DB_PATH

# Feature 4: Mobile App (PWA) Infrastructure
MOBILE_APP_SCHEMA = """
-- Mobile Devices
CREATE TABLE IF NOT EXISTS mobile_devices (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_type TEXT NOT NULL,  -- ios, android, web
    device_name TEXT,
    push_token TEXT UNIQUE,
    os_version TEXT,
    app_version TEXT,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Mobile Sessions
CREATE TABLE IF NOT EXISTS mobile_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP,
    session_token TEXT UNIQUE,
    ip_address TEXT,
    location TEXT,
    FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Offline Sync Queue
CREATE TABLE IF NOT EXISTS offline_sync_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,  -- create, update, delete
    entity_type TEXT NOT NULL,  -- assignment, grade, attendance
    data TEXT NOT NULL,  -- JSON
    sync_status TEXT DEFAULT 'pending',  -- pending, synced, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
);

-- Mobile Preferences
CREATE TABLE IF NOT EXISTS mobile_preferences (
    pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    theme TEXT DEFAULT 'light',  -- light, dark, auto
    notifications_enabled BOOLEAN DEFAULT 1,
    offline_mode_enabled BOOLEAN DEFAULT 1,
    data_saver_mode BOOLEAN DEFAULT 0,
    auto_sync BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- App Installations
CREATE TABLE IF NOT EXISTS app_installations (
    install_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uninstalled_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
);

-- Mobile Analytics
CREATE TABLE IF NOT EXISTS mobile_analytics (
    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    device_id INTEGER,
    event_type TEXT NOT NULL,  -- page_view, button_click, feature_use
    event_data TEXT,  -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
);
"""

# Feature 5: Accessibility & Accommodation Tools
ACCESSIBILITY_SCHEMA = """
-- Accessibility Profiles
CREATE TABLE IF NOT EXISTS accessibility_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    disabilities TEXT,  -- JSON array
    accommodations TEXT,  -- JSON array
    assistive_technologies TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Accommodation Requests
CREATE TABLE IF NOT EXISTS accommodation_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    accommodation_type TEXT NOT NULL,  -- extended_time, alternative_format, etc.
    description TEXT,
    status TEXT DEFAULT 'pending',  -- pending, approved, denied
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER,
    review_date TIMESTAMP,
    review_notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Disability Documentation
CREATE TABLE IF NOT EXISTS disability_documentation (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    disability_type TEXT NOT NULL,
    file_url TEXT,
    uploaded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE,
    verified_by INTEGER,
    verified_date TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Exam Accommodations
CREATE TABLE IF NOT EXISTS exam_accommodations (
    accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    exam_id INTEGER,
    extended_time INTEGER,  -- minutes
    separate_room BOOLEAN DEFAULT 0,
    assistive_technology TEXT,
    reader_scribe BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'active',
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Alternative Materials
CREATE TABLE IF NOT EXISTS alternative_materials (
    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    original_material_id INTEGER,
    format_type TEXT NOT NULL,  -- braille, audio, large_print, digital
    file_url TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
);

-- Assistive Tech Requests
CREATE TABLE IF NOT EXISTS assistive_tech_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    technology_type TEXT NOT NULL,  -- screen_reader, magnifier, etc.
    status TEXT DEFAULT 'pending',
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fulfilled_date TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Accessibility Settings
CREATE TABLE IF NOT EXISTS accessibility_settings (
    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    theme TEXT DEFAULT 'standard',  -- standard, high_contrast, dark
    font_size INTEGER DEFAULT 16,
    contrast_level TEXT DEFAULT 'normal',
    screen_reader_enabled BOOLEAN DEFAULT 0,
    keyboard_navigation BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Accommodation Approvals
CREATE TABLE IF NOT EXISTS accommodation_approvals (
    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    approved_by INTEGER NOT NULL,
    approved_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id)
);

-- Accessibility Audit Logs
CREATE TABLE IF NOT EXISTS accessibility_audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url TEXT NOT NULL,
    issues_found TEXT,  -- JSON array
    severity TEXT,  -- low, medium, high, critical
    audited_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    audited_by INTEGER
);
"""

# Feature 6: Parent Portal Enhancement
PARENT_PORTAL_SCHEMA = """
-- Parent Accounts
CREATE TABLE IF NOT EXISTS parent_accounts (
    parent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- Parent Student Links
CREATE TABLE IF NOT EXISTS parent_student_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    relationship TEXT NOT NULL,  -- parent, guardian, other
    permissions TEXT,  -- JSON
    is_primary BOOLEAN DEFAULT 0,
    verified BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(parent_id, student_id)
);

-- Parent Permissions
CREATE TABLE IF NOT EXISTS parent_permissions (
    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL,
    permission_type TEXT NOT NULL,  -- view_grades, view_attendance, view_financial
    granted BOOLEAN DEFAULT 1,
    FOREIGN KEY (link_id) REFERENCES parent_student_links(link_id),
    UNIQUE(link_id, permission_type)
);

-- Parent Communications
CREATE TABLE IF NOT EXISTS parent_communications (
    comm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    staff_id INTEGER,
    student_id INTEGER,
    subject TEXT,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);

-- Parent Conference Requests
CREATE TABLE IF NOT EXISTS parent_conference_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    preferred_times TEXT,  -- JSON array
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);

-- Parent Conferences
CREATE TABLE IF NOT EXISTS parent_conferences (
    conference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    student_id INTEGER,
    datetime TIMESTAMP NOT NULL,
    location TEXT,
    meeting_type TEXT DEFAULT 'in_person',  -- in_person, virtual, phone
    meeting_link TEXT,
    status TEXT DEFAULT 'scheduled',
    notes TEXT,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);

-- Parent Notifications
CREATE TABLE IF NOT EXISTS parent_notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    student_id INTEGER,
    notification_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);

-- Parent Document Access
CREATE TABLE IF NOT EXISTS parent_document_access (
    access_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    document_id INTEGER,
    document_type TEXT,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Parent Portal Activity
CREATE TABLE IF NOT EXISTS parent_portal_activity (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);
"""

# Feature 7: Transportation & Parking Management
TRANSPORTATION_SCHEMA = """
-- Parking Permits
CREATE TABLE IF NOT EXISTS parking_permits (
    permit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    permit_type TEXT NOT NULL,  -- student, faculty, staff, visitor, reserved
    permit_number TEXT UNIQUE,
    issue_date DATE,
    expiry_date DATE,
    cost REAL,
    status TEXT DEFAULT 'active',
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
);

-- Vehicles
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER,
    color TEXT,
    license_plate TEXT NOT NULL UNIQUE,
    state TEXT,
    registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Parking Lots
CREATE TABLE IF NOT EXISTS parking_lots (
    lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_name TEXT NOT NULL,
    location TEXT,
    capacity INTEGER NOT NULL,
    lot_type TEXT DEFAULT 'general',  -- general, reserved, visitor, faculty
    hourly_rate REAL,
    daily_rate REAL,
    is_covered BOOLEAN DEFAULT 0,
    has_ev_charging BOOLEAN DEFAULT 0
);

-- Parking Spaces
CREATE TABLE IF NOT EXISTS parking_spaces (
    space_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id INTEGER NOT NULL,
    space_number TEXT NOT NULL,
    type TEXT DEFAULT 'standard',  -- standard, accessible, ev_charging, compact
    reserved_for INTEGER,  -- user_id
    status TEXT DEFAULT 'available',
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id),
    UNIQUE(lot_id, space_number)
);

-- Parking Violations
CREATE TABLE IF NOT EXISTS parking_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    permit_id INTEGER,
    license_plate TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    violation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    location TEXT,
    fine_amount REAL NOT NULL,
    status TEXT DEFAULT 'unpaid',  -- unpaid, paid, appealed, waived
    officer_id INTEGER,
    notes TEXT
);

-- Violation Appeals
CREATE TABLE IF NOT EXISTS violation_appeals (
    appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    supporting_documents TEXT,  -- JSON array
    status TEXT DEFAULT 'pending',
    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER,
    review_date TIMESTAMP,
    decision TEXT,
    FOREIGN KEY (violation_id) REFERENCES parking_violations(violation_id)
);

-- Shuttle Routes
CREATE TABLE IF NOT EXISTS shuttle_routes (
    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_name TEXT NOT NULL,
    description TEXT,
    schedule TEXT,  -- JSON
    stops TEXT,  -- JSON array
    is_active BOOLEAN DEFAULT 1
);

-- Shuttle Buses
CREATE TABLE IF NOT EXISTS shuttle_buses (
    bus_id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    bus_number TEXT UNIQUE,
    capacity INTEGER DEFAULT 40,
    current_location TEXT,  -- lat,lon
    current_stop_id INTEGER,
    in_service BOOLEAN DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (route_id) REFERENCES shuttle_routes(route_id)
);

-- Shuttle Stops
CREATE TABLE IF NOT EXISTS shuttle_stops (
    stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stop_name TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    arrival_time TIME,
    amenities TEXT  -- JSON
);

-- Rideshare Posts
CREATE TABLE IF NOT EXISTS rideshare_posts (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    post_type TEXT DEFAULT 'offer',  -- offer, request
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_time TIMESTAMP NOT NULL,
    seats_available INTEGER,
    cost_per_seat REAL,
    notes TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Visitor Parking
CREATE TABLE IF NOT EXISTS visitor_parking (
    visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    vehicle_license TEXT NOT NULL,
    visit_date DATE NOT NULL,
    host_id INTEGER,
    lot_id INTEGER,
    check_in_time TIMESTAMP,
    check_out_time TIMESTAMP,
    FOREIGN KEY (host_id) REFERENCES users(user_id),
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
);

-- Parking Occupancy
CREATE TABLE IF NOT EXISTS parking_occupancy (
    occupancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    available_spaces INTEGER NOT NULL,
    total_spaces INTEGER NOT NULL,
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
);
"""

# Feature 8: Blockchain Credentials & Digital Badges
BLOCKCHAIN_SCHEMA = """
-- Blockchain Credentials
CREATE TABLE IF NOT EXISTS blockchain_credentials (
    credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    credential_type TEXT NOT NULL,  -- degree, certificate, diploma, transcript
    credential_name TEXT NOT NULL,
    issue_date DATE NOT NULL,
    blockchain_hash TEXT UNIQUE NOT NULL,
    blockchain_address TEXT,
    ipfs_hash TEXT,  -- For document storage
    metadata TEXT,  -- JSON
    is_revoked BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Digital Badges
CREATE TABLE IF NOT EXISTS digital_badges (
    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_name TEXT NOT NULL,
    description TEXT,
    criteria TEXT NOT NULL,
    badge_image_url TEXT,
    issuer_name TEXT NOT NULL,
    badge_type TEXT DEFAULT 'skill',  -- skill, achievement, completion
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Badge Issuances
CREATE TABLE IF NOT EXISTS badge_issuances (
    issuance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    blockchain_hash TEXT,
    evidence_url TEXT,
    expires_at DATE,
    is_revoked BOOLEAN DEFAULT 0,
    FOREIGN KEY (badge_id) REFERENCES digital_badges(badge_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Credential Verifications
CREATE TABLE IF NOT EXISTS credential_verifications (
    verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER,
    badge_issuance_id INTEGER,
    verifier_name TEXT,
    verifier_email TEXT,
    verified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_method TEXT,  -- blockchain, api, manual
    FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
    FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
);

-- Blockchain Wallets
CREATE TABLE IF NOT EXISTS blockchain_wallets (
    wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    wallet_address TEXT UNIQUE NOT NULL,
    blockchain_type TEXT DEFAULT 'ethereum',  -- ethereum, hyperledger, etc.
    public_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Credential Templates
CREATE TABLE IF NOT EXISTS credential_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    template_design TEXT,  -- JSON or HTML
    fields TEXT,  -- JSON array
    is_active BOOLEAN DEFAULT 1
);

-- Verification Requests
CREATE TABLE IF NOT EXISTS verification_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER,
    badge_issuance_id INTEGER,
    requester_name TEXT NOT NULL,
    requester_email TEXT,
    requester_organization TEXT,
    status TEXT DEFAULT 'pending',
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_date TIMESTAMP,
    FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
    FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
);

-- Revoked Credentials
CREATE TABLE IF NOT EXISTS revoked_credentials (
    revocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER,
    badge_issuance_id INTEGER,
    revoked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL,
    revoked_by INTEGER,
    blockchain_revocation_hash TEXT,
    FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
    FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
);

-- Micro Credentials
CREATE TABLE IF NOT EXISTS micro_credentials (
    micro_id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    description TEXT,
    criteria TEXT NOT NULL,
    points INTEGER DEFAULT 1,
    category TEXT,  -- technical, soft_skills, academic
    is_stackable BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def create_all_remaining_tables():
    """Create all remaining feature tables"""
    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        print("Creating Mobile App tables...")
        cursor.executescript(MOBILE_APP_SCHEMA)

        print("Creating Accessibility tables...")
        cursor.executescript(ACCESSIBILITY_SCHEMA)

        print("Creating Parent Portal tables...")
        cursor.executescript(PARENT_PORTAL_SCHEMA)

        print("Creating Transportation & Parking tables...")
        cursor.executescript(TRANSPORTATION_SCHEMA)

        print("Creating Blockchain Credentials tables...")
        cursor.executescript(BLOCKCHAIN_SCHEMA)

        conn.commit()
        conn.close()

        print("\nAll remaining feature tables created successfully!")
        print("- Mobile App (PWA) Infrastructure")
        print("- Accessibility & Accommodation Tools")
        print("- Parent Portal Enhancement")
        print("- Transportation & Parking Management")
        print("- Blockchain Credentials & Digital Badges")

        return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False

if __name__ == "__main__":
    create_all_remaining_tables()
