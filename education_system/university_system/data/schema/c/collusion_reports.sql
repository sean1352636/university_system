CREATE TABLE IF NOT EXISTS collusion_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        student_id_1 TEXT NOT NULL,
                        student_id_2 TEXT NOT NULL,
                        similarity_score REAL NOT NULL,
                        analysis_json TEXT,
                        flagged INTEGER DEFAULT 0,
                        reviewed INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL
                    );
