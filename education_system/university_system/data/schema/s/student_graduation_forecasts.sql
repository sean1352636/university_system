CREATE TABLE IF NOT EXISTS student_graduation_forecasts (
                    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    program_code TEXT NOT NULL,
                    estimated_graduation_date TEXT,
                    estimated_semester TEXT,
                    remaining_credits INTEGER DEFAULT 0,
                    required_semesters INTEGER DEFAULT 0,
                    on_track BOOLEAN DEFAULT 1,
                    delay_reasons_json TEXT,
                    acceleration_options_json TEXT,
                    confidence_level REAL DEFAULT 0.0,
                    last_calculated TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id)
                );
