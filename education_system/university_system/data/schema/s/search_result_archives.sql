CREATE TABLE IF NOT EXISTS search_result_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                search_name TEXT,
                search_criteria TEXT,
                results_json TEXT
            , "archived_at" TEXT, "expires_at" TEXT, "result_count" INTEGER DEFAULT 0, "results_data" TEXT, "search_query" TEXT);
