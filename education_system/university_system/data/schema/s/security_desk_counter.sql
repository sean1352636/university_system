CREATE TABLE IF NOT EXISTS security_desk_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    counter INTEGER DEFAULT 1000
);
