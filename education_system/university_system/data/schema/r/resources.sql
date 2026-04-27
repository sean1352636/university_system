CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    capacity INTEGER,
                    location TEXT,
                    equipment TEXT,
                    status TEXT DEFAULT 'available',
                    date_added TEXT NOT NULL
                );
