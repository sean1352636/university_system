"""Receiver-side helpers — let sibling GUIs honour an EQA drill-through.

The EQA dashboard pushes a context dict onto ``app._last_academic_context``
before invoking a sibling launcher (see ``QADashboardGUI._dispatch_with_context``).
Each launcher calls :func:`consume_eqa_context` after building its window;
that copies the dict onto ``app._active_eqa_context`` (so other code can
introspect the most recent drill-through) and stamps it on the launched
object as ``eqa_context``. Downstream GUIs that want to actually prefilter
read ``eqa_context`` and apply it to their own filter widgets.

Why a bridge instead of editing every downstream GUI directly: this keeps
the per-launcher patch to one line, and lets each downstream GUI opt in
to context-aware prefiltering at its own pace.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def consume_eqa_context(app, label: str = "",
                          target=None) -> dict | None:
    """Pop the pending EQA drill-through context off ``app`` and stamp it
    on the launched GUI.

    * ``app`` — the ``UnifiedManagementGUI`` instance that holds
      ``_last_academic_context``. Called from each ``show_*_gui`` launcher.
    * ``label`` — human label used in log lines (e.g. ``"Grades"``).
    * ``target`` — the launched object (window, frame, manager). The
      context is attached as ``target.eqa_context``. If ``None``, only
      the app-level snapshot is updated.

    Returns the context dict (or ``None`` when no drill-through is
    pending — the launcher then opens at default state).
    """
    if app is None:
        return None
    ctx: Any = getattr(app, "_last_academic_context", None)
    # Always clear so a stale context can't bleed into the next plain
    # menu click — same convention as ``academic_link_bar.consume_context``.
    try:
        app._last_academic_context = None
    except Exception:
        pass
    if not ctx:
        return None
    try:
        app._active_eqa_context = ctx
    except Exception:
        pass
    if target is not None:
        try:
            target.eqa_context = ctx
        except Exception:
            logger.debug("could not stamp eqa_context on %r", target)
    src = ctx.get("source") if isinstance(ctx, dict) else None
    logger.info("EQA drill-through → %s (source=%s, keys=%s)",
                label or "?", src, list(ctx.keys()) if isinstance(ctx, dict) else "?")
    return ctx if isinstance(ctx, dict) else None


__all__ = ["consume_eqa_context"]
