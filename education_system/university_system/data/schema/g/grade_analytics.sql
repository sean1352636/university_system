CREATE TABLE IF NOT EXISTS grade_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                module_code TEXT,
                assessment_date TEXT,
                grade_value DECIMAL(5,2),
                class_average DECIMAL(5,2),
                percentile_rank INTEGER,
                trend_direction TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (module_code) REFERENCES modules (module_code)
            );
