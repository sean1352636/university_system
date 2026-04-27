CREATE TABLE IF NOT EXISTS ed_incident_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        uploaded_by TEXT,
        uploaded_at TEXT,
        FOREIGN KEY (incident_id) REFERENCES ed_incidents(id) ON DELETE CASCADE
    );
