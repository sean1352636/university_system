CREATE TABLE IF NOT EXISTS extension_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            new_due_date TIMESTAMP NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            reviewed_date TIMESTAMP,
            review_comments TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (reviewed_by) REFERENCES users (id)
        );
