CREATE TABLE IF NOT EXISTS archived_financial_aid (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    aid_type TEXT,
                    amount REAL,
                    academic_year TEXT,
                    status TEXT,
                    awarded_date TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                );
