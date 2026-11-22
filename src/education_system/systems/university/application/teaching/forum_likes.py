"""Liking a discussion forum post: each person can like a post once.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

ENSURE_SQL = """
    CREATE TABLE IF NOT EXISTS module_forum_post_likes (
        post_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        liked_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (post_id, user_id),
        FOREIGN KEY (post_id) REFERENCES module_forum_posts (post_id) ON DELETE CASCADE
    )
"""


def like_post(conn, post_id, user_id) -> bool:
    """Add this person's like. False if they had already liked the post."""
    user_id = str(user_id or "").strip()
    if not user_id:
        raise ValueError("You need to be signed in to like a post")
    added = conn.execute("INSERT OR IGNORE INTO module_forum_post_likes (post_id, user_id) "
                         "VALUES (?, ?)", (post_id, user_id)).rowcount
    if not added:
        return False
    conn.execute("UPDATE module_forum_posts SET likes_count = COALESCE(likes_count, 0) + 1 "
                 "WHERE post_id = ?", (post_id,))
    return True
