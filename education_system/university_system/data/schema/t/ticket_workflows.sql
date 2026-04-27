CREATE TABLE IF NOT EXISTS ticket_workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            trigger_type TEXT NOT NULL,
            trigger_conditions TEXT,
            actions TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users (id)
        );
