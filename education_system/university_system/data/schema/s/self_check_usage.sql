CREATE TABLE IF NOT EXISTS self_check_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_hash TEXT NOT NULL,
                score_range TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
