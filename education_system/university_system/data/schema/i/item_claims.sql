CREATE TABLE IF NOT EXISTS item_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    found_item_id INTEGER NOT NULL,
                    claimant_id TEXT NOT NULL,
                    claim_description TEXT NOT NULL,
                    verification_questions TEXT,
                    verification_answers TEXT,
                    supporting_evidence TEXT,
                    status TEXT DEFAULT 'Pending',
                    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    resolution_notes TEXT,
                    FOREIGN KEY (found_item_id) REFERENCES found_items(item_id) ON DELETE CASCADE,
                    FOREIGN KEY (claimant_id) REFERENCES students(student_id)
                );
