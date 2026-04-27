CREATE TABLE IF NOT EXISTS barber_gift_card_redemptions (
                redemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_card_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                appointment_id INTEGER,
                redeemed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gift_card_id) REFERENCES barber_gift_cards(gift_card_id)
            );
