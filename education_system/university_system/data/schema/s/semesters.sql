CREATE TABLE IF NOT EXISTS semesters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    registration_start TEXT,
                    registration_end TEXT,
                    final_exams_start TEXT,
                    final_exams_end TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                    UNIQUE(academic_year_id, name),
                    CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                );
