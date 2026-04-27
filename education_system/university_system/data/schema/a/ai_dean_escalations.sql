CREATE TABLE IF NOT EXISTS ai_dean_escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER,
                    student_name TEXT,
                    assignment_name TEXT,
                    escalated_by TEXT,
                    escalation_notes TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
