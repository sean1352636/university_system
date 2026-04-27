CREATE TABLE IF NOT EXISTS volunteer_opportunities (
            opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT,
            contact_person TEXT,
            contact_email TEXT,
            description TEXT,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            hours_required REAL,
            skills_needed TEXT,
            max_volunteers INTEGER,
            current_volunteers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open'
        );
