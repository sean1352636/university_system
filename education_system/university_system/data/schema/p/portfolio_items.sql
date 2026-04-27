CREATE TABLE IF NOT EXISTS portfolio_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id INTEGER NOT NULL,
                    category TEXT NOT NULL CHECK(category IN (
                        'project', 'research', 'leadership', 'work_experience',
                        'award', 'certification', 'publication', 'presentation'
                    )),
                    title TEXT NOT NULL,
                    description TEXT,
                    organization TEXT,
                    role TEXT,
                    start_date DATE,
                    end_date DATE,
                    is_current BOOLEAN DEFAULT 0,
                    technologies TEXT,
                    achievements TEXT,
                    url TEXT,
                    attachments TEXT,
                    display_order INTEGER DEFAULT 0,
                    is_featured BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id) ON DELETE CASCADE
                );
