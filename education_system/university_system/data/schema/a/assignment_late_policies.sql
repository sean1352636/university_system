CREATE TABLE IF NOT EXISTS assignment_late_policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        policy_id INTEGER NOT NULL,
                        applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (policy_id) REFERENCES late_policies(id)
                    );
