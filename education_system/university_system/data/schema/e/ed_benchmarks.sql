CREATE TABLE IF NOT EXISTS ed_benchmarks (
        field TEXT NOT NULL,
        category TEXT NOT NULL,
        baseline_pct REAL NOT NULL,
        source TEXT,
        PRIMARY KEY (field, category)
    );
