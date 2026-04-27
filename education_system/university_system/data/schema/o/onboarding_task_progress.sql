CREATE TABLE IF NOT EXISTS onboarding_task_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    due_date TEXT,
                    completed_by TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES onboarding_assignments(assignment_id),
                    FOREIGN KEY (task_id) REFERENCES onboarding_template_tasks(task_id),
                    UNIQUE(assignment_id, task_id)
                );
