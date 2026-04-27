CREATE TABLE IF NOT EXISTS asset_depreciation (
                depreciation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                fiscal_year TEXT NOT NULL,
                period TEXT,
                depreciation_method TEXT DEFAULT 'straight-line',
                beginning_value REAL,
                depreciation_amount REAL,
                accumulated_depreciation REAL,
                ending_value REAL,
                calculated_date TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
                UNIQUE(asset_id, fiscal_year, period)
            );
