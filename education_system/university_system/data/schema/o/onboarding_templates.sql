CREATE TABLE IF NOT EXISTS onboarding_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    role TEXT,
                    department TEXT,
                    template_type TEXT DEFAULT 'onboarding',
                    estimated_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
