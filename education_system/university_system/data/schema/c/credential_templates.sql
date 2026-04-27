CREATE TABLE IF NOT EXISTS credential_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    template_design TEXT,  -- JSON or HTML
    fields TEXT,  -- JSON array
    is_active BOOLEAN DEFAULT 1
);
