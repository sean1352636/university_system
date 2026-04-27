CREATE TABLE IF NOT EXISTS insurance_information (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            insurance_provider TEXT,
            policy_number TEXT,
            group_number TEXT,
            subscriber_name TEXT,
            relationship_to_subscriber TEXT,
            effective_date TEXT,
            expiry_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
