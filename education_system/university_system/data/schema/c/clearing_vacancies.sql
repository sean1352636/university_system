CREATE TABLE IF NOT EXISTS clearing_vacancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    department TEXT,
                    available_places INTEGER DEFAULT 0,
                    minimum_tariff INTEGER DEFAULT 0,
                    requirements TEXT,
                    is_active INTEGER DEFAULT 1,
                    academic_year TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
