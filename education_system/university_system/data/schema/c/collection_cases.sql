CREATE TABLE IF NOT EXISTS collection_cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            agency_id INTEGER,
            total_debt DECIMAL(10,2) NOT NULL,
            case_status TEXT DEFAULT 'new', -- new, assigned, in_progress, resolved, closed
            assigned_date TEXT,
            resolution_date TEXT,
            amount_collected DECIMAL(10,2) DEFAULT 0,
            commission_paid DECIMAL(10,2) DEFAULT 0,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (agency_id) REFERENCES collection_agencies (agency_id)
        );
