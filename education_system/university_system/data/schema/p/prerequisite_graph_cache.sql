CREATE TABLE IF NOT EXISTS prerequisite_graph_cache (
                    cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL UNIQUE,
                    all_prerequisites_json TEXT NOT NULL,
                    depth_level INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses(code)
                );
