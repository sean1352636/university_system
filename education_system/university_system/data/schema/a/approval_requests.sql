CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    context_json TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP,
                    due_date TIMESTAMP,
                    decision_at TIMESTAMP,
                    decision_by TEXT,
                    comments TEXT,
                    FOREIGN KEY (instance_id) REFERENCES workflow_instances(instance_id)
                );
