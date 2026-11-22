"""Facts about the university REST API for the admin "API Management" window.

Nothing here serves requests or starts the API's background jobs:

* :func:`university_routes` builds a bare Flask app, mounts only the
  university blueprints the way the unified server does (through the API
  registry's ``Mount`` and ``reprefix``), and reads its ``url_map``. Auth and
  rate-limit gates are found by walking each view's ``__wrapped__`` chain to
  the decorators that produced it.
* :func:`request_log_stats` counts the request lines the API's request
  middleware writes to the university application logs. That is the only
  per-request record the API keeps (its Prometheus counters live in the
  server process's memory).
* :func:`security_settings` reports the settings the API reads from the
  environment, resolved the same way the server resolves them. They describe
  *this* process's environment; an API server started with different
  variables will differ.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

_ROUTE_CACHE: dict | None = None


# ── Routes ────────────────────────────────────────────────────────────────

def _gates(view) -> tuple[list[str], str | None]:
    """(auth gates, per-route rate limit) found on *view*'s decorator chain."""
    gates: list[str] = []
    rate = None
    fn = view
    seen = 0
    while fn is not None and seen < 20:
        seen += 1
        code = getattr(fn, "__code__", None)
        if code is not None:
            filename = code.co_filename.replace("\\", "/")
            qual = getattr(code, "co_qualname", code.co_name)
            if filename.endswith(("security/principals.py", "security/authentication.py",
                                  "api/auth.py", "university/auth.py")):
                label = "JWT"
                for name, text in (("staff_required", "staff"), ("require_staff", "staff"),
                                   ("scoped_to", "object scope"),
                                   ("authorize_object", "object scope"),
                                   ("role_required", "role"), ("permission_required", "permission")):
                    if name in qual:
                        label = f"JWT + {text}"
                        break
                if label not in gates:
                    gates.append(label)
            elif filename.endswith("security/api_keys.py"):
                kind = "JWT or API key" if "api_key_or_token" in qual else "API key"
                if kind not in gates:
                    gates.append(kind)
            elif filename.endswith("middleware/rate_limit.py") and "limit" in qual:
                cells = dict(zip(code.co_freevars, fn.__closure__ or ()))
                try:
                    count = cells["count"].cell_contents
                    period = cells["period"].cell_contents
                    unit = {1: "second", 60: "minute", 3600: "hour", 86400: "day"}.get(
                        int(period), f"{period}s")
                    rate = f"{count}/{unit}"
                except (KeyError, ValueError, TypeError):
                    rate = "per-route limit"
        fn = getattr(fn, "__wrapped__", None)
    # "JWT + staff" already implies the token check.
    if any(g.startswith("JWT + ") for g in gates):
        gates = [g for g in gates if g != "JWT"]
    return gates, rate


def _original(view):
    fn = view
    while getattr(fn, "__wrapped__", None) is not None:
        fn = fn.__wrapped__
    return fn


def university_routes(refresh: bool = False) -> dict:
    """``{"routes": [...], "error": str|None, "blueprints": int}``.

    Each route: ``methods``, ``rule``, ``endpoint``, ``description``,
    ``docstring``, ``module``, ``auth`` (text), ``rate_limit``,
    ``takes_object_id``.
    """
    global _ROUTE_CACHE
    if _ROUTE_CACHE is not None and not refresh:
        return _ROUTE_CACHE

    from flask import Flask
    from education_system.platform.delivery.api import registry
    from education_system.platform.delivery.api.versioning import reprefix

    result: dict = {"routes": [], "error": None, "blueprints": 0}
    mount = registry.get_mount("university")
    if mount is None:
        result["error"] = "the API registry has no university entry"
        _ROUTE_CACHE = result
        return result
    blueprints = mount.load()
    if mount.error:
        result["error"] = mount.error
    app = Flask("university_route_inventory")
    for bp in blueprints:
        try:
            app.register_blueprint(bp, url_prefix=reprefix(bp.url_prefix, mount.key),
                                   name=f"{mount.key}_{bp.name}")
            result["blueprints"] += 1
        except Exception as exc:  # a duplicate or broken blueprint
            result["error"] = (result["error"] or "") + f" {bp.name}: {exc}"

    guarded = {name for name, funcs in app.before_request_funcs.items() if name and funcs}
    try:
        from education_system.platform.delivery.api.middleware.rate_limit import (
            _GLOBAL_LIMIT_EXEMPT_PREFIXES as exempt,
        )
    except ImportError:
        exempt = ()
    default_rate = security_settings()["rate_limit"]

    for rule in sorted(app.url_map.iter_rules(), key=lambda r: (str(r.rule), r.endpoint)):
        if rule.endpoint == "static":
            continue
        view = app.view_functions.get(rule.endpoint)
        gates, rate = _gates(view) if view else ([], None)
        blueprint = rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
        if blueprint in guarded:
            gates.append("blueprint guard")
        original = _original(view) if view else None
        doc = (getattr(original, "__doc__", None) or "").strip()
        rule_text = str(rule.rule)
        if rate is None:
            rate = ("exempt" if any(rule_text.startswith(p) for p in exempt)
                    else f"global {default_rate}" if default_rate != "off" else "none")
        result["routes"].append({
            "methods": sorted(rule.methods - {"HEAD", "OPTIONS"}),
            "rule": rule_text,
            "endpoint": rule.endpoint,
            "description": doc.splitlines()[0] if doc else "",
            "docstring": doc,
            "module": getattr(original, "__module__", ""),
            "auth": ", ".join(gates) if gates else "none found",
            "rate_limit": rate,
            "takes_object_id": bool(rule.arguments),
        })
    _ROUTE_CACHE = result
    return result


