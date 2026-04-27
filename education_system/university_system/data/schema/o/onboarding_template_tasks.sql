CREATE TABLE IF NOT EXISTS onboarding_template_tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    assigned_to_role TEXT DEFAULT 'employee',
                    due_days INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT 1,
                    order_num INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                );
