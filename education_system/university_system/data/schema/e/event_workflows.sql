CREATE TABLE IF NOT EXISTS event_workflows (
                    id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    description TEXT,
                    template_data TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                );
