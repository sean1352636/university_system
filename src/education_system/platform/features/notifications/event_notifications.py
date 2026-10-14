"""Turn cross-system bus events into notifications for the people involved.

The transition workflow publishes an event at every step, but until now
nothing listened: a university admissions officer learned that a sixth-form
handover had been approved by opening a board and looking. This module is a
shared bus consumer (registered for every system by ``bus_consumers``) that
works out who each event concerns and sends them an in-app notification,
or an email where they have asked for one.

Audiences
---------
``receiving``   staff at the destination of the transition
``sending``     staff at the source of the transition
``learner``     the learner's own account in a system that holds them
``guardian``    parents linked to the learner in any such system
``open_destinations``  staff at the destination of any open transition
``enrolled_admins``    staff in every system the learner is enrolled in

"Staff" here means the transfer-running tier — capability ``admin`` or
``manager`` in that system (see ``role_manager``) — not every teacher.

What goes into a notification is the step, the two systems and the
pseudonymous journey/transition ids. Never handover content: a notification
is readable by anyone who can open that user's inbox.

Learner accounts are found by the convention the seeded systems use — the
local student id is the username (``S12345``) — and parents through
``parent_child_links``. A system that does neither simply has no learner or
guardian recipients.

Idempotent per (event, recipient, channel): see
:meth:`CrossSystemNotificationService.send_for_event`.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from education_system.paths import SYSTEM_LABELS
from education_system.platform.features.notifications.preferences import (
    CHANNEL_EMAIL,
    EVENT_CATEGORIES,
    NotificationPreferences,
)
from education_system.platform.features.notifications.service import (
    CrossSystemNotificationService,
)
from education_system.platform.identity.auth.db import connect as auth_connect
from education_system.platform.identity.auth.role_manager import (
    capability_for,
    is_superadmin_systems,
)
from education_system.platform.integrations.external import cross_system_bus
from education_system.platform.kernel.core.system_keys import canonical_system_key

logger = logging.getLogger(__name__)

HANDLER_NAME = "platform.features.notifications.event_notifications"

RECEIVING = "receiving"
SENDING = "sending"
LEARNER = "learner"
GUARDIAN = "guardian"
OPEN_DESTINATIONS = "open_destinations"
ENROLLED_ADMINS = "enrolled_admins"
REMINDER = "reminder"

#: Event -> audiences. ``transition.reminder`` resolves its audience from
#: the payload's ``awaiting`` key (``source``/``destination``/``both``).
EVENT_AUDIENCES: dict[str, tuple[str, ...]] = {
    cross_system_bus.EVENT_APPLICATION_SUBMITTED: (RECEIVING,),
    cross_system_bus.EVENT_PLACE_OFFERED: (SENDING, LEARNER, GUARDIAN),
    cross_system_bus.EVENT_PLACE_ACCEPTED: (RECEIVING, SENDING),
    cross_system_bus.EVENT_PROGRESSION_REJECTED: (SENDING, LEARNER, GUARDIAN),
    cross_system_bus.EVENT_PROGRESSION_COMPLETED: (
        RECEIVING, SENDING, LEARNER, GUARDIAN),
    cross_system_bus.EVENT_HANDOVER_APPROVED: (RECEIVING,),
    cross_system_bus.EVENT_HANDOVER_ACKNOWLEDGED: (SENDING,),
    cross_system_bus.EVENT_TRANSITION_REMINDER: (REMINDER,),
    cross_system_bus.EVENT_JOURNEY_MERGED: (ENROLLED_ADMINS,),
    cross_system_bus.EVENT_STUDENT_WITHDRAWN: (OPEN_DESTINATIONS, ENROLLED_ADMINS),
}

NOTIFIED_EVENTS: frozenset[str] = frozenset(EVENT_AUDIENCES)

#: Capability classes that count as "staff" for a transfer notice.
STAFF_CAPABILITIES: frozenset[str] = frozenset({"admin", "manager"})

_HIGH_PRIORITY = frozenset({
    cross_system_bus.EVENT_PROGRESSION_REJECTED,
    cross_system_bus.EVENT_STUDENT_WITHDRAWN,
})

# (staff wording, learner/guardian wording). {src}/{dst} are system labels.
_WORDING: dict[str, tuple[str, str]] = {
    cross_system_bus.EVENT_APPLICATION_SUBMITTED: (
        "New application: {src} to {dst}",
        "Your application to {dst} has been received"),
    cross_system_bus.EVENT_PLACE_OFFERED: (
        "Place offered: {src} to {dst}",
        "You have been offered a place at {dst}"),
    cross_system_bus.EVENT_PLACE_ACCEPTED: (
        "Place accepted: {src} to {dst}",
        "Your place at {dst} is confirmed as accepted"),
    cross_system_bus.EVENT_PROGRESSION_REJECTED: (
        "Application not successful: {src} to {dst}",
        "Your application to {dst} was not successful"),
    cross_system_bus.EVENT_PROGRESSION_COMPLETED: (
        "Transfer completed: {src} to {dst}",
        "Your move to {dst} is complete"),
    cross_system_bus.EVENT_HANDOVER_APPROVED: (
        "Handover approved: {src} to {dst}",
        "Information for your move to {dst} has been shared"),
    cross_system_bus.EVENT_HANDOVER_ACKNOWLEDGED: (
        "Handover acknowledged by {dst}",
        "{dst} has received your information"),
    cross_system_bus.EVENT_TRANSITION_REMINDER: (
        "Reminder: transfer {src} to {dst} needs action",
        "Reminder about your move to {dst}"),
    cross_system_bus.EVENT_JOURNEY_MERGED: (
        "Learner records merged",
        "Your learner records have been combined"),
    cross_system_bus.EVENT_STUDENT_WITHDRAWN: (
        "Learner withdrawn from {src}",
        "Withdrawal recorded at {src}"),
}

EmailSender = Callable[[str, str, str], Any]


def _label(system: str | None) -> str:
    if not system:
        return "another institution"
    return SYSTEM_LABELS.get(system, system.replace("_", " ").title())


def _default_email_sender(to: str, subject: str, body: str) -> Any:
    from education_system.platform.integrations.email.email_service import EmailService
    return EmailService().send_email(to, subject, body)


class EventNotifier:
    """Resolve an event's audience and send each member their notice."""

    def __init__(self, db_path: str | None = None, *,
                 email_sender: EmailSender | None = None,
                 preferences: NotificationPreferences | None = None):
        self._db_path = db_path
        self._service = CrossSystemNotificationService(db_path=db_path)
        self._prefs = preferences or NotificationPreferences(db_path)
        self._email_sender = email_sender or _default_email_sender

    # ── Directory lookups ─────────────────────────────────────────────

    def _user_roles(self) -> list[sqlite3.Row]:
        conn = auth_connect(self._db_path)
        try:
            return conn.execute(
                "SELECT u.id AS user_id, u.username, u.email, us.system_key, us.role "
                "FROM users u JOIN user_systems us ON us.user_id = u.id "
                "WHERE u.is_active = 1").fetchall()
        finally:
            conn.close()

    def staff_for(self, system: str | None,
                  roles: Iterable[sqlite3.Row] | None = None) -> set[int]:
        """Transfer-running staff (admin/manager capability) in *system*."""
        if not system:
            return set()
        target = canonical_system_key(system)
        rows = roles if roles is not None else self._user_roles()
        return {
            int(r["user_id"]) for r in rows
            if canonical_system_key(r["system_key"]) == target
            and capability_for(target, r["role"]) in STAFF_CAPABILITIES
        }

    def superadmins(self, roles: Iterable[sqlite3.Row] | None = None) -> set[int]:
        rows = list(roles if roles is not None else self._user_roles())
        by_user: dict[int, list[dict]] = {}
        for r in rows:
            by_user.setdefault(int(r["user_id"]), []).append(
                {"system_key": r["system_key"], "role": r["role"]})
        return {uid for uid, systems in by_user.items()
                if is_superadmin_systems(systems)}

    def _local_ids(self, journey_id: str | None) -> set[tuple[str, str]]:
        """(system, local id) pairs the learner holds, from slots and enrolments."""
        if not journey_id:
            return set()
        pairs: set[tuple[str, str]] = set()
        try:
            from education_system.platform.cross_system import enrolments, identity_service
            journey = identity_service.get(journey_id, db_path=self._db_path) or {}
            for system, (_pk, id_col) in identity_service.SYSTEM_SLOTS.items():
                if journey.get(id_col):
                    pairs.add((system, str(journey[id_col])))
            for row in enrolments.list_enrolments(journey_id, db_path=self._db_path):
                if row.get("local_student_id"):
                    pairs.add((canonical_system_key(row["system"]) or row["system"],
                               str(row["local_student_id"])))
        except Exception:
            logger.debug("Could not resolve local ids for %s", journey_id,
                         exc_info=True)
        return pairs

    def _enrolled_systems(self, journey_id: str | None) -> set[str]:
        if not journey_id:
            return set()
        systems = {s for s, _ in self._local_ids(journey_id)}
        try:
            from education_system.platform.cross_system import enrolments
            systems |= {canonical_system_key(r["system"]) or r["system"]
                        for r in enrolments.open_enrolments(
                            journey_id, db_path=self._db_path)}
        except Exception:
            logger.debug("Open enrolments unavailable for %s", journey_id,
                         exc_info=True)
        return systems

    def learners(self, journey_id: str | None,
                 roles: Iterable[sqlite3.Row] | None = None) -> dict[int, str]:
        """``{user_id: system}`` for the learner's own accounts.

        Explicit links first (``users.journey_id``, set by
        ``identity_service.link_user_account``); then the seeded convention
        that a learner's username is their local student id, for accounts
        nobody has linked yet.
        """
        out: dict[int, str] = {}
        if not journey_id:
            return out
        try:
            from education_system.platform.cross_system import identity_service
            linked = identity_service.users_for_journey(journey_id, db_path=self._db_path)
        except Exception:
            logger.debug("Linked accounts unavailable for %s", journey_id, exc_info=True)
            linked = []
        for user in linked:
            if not user.get("is_active", 1):
                continue
            for entry in user.get("systems") or []:
                system = canonical_system_key(entry.get("system_key"))
                if capability_for(system, entry.get("role")) == "learner":
                    out.setdefault(int(user["id"]), system)
        pairs = self._local_ids(journey_id)
        if not pairs:
            return out
        rows = roles if roles is not None else self._user_roles()
        for r in rows:
            system = canonical_system_key(r["system_key"])
            if (system, str(r["username"])) in pairs and \
                    capability_for(system, r["role"]) == "learner":
                out.setdefault(int(r["user_id"]), system)
        return out

    def guardians(self, journey_id: str | None) -> dict[int, str]:
        """``{parent_user_id: system}`` via ``parent_child_links``."""
        pairs = self._local_ids(journey_id)
        if not pairs:
            return {}
        conn = auth_connect(self._db_path)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='parent_child_links'").fetchone()
            if not exists:
                return {}
            ids = sorted({local for _, local in pairs})
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                "SELECT parent_user_id, child_student_id, child_system_key "
                "FROM parent_child_links WHERE is_active = 1 "
                f"AND child_student_id IN ({placeholders})",  # nosec B608
                ids).fetchall()
        finally:
            conn.close()
        out: dict[int, str] = {}
        for r in rows:
            system = canonical_system_key(r["child_system_key"])
            if (system, str(r["child_student_id"])) in pairs:
                out[int(r["parent_user_id"])] = system
        return out

    def _existing_user(self, user_id: Any) -> int | None:
        if not isinstance(user_id, int):
            return None
        conn = auth_connect(self._db_path)
        try:
            row = conn.execute("SELECT id FROM users WHERE id = ?",
                               (user_id,)).fetchone()
        finally:
            conn.close()
        return int(row["id"]) if row else None

    def _email_of(self, user_id: int) -> str | None:
        conn = auth_connect(self._db_path)
        try:
            row = conn.execute("SELECT email FROM users WHERE id = ?",
                               (user_id,)).fetchone()
        finally:
            conn.close()
        return row["email"] if row and row["email"] else None

    # ── Event context ────────────────────────────────────────────────

    def _context(self, envelope: dict) -> dict:
        payload = envelope.get("payload") or {}
        transition = None
        tid = payload.get("transition_id")
        if tid:
            try:
                from education_system.platform.cross_system import transitions
                transition = transitions.get_transition(tid, db_path=self._db_path)
            except Exception:
                logger.debug("Transition %s unreadable", tid, exc_info=True)
        journey_id = envelope.get("journey_id") or (transition or {}).get("journey_id")
        if journey_id:
            # An event published before a merge still names the duplicate;
            # its accounts and enrolments now hang off the survivor.
            try:
                from education_system.platform.cross_system import identity_service
                journey_id = identity_service.resolve_journey_id(
                    journey_id, db_path=self._db_path) or journey_id
            except Exception:
                logger.debug("Could not resolve journey %s", journey_id, exc_info=True)
        source = ((transition or {}).get("source_system")
                  or envelope.get("source_system"))
        destination = ((transition or {}).get("destination_system")
                       or payload.get("destination_system")
                       or envelope.get("target_system"))
        return {
            "transition": transition,
            "transition_id": tid,
            "journey_id": journey_id,
            "source": canonical_system_key(source) if source else None,
            "destination": canonical_system_key(destination) if destination else None,
            "payload": payload,
        }

    def _open_destinations(self, journey_id: str | None) -> set[str]:
        if not journey_id:
            return set()
        try:
            from education_system.platform.cross_system import transitions
            rows = transitions.list_transitions(journey_id, db_path=self._db_path)
        except Exception:
            return set()
        return {r["destination_system"] for r in rows
                if r.get("status") not in ("completed", "cancelled", "rejected")}

    def recipients(self, envelope: dict) -> dict[int, tuple[str, str]]:
        """``{user_id: (recipient_system, audience)}`` for one event.

        Staff audiences are resolved first, so a user who is both staff at
        the destination and a parent of the learner is addressed as staff.
        """
        event = envelope.get("event_name")
        audiences = EVENT_AUDIENCES.get(event, ())
        if not audiences:
            return {}
        ctx = self._context(envelope)
        roles = self._user_roles()
        out: dict[int, tuple[str, str]] = {}

        def add(users: Iterable[int], system: str | None, audience: str) -> None:
            for uid in users:
                out.setdefault(uid, (system or "platform", audience))

        for audience in audiences:
            if audience == REMINDER:
                awaiting = str(ctx["payload"].get("awaiting") or "both").lower()
                if awaiting in ("source", "sending", "both"):
                    add(self.staff_for(ctx["source"], roles), ctx["source"], SENDING)
                if awaiting in ("destination", "receiving", "both"):
                    add(self.staff_for(ctx["destination"], roles),
                        ctx["destination"], RECEIVING)
            elif audience == RECEIVING:
                add(self.staff_for(ctx["destination"], roles),
                    ctx["destination"], RECEIVING)
            elif audience == SENDING:
                add(self.staff_for(ctx["source"], roles), ctx["source"], SENDING)
            elif audience == OPEN_DESTINATIONS:
                for system in self._open_destinations(ctx["journey_id"]):
                    add(self.staff_for(system, roles), system, RECEIVING)
            elif audience == ENROLLED_ADMINS:
                for system in self._enrolled_systems(ctx["journey_id"]):
                    # The system that withdrew the learner already knows.
                    if event == cross_system_bus.EVENT_STUDENT_WITHDRAWN and \
                            system == ctx["source"]:
                        continue
                    add(self.staff_for(system, roles), system, ENROLLED_ADMINS)
        # Learner and guardian last, so staff addressing wins on overlap.
        if LEARNER in audiences:
            for uid, system in self.learners(ctx["journey_id"], roles).items():
                out.setdefault(uid, (system, LEARNER))
        if GUARDIAN in audiences:
            for uid, system in self.guardians(ctx["journey_id"]).items():
                out.setdefault(uid, (system, GUARDIAN))
        # The person who took the action does not need telling about it.
        actor = envelope.get("actor_user_id")
        if isinstance(actor, int):
            out.pop(actor, None)
        return out

    # ── Compose + send ───────────────────────────────────────────────

    @staticmethod
    def compose(event: str, ctx: dict, audience: str) -> tuple[str, str]:
        staff_text, personal_text = _WORDING.get(
            event, ("Cross-system update: {src} to {dst}", "Update about your journey"))
        template = personal_text if audience in (LEARNER, GUARDIAN) else staff_text
        title = template.format(src=_label(ctx.get("source")),
                                dst=_label(ctx.get("destination")))
        if audience in (LEARNER, GUARDIAN):
            message = "Sign in to see the details."
        else:
            parts = []
            if ctx.get("transition_id"):
                parts.append(f"Transition {ctx['transition_id']}")
            if ctx.get("journey_id"):
                parts.append(f"journey {ctx['journey_id']}")
            status = (ctx.get("transition") or {}).get("status") \
                or ctx["payload"].get("status")
            if status:
                parts.append(f"status {status}")
            message = (", ".join(parts) + ". " if parts else "") + \
                "Open the Transfer Monitor for details."
        return title, message

    def handle(self, envelope: dict) -> int:
        """Notify everyone *envelope* concerns. Returns notifications sent."""
        event = envelope.get("event_name")
        category = EVENT_CATEGORIES.get(event or "")
        if event not in NOTIFIED_EVENTS or not category:
            return 0
        recipients = self.recipients(envelope)
        if not recipients:
            return 0
        ctx = self._context(envelope)
        priority = "high" if event in _HIGH_PRIORITY else "normal"
        actor = self._existing_user(envelope.get("actor_user_id"))
        sender_system = envelope.get("source_system") or "platform"
        sent = 0
        for uid, (system, audience) in sorted(recipients.items()):
            title, message = self.compose(event, ctx, audience)
            for channel in self._prefs.enabled_channels(uid, category):
                result = self._service.send_for_event(
                    envelope["event_id"], actor or uid, sender_system, uid,
                    system, title, message, priority, channel=channel)
                if result is None:
                    continue
                if channel == CHANNEL_EMAIL:
                    self._email(uid, title, message)
                sent += 1
        return sent

    def _email(self, user_id: int, subject: str, body: str) -> None:
        address = self._email_of(user_id)
        if not address:
            return
        try:
            self._email_sender(address, subject, body)
        except Exception:
            # The in-app copy is the record; a mail outage must not fail the
            # bus handler and trigger a redelivery of every other channel.
            logger.warning("Notification email to user %s failed", user_id,
                           exc_info=True)

    def notify_dead_letter(self, details: dict) -> int:
        """Tell platform superadmins that a delivery was abandoned by the bus."""
        key = "dead_letter:{event_id}:{consumer_system}:{consumer_handler}".format(
            **{k: details.get(k) for k in
               ("event_id", "consumer_system", "consumer_handler")})
        title = f"Cross-system delivery failed: {details.get('event_name')}"
        message = (
            f"Handler {details.get('consumer_handler')} in "
            f"{details.get('consumer_system')} gave up after "
            f"{details.get('attempts')} attempt(s) on event "
            f"{details.get('event_id')}. Retry or abandon it from the Event Monitor.")
        sent = 0
        for uid in sorted(self.superadmins()):
            for channel in self._prefs.enabled_channels(uid, "operations"):
                result = self._service.send_for_event(
                    key, uid, "platform", uid, "platform", title, message,
                    "high", channel=channel)
                if result is None:
                    continue
                if channel == CHANNEL_EMAIL:
                    self._email(uid, title, message)
                sent += 1
        return sent


