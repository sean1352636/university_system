"""Socket.IO namespaces, one class each.

The namespaces were previously handler functions registered inline in the
server module, which made it hard to see what a namespace exposed or to
authenticate one without touching the others. A class per namespace gives
each one an obvious surface and a single place to check credentials.

Namespaces mirror the notification domains already in use:
``/notifications``, ``/chat`` and ``/presence``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from flask_socketio import Namespace, emit
except Exception:  # pragma: no cover - optional dependency
    Namespace = object  # type: ignore[assignment,misc]

    def emit(*_args, **_kwargs):  # type: ignore[misc]
        raise RuntimeError("flask_socketio is not installed")


class AuthenticatedNamespace(Namespace):
    """Base class: refuse a connection that carries no valid token.

    A websocket bypasses the HTTP middleware chain entirely, so the token
    check that ``before_request`` performs for REST routes has to be done
    again here. Returning False from ``on_connect`` rejects the socket.
    """

    name = "/"

    def _authenticate(self, auth):
        token = None
        if isinstance(auth, dict):
            token = auth.get("token")
        if not token:
            from flask import request
            header = request.args.get("token") or ""
            token = header or None
        if not token:
            return None
        try:
            from education_system.platform.delivery.api.security.authentication import (
                decode_token,
            )
            return decode_token(token)
        except Exception:
            logger.info("Rejected %s socket: bad token", self.name)
            return None

    def on_connect(self, auth=None):
        user = self._authenticate(auth)
        if user is None:
            return False
        from flask import g
        g.socket_user = user
        logger.debug("%s socket connected: %s", self.name, user.get("username"))
        return True

    def on_disconnect(self):
        logger.debug("%s socket disconnected", self.name)


class NotificationsNamespace(AuthenticatedNamespace):
    """Server-pushed notifications for the signed-in user."""
    name = "/notifications"

    def on_subscribe(self, data):
        emit("subscribed", {"channel": (data or {}).get("channel", "all")})


class ChatNamespace(AuthenticatedNamespace):
    """Direct and group messaging."""
    name = "/chat"

    def on_message(self, data):
        emit("message", data, broadcast=True, include_self=False)


class PresenceNamespace(AuthenticatedNamespace):
    """Who is currently online."""
    name = "/presence"

    def on_ping_presence(self, _data=None):
        emit("presence", {"status": "online"})


class CatalogueNamespace(AuthenticatedNamespace):
    """Live catalogue changes, so an open page reflects a desktop edit.

    The GUI and CLI already publish ``course.changed`` through the in-process
    event bus whenever a course is created, edited, archived or deleted -
    ``CourseLifecycleService`` does it for all three adapters. Bridging that
    onto a namespace is what turns it into something a browser can see,
    instead of a signal only other Tk windows in the same process receive.
    """
    name = "/catalogue"

    def on_subscribe(self, _data=None):
        emit("subscribed", {"namespace": self.name})


#: Registered by ``socketio.py``.
ALL_NAMESPACES = (NotificationsNamespace, ChatNamespace, PresenceNamespace,
                  CatalogueNamespace)


def register_namespaces(socketio) -> list[str]:
    """Attach every namespace to *socketio*. Returns the paths attached."""
    attached = []
    for cls in ALL_NAMESPACES:
        try:
            socketio.on_namespace(cls(cls.name))
            attached.append(cls.name)
        except Exception as exc:
            logger.error("Could not register namespace %s: %s", cls.name, exc)
    logger.info("Socket.IO namespaces: %s", ", ".join(attached) or "none")
    return attached


def bridge_domain_events(socketio) -> bool:
    """Forward in-process domain events onto the catalogue namespace.

    Best-effort: a missing event bus leaves the namespaces working, just
    without live pushes. Subscribed rather than polled, so a course edited in
    the desktop app reaches an open portal page without a refresh.
    """
    try:
        from education_system.systems.university.infrastructure.event_bus import (
            EVENT_COURSE_CHANGED,
            subscribe,
        )
    except Exception:
        logger.info("Event bus unavailable; catalogue pushes disabled")
        return False

    def _forward(**payload):
        try:
            socketio.emit("course.changed", payload,
                          namespace=CatalogueNamespace.name)
        except Exception:
            logger.debug("could not forward course.changed", exc_info=True)

    try:
        subscribe(EVENT_COURSE_CHANGED, _forward)
    except Exception:
        logger.warning("could not subscribe to %s", EVENT_COURSE_CHANGED,
                       exc_info=True)
        return False
    logger.info("Bridged course.changed onto %s", CatalogueNamespace.name)
    return True


__all__ = ["AuthenticatedNamespace", "NotificationsNamespace", "ChatNamespace",
           "PresenceNamespace", "CatalogueNamespace", "ALL_NAMESPACES",
           "bridge_domain_events", "register_namespaces"]
