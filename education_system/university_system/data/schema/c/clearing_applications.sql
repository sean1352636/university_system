CREATE TABLE IF NOT EXISTS clearing_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    ucas_id TEXT,
                    tariff_points INTEGER DEFAULT 0,
                    qualifications TEXT,
                    preferred_course TEXT,
                    status TEXT DEFAULT 'pending',
                    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    processed_at TEXT,
                    notes TEXT
                );
