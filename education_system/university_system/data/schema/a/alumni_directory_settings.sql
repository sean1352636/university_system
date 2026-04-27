CREATE TABLE IF NOT EXISTS alumni_directory_settings (
            alumni_id TEXT PRIMARY KEY,
            show_contact_info BOOLEAN DEFAULT 1,
            show_employment BOOLEAN DEFAULT 1,
            show_education BOOLEAN DEFAULT 1,
            searchable BOOLEAN DEFAULT 1,
            networking_available BOOLEAN DEFAULT 1,
            mentor_available BOOLEAN DEFAULT 0,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
