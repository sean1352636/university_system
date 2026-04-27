CREATE TABLE IF NOT EXISTS advisors (
                    advisor_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    office TEXT DEFAULT '',
                    specialization TEXT DEFAULT '',
                    available_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri',
                    available_hours TEXT DEFAULT '09:00-17:00'
                );
