CREATE TABLE IF NOT EXISTS exit_checklist_template_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    description TEXT,
                    responsible_party TEXT,
                    category TEXT,
                    days_before_exit INTEGER DEFAULT 0,
                    is_mandatory BOOLEAN DEFAULT 1,
                    order_index INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES exit_checklist_templates(template_id)
                );
