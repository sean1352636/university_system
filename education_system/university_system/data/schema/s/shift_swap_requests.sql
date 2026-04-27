CREATE TABLE IF NOT EXISTS shift_swap_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            original_shift_id INTEGER NOT NULL,
            requested_with_id INTEGER,
            target_shift_id INTEGER,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (requester_id) REFERENCES staff(id),
            FOREIGN KEY (original_shift_id) REFERENCES shifts(id),
            FOREIGN KEY (requested_with_id) REFERENCES staff(id),
            FOREIGN KEY (target_shift_id) REFERENCES shifts(id),
            FOREIGN KEY (reviewed_by) REFERENCES staff(id)
        );
