CREATE TABLE IF NOT EXISTS abs_tracker_delegations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user   INTEGER,
            to_user     INTEGER,
            active_from TEXT,
            active_to   TEXT
        );
