CREATE TABLE IF NOT EXISTS degree_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    advisor_id TEXT,
                    plan_name TEXT NOT NULL,
                    target_graduation TEXT,
                    total_credits_required INTEGER DEFAULT 120,
                    credits_completed INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_date TEXT DEFAULT (date('now')),
                    last_updated TEXT DEFAULT (date('now')),
                    status TEXT DEFAULT 'active'
                );
