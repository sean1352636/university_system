CREATE TABLE IF NOT EXISTS risks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                category    TEXT NOT NULL,
                department  TEXT NOT NULL,
                description TEXT,
                likelihood  INTEGER NOT NULL CHECK(likelihood BETWEEN 1 AND 5),
                impact      INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5),
                status      TEXT NOT NULL,
                owner       TEXT,
                mitigation  TEXT,
                created     TEXT NOT NULL,
                updated     TEXT NOT NULL
            );
