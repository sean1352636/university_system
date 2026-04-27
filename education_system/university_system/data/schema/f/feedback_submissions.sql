CREATE TABLE IF NOT EXISTS feedback_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    category_id INTEGER NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('feedback', 'suggestion')),
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    is_anonymous BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT 'Submitted',
                    priority TEXT DEFAULT 'Normal' CHECK(priority IN ('Low', 'Normal', 'High', 'Critical')),
                    votes INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES feedback_categories(id)
                );
