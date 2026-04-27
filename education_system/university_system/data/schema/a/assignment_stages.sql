CREATE TABLE IF NOT EXISTS assignment_stages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        stage_number INTEGER NOT NULL,
                        stage_name TEXT NOT NULL,
                        description TEXT,
                        weight_percent REAL NOT NULL DEFAULT 0,
                        deadline TEXT NOT NULL,
                        feedback_required INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
