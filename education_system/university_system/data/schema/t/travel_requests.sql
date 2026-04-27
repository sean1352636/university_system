CREATE TABLE IF NOT EXISTS travel_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    estimated_budget REAL DEFAULT 0,
                    budget_breakdown_json TEXT,
                    funding_source TEXT DEFAULT 'department',
                    status TEXT DEFAULT 'draft',
                    justification TEXT,
                    department TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
