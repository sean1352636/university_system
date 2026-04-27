CREATE TABLE IF NOT EXISTS safety_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                warning_signs TEXT,
                coping_strategies TEXT,
                distractions TEXT,
                support_people TEXT,
                professionals TEXT,
                safe_environment TEXT,
                emergency_contacts TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
