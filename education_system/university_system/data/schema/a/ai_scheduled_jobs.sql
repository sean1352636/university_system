CREATE TABLE IF NOT EXISTS ai_scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT,
                source_path TEXT,
                scheduled_hour INTEGER,
                scheduled_minute INTEGER,
                status TEXT DEFAULT 'scheduled',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_run TIMESTAMP
            );
