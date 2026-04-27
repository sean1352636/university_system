CREATE TABLE IF NOT EXISTS event_ticket_types (
                ticket_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                type_name TEXT NOT NULL,
                price REAL NOT NULL,
                total_quantity INTEGER NOT NULL,
                sold_quantity INTEGER DEFAULT 0,
                sale_start_date TEXT,
                sale_end_date TEXT,
                description TEXT,
                created_by TEXT,
                created_date TEXT
            );
