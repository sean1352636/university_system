"""Staff HR schemas — Facilities (access, assets, lab/equipment booking).

Auto-grouped from the former staff_hr_schemas_all.py by domain, not by the
historical _init_staff_hr_vN_schemas sprint numbering.

Idempotent. Safe to call repeatedly: every statement is CREATE TABLE
IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / INSERT OR IGNORE.
"""
from __future__ import annotations

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.university_system.core.sql_safety import (
    safe_alter_table_add_column,
)


def _init_facilities_schemas() -> None:
    """Create every facilities-domain Staff HR table."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---- interdepartmental_requests ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interdepartmental_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_type TEXT NOT NULL,
                    from_department TEXT,
                    to_department TEXT,
                    requested_by TEXT NOT NULL,
                    requested_by_name TEXT,
                    request_title TEXT NOT NULL,
                    request_description TEXT,
                    priority TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    assigned_to_name TEXT,
                    due_date TEXT,
                    completed_date TEXT,
                    response TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- access_cards ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_cards (
                    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_number TEXT UNIQUE NOT NULL,
                    user_id TEXT,
                    user_name TEXT,
                    card_type TEXT DEFAULT 'staff',
                    access_level TEXT,
                    buildings_access TEXT,
                    issue_date TEXT,
                    expiry_date TEXT,
                    status TEXT DEFAULT 'active',
                    issued_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- key_assignments ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS key_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_number TEXT NOT NULL,
                    key_type TEXT,
                    room_location TEXT,
                    building TEXT,
                    assigned_to TEXT,
                    assigned_to_name TEXT,
                    assigned_date TEXT,
                    return_date TEXT,
                    status TEXT DEFAULT 'assigned',
                    issued_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- visitor_registrations ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS visitor_registrations (
                    visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visitor_name TEXT NOT NULL,
                    visitor_email TEXT,
                    visitor_phone TEXT,
                    visitor_company TEXT,
                    host_id TEXT NOT NULL,
                    host_name TEXT,
                    host_department TEXT,
                    visit_purpose TEXT,
                    scheduled_date TEXT,
                    scheduled_time TEXT,
                    check_in_time TEXT,
                    check_out_time TEXT,
                    badge_number TEXT,
                    vehicle_registration TEXT,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_visitor_reg_date ON visitor_registrations(scheduled_date)')

            # ---- asset_categories ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    depreciation_years INTEGER DEFAULT 5,
                    requires_approval INTEGER DEFAULT 0,
                    parent_category_id INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_category_id) REFERENCES asset_categories(category_id)
                )
            ''')

            # ---- assets ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_tag TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    category_id INTEGER NOT NULL,
                    serial_number TEXT,
                    manufacturer TEXT,
                    model TEXT,
                    purchase_date TEXT,
                    purchase_price REAL,
                    supplier TEXT,
                    warranty_start TEXT,
                    warranty_expiry TEXT,
                    warranty_provider TEXT,
                    current_value REAL,
                    location TEXT,
                    building TEXT,
                    room TEXT,
                    department TEXT,
                    status TEXT DEFAULT 'available',
                    condition TEXT DEFAULT 'good',
                    last_inspection_date TEXT,
                    next_inspection_date TEXT,
                    disposal_date TEXT,
                    disposal_method TEXT,
                    disposal_value REAL,
                    insurance_policy TEXT,
                    insurance_value REAL,
                    barcode TEXT,
                    qr_code TEXT,
                    image_path TEXT,
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES asset_categories(category_id)
                )
            ''')

            # ---- asset_assignments ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    user_department TEXT,
                    assigned_by TEXT NOT NULL,
                    assigned_by_name TEXT,
                    assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    expected_return_date TEXT,
                    actual_return_date TEXT,
                    return_condition TEXT,
                    return_notes TEXT,
                    return_processed_by TEXT,
                    status TEXT DEFAULT 'active',
                    purpose TEXT,
                    location TEXT,
                    acknowledgement_date TEXT,
                    acknowledgement_signature TEXT,
                    checkout_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
                )
            ''')

            # ---- asset_issues ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_issues (
                    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    reported_by TEXT NOT NULL,
                    reported_by_name TEXT,
                    reported_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    issue_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    priority TEXT DEFAULT 'normal',
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    impact TEXT,
                    steps_to_reproduce TEXT,
                    resolution TEXT,
                    resolution_notes TEXT,
                    resolved_by TEXT,
                    resolved_by_name TEXT,
                    resolved_date TEXT,
                    resolution_cost REAL,
                    status TEXT DEFAULT 'open',
                    assigned_to TEXT,
                    assigned_to_name TEXT,
                    estimated_resolution_date TEXT,
                    attachments TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
                )
            ''')

            # ---- asset_maintenance ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    maintenance_category TEXT DEFAULT 'routine',
                    title TEXT,
                    description TEXT,
                    scheduled_date TEXT,
                    scheduled_time TEXT,
                    completed_date TEXT,
                    performed_by TEXT,
                    performed_by_name TEXT,
                    vendor TEXT,
                    vendor_contact TEXT,
                    cost REAL DEFAULT 0,
                    labor_cost REAL DEFAULT 0,
                    parts_cost REAL DEFAULT 0,
                    parts_replaced TEXT,
                    work_performed TEXT,
                    findings TEXT,
                    recommendations TEXT,
                    next_maintenance_date TEXT,
                    next_maintenance_type TEXT,
                    status TEXT DEFAULT 'scheduled',
                    priority TEXT DEFAULT 'normal',
                    downtime_hours REAL DEFAULT 0,
                    attachments TEXT,
                    approval_required INTEGER DEFAULT 0,
                    approved_by TEXT,
                    approved_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
                )
            ''')

            # ---- asset_audit_log ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    action_category TEXT,
                    action_by TEXT NOT NULL,
                    action_by_name TEXT,
                    action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    old_values TEXT,
                    new_values TEXT,
                    field_changed TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    notes TEXT,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
                )
            ''')

            # ---- asset_requests ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requested_by TEXT NOT NULL,
                    requested_by_name TEXT,
                    department TEXT,
                    category_id INTEGER,
                    request_type TEXT DEFAULT 'new',
                    item_name TEXT NOT NULL,
                    item_description TEXT,
                    quantity INTEGER DEFAULT 1,
                    preferred_vendor TEXT,
                    estimated_cost REAL,
                    budget_code TEXT,
                    justification TEXT,
                    business_case TEXT,
                    urgency TEXT DEFAULT 'normal',
                    needed_by_date TEXT,
                    status TEXT DEFAULT 'pending',
                    reviewed_by TEXT,
                    reviewed_by_name TEXT,
                    review_date TEXT,
                    review_comments TEXT,
                    approved_by TEXT,
                    approved_by_name TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    approved_amount REAL,
                    fulfilled_date TEXT,
                    fulfilled_asset_ids TEXT,
                    attachments TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES asset_categories(category_id)
                )
            ''')

            # ---- asset_transfers ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_transfers (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    from_location TEXT,
                    from_department TEXT,
                    from_user_id TEXT,
                    to_location TEXT,
                    to_department TEXT,
                    to_user_id TEXT,
                    transfer_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    transfer_reason TEXT,
                    transferred_by TEXT NOT NULL,
                    transferred_by_name TEXT,
                    received_by TEXT,
                    received_date TEXT,
                    condition_at_transfer TEXT,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
                )
            ''')

            # ---- asset_depreciation ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_depreciation (
                    depreciation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    fiscal_year TEXT NOT NULL,
                    period TEXT,
                    depreciation_method TEXT DEFAULT 'straight-line',
                    beginning_value REAL,
                    depreciation_amount REAL,
                    accumulated_depreciation REAL,
                    ending_value REAL,
                    calculated_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
                    UNIQUE(asset_id, fiscal_year, period)
                )
            ''')

            # ---- assets ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_tag ON assets(asset_tag)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_department ON assets(department)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_serial ON assets(serial_number)')

            # ---- asset_assignments ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_asset ON asset_assignments(asset_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_user ON asset_assignments(user_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_status ON asset_assignments(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_assignments_date ON asset_assignments(assigned_date)')

            # ---- asset_issues ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_asset ON asset_issues(asset_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_status ON asset_issues(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_severity ON asset_issues(severity)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_issues_reported ON asset_issues(reported_by)')

            # ---- asset_maintenance ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_maintenance_asset ON asset_maintenance(asset_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_maintenance_status ON asset_maintenance(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_maintenance_scheduled ON asset_maintenance(scheduled_date)')

            # ---- asset_audit_log ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_audit_asset ON asset_audit_log(asset_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_audit_action ON asset_audit_log(action)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_audit_date ON asset_audit_log(action_date)')

            # ---- asset_requests ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_requests_status ON asset_requests(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_requests_user ON asset_requests(requested_by)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_requests_dept ON asset_requests(department)')

            # ---- asset_transfers ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_transfers_asset ON asset_transfers(asset_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_transfers_status ON asset_transfers(status)')

            # ---- asset_depreciation ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_depreciation_asset ON asset_depreciation(asset_id)')

            default_categories = [
                ('Computers', 'Desktop and laptop computers', 5, 0),
                ('Monitors', 'Computer monitors and displays', 5, 0),
                ('Printers', 'Printers, scanners, and multifunction devices', 5, 0),
                ('Phones', 'Desk phones and mobile devices', 3, 0),
                ('Tablets', 'Tablets and mobile computing devices', 3, 0),
                ('Networking', 'Routers, switches, and network equipment', 7, 1),
                ('Servers', 'Servers and data center equipment', 7, 1),
                ('Storage', 'External storage and backup devices', 5, 0),
                ('Office Furniture', 'Desks, chairs, cabinets, and shelving', 10, 1),
                ('Lab Equipment', 'Laboratory and research equipment', 7, 1),
                ('Audio/Visual', 'Projectors, cameras, speakers, and AV equipment', 5, 1),
                ('Vehicles', 'University vehicles and transportation', 7, 1),
                ('Software Licenses', 'Software and subscription licenses', 1, 0),
                ('Medical Equipment', 'Medical and healthcare equipment', 7, 1),
                ('Sports Equipment', 'Sports and fitness equipment', 5, 0),
                ('Security Equipment', 'Security cameras, access systems', 7, 1),
                ('HVAC', 'Heating, ventilation, and air conditioning', 10, 1),
                ('Cleaning Equipment', 'Cleaning and maintenance equipment', 5, 0),
                ('Kitchen Equipment', 'Kitchen and catering equipment', 7, 0),
                ('Other', 'Other equipment and assets', 5, 0),
            ]

            for cat in default_categories:
                cursor.execute('''
                    INSERT OR IGNORE INTO asset_categories
                    (name, description, depreciation_years, requires_approval)
                    VALUES (?, ?, ?, ?)
                ''', cat)

            cursor = conn.cursor()

            migration_columns = [
                ('expense_claims', 'status', "TEXT DEFAULT 'draft'"),
                ('grievances', 'status', "TEXT DEFAULT 'submitted'"),
                ('disciplinary_records', 'status', "TEXT DEFAULT 'under_review'"),
                ('staff_contracts', 'status', "TEXT DEFAULT 'active'"),
                ('exit_interviews', 'status', "TEXT DEFAULT 'scheduled'"),
            ]

            for table, column, column_def in migration_columns:
                try:
                    safe_alter_table_add_column(table, column, column_def, conn)
                except Exception:
                    pass  # Table doesn't exist yet, will be created below

            # ---- equipment_categories ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equipment_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    parent_category_id INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_category_id) REFERENCES equipment_categories(category_id)
                )
            ''')

            # ---- lab_equipment ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lab_equipment (
                    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category_id INTEGER,
                    location TEXT,
                    building TEXT,
                    room_number TEXT,
                    serial_number TEXT,
                    model TEXT,
                    manufacturer TEXT,
                    status TEXT DEFAULT 'available',
                    max_booking_hours INTEGER DEFAULT 8,
                    min_booking_hours INTEGER DEFAULT 1,
                    requires_approval INTEGER DEFAULT 0,
                    requires_training INTEGER DEFAULT 0,
                    description TEXT,
                    image_url TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES equipment_categories(category_id)
                )
            ''')

            # ---- equipment_bookings ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equipment_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    booking_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    purpose TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    checked_in_at TEXT,
                    checked_out_at TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id)
                )
            ''')

            # ---- equipment_maintenance ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equipment_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER NOT NULL,
                    maintenance_type TEXT DEFAULT 'routine',
                    description TEXT,
                    scheduled_date TEXT,
                    completed_date TEXT,
                    performed_by TEXT,
                    cost REAL DEFAULT 0,
                    status TEXT DEFAULT 'scheduled',
                    next_due_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id)
                )
            ''')

            # ---- booking_rules ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS booking_rules (
                    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER,
                    category_id INTEGER,
                    rule_type TEXT NOT NULL,
                    rule_value TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (equipment_id) REFERENCES lab_equipment(equipment_id),
                    FOREIGN KEY (category_id) REFERENCES equipment_categories(category_id)
                )
            ''')

            conn.commit()
    except sqlite3.Error as exc:
        print(f"Error initialising Staff HR facilities schemas: {exc}")
        raise


def get_asset_statuses():
    """Get list of asset statuses."""
    return [
        'available', 'assigned', 'in_use', 'in_repair', 'in_maintenance',
        'reserved', 'lost', 'stolen', 'disposed', 'retired', 'pending_disposal'
    ]


def get_asset_conditions():
    """Get list of asset conditions."""
    return ['excellent', 'good', 'fair', 'poor', 'non_functional']


def get_issue_types():
    """Get list of issue types."""
    return [
        'hardware_failure', 'software_issue', 'physical_damage', 'malfunction',
        'performance_issue', 'connectivity_issue', 'missing_parts', 'wear_and_tear',
        'user_error', 'other'
    ]


def get_issue_severities():
    """Get list of issue severities."""
    return ['critical', 'high', 'medium', 'low']


def get_maintenance_types():
    """Get list of maintenance types."""
    return [
        'preventive', 'corrective', 'inspection', 'calibration', 'cleaning',
        'software_update', 'hardware_upgrade', 'replacement', 'routine', 'emergency'
    ]


def get_maintenance_categories():
    """Get list of maintenance categories."""
    return ['routine', 'scheduled', 'emergency', 'repair', 'upgrade']


def get_request_types():
    """Get list of asset request types."""
    return ['new', 'replacement', 'upgrade', 'temporary', 'project']


def get_request_urgencies():
    """Get list of request urgency levels."""
    return ['critical', 'high', 'normal', 'low']


def get_depreciation_methods():
    """Get list of depreciation methods."""
    return ['straight-line', 'declining-balance', 'units-of-production', 'sum-of-years']


def generate_asset_tag(category_id: int) -> str:
    """Generate a unique asset tag."""
    import datetime
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get category prefix
        category = cursor.execute(
            'SELECT name FROM asset_categories WHERE category_id = ?',
            (category_id,)
        ).fetchone()

        prefix = 'AST'
        if category:
            # Create prefix from first 3 letters of category name
            prefix = category[0][:3].upper()

        # Get current year
        year = datetime.datetime.now().strftime('%y')

        # Get next sequence number for this prefix and year
        result = cursor.execute('''
            SELECT COUNT(*) FROM assets
            WHERE asset_tag LIKE ?
        ''', (f'{prefix}{year}%',)).fetchone()

        seq = (result[0] if result else 0) + 1

        return f'{prefix}{year}{seq:05d}'
