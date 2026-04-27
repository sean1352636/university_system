CREATE TABLE IF NOT EXISTS workflow_audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL,
                    step_id TEXT,
                    action TEXT NOT NULL,
                    actor TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details_json TEXT,
                    FOREIGN KEY (instance_id) REFERENCES workflow_instances(instance_id)
                );
