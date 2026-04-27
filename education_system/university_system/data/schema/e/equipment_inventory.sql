CREATE TABLE IF NOT EXISTS equipment_inventory (
    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    daily_rate REAL NOT NULL,
    quantity_available INTEGER DEFAULT 1,
    quantity_total INTEGER DEFAULT 1,
    condition TEXT DEFAULT 'Good',
    created_date TEXT NOT NULL
);
