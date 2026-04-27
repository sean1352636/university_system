CREATE TABLE IF NOT EXISTS campaign_materials (
            material_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            material_type TEXT,
            content TEXT,
            file_path TEXT,
            upload_date TEXT,
            status TEXT DEFAULT 'pending_approval', reviewed_at TEXT, reviewed_by INTEGER, rejection_reason TEXT,
            FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
        );
