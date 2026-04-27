CREATE TABLE IF NOT EXISTS club_expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            requester_id TEXT,
            expense_type TEXT,
            amount REAL,
            description TEXT,
            receipt_path TEXT,
            request_date TEXT,
            approval_date TEXT,
            approver_id TEXT,
            status TEXT DEFAULT 'pending',
            budget_category TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (requester_id) REFERENCES students (student_id),
            FOREIGN KEY (approver_id) REFERENCES students (student_id)
        );
