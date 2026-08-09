"""Interface preferences, one row per username and key."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    connect,
    init_db,
)


def load(username: str) -> dict[str, str]:
    """Every preference stored against *username*."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT pref_key, pref_value FROM user_preferences WHERE username = ?",
            (username,),
        ).fetchall()
    return {r["pref_key"]: r["pref_value"] for r in rows if r["pref_value"] is not None}


def save(username: str, values: dict[str, Any]) -> None:
    """Upsert a batch of preferences in one transaction."""
    if not values:
        return
    init_db()
    with connect() as conn:
        conn.executemany(
            """INSERT INTO user_preferences (username, pref_key, pref_value)
                    VALUES (?, ?, ?)
               ON CONFLICT(username, pref_key) DO UPDATE SET
                    pref_value = excluded.pref_value,
                    updated_at = datetime('now')""",
            [(username, key, None if value is None else str(value))
             for key, value in values.items()],
        )


def clear(username: str) -> None:
    """Drop every stored preference, so the defaults apply again."""
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM user_preferences WHERE username = ?", (username,))
