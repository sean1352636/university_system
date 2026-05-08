"""Auto-posting hooks — fire-and-forget bridge from operational writes to the GL.

The hook is designed to be called immediately after an operational INSERT
or UPDATE has been committed. It is **never** allowed to raise: a posting
failure must not break the operational write path. Failures are logged
and surface in the dispatcher's `LEDGER_HOOK_FAILURES` list (intended for
test assertions and the on-page health indicator on the Trial Balance tab,
not as a control-flow signal).

Posting is also gated on whether the ledger is initialised — if `gl_*`
tables don't exist (because `init_ledger()` hasn't been run on this DB),
the hook silently no-ops. This keeps the operational paths usable on
fresh deployments before finance has bootstrapped the ledger.

Idempotency is provided by the underlying `post_*` functions via
`UNIQUE(source_type, source_id)` on `gl_journals`, so a duplicate hook
firing is harmless.
"""

import logging

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.finance.ledger.posting import (
    post_payment, post_refund, post_fee_assignment,
)


logger = logging.getLogger(__name__)

# Last-N failures kept in-process for debugging / tests. Bounded so the list
# can't grow without limit if posting is broken in production.
_FAILURE_CAP = 50
LEDGER_HOOK_FAILURES: list[tuple[str, int, str]] = []


_DISPATCHERS = {
    'payment': post_payment,
    'refund': post_refund,
    'fee_assignment': post_fee_assignment,
}


def _ledger_initialised() -> bool:
    """Cheap probe: does the GL schema exist on this DB?"""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='gl_journals' LIMIT 1"
            )
            return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        return False


def _record_failure(source_type: str, source_id, message: str) -> None:
    LEDGER_HOOK_FAILURES.append((source_type, source_id, message))
    if len(LEDGER_HOOK_FAILURES) > _FAILURE_CAP:
        del LEDGER_HOOK_FAILURES[:-_FAILURE_CAP]


def notify_ledger(source_type: str, source_id, posted_by: str = 'auto') -> bool:
    """Post an operational event to the GL. Never raises.

    Returns True if a journal was created (or already existed), False if the
    hook was skipped or failed. Callers should not rely on the return value
    for control flow — it's informational only.
    """
    if source_id is None:
        return False
    fn = _DISPATCHERS.get(source_type)
    if fn is None:
        _record_failure(source_type, source_id, f"no dispatcher for {source_type!r}")
        logger.warning("notify_ledger: unknown source_type %r", source_type)
        return False

    if not _ledger_initialised():
        # Silent no-op: ledger hasn't been bootstrapped on this DB.
        return False

    try:
        fn(source_id, posted_by=posted_by)
        return True
    except Exception as e:
        _record_failure(source_type, source_id, str(e))
        logger.warning(
            "notify_ledger failed for %s id=%s: %s", source_type, source_id, e,
        )
        return False
