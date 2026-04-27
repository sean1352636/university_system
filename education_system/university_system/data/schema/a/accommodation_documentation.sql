CREATE TABLE IF NOT EXISTS accommodation_documentation (
                    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    document_type TEXT,
                    FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id)
                );
