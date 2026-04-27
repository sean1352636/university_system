CREATE TABLE IF NOT EXISTS research_equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            model_number TEXT,
            serial_number TEXT,
            purchase_date TEXT,
            purchase_cost REAL,
            current_location TEXT,
            assigned_project_id INTEGER,
            maintenance_schedule TEXT,
            last_maintenance_date TEXT,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (assigned_project_id) REFERENCES research_projects (project_id)
        );
