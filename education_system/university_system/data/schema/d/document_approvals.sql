CREATE TABLE IF NOT EXISTS document_approvals (
                approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_type TEXT NOT NULL,
                document_title TEXT,
                document_description TEXT,
                document_path TEXT,
                submitted_by TEXT NOT NULL,
                submitted_by_name TEXT,
                submitted_date TEXT DEFAULT CURRENT_TIMESTAMP,
                current_approver TEXT,
                approval_chain TEXT,
                current_step INTEGER DEFAULT 1,
                total_steps INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                comments TEXT,
                completed_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