# ── Request log ───────────────────────────────────────────────────────────

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[,.]\d+ - \w+ - "
    r"education_system\.platform\.delivery\.api\.middleware[\w.]* - "
    r"(?P<method>[A-Z]+) (?P<path>/\S*) (?P<status>\d{3}) (?P<ms>\d+)ms")
_ID_RE = re.compile(r"/(\d+|[0-9a-f]{8}-[0-9a-f-]{27,}|[A-Z]{1,4}\d{3,})(?=/|$)")


def _log_files() -> list[Path]:
    from education_system.paths import UNIVERSITY_LOG_DIR
    folder = Path(UNIVERSITY_LOG_DIR)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and (p.name == "app.log" or p.name.startswith("app.")))


def request_log_stats(days: int | None = None) -> dict:
    """Counts from the API request lines in the university logs.

    Returns totals, per-status and per-endpoint counts (identifiers folded to
    ``{id}``), response-time figures, the first/last request seen and the
    files read. ``total`` is 0 when nothing was recorded.
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S") if days else None
    day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    statuses: Counter = Counter()
    endpoints: Counter = Counter()
    university: Counter = Counter()
    hours: Counter = Counter()
    times: list[int] = []
    total = last_24h = 0
    first = last = None
    files = _log_files()
    for path in files:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if "delivery.api.middleware" not in line:
                        continue
                    m = _LINE_RE.match(line)
                    if not m:
                        continue
                    ts = m["ts"]
                    if cutoff and ts < cutoff:
                        continue
                    total += 1
                    if ts >= day_ago:
                        last_24h += 1
                    first = ts if first is None or ts < first else first
                    last = ts if last is None or ts > last else last
                    statuses[m["status"]] += 1
                    key = f"{m['method']} {_ID_RE.sub('/{id}', m['path'])}"
                    endpoints[key] += 1
                    if m["path"].startswith("/api/v1/university"):
                        university[key] += 1
                    hours[ts[11:13]] += 1
                    times.append(int(m["ms"]))
        except OSError:
            continue
    times.sort()

    def pct(p):
        return times[min(len(times) - 1, int(len(times) * p))] if times else None

    errors_5xx = sum(n for s, n in statuses.items() if s.startswith("5"))
    errors_4xx = sum(n for s, n in statuses.items() if s.startswith("4"))
    return {
        "total": total,
        "last_24h": last_24h,
        "first": first,
        "last": last,
        "statuses": dict(sorted(statuses.items())),
        "errors_4xx": errors_4xx,
        "errors_5xx": errors_5xx,
        "error_rate": (100.0 * errors_5xx / total) if total else None,
        "top_endpoints": endpoints.most_common(15),
        "top_university": university.most_common(10),
        "university_total": sum(university.values()),
        "by_hour": dict(sorted(hours.items())),
        "avg_ms": (sum(times) / len(times)) if times else None,
        "median_ms": pct(0.5),
        "p95_ms": pct(0.95),
        "max_ms": times[-1] if times else None,
        "files": [str(p) for p in files],
    }


# ── Security settings ─────────────────────────────────────────────────────

def security_settings() -> dict:
    """The API's security settings as this process's environment resolves them."""
    env = os.environ
    app_env = env.get("APP_ENV", "production").strip().lower()
    is_dev = app_env in ("development", "dev", "local", "test")

    rate = env.get("API_DEFAULT_RATE_LIMIT", "300/minute").strip()
    rate_text = "off" if rate.lower() in ("", "off", "0", "none") else rate

    origins = [o.strip() for o in env.get("API_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:
        cors = ", ".join(origins)
    elif is_dev:
        cors = "localhost only (development default: ports 3000 and 5000)"
    else:
        cors = "not set - the API refuses to start in production without API_CORS_ORIGINS"

    try:
        from education_system.platform.delivery.api.security import authentication as _auth
        access_hours = _auth._JWT_EXPIRY_HOURS
        refresh_days = _auth._JWT_REFRESH_DAYS
    except Exception:
        access_hours = int(env.get("JWT_EXPIRY_HOURS", "24"))
        refresh_days = int(env.get("JWT_REFRESH_DAYS", "7"))

    return {
        "app_env": app_env or "production",
        "rate_limit": rate_text,
        "cors": cors,
        "jwt_access_hours": access_hours,
        "jwt_refresh_days": refresh_days,
        "jwt_secret_set": bool(env.get("JWT_SECRET_KEY")),
        "api_secret_set": bool(env.get("API_SECRET_KEY")),
        "api_key_pepper_set": bool(env.get("API_KEY_PEPPER")),
        "max_content_mb": int(env.get("API_MAX_CONTENT_LENGTH", 16 * 1024 * 1024)) / (1024 * 1024),
        "debug": env.get("API_DEBUG", "false").lower() == "true",
        "host": env.get("API_HOST", "0.0.0.0"),
        "port": int(env.get("API_PORT", "5000")),
        "dev_mode": is_dev,
    }


def recent_security_events(limit: int = 60) -> list[dict]:
    """Authentication warnings from the audit stores (failed logins etc.)."""
    from education_system.systems.university.infrastructure.security.audit_log_reader import (
        read_audit_entries,
    )
    return read_audit_entries(category="Authentication", level="WARNING", limit=limit)
