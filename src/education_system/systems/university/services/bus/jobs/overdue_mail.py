"""Focused components extracted from the legacy integration bus."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED,
    EVENT_CERT_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
    publish,
    subscribe,
)

logger = logging.getLogger(__name__)

_MAIL_FREE_DAYS = 7

_MAIL_DAILY_FEE = 0.50

def sweep_overdue_mail(*, free_days: int = _MAIL_FREE_DAYS,
                       daily_fee: float = _MAIL_DAILY_FEE) -> dict[str, int]:
    """Sweep ``mail_packages`` for unclaimed packages past the free
    window. Idempotent — uses ``reference_id='package:<id>'`` so a
    second sweep on the same day doesn't double-bill.

    Returns ``{"charged": N, "emailed": M}``.
    """
    charged = 0
    emailed = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='mail_packages'"
            ).fetchone()
            if not tbl:
                return {"charged": 0, "emailed": 0}
            rows = conn.execute(
                "SELECT package_id, recipient_id, recipient_name, "
                "       recipient_email, tracking_number, received_date "
                "FROM mail_packages "
                "WHERE LOWER(status) IN ('received', 'stored') "
                "  AND julianday('now') - julianday(received_date) > ?",
                (int(free_days),),
            ).fetchall()
    except Exception as exc:
        logger.warning("sweep_overdue_mail query failed: %s", exc)
        return {"charged": 0, "emailed": 0}

    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
    except Exception:
        return {"charged": 0, "emailed": 0}

    for r in rows:
        d = dict(r)
        try:
            received = datetime.strptime(
                str(d["received_date"])[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        days_over = max((date.today() - received).days - free_days, 0)
        if days_over <= 0:
            continue
        amount = round(days_over * float(daily_fee), 2)
        ref = f"package:{d['package_id']}:{date.today().isoformat()}"
        if not d.get("recipient_id"):
            continue
        try:
            tx = raise_charge(
                d["recipient_id"], amount,
                source="mail_storage",
                description=(
                    f"Mail storage overdue ({days_over}d): "
                    f"{d.get('tracking_number') or ''}"
                ),
                reference_id=ref,
            )
            if tx:
                charged += 1
        except Exception as exc:
            logger.debug("mail charge failed for %s: %s",
                         d["package_id"], exc)
            continue
        try:
            send_templated(
                d["recipient_id"], "mail.overdue",
                {
                    "tracking_number": d.get("tracking_number") or "",
                    "days_over": days_over,
                    "amount": amount,
                },
                related_to=f"package:{d['package_id']}",
                force=True,
            )
            emailed += 1
        except Exception as exc:
            logger.debug("mail email failed: %s", exc)

    return {"charged": charged, "emailed": emailed}
