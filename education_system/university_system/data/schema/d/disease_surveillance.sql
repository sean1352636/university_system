CREATE TABLE IF NOT EXISTS disease_surveillance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disease_name TEXT,
                    case_date TEXT,
                    student_id TEXT,
                    symptoms TEXT,
                    severity TEXT,
                    status TEXT DEFAULT 'under_investigation',
                    contact_tracing_needed INTEGER DEFAULT 0,
                    contact_tracing_completed INTEGER DEFAULT 0,
                    contacts_identified INTEGER DEFAULT 0,
                    reported_to_health_dept INTEGER DEFAULT 0,
                    isolation_required INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
