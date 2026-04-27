CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            work_order_type TEXT NOT NULL,
            description TEXT NOT NULL,
            assigned_technician TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            materials_cost REAL,
            labor_cost REAL,
            total_cost REAL,
            start_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (request_id) REFERENCES maintenance_requests (request_id)
        );
