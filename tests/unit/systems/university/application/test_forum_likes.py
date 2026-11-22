"""A person can like a forum post once."""

import sqlite3

import pytest

from education_system.systems.university.application.teaching import forum_likes


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("CREATE TABLE module_forum_posts (post_id INTEGER PRIMARY KEY, "
              "likes_count INTEGER DEFAULT 0)")
    c.execute(forum_likes.ENSURE_SQL)
    c.execute("INSERT INTO module_forum_posts VALUES (1, 5), (2, NULL)")
    yield c
    c.close()


def _likes(conn, post_id):
    return conn.execute("SELECT likes_count FROM module_forum_posts WHERE post_id = ?",
                        (post_id,)).fetchone()[0]


def test_second_like_from_the_same_person_counts_for_nothing(conn):
    assert forum_likes.like_post(conn, 1, "alice") is True
    assert forum_likes.like_post(conn, 1, "alice") is False
    assert _likes(conn, 1) == 6


def test_different_people_and_different_posts_each_count(conn):
    assert forum_likes.like_post(conn, 1, "alice")
    assert forum_likes.like_post(conn, 1, "bob")
    assert forum_likes.like_post(conn, 2, "alice")
    assert _likes(conn, 1) == 7 and _likes(conn, 2) == 1


def test_needs_someone_signed_in(conn):
    with pytest.raises(ValueError, match="signed in"):
        forum_likes.like_post(conn, 1, "  ")
    assert _likes(conn, 1) == 5


def test_a_post_that_does_not_exist_is_refused(conn):
    with pytest.raises(sqlite3.IntegrityError):
        forum_likes.like_post(conn, 99, "alice")
