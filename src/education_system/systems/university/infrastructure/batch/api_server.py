"""Running the unified REST API from Batch Operations (Automation → Start
API Server).

The server is the platform's own unified API (``python -m education_system
--university --api``: JWT sign-in, CSRF, rate limits, every system's
routes), started as a separate process so it survives the window being
closed and can be stopped again. Only a server this module started is ever
stopped; one started some other way is reported, not touched. Its output
goes to ``var/logs/university/api_server.log``.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess  # nosec B404 - fixed argument list, no shell
import sys
from pathlib import Path


def _dirs():
    from education_system.paths import UNIVERSITY_LOG_DIR, VAR_DIR
    run = VAR_DIR / "run"
    run.mkdir(parents=True, exist_ok=True)
    UNIVERSITY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return run / "university_api.pid", UNIVERSITY_LOG_DIR / "api_server.log"


def config() -> dict:
    """What the server would start with (from the environment, as the
    launcher reads it)."""
    return {"host": os.getenv("API_HOST", "0.0.0.0"), "port": int(os.getenv("API_PORT", "5000")),
            "cors_origins": os.getenv("API_CORS_ORIGINS", "(same origin only)"),
            "rate_limit": os.getenv("API_DEFAULT_RATE_LIMIT", "300/minute"),
            "debug": os.getenv("API_DEBUG", "false"),
            "environment": os.getenv("APP_ENV", "production (unset)"),
            "command": f"{sys.executable} -m education_system --university --api"}


def security() -> list[tuple[str, str]]:
    """The protections the unified server applies to every request."""
    c = config()
    return [("Authentication", "JWT bearer tokens from /api/v1/auth/login (shared auth.db "
                               "accounts, MFA where enrolled); every data route needs one"),
            ("Authorisation", "role and object-scope checks on each route"),
            ("CSRF", "double-submit token for cookie-carrying writes (middleware/csrf)"),
            ("Rate limiting", f"{c['rate_limit']} per user and IP by default "
                              "(API_DEFAULT_RATE_LIMIT), tighter limits on sign-in"),
            ("CORS", f"allowed origins: {c['cors_origins']} (never a wildcard)"),
            ("Debugger", "refused in production (API_DEBUG)"),
            ("Security headers", "set on every response (security_headers)")]


def listening(host="127.0.0.1", port=None) -> bool:
    port = port or config()["port"]
    try:
        with socket.create_connection((host if host not in ("0.0.0.0", "::") else "127.0.0.1",
                                       port), timeout=0.5):
            return True
    except OSError:
        return False


def _pid():
    pid_file, _log = _dirs()
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        pid_file.unlink(missing_ok=True)
        return None
    return pid


def status() -> dict:
    c = config()
    pid = _pid()
    up = listening(port=c["port"])
    if pid and up:
        state = f"running (started here, process {pid})"
    elif up:
        state = "running (started outside Batch Operations; not managed here)"
    elif pid:
        state = f"starting (process {pid})"
    else:
        state = "stopped"
    return {"state": state, "managed": bool(pid), "listening": up, "pid": pid, **c,
            "url": f"http://localhost:{c['port']}/", "health":
            f"http://localhost:{c['port']}/api/v1/health"}


def start() -> dict:
    """Start the unified API in its own process. Refuses when something is
    already listening on the port."""
    c = config()
    if listening(port=c["port"]):
        raise ValueError(f"Something is already listening on port {c['port']}")
    pid_file, log = _dirs()
    handle = open(log, "a", encoding="utf-8")  # noqa: SIM115 - handed to the child
    proc = subprocess.Popen(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-m", "education_system", "--university", "--api"],
        stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True, env=dict(os.environ))
    handle.close()
    pid_file.write_text(str(proc.pid))
    return status()


def stop() -> dict:
    """Stop the server this module started (never another one)."""
    pid = _pid()
    if not pid:
        raise ValueError("No API server started from here is running")
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        os.kill(pid, signal.SIGTERM)
    _dirs()[0].unlink(missing_ok=True)
    return status()


def log_tail(lines=200) -> str:
    _pid_file, log = _dirs()
    if not Path(log).exists():
        return "(the server has not been started from here yet)"
    with open(log, encoding="utf-8", errors="replace") as handle:
        return "".join(handle.readlines()[-int(lines):])


def health(timeout=2.0) -> dict | None:
    """The running server's own health report, or ``None``."""
    import json
    import urllib.request
    url = status()["health"]
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310 - localhost
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def endpoints() -> list[tuple[str, str]]:
    """Every route the unified server mounts (builds the app in this
    process; takes a few seconds)."""
    from education_system.platform.delivery.api.unified_server import create_unified_app
    app = create_unified_app()
    found = []
    for rule in app.url_map.iter_rules():
        methods = ",".join(sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")))
        found.append((str(rule.rule), methods))
    return sorted(found)
