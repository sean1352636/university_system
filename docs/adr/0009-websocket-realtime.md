# 0009 — WebSocket / Socket.IO for Real-Time Features

**Date:** 2026-03-26
**Status:** Proposed

---

## Context

Several platform features would benefit from push-based updates rather than polling:
- **Attendance register**: a teacher marks a student absent and the pastoral dashboard should
  update without a manual refresh
- **Live session monitoring**: the superadmin dashboard already refreshes every 5 seconds via
  `setInterval`; this wastes bandwidth and adds latency
- **Notifications**: email/in-app alerts currently appear only on the next page load
- **Safeguarding alerts**: high-urgency items should appear immediately for the designated
  safeguarding lead

The current architecture has no persistent connection between server and clients. All real-time
simulation is done via polling in the web portal's JavaScript.

## Decision

We propose adding Socket.IO support to the unified Flask server using
[Flask-SocketIO](https://flask-socketio.readthedocs.io/) with `eventlet` as the async worker.

Design:
- **Rooms by system and role**: clients join a room on connection, e.g. `college:attendance`
  or `school:safeguarding:dsls`. The server emits targeted events only to relevant rooms,
  avoiding broadcast storms
- **Auth on connect**: the Socket.IO `connect` event handler validates the JWT from the
  `Authorization` header (or a query-string token for browser clients) using the existing
  `jwt_utils.verify_token()` function; unauthenticated connections are rejected immediately
- **Events emitted by services**: service methods that modify high-priority state (attendance
  marks, safeguarding referrals, session force-logouts) call a thin `emit_event(room, event,
  data)` helper; the helper is a no-op when the SocketIO instance is not initialised (e.g. in
  test mode or CLI usage)
- **Web portal client**: `app.js` connects via `socket.io.min.js` (CDN or self-hosted);
  event handlers update the relevant section of the DOM without a full re-render
- **Graceful degradation**: if the WebSocket handshake fails (e.g. behind a proxy that does
  not support Upgrade), Socket.IO falls back to long-polling automatically

Production deployment would require replacing the standard Flask dev server with
`eventlet.wsgi` or `gunicorn --worker-class eventlet`. The `docker-compose.yml` and nginx
configuration would need corresponding updates (WebSocket proxy headers).

## Consequences

### Positive
- Eliminates polling loops in the web portal; reduces server load and client latency
- Force-logout from the superadmin dashboard takes effect immediately without the 5-second
  polling window
- Safeguarding and medical alerts reach responsible staff instantly

### Negative / Trade-offs
- `eventlet` monkey-patches Python's standard library; this can cause subtle compatibility
  issues with some libraries (notably some versions of `bcrypt` require gevent instead)
- Persistent connections increase memory usage per connected client; the server must be sized
  for concurrent WebSocket connections, not just request rate
- Horizontal scaling requires a message broker (Redis Pub/Sub) so events emitted on one
  worker process are broadcast to clients connected to other workers
- Adds `flask-socketio` and `eventlet` to `requirements.txt` — non-trivial dependencies

### Neutral
- Socket.IO is a superset of WebSockets; using it rather than raw `websockets` gives automatic
  reconnection and room/namespace management at the cost of a larger client-side library
- The tkinter GUI and CLI interfaces are unaffected; real-time features in those interfaces
  would require separate threading work

---

*Depends on: [0001](0001-unified-flask-server.md) (Flask server), [0002](0002-shared-authentication.md) (JWT validation)*
*Related: [0008](0008-graphql-api.md) (GraphQL subscriptions build on WebSockets)*
