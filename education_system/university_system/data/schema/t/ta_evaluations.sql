CREATE TABLE IF NOT EXISTS ta_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ta_id TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        evaluation_period TEXT,
                        hours_logged REAL DEFAULT 0,
                        avg_grading_turnaround_days REAL DEFAULT 0,
                        submissions_graded INTEGER DEFAULT 0,
                        feedback_score REAL,
                        evaluator_id TEXT,
                        evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
