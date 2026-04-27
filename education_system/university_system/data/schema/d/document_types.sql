CREATE TABLE IF NOT EXISTS document_types (
        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_required BOOLEAN DEFAULT 0,
        max_file_size INTEGER DEFAULT 10485760,
        allowed_extensions TEXT DEFAULT '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        retention_days INTEGER DEFAULT 2555,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    , has_expiry BOOLEAN DEFAULT 0, expiry_reminder_days INTEGER, max_file_size_mb INTEGER DEFAULT 10, allowed_formats TEXT DEFAULT ".pdf,.jpg,.jpeg,.png,.doc,.docx", requires_approval BOOLEAN DEFAULT 1, category TEXT, sort_order INTEGER DEFAULT 0, is_active BOOLEAN DEFAULT 1);
