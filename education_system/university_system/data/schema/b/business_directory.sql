CREATE TABLE IF NOT EXISTS business_directory (
            business_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            business_name TEXT,
            business_description TEXT,
            industry TEXT,
            website TEXT,
            contact_email TEXT,
            services_offered TEXT,
            location TEXT,
            created_date TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
