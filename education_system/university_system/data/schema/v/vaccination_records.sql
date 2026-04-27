CREATE TABLE IF NOT EXISTS vaccination_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    vaccine_name TEXT,
                    administered_date TEXT,
                    expiry_date TEXT,
                    lot_number TEXT,
                    manufacturer TEXT,
                    administered_by TEXT,
                    location TEXT,
                    adverse_reaction INTEGER DEFAULT 0,
                    reaction_description TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_date TEXT,
                    created_at TEXT, "last_vaccination_date" TEXT, "next_due_date" TEXT, "vaccine_type" TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
