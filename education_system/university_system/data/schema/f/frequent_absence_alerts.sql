CREATE TABLE IF NOT EXISTS frequent_absence_alerts (
                       student_id    TEXT NOT NULL,
                       year_month    TEXT NOT NULL,
                       sent_at       TEXT NOT NULL,
                       count_at_send INTEGER NOT NULL,
                       PRIMARY KEY (student_id, year_month)
                   );
