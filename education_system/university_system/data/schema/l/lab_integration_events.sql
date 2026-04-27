CREATE TABLE IF NOT EXISTS lab_integration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                patient_id TEXT,
                test_code TEXT,
                event_type TEXT,        -- order_sent/result_received/ack/error
                status TEXT,
                external_id TEXT,
                correlation_id TEXT,
                payload TEXT,
                response TEXT,
                result_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );
