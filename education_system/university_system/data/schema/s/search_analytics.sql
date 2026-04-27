CREATE TABLE IF NOT EXISTS search_analytics (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT NOT NULL,
            search_type TEXT NOT NULL,  -- faq, resource, ticket, global
            results_count INTEGER NOT NULL,
            clicked_result_id TEXT,
            search_datetime TEXT NOT NULL,
            session_id TEXT
        , search_criteria TEXT, execution_time REAL);
