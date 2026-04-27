CREATE TABLE IF NOT EXISTS student_behavior (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                incident_date TEXT,
                behavior_type TEXT,
                severity TEXT,
                description TEXT,
                action_taken TEXT,
                reported_by TEXT,
                follow_up_required BOOLEAN DEFAULT 0,
                resolved BOOLEAN DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
