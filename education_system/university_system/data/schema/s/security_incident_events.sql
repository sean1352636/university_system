CREATE TABLE IF NOT EXISTS security_incident_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_pk INTEGER NOT NULL,       -- FK to security_incidents.id
                event_time TEXT DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT,                    -- note, containment, escalation, closure, etc.
                details TEXT,
                actor TEXT
            , "incident_id" INTEGER, "description" TEXT, "performed_by" INTEGER, "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