# ---------------------------------------------------------------------------
# Bus wiring
# ---------------------------------------------------------------------------

_registered = False
_alerts_registered = False


def handle_event(envelope: dict) -> None:
    """Bus handler: notify the audience of one event."""
    EventNotifier(cross_system_bus.current_dispatch_db_path()).handle(envelope)


def handle_dead_letter(details: dict) -> None:
    """Delivery-alert adapter: turn a dead letter into a superadmin notice."""
    EventNotifier(details.get("db_path")).notify_dead_letter(details)


def register_consumer() -> None:
    """Subscribe :func:`handle_event` to every notified event. Idempotent."""
    global _registered
    if _registered:
        return
    for name in sorted(NOTIFIED_EVENTS):
        cross_system_bus.subscribe(name, handle_event, handler_name=HANDLER_NAME)
    _registered = True


def register_delivery_alerts() -> None:
    """Route bus dead letters to superadmin notifications. Idempotent."""
    global _alerts_registered
    if _alerts_registered:
        return
    cross_system_bus.subscribe_delivery_alerts(handle_dead_letter)
    _alerts_registered = True


def reset_for_test() -> None:
    global _registered, _alerts_registered
    _registered = False
    _alerts_registered = False


__all__ = [
    "EVENT_AUDIENCES",
    "EventNotifier",
    "HANDLER_NAME",
    "NOTIFIED_EVENTS",
    "handle_dead_letter",
    "handle_event",
    "register_consumer",
    "register_delivery_alerts",
    "reset_for_test",
]
