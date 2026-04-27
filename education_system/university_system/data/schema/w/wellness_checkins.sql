CREATE TABLE IF NOT EXISTS wellness_checkins (
                    checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    checkin_date TEXT NOT NULL,
                    overall_mood INTEGER CHECK(overall_mood BETWEEN 1 AND 10),
                    stress_level INTEGER CHECK(stress_level BETWEEN 1 AND 10),
                    sleep_quality INTEGER CHECK(sleep_quality BETWEEN 1 AND 10),
                    energy_level INTEGER CHECK(energy_level BETWEEN 1 AND 10),
                    anxiety_level INTEGER CHECK(anxiety_level BETWEEN 1 AND 10),
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
