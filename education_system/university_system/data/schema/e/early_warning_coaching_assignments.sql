CREATE TABLE IF NOT EXISTS early_warning_coaching_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            coach_id INTEGER NOT NULL,
            assigned_date TEXT DEFAULT CURRENT_DATE,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            meeting_frequency TEXT DEFAULT 'weekly',
            last_meeting_date TEXT,
            next_meeting_date TEXT,
            progress_notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (coach_id) REFERENCES early_warning_coaches (coach_id)
        );
