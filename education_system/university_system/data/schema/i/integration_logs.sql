CREATE TABLE IF NOT EXISTS integration_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT,          -- e.g., 'insurance','lab','hl7','fhir'
                system   TEXT,          -- optional: vendor/system name
                event_type TEXT,
                status TEXT,            -- success, error, pending
                message TEXT,
                correlation_id TEXT,
                http_status INTEGER,
                duration_ms INTEGER,
                endpoint TEXT,
                payload TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
