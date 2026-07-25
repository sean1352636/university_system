"""Admin features context, audit helper, and ``safe`` decorator.

Also owns the shared ``logger`` instance used across the admin_features
package. All other submodules import it from here.
"""
from __future__ import annotations

import functools
import logging
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox
from typing import Any, Callable, Optional

try:
    from education_system.systems.university.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_tracker.admin")
except Exception:  # pragma: no cover
    logger = logging.getLogger("absence_tracker.admin")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)


@dataclass
class AdminContext:
    """Lightweight bag passed into every admin feature."""
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def uid(self) -> Optional[int]:
        v = self.user.get("id")
        return int(v) if v is not None else None

    @property
    def username(self) -> str:
        return str(self.user.get("username") or "")


def audit(ctx: AdminContext, action: str, target: str = "",
          target_id: Any = "", details: str = "") -> None:
    """Write a row to the admin audit table. Never raises."""
    try:
        ctx.db.cur.execute(
            """INSERT INTO abs_tracker_audit
               (user_id, username, action, target, target_id, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.user.get("id"), ctx.user.get("username"),
             action, target, str(target_id), details))
        ctx.db.conn.commit()
    except sqlite3.Error:
        logger.exception("audit write failed for action=%s", action)


def safe(title: str = "Error") -> Callable:
    """Decorator: logs + shows a friendly error dialog on any exception."""
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(ctx_or_self, *args, **kwargs):
            # Resolve the user for the start log line whether the call was
            # `fn(ctx, ...)` (legacy module-level functions) or
            # `method(self, ctx, ...)` (service methods bound through the
            # legacy aliases).
            if isinstance(ctx_or_self, AdminContext):
                username = ctx_or_self.user.get("username")
            elif args and isinstance(args[0], AdminContext):
                username = args[0].user.get("username")
            else:
                ctx = getattr(ctx_or_self, "ctx", None)
                username = ctx.user.get("username") if ctx else "?"
            try:
                logger.info("▶ %s user=%s", fn.__name__, username)
                out = fn(ctx_or_self, *args, **kwargs)
                logger.info("✓ %s", fn.__name__)
                return out
            except Exception as e:
                logger.exception("✗ %s failed", fn.__name__)
                # Resolve a parent window for the error dialog.
                parent = None
                if isinstance(ctx_or_self, AdminContext):
                    parent = ctx_or_self.parent
                elif args and isinstance(args[0], AdminContext):
                    parent = args[0].parent
                else:
                    ctx = getattr(ctx_or_self, "ctx", None)
                    parent = ctx.parent if ctx else None
                try:
                    messagebox.showerror(
                        title, f"{fn.__name__} failed:\n{e}", parent=parent)
                except Exception:
                    pass
        return wrapped
    return deco
