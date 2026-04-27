CREATE TABLE IF NOT EXISTS examiner_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visit_id INTEGER NOT NULL,
                    action_description TEXT NOT NULL,
                    responsible_person TEXT,
                    deadline TEXT,
                    status TEXT DEFAULT 'pending',
                    completed_at TEXT,
                    notes TEXT,
                    FOREIGN KEY (visit_id) REFERENCES examiner_visits(id)
                );
