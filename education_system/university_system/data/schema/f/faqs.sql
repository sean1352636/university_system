CREATE TABLE IF NOT EXISTS faqs (
            faq_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            updated_datetime TEXT,
            view_count INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            tags TEXT,  -- JSON array
            is_featured BOOLEAN DEFAULT 0
        );
