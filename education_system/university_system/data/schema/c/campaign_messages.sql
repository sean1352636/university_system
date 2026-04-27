CREATE TABLE IF NOT EXISTS campaign_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            prospect_id INTEGER NOT NULL,
            sent_date TEXT DEFAULT CURRENT_TIMESTAMP,
            opened_date TEXT,
            clicked_date TEXT,
            status TEXT DEFAULT 'sent',
            FOREIGN KEY (campaign_id) REFERENCES recruitment_campaigns (campaign_id),
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        );
