CREATE TABLE IF NOT EXISTS integrity_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    assignment_id INTEGER,
                    case_type TEXT NOT NULL CHECK(case_type IN ('plagiarism','cheating','collusion','other')),
                    description TEXT,
                    evidence_path TEXT,
                    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','investigating','resolved','dismissed')),
                    outcome TEXT,
                    penalty TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    resolved_at TEXT
                );
