CREATE TABLE IF NOT EXISTS exit_checklist (
                    checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER,
                    task_name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    responsible_party TEXT,
                    due_date TEXT,
                    completed BOOLEAN DEFAULT 0,
                    completed_date TEXT,
                    completed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES exit_checklist_templates(template_id)
                );
