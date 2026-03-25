"""Real-time notification support via Server-Sent Events (SSE).

Improvement #13: Real-time notifications

Uses SSE instead of WebSocket for simplicity — no extra dependencies required.
Works with any modern browser and Flask.
"""

import json
import logging
import queue
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationBroker:
    """In-memory pub/sub broker for real-time notifications.

    Uses Server-Sent Events (SSE) which works with plain Flask
    without requiring Flask-SocketIO or any WebSocket library.

    Usage:
        broker = NotificationBroker()

        # In a route — subscribe to events
        @app.route("/api/notifications/stream")
        def stream():
            user_id = get_current_user_id()
            return broker.stream(user_id)

        # From anywhere — push a notification
        broker.publish(user_id=123, event="attendance", data={"status": "late"})
    """

    def __init__(self, max_queue_size: int = 100):
        self._subscribers: dict[int, list[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._max_queue_size = max_queue_size

    def subscribe(self, user_id: int) -> queue.Queue:
        """Subscribe to notifications for a user. Returns a Queue."""
        q = queue.Queue(maxsize=self._max_queue_size)
        with self._lock:
            if user_id not in self._subscribers:
                self._subscribers[user_id] = []
            self._subscribers[user_id].append(q)
        logger.debug("User %d subscribed (total: %d)", user_id,
                     len(self._subscribers.get(user_id, [])))
        return q

    def unsubscribe(self, user_id: int, q: queue.Queue) -> None:
        """Remove a subscription."""
        with self._lock:
            if user_id in self._subscribers:
                try:
                    self._subscribers[user_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[user_id]:
                    del self._subscribers[user_id]

    def publish(
        self,
        user_id: int,
        event: str,
        data: dict | str | None = None,
        *,
        broadcast: bool = False,
    ) -> int:
        """Push a notification to a user (or all users if broadcast=True).

        Returns the number of subscribers notified.
        """
        message = {
            "event": event,
            "data": data if isinstance(data, str) else json.dumps(data or {}),
            "timestamp": datetime.now().isoformat(),
        }

        count = 0
        with self._lock:
            targets = (
                list(self._subscribers.values())
                if broadcast
                else [self._subscribers.get(user_id, [])]
            )
            for queues in targets:
                for q in queues:
                    try:
                        q.put_nowait(message)
                        count += 1
                    except queue.Full:
                        logger.warning("Notification queue full for user")

        return count

    def stream(self, user_id: int):
        """Create an SSE response generator for Flask.

        Usage in Flask:
            @app.route("/api/notifications/stream")
            def sse_stream():
                user_id = get_current_user_id()
                return Response(broker.stream(user_id), mimetype="text/event-stream")
        """
        from flask import Response

        def generate():
            q = self.subscribe(user_id)
            try:
                # Send initial keepalive
                yield f"event: connected\ndata: {json.dumps({'user_id': user_id})}\n\n"

                while True:
                    try:
                        msg = q.get(timeout=30)
                        event = msg.get("event", "message")
                        data = msg.get("data", "{}")
                        yield f"event: {event}\ndata: {data}\n\n"
                    except queue.Empty:
                        # Send keepalive ping every 30s
                        yield f"event: ping\ndata: {json.dumps({'time': datetime.now().isoformat()})}\n\n"
            except GeneratorExit:
                self.unsubscribe(user_id, q)

        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def active_subscribers(self) -> dict[int, int]:
        """Return count of active subscribers per user_id."""
        with self._lock:
            return {uid: len(queues) for uid, queues in self._subscribers.items()}


# Global broker instance
notification_broker = NotificationBroker()
