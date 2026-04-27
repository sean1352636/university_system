CREATE TABLE IF NOT EXISTS workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            workflow_type TEXT NOT NULL, -- 'approval', 'notification', 'automation'
            trigger_conditions TEXT, -- JSON
            workflow_steps TEXT, -- JSON with step definitions
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );
