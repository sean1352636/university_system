CREATE TABLE IF NOT EXISTS schedule_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER,
                action TEXT,
                old_values TEXT,
                new_values TEXT,
                changed_by TEXT,
                change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
