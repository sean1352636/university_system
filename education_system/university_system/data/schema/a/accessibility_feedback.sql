CREATE TABLE IF NOT EXISTS accessibility_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        issue_type TEXT,
                        description TEXT,
                        contact_email TEXT,
                        submitted_date TEXT,
                        status TEXT DEFAULT 'pending'
                    );
