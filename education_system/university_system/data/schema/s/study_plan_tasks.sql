CREATE TABLE IF NOT EXISTS study_plan_tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    task_title TEXT NOT NULL,
                    task_description TEXT,
                    scheduled_date TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    priority TEXT DEFAULT 'Medium',
                    completed BOOLEAN DEFAULT 0,
                    completed_at TEXT,
                    FOREIGN KEY (plan_id) REFERENCES study_plans(plan_id) ON DELETE CASCADE
                );
