"""WebSocket / Socket.IO integration for the Education System.

Provides real-time features: notifications, chat, and presence across all
four education sub-systems (university, college, secondary school, primary).

Usage
-----
    from education_system.platform.delivery.api.websocket_server import init_socketio, socketio
    socketio = init_socketio(app)
    # Then run with: socketio.run(app, ...)
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional import – graceful fallback if flask-socketio is not installed
# ---------------------------------------------------------------------------
try:
    from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, disconnect
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    logger.warning("flask-socketio not installed – WebSocket features disabled")

# Module-level singleton so helpers can reference it without circular imports
socketio: "SocketIO | None" = None

# Track online users:  {user_id: {sid: ..., system_key: ..., role: ..., joined: ...}}
_online_users: dict[int, dict] = {}
# Reverse map:        {sid: user_id}
_sid_to_user: dict[str, int] = {}


# ---------------------------------------------------------------------------
# JWT validation helper
# ---------------------------------------------------------------------------
def _validate_token(token: str) -> dict | None:
    """Decode a JWT access token and return the payload, or None on failure."""
    try:
        from education_system.platform.delivery.api.auth import _jwt_manager  # type: ignore[attr-defined]
        if _jwt_manager is None:
            return None
        return _jwt_manager.decode(token)
    except Exception:
        pass
    # Fallback: try raw PyJWT with env secret
    try:
        import jwt as pyjwt
        secret = os.getenv("JWT_SECRET_KEY", "")
        if secret:
            return pyjwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------
def emit_to_user(user_id: int, event: str, data: dict) -> bool:
    """Emit an event to a specific connected user (all their sessions)."""
    if not SOCKETIO_AVAILABLE or socketio is None:
        return False
    if user_id not in _online_users:
        return False
    sid = _online_users[user_id].get("sid")
    if sid:
        socketio.emit(event, data, room=sid)
        return True
    return False


def emit_to_room(room: str, event: str, data: dict) -> None:
    """Emit an event to every client in a named room."""
    if not SOCKETIO_AVAILABLE or socketio is None:
        return
    socketio.emit(event, data, room=room)


def broadcast_notification(system: str, data: dict) -> None:
    """Broadcast a notification to all users in a system room."""
    emit_to_room(f"system:{system}", "notification", data)


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------
if SOCKETIO_AVAILABLE:

    class NotificationsNamespace(Namespace):
        """Namespace for server-push notifications (/notifications)."""

        def on_connect(self, auth):
            from flask import request
            token = (
                (auth or {}).get("token")
                or request.args.get("token")
                or (request.headers.get("Authorization", "").replace("Bearer ", "") or None)
            )
            if not token:
                logger.warning("WS /notifications: missing auth from %s", request.sid)  # nosemgrep: python-logger-credential-disclosure
                return False  # reject
            payload = _validate_token(token)
            if payload is None:
                logger.warning("WS /notifications: invalid auth from %s", request.sid)  # nosemgrep: python-logger-credential-disclosure
                return False

            sid = request.sid
            user_id = int(payload.get("sub", 0))
            system_key = payload.get("system_key", "unknown")
            role = payload.get("role", "student")

            _online_users[user_id] = {
                "sid": sid, "system_key": system_key, "role": role,
                "joined": datetime.utcnow().isoformat(),
            }
            _sid_to_user[sid] = user_id

            # Auto-join system and role rooms
            join_room(f"system:{system_key}")
            join_room(f"{system_key}:{role}")
            join_room(f"user:{user_id}")

            logger.info("WS /notifications connected: user_id=%s system=%s role=%s",
                        user_id, system_key, role)
            emit("connected", {
                "user_id": user_id,
                "system_key": system_key,
                "role": role,
                "rooms": [f"system:{system_key}", f"{system_key}:{role}", f"user:{user_id}"],
            })

        def on_disconnect(self):
            from flask import request
            sid = request.sid
            user_id = _sid_to_user.pop(sid, None)
            if user_id and user_id in _online_users:
                info = _online_users.pop(user_id)
                logger.info("WS /notifications disconnected: user_id=%s", user_id)
                # Notify presence namespace of offline status
                socketio.emit("presence_update", {
                    "user_id": user_id, "status": "offline",
                    "system_key": info.get("system_key"),
                }, namespace="/presence")

        def on_join_room(self, data):
            room = data.get("room")
            if room:
                join_room(room)
                emit("joined_room", {"room": room})

        def on_leave_room(self, data):
            room = data.get("room")
            if room:
                leave_room(room)
                emit("left_room", {"room": room})

        def on_send_notification(self, data):
            """Server-side trigger: push a notification to a user or room."""
            target_user = data.get("user_id")
            target_room = data.get("room")
            payload = data.get("payload", data)
            if target_user:
                emit_to_user(int(target_user), "notification", payload)
            elif target_room:
                emit_to_room(target_room, "notification", payload)

    class ChatNamespace(Namespace):
        """Namespace for bidirectional chat (/chat)."""

        def on_connect(self, auth):
            from flask import request
            token = (
                (auth or {}).get("token")
                or request.args.get("token")
                or (request.headers.get("Authorization", "").replace("Bearer ", "") or None)
            )
            if not token:
                return False
            payload = _validate_token(token)
            if payload is None:
                return False
            logger.info("WS /chat connected: user_id=%s", payload.get("sub"))
            emit("connected", {"status": "ok", "user_id": payload.get("sub")})

        def on_disconnect(self):
            from flask import request
            logger.info("WS /chat disconnected: sid=%s", request.sid)

        def on_join_room(self, data):
            room_id = data.get("room_id")
            if room_id:
                join_room(f"chat:{room_id}")
                emit("joined_room", {"room_id": room_id})

        def on_leave_room(self, data):
            room_id = data.get("room_id")
            if room_id:
                leave_room(f"chat:{room_id}")
                emit("left_room", {"room_id": room_id})

        def on_chat_message(self, data):
            """Client sends a message; broadcast to room and persist via ChatService."""
            from flask import request
            sid = request.sid
            user_id = _sid_to_user.get(sid)
            room_id = data.get("room_id")
            text = data.get("message", "").strip()
            if not room_id or not text:
                emit("error", {"message": "room_id and message are required"})
                return
            # Persist the message
            try:
                from education_system.platform.services.chat_service import ChatService
                from education_system.platform.identity.auth.db import AUTH_DB_FILE
                svc = ChatService(str(AUTH_DB_FILE))
                msg = svc.send_message(
                    room_id=int(room_id),
                    sender_id=user_id,
                    message_text=text,
                )
                payload = {
                    "id": msg["id"],
                    "room_id": room_id,
                    "sender_id": user_id,
                    "message": text,
                    "created_at": msg["created_at"],
                }
            except Exception as exc:
                logger.warning("Chat persist failed: %s", exc)
                payload = {
                    "room_id": room_id,
                    "sender_id": user_id,
                    "message": text,
                    "created_at": datetime.utcnow().isoformat(),
                }
            # Broadcast to all participants in the chat room
            socketio.emit("chat_message", payload, room=f"chat:{room_id}", namespace="/chat")

        def on_typing(self, data):
            """Broadcast typing indicator to other room participants."""
            from flask import request
            sid = request.sid
            user_id = _sid_to_user.get(sid)
            room_id = data.get("room_id")
            is_typing = bool(data.get("typing", True))
            if room_id:
                socketio.emit("typing", {
                    "room_id": room_id, "user_id": user_id, "typing": is_typing,
                }, room=f"chat:{room_id}", namespace="/chat", skip_sid=sid)

    class PresenceNamespace(Namespace):
        """Namespace for user presence tracking (/presence)."""

        def on_connect(self, auth):
            from flask import request
            token = (
                (auth or {}).get("token")
                or request.args.get("token")
                or (request.headers.get("Authorization", "").replace("Bearer ", "") or None)
            )
            if not token:
                return False
            payload = _validate_token(token)
            if payload is None:
                return False
            user_id = int(payload.get("sub", 0))
            system_key = payload.get("system_key", "unknown")
            # Broadcast online status to the system room
            socketio.emit("presence_update", {
                "user_id": user_id, "status": "online", "system_key": system_key,
            }, room=f"system:{system_key}", namespace="/presence")
            join_room(f"system:{system_key}")
            emit("connected", {"user_id": user_id, "status": "online"})
            logger.info("WS /presence connected: user_id=%s", user_id)

        def on_disconnect(self):
            from flask import request
            sid = request.sid
            user_id = _sid_to_user.get(sid)
            if user_id and user_id in _online_users:
                system_key = _online_users[user_id].get("system_key", "unknown")
                socketio.emit("presence_update", {
                    "user_id": user_id, "status": "offline", "system_key": system_key,
                }, room=f"system:{system_key}", namespace="/presence")
            logger.info("WS /presence disconnected: sid=%s", sid)

        def on_presence_update(self, data):
            """Client pushes its own status (away, busy, online, etc.)."""
            from flask import request
            sid = request.sid
            user_id = _sid_to_user.get(sid)
            status = data.get("status", "online")
            if user_id and user_id in _online_users:
                system_key = _online_users[user_id].get("system_key", "unknown")
                socketio.emit("presence_update", {
                    "user_id": user_id, "status": status, "system_key": system_key,
                }, room=f"system:{system_key}", namespace="/presence", skip_sid=sid)

        def on_get_online_users(self, data):
            """Return list of currently online user IDs."""
            emit("online_users", {"user_ids": list(_online_users.keys())})


# ---------------------------------------------------------------------------
# Init function
# ---------------------------------------------------------------------------
def init_socketio(app) -> "SocketIO | None":
    """Initialise and attach Socket.IO to the Flask app.

    Returns the SocketIO instance (or None if flask-socketio is not installed).
    """
    global socketio

    if not SOCKETIO_AVAILABLE:
        logger.warning("init_socketio: flask-socketio not available – skipping")
        return None

    cors_origins = os.getenv("API_CORS_ORIGINS", "*")
    if cors_origins != "*":
        cors_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

    socketio = SocketIO(
        app,
        cors_allowed_origins=cors_origins,
        async_mode="eventlet",
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
    )

    # Register namespaces
    socketio.on_namespace(NotificationsNamespace("/notifications"))
    socketio.on_namespace(ChatNamespace("/chat"))
    socketio.on_namespace(PresenceNamespace("/presence"))

    logger.info("Socket.IO initialised with namespaces: /notifications, /chat, /presence")
    return socketio


# Keep a module-level ref for the helper functions below
_socketio = None


def _get_socketio():
    """Return the active SocketIO instance."""
    global _socketio
    if _socketio is None:
        _socketio = socketio
    return _socketio


def broadcast_system_alert(system_key: str, title: str, message: str,
                           severity: str = "info"):
    """Broadcast a system-wide alert to all connected users in a system."""
    sio = _get_socketio()
    if sio is None:
        return
    sio.emit("system_alert", {
        "system_key": system_key,
        "title": title,
        "message": message,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat(),
    }, namespace="/notifications", room=system_key)


def emit_grade_update(student_user_id: int, course: str, grade: str,
                      system_key: str = "university"):
    """Notify a student in real time that a grade has been posted."""
    emit_to_user(student_user_id, "grade_update", {
        "course": course,
        "grade": grade,
        "system_key": system_key,
        "timestamp": datetime.utcnow().isoformat(),
    })


def emit_attendance_alert(student_user_id: int, date: str, status: str,
                          system_key: str = "university"):
    """Notify a student/parent about an attendance mark."""
    emit_to_user(student_user_id, "attendance_alert", {
        "date": date,
        "status": status,
        "system_key": system_key,
        "timestamp": datetime.utcnow().isoformat(),
    })


def emit_early_warning(staff_user_id: int, student_name: str,
                       risk_level: str, system_key: str):
    """Notify staff about a student early warning flag."""
    emit_to_user(staff_user_id, "early_warning", {
        "student_name": student_name,
        "risk_level": risk_level,
        "system_key": system_key,
        "timestamp": datetime.utcnow().isoformat(),
    })
