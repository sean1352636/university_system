CREATE TABLE IF NOT EXISTS onboarding_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    assigned_by TEXT,
                    start_date TEXT NOT NULL,
                    target_completion_date TEXT,
                    actual_completion_date TEXT,
                    status TEXT DEFAULT 'in_progress',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                );
