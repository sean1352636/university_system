"""Email / SMS / Push delivery for notifications.

A notification is always delivered to the in-app inbox once it is Sent.
Its channel (Email, SMS, Push or Multiple) asks for a copy elsewhere
too; this module hands that copy over and records what really happened,
one ``notification_deliveries`` row per (notification, channel):

* **Email** and **SMS** become an outgoing message in the messages log
  and go through the sixth form outbox (:mod:`messages.delivery`), which
  obeys the platform delivery mode (inbox_only / sandbox / live) and the
  SMS provider setting. The row mirrors the outbox state — *Sent* only
  when a provider accepted it.
* **Push** has no provider on this installation, so the row says
  *Unavailable* and the notification stays in-app only — never "Sent".

The notification itself moves to *Delivered* (``delivered_at``) only
when an Email/SMS copy was accepted by a provider.

Notifications sent before this module first ran are left alone (a
watermark is stored on first use), so switching it on does not e-mail
the whole back catalogue.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field

from education_system.systems.sixth_form.domains.communications.domain.notifications import (
    notifications as _n,
)

logger = logging.getLogger(__name__)

CHANNEL_EMAIL = "Email"
CHANNEL_SMS = "SMS"
CHANNEL_PUSH = "Push"
OUTBOX_CHANNELS = (CHANNEL_EMAIL, CHANNEL_SMS)

#: States of a notification_deliveries row. Outbox states are copied
#: from messages.delivery as they change.
UNAVAILABLE = "Unavailable"
NO_ADDRESS = "No address"
ERROR = "Error"
#: Rows in these states are final — nothing more will happen to them.
FINAL_STATES = ("Sent", "Failed", "Cancelled", UNAVAILABLE, NO_ADDRESS, ERROR)

ACTIVE_STATUSES = ("Sent", "Delivered", "Read", "Acknowledged")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_deliveries (
    notification_id INTEGER NOT NULL,
    channel         TEXT NOT NULL,
    state           TEXT NOT NULL,
    message_id      INTEGER,
    recipient       TEXT,
    detail          TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (notification_id, channel),
    FOREIGN KEY (notification_id) REFERENCES notifications(notification_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_notifdel_state ON notification_deliveries(state);

CREATE TABLE IF NOT EXISTS notification_delivery_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    _n.init_db()
    with _n._connect() as conn:
        conn.executescript(_SCHEMA)
    _READY = True


@dataclass
class ChannelDelivery:
    notification_id: int
    channel: str
    state: str
    message_id: int | None
    recipient: str | None
    detail: str | None
    created_at: str
    updated_at: str

    @property
    def is_final(self) -> bool:
        return self.state in FINAL_STATES


@dataclass
class DeliveryReport:
    notifications: int = 0
    handed_to_outbox: int = 0
    sent: int = 0
    waiting: int = 0
    unavailable: int = 0
    no_address: int = 0
    failed: int = 0
    refreshed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.notifications} notification(s): {self.handed_to_outbox} "
                f"copy(ies) handed to the outbox, {self.sent} sent, "
                f"{self.waiting} waiting (held / no provider / retrying), "
                f"{self.unavailable} channel unavailable (in-app only), "
                f"{self.no_address} with no address, {self.failed} failed; "
                f"{self.refreshed} earlier copy(ies) updated")


def _since() -> str:
    """The watermark: only notifications sent at or after it are copied."""
    init_db()
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _n._connect() as conn:
        conn.execute("INSERT OR IGNORE INTO notification_delivery_meta "
                     "(key, value) VALUES ('since', ?)", (now,))
        return conn.execute("SELECT value FROM notification_delivery_meta "
                            "WHERE key = 'since'").fetchone()["value"]


def deliveries_for(notification_id: int) -> list[ChannelDelivery]:
    init_db()
    with _n._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notification_deliveries WHERE notification_id = ? "
            "ORDER BY channel", (notification_id,)).fetchall()
    return [ChannelDelivery(**{k: r[k] for k in r.keys()}) for r in rows]


def _record(notification_id: int, channel: str, state: str, *,
            message_id: int | None = None, recipient: str | None = None,
            detail: str | None = None) -> None:
    with _n._connect() as conn:
        conn.execute(
            """INSERT INTO notification_deliveries
                   (notification_id, channel, state, message_id, recipient, detail)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(notification_id, channel) DO UPDATE SET
                   state = excluded.state,
                   message_id = COALESCE(excluded.message_id,
                                         notification_deliveries.message_id),
                   recipient = COALESCE(excluded.recipient,
                                        notification_deliveries.recipient),
                   detail = excluded.detail,
                   updated_at = datetime('now')""",
            (notification_id, channel, state, message_id, recipient, detail))


def _channels_for(n: _n.Notification) -> list[str]:
    if n.channel == "Multiple":
        return [CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PUSH]
    if n.channel in (CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PUSH):
        return [n.channel]
    return []


@dataclass
class _Target:
    email: str | None = None
    phone: str | None = None
    student_id: str | None = None
    parent_contact_id: int | None = None


def _target(n: _n.Notification) -> _Target:
    rid = (n.recipient_id or "").strip()
    t = _Target()
    if n.recipient_type == "Student":
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _st,
        )
        s = _st.get_student(rid)
        if s is not None:
            t.email, t.phone, t.student_id = s.email, s.phone, s.student_id
    elif n.recipient_type in ("Staff", "Tutor"):
        from education_system.systems.sixth_form.domain.staff import staff as _sf
        s = _sf.get_staff(rid.upper())
        if s is not None:
            t.email, t.phone = s.email, (s.work_phone or s.personal_phone)
    elif n.recipient_type == "Parent":
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
            parent_contacts as _pc,
        )
        try:
            c = _pc.get_contact(int(rid))
        except (TypeError, ValueError):
            c = None
        if c is not None:
            t.email = c.email
            t.phone = c.primary_phone or c.secondary_phone
            t.student_id, t.parent_contact_id = c.student_id, c.contact_id
    elif "@" in rid:
        t.email = rid
    return t


def _category(n: _n.Notification) -> str:
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _m,
    )
    return n.notification_type if n.notification_type in _m.CATEGORIES else "General"


def _body(n: _n.Notification) -> str:
    parts = [n.body or n.title]
    if n.requires_action and n.action_label:
        parts.append(f"Action needed: {n.action_label}"
                     + (f" — {n.action_url}" if n.action_url else ""))
    elif n.url:
        parts.append(n.url)
    return "\n\n".join(p for p in parts if p)


def _hand_to_outbox(n: _n.Notification, channel: str, address: str,
                    target: _Target) -> tuple[str, int, str | None]:
    """Create the outgoing message and send it through the outbox.
    Returns (delivery state, message id, detail)."""
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _m,
    )
    msg = _m.create_message({
        "direction": "Outgoing", "channel": channel,
        "category": _category(n),
        "priority": "Urgent" if n.priority >= 5 else
                    "High" if n.priority == 4 else "Normal",
        "status": "Queued",
        "subject": n.title[:_m.MAX_SUBJECT_LEN],
        "body": _body(n),
        "to_name": n.recipient_name,
        "to_address": address,
        "student_id": target.student_id,
        "parent_contact_id": target.parent_contact_id,
        "tags": f"notification:{n.notification_id}",
    })
    msg = _m.send_message(msg.message_id)
    d = _m.delivery_status(msg.message_id)
    if d is None:
        return msg.status, msg.message_id, None
    return d.state, msg.message_id, d.detail or d.last_error


def _deliver_one(n: _n.Notification, channel: str, report: DeliveryReport) -> None:
    if channel == CHANNEL_PUSH:
        _record(n.notification_id, channel, UNAVAILABLE,
                detail="No push provider is configured on this installation — "
                       "delivered in-app only")
        report.unavailable += 1
        return
    target = _target(n)
    address = target.email if channel == CHANNEL_EMAIL else target.phone
    if not address:
        _record(n.notification_id, channel, NO_ADDRESS,
                detail=f"No {'e-mail address' if channel == CHANNEL_EMAIL else 'mobile number'}"
                       f" on file for {n.recipient_type} {n.recipient_id} — "
                       "delivered in-app only")
        report.no_address += 1
        return
    try:
        state, mid, detail = _hand_to_outbox(n, channel, address, target)
    except Exception as e:  # noqa: BLE001 - recorded, and reported to the job
        _record(n.notification_id, channel, ERROR, recipient=address,
                detail=str(e)[:500])
        report.failed += 1
        report.errors.append(f"Notification #{n.notification_id} {channel}: {e}")
        return
    _record(n.notification_id, channel, state, message_id=mid,
            recipient=address, detail=detail)
    report.handed_to_outbox += 1
    _count(state, report)


def _count(state: str, report: DeliveryReport) -> None:
    if state == "Sent":
        report.sent += 1
    elif state in ("Failed", ERROR):
        report.failed += 1
    else:
        report.waiting += 1


def _mark_delivered_if_sent(notification_id: int) -> None:
    rows = deliveries_for(notification_id)
    if any(r.state == "Sent" for r in rows):
        n = _n.get_notification(notification_id)
        if n is not None and not n.delivered_at:
            _n.mark_delivered(notification_id)


def refresh() -> int:
    """Copy the latest outbox state onto unfinished delivery rows
    (a held e-mail released later, a retry that succeeded)."""
    init_db()
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        delivery as _d,
    )
    with _n._connect() as conn:
        rows = conn.execute(
            "SELECT notification_id, channel, state, message_id "
            "FROM notification_deliveries WHERE message_id IS NOT NULL").fetchall()
    changed = 0
    for r in rows:
        if r["state"] in FINAL_STATES:
            continue
        d = _d.delivery_for(r["message_id"])
        if d is None or d.state == r["state"]:
            continue
        _record(r["notification_id"], r["channel"], d.state,
                detail=d.detail or d.last_error)
        changed += 1
        if d.state == "Sent":
            _mark_delivered_if_sent(r["notification_id"])
    return changed


def deliver_pending(*, limit: int = 200) -> DeliveryReport:
    """Hand the Email/SMS/Push copies of newly sent notifications over."""
    init_db()
    since = _since()
    report = DeliveryReport()
    report.refreshed = refresh()
    ph = ",".join("?" * len(ACTIVE_STATUSES))
    with _n._connect() as conn:
        ids = [r["notification_id"] for r in conn.execute(
            f"SELECT notification_id FROM notifications n "
            f"WHERE status IN ({ph}) AND channel != 'In-App' "
            f"AND sent_at IS NOT NULL AND REPLACE(sent_at, ' ', 'T') >= ? "
            f"AND NOT EXISTS (SELECT 1 FROM notification_deliveries d "
            f"  WHERE d.notification_id = n.notification_id) "
            f"ORDER BY notification_id LIMIT ?",
            (*ACTIVE_STATUSES, since, int(limit))).fetchall()]
    for nid in ids:
        n = _n.get_notification(nid)
        if n is None:
            continue
        channels = _channels_for(n)
        if not channels:
            continue
        report.notifications += 1
        for ch in channels:
            _deliver_one(n, ch, report)
        _mark_delivered_if_sent(nid)
    if report.notifications or report.refreshed:
        logger.info("Notification channels: %s", report.summary)
    return report
