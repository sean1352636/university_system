CREATE TABLE IF NOT EXISTS early_warning_progress_monitoring (
            monitoring_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            coach_id INTEGER NOT NULL,
            monitoring_date TEXT DEFAULT CURRENT_DATE,
            academic_progress TEXT,
            attendance_progress TEXT,
            engagement_progress TEXT,
            goals_achieved TEXT,
            concerns TEXT,
            next_steps TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (coach_id) REFERENCES early_warning_coaches (coach_id)
        );
