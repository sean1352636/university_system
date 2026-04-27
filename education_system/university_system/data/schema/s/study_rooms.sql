CREATE TABLE IF NOT EXISTS study_rooms (
                    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_number TEXT NOT NULL,
                    building TEXT DEFAULT '',
                    capacity INTEGER DEFAULT 4,
                    room_type TEXT DEFAULT 'study',
                    equipment TEXT DEFAULT '',
                    has_whiteboard INTEGER DEFAULT 0,
                    has_projector INTEGER DEFAULT 0,
                    has_power_outlets INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'available'
                );
