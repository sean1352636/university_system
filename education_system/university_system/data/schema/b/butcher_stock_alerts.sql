CREATE TABLE IF NOT EXISTS butcher_stock_alerts (
                        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        alert_type TEXT NOT NULL,
                        alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved BOOLEAN DEFAULT 0,
                        resolved_date TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    );
