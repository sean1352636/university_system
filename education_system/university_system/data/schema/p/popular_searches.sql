CREATE TABLE IF NOT EXISTS popular_searches (
                    query TEXT PRIMARY KEY,
                    entity_type TEXT,
                    search_count INTEGER DEFAULT 1,
                    last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
