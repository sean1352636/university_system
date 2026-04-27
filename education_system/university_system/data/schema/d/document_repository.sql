CREATE TABLE IF NOT EXISTS document_repository (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK(length(title) > 0),
                    content TEXT NOT NULL CHECK(length(content) > 0),
                    content_hash TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    module_code TEXT,
                    submission_date TEXT NOT NULL,
                    file_type TEXT,
                    word_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code) ON DELETE SET NULL
                );
