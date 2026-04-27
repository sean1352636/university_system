CREATE TABLE IF NOT EXISTS evaluation_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                average_score REAL,
                response_count INTEGER,
                calculated_at TEXT NOT NULL DEFAULT (datetime('now')), "median_score" REAL, "mode_score" REAL, "percentile_25" REAL, "percentile_75" REAL, "standard_deviation" REAL,
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE,
                UNIQUE(evaluation_id, question_id)
            );
