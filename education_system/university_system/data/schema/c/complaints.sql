CREATE TABLE IF NOT EXISTS complaints (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    email       TEXT NOT NULL,
    category    TEXT NOT NULL,
    priority    TEXT NOT NULL,
    subject     TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Pending',
    response    TEXT NOT NULL DEFAULT '',
    submitted   TEXT NOT NULL,
    updated     TEXT NOT NULL,
    submitted_by TEXT
);
