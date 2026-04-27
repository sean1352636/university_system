CREATE TABLE IF NOT EXISTS search_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                criteria TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                is_shared BOOLEAN DEFAULT FALSE
            , "created_at" TEXT, "is_default" INTEGER DEFAULT 0, "profile_name" TEXT, "search_criteria" TEXT, "user_id" INTEGER);
