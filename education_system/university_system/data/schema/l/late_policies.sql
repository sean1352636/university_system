CREATE TABLE IF NOT EXISTS late_policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        penalty_type TEXT NOT NULL DEFAULT 'percentage'
                            CHECK(penalty_type IN ('percentage', 'fixed', 'none')),
                        penalty_per_day REAL NOT NULL DEFAULT 10.0,
                        max_late_days INTEGER NOT NULL DEFAULT 5,
                        grace_period_hours INTEGER NOT NULL DEFAULT 0,
                        min_grade_floor REAL NOT NULL DEFAULT 0.0,
                        is_default INTEGER NOT NULL DEFAULT 0,
                        created_by TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
