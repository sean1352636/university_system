CREATE TABLE IF NOT EXISTS feedback_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    vote_type TEXT DEFAULT 'upvote' CHECK(vote_type IN ('upvote', 'downvote')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(submission_id, user_id),
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                );
