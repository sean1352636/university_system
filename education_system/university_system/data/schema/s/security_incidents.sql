CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE,            -- human-friendly ref (e.g., INC-2025-0001)
                summary TEXT,
                description TEXT,
                severity TEXT,                      -- low/medium/high/critical
                status TEXT,                        -- open/contained/eradicated/monitoring/closed
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reported_by TEXT,
                assigned_to TEXT,
                category TEXT,                      -- phishing, malware, policy_violation, etc.
                source TEXT,                        -- system/user/external
                affected_user TEXT,
                containment TEXT,
                eradication TEXT,
                recovery TEXT,
                resolved_at TEXT,
                root_cause TEXT,
                tags TEXT
            , title TEXT, opened_at TEXT, closed_at TEXT, priority TEXT, "resolution_notes" TEXT, created_at TIMESTAMP DEFAULT NULL);
