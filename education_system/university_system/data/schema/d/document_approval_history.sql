CREATE TABLE IF NOT EXISTS document_approval_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                approval_id INTEGER NOT NULL,
                approver_id TEXT NOT NULL,
                approver_name TEXT,
                action TEXT,
                step_number INTEGER,
                comments TEXT,
                action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (approval_id) REFERENCES document_approvals(approval_id)
            );
