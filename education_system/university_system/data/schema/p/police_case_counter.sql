CREATE TABLE IF NOT EXISTS police_case_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    counter INTEGER DEFAULT 1000
);
