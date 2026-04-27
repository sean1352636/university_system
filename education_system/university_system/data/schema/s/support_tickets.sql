CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            last_updated_datetime TEXT,
            assigned_to TEXT,
            escalated_at TEXT,
            resolved_at TEXT,
            closed_at TEXT,
            estimated_resolution TEXT,
            sentiment TEXT DEFAULT 'neutral',
            satisfaction_rating INTEGER,
            tags TEXT,  -- JSON array of tags
            parent_ticket_id INTEGER, due_date TEXT, user_id INTEGER, subject TEXT DEFAULT 'No Subject', created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, message TEXT, satisfaction_feedback TEXT, impact TEXT DEFAULT 'low', urgency TEXT DEFAULT 'low', source TEXT DEFAULT 'web', resolution TEXT, first_response_at TEXT, escalation_level INTEGER DEFAULT 0, department TEXT, last_activity_at TEXT,  -- For merged tickets
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
        );
