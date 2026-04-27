CREATE TABLE IF NOT EXISTS visitor_parking (
                visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_user_id INTEGER,
                visitor_name TEXT NOT NULL,
                visitor_vehicle TEXT,
                visitor_plate TEXT,
                visit_date TEXT NOT NULL,
                duration_hours INTEGER,
                parking_location TEXT,
                status TEXT DEFAULT 'pending', "check_in_time" TEXT, "check_out_time" TEXT, "host_id" INTEGER, "id" INTEGER, "lot_id" INTEGER, "pass_number" TEXT, "vehicle_plate" TEXT,
                FOREIGN KEY (host_user_id) REFERENCES users(id)
            );
