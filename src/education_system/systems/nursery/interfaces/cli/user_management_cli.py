"""CLI flow for User Management (Nursery System) — roles and access on the
shared sign-in accounts. See :mod:`interfaces.user_management`."""

from __future__ import annotations

from typing import Any

from education_system.systems.nursery.interfaces import user_management as data


def run(auth: Any = None) -> None:
    data.run_cli(auth)


def dispatch(label: str, auth=None) -> bool:
    if label != data.FEATURE_NAME:
        return False
    return data.run_cli(auth)
