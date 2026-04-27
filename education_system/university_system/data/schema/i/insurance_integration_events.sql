CREATE TABLE IF NOT EXISTS insurance_integration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                patient_id TEXT,
                event_type TEXT,        -- submitted/approved/denied/cancelled
                status TEXT,
                external_id TEXT,
                correlation_id TEXT,
                payload TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );
