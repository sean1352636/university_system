CREATE TABLE IF NOT EXISTS department_kpis (
                kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department TEXT NOT NULL,
                kpi_name TEXT NOT NULL,
                kpi_description TEXT,
                kpi_category TEXT,
                target_value REAL,
                current_value REAL DEFAULT 0,
                unit TEXT,
                period TEXT DEFAULT 'annual',
                academic_year TEXT,
                quarter TEXT,
                status TEXT DEFAULT 'on_track',
                owner_id TEXT,
                owner_name TEXT,
                last_updated TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
