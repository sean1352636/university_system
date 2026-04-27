CREATE TABLE IF NOT EXISTS abs_tracker_request_route (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, routed_to INTEGER, reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
