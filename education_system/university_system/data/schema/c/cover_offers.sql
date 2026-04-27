CREATE TABLE IF NOT EXISTS cover_offers (
                    offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    volunteer_id TEXT NOT NULL,
                    message TEXT,
                    status TEXT DEFAULT 'offered',
                    offered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES cover_requests(request_id)
                );
