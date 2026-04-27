CREATE TABLE IF NOT EXISTS absence_evidence_signatures (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         request_id INTEGER NOT NULL, file_path TEXT NOT NULL,
         sha256 TEXT NOT NULL, signed_by TEXT,
         signed_at TEXT DEFAULT CURRENT_TIMESTAMP
       );
