CREATE TABLE IF NOT EXISTS grant_funding_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    allocation_id INTEGER,
                    alert_type TEXT DEFAULT 'threshold',
                    severity TEXT DEFAULT 'info',
                    message TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    is_resolved INTEGER DEFAULT 0,
                    triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(grant_application_id),
                    FOREIGN KEY (allocation_id) REFERENCES grant_budget_allocations(allocation_id)
                );
