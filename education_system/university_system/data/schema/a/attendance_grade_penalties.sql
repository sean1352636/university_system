CREATE TABLE IF NOT EXISTS attendance_grade_penalties (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   TEXT NOT NULL,
            module_code  TEXT NOT NULL,
            threshold    REAL,
            pct          REAL,
            applied_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            applied_by   TEXT,
            grade_row_id INTEGER,
            UNIQUE(student_id, module_code)
        );
