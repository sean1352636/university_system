"""
Background task processing.

The support jobs (escalation rules every five minutes, the metrics snapshot
hourly) run on one daemon thread per process, started from the university
launch beside the other university jobs
(``services/bus/jobs/support_jobs.start_worker``). Creating an
``EnhancedStudentSupport`` no longer starts a thread.
"""

import logging

from education_system.systems.university.domains.student_support.domain.student_support import store
from education_system.systems.university.domains.student_support.domain.student_support.automation.escalations import _process_escalations
from education_system.systems.university.domains.student_support.domain.student_support.utils.metrics import _update_metrics

logger = logging.getLogger(__name__)

__all__ = ['_start_background_tasks', '_process_notification_queue', '_update_metrics',
           '_load_staff_assignments', '_process_escalations']


def _start_background_tasks():
    """Start the process-wide support worker (once per process)."""
    from education_system.systems.university.services.bus.jobs import support_jobs
    started = support_jobs.start_worker()
    logger.info("Support background worker %s", "started" if started else "already running")
    return started


def _process_notification_queue():
    """Nothing to process: in-app notices are ``messages`` rows delivered
    when the event happens (the old ``notifications`` queue table is gone)."""
    return 0


def _load_staff_assignments():
    """Category -> staff mapping from ``staff_assignments`` (auto-assign on)."""
    try:
        with store.reading() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'staff_assignments'").fetchone():
                logger.info("Staff assignments table doesn't exist yet, using empty assignments")
                return {}
            rows = conn.execute('SELECT staff_id, category, is_primary FROM staff_assignments '
                                'WHERE auto_assign_enabled = 1').fetchall()
        staff_assignments = {}
        for staff_id, category, is_primary in rows:
            staff_assignments.setdefault(category, []).append({
                'staff_id': staff_id,
                'is_primary': bool(is_primary)
            })
        logger.info(f"Loaded staff assignments for {len(staff_assignments)} categories")
        return staff_assignments

    except Exception as e:
        logger.error(f"Error loading staff assignments: {e}")
        return {}
