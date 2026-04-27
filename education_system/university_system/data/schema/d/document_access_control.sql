CREATE TABLE IF NOT EXISTS document_access_control (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                classification TEXT DEFAULT 'internal',  -- 'public', 'internal', 'confidential', 'restricted'
                watermark_enabled BOOLEAN DEFAULT 0,
                print_disabled BOOLEAN DEFAULT 0,
                screenshot_disabled BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, document_type)
            );
