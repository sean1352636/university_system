"""Per-user notification preferences: which event categories, on which channel.

The bus-driven notifications (see :mod:`.event_notifications`) reach
receiving staff, sending staff, learners and parents. Without a way to say
"not by email" or "no reminders", the only lever a user has is to ignore the
lot, so every notification respects the choices stored here.

One row per ``(user, category, channel)``. A missing row means "use the
default", and the default is in-app on, email off: an in-app notice costs
nothing to ignore, whereas an email nobody asked for is the thing that gets
the whole feed marked as spam. ``category='*'`` sets a user's choice for
every category at once; an explicit category row still wins over it.

The table lives in the shared auth database beside
``cross_system_notifications``, and is created on first use rather than on
import so that constructing the notification service against a minimal
database (as its tests do) stays side-effect free.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from education_system.platform.identity.auth.db import connect as auth_connect

logger = logging.getLogger(__name__)

CHANNEL_IN_APP = "in_app"
CHANNEL_EMAIL = "email"
CHANNELS: tuple[str, ...] = (CHANNEL_IN_APP, CHANNEL_EMAIL)

#: The wildcard category: one switch for everything.
ALL_CATEGORIES = "*"

#: Category -> description, in display order.
CATEGORIES: dict[str, str] = {
    "applications": "A new application or transfer request arrives",
    "offers": "A place is offered, accepted or rejected",
    "handover": "Handover information is approved or acknowledged",
    "progression": "A learner completes a move between institutions",
    "reminders": "Deadlines on a transfer that is waiting for you",
    "identity": "Learner records are merged",
    "withdrawals": "A learner withdraws",
    "operations": "Cross-system delivery failures (administrators)",
}

#: Bus event -> category. Events not listed here are not notified at all.
EVENT_CATEGORIES: dict[str, str] = {
    "application.submitted": "applications",
    "place.offered": "offers",
    "place.accepted": "offers",
    "progression.rejected": "offers",
    "handover.approved": "handover",
    "handover.acknowledged": "handover",
    "progression.completed": "progression",
    "transition.reminder": "reminders",
    "journey.merged": "identity",
    "student.withdrawn": "withdrawals",
    "bus.dead_letter": "operations",
}

DEFAULTS: dict[str, bool] = {CHANNEL_IN_APP: True, CHANNEL_EMAIL: False}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id     INTEGER NOT NULL,
    category    TEXT    NOT NULL,
    channel     TEXT    NOT NULL CHECK (channel IN ('in_app', 'email')),
    enabled     INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, category, channel)
);
"""


class PreferenceError(ValueError):
    """An unknown category or channel."""


def _check(category: str, channel: str) -> None:
    if category != ALL_CATEGORIES and category not in CATEGORIES:
        raise PreferenceError(
            f"Unknown category {category!r}; expected one of "
            f"{', '.join([ALL_CATEGORIES, *CATEGORIES])}")
    if channel not in CHANNELS:
        raise PreferenceError(
            f"Unknown channel {channel!r}; expected one of {', '.join(CHANNELS)}")


class NotificationPreferences:
    """Read and write notification preferences in the shared auth DB."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._ready = False

    def _conn(self):
        conn = auth_connect(self._db_path)
        if not self._ready:
            conn.executescript(_SCHEMA)
            conn.commit()
            self._ready = True
        return conn

    # ── Read ──────────────────────────────────────────────────────────

    def _stored(self, user_id: int) -> dict[tuple[str, str], bool]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT category, channel, enabled FROM notification_preferences "
                "WHERE user_id = ?", (int(user_id),)).fetchall()
        finally:
            conn.close()
        return {(r["category"], r["channel"]): bool(r["enabled"]) for r in rows}

    @staticmethod
    def _resolve(stored: Mapping[tuple[str, str], bool], category: str,
                 channel: str) -> bool:
        if (category, channel) in stored:
            return stored[(category, channel)]
        if (ALL_CATEGORIES, channel) in stored:
            return stored[(ALL_CATEGORIES, channel)]
        return DEFAULTS[channel]

    def is_enabled(self, user_id: int, category: str, channel: str) -> bool:
        """Whether *user_id* wants *category* notices on *channel*."""
        _check(category, channel)
        return self._resolve(self._stored(user_id), category, channel)

    def enabled_channels(self, user_id: int, category: str) -> list[str]:
        """The channels *user_id* has switched on for *category*."""
        stored = self._stored(user_id)
        return [c for c in CHANNELS if self._resolve(stored, category, c)]

    def get_preferences(self, user_id: int) -> dict:
        """Effective settings for every category, plus what was set explicitly.

        Returns ``{"categories": {category: {"description", "in_app",
        "email"}}, "explicit": [{category, channel, enabled}], "defaults"}``
        so a settings screen can show both the answer and why.
        """
        stored = self._stored(user_id)
        categories = {
            name: {
                "description": description,
                **{c: self._resolve(stored, name, c) for c in CHANNELS},
            }
            for name, description in CATEGORIES.items()
        }
        explicit = [
            {"category": cat, "channel": ch, "enabled": on}
            for (cat, ch), on in sorted(stored.items())
        ]
        return {"user_id": int(user_id), "categories": categories,
                "explicit": explicit, "defaults": dict(DEFAULTS)}

    # ── Write ─────────────────────────────────────────────────────────

    def set_preference(self, user_id: int, category: str, channel: str,
                       enabled: bool) -> None:
        _check(category, channel)
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO notification_preferences
                       (user_id, category, channel, enabled)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (user_id, category, channel) DO UPDATE
                       SET enabled = excluded.enabled,
                           updated_at = datetime('now')""",
                (int(user_id), category, channel, 1 if enabled else 0))
            conn.commit()
        finally:
            conn.close()

    def set_preferences(self, user_id: int,
                        changes: Mapping[str, Mapping[str, bool]]) -> dict:
        """Apply ``{category: {channel: bool}}`` in one transaction.

        Validates every entry before writing any, so a request with one bad
        category does not half-apply.
        """
        flat = []
        for category, channels in (changes or {}).items():
            if not isinstance(channels, Mapping):
                raise PreferenceError(
                    f"Category {category!r} must map channels to true/false")
            for channel, enabled in channels.items():
                _check(category, channel)
                if not isinstance(enabled, bool):
                    raise PreferenceError(
                        f"{category}.{channel} must be true or false")
                flat.append((int(user_id), category, channel, 1 if enabled else 0))
        conn = self._conn()
        try:
            conn.executemany(
                """INSERT INTO notification_preferences
                       (user_id, category, channel, enabled)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (user_id, category, channel) DO UPDATE
                       SET enabled = excluded.enabled,
                           updated_at = datetime('now')""", flat)
            conn.commit()
        finally:
            conn.close()
        return self.get_preferences(user_id)

    def reset(self, user_id: int) -> int:
        """Forget every explicit choice; returns how many rows went."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM notification_preferences WHERE user_id = ?",
                (int(user_id),))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


__all__ = [
    "ALL_CATEGORIES",
    "CATEGORIES",
    "CHANNELS",
    "CHANNEL_EMAIL",
    "CHANNEL_IN_APP",
    "DEFAULTS",
    "EVENT_CATEGORIES",
    "NotificationPreferences",
    "PreferenceError",
]
