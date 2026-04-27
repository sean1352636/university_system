CREATE TABLE IF NOT EXISTS financial_kpis (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_value DECIMAL(15,2) NOT NULL,
            kpi_type TEXT NOT NULL, -- 'amount', 'percentage', 'count', 'ratio'
            calculation_period TEXT NOT NULL, -- 'daily', 'weekly', 'monthly', 'yearly'
            calculation_date TEXT NOT NULL,
            academic_year TEXT,
            created_at TEXT
        );
