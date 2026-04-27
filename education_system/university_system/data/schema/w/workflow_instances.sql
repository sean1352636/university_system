CREATE TABLE IF NOT EXISTS workflow_instances (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            entity_type TEXT NOT NULL, -- 'refund', 'payment_plan', 'scholarship', etc.
            entity_id INTEGER NOT NULL,
            current_step INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending', -- pending, in_progress, completed, cancelled
            assigned_to TEXT,
            started_at TEXT,
            completed_at TEXT,
            metadata TEXT, -- JSON with instance-specific data
            FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id)
        );
