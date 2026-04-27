CREATE TABLE IF NOT EXISTS restaurant_food_safety_checks (
            check_id TEXT PRIMARY KEY,
            check_type TEXT NOT NULL,
            check_date TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            results TEXT NOT NULL,
            notes TEXT,
            corrective_actions TEXT,
            follow_up_date TEXT,
            status TEXT DEFAULT 'Completed'
        );
