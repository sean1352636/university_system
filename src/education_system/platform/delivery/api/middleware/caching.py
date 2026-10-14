"""HTTP caching utilities for API responses.

Medium Priority #7: Cache-Control, ETag, and Last-Modified headers.

Usage in route handlers:
    from education_system.platform.delivery.api.caching import cache_control, etag_response

    @app.route("/api/v1/college/courses")
    @cache_control(max_age=300, private=True)
    def list_courses():
        ...

    @app.route("/api/v1/college/timetable/<student_id>")
    def get_timetable(student_id):
        data = service.get_timetable(student_id)
        return etag_response(data)

Or register caching globally for GET endpoints:
    from education_system.platform.delivery.api.caching import register_caching_middleware
    register_caching_middleware(app)
"""

import hashlib
import json
import functools

from flask import request, make_response, jsonify


def cache_control(max_age: int = 0, private: bool = True,
                  no_store: bool = False, must_revalidate: bool = True):
    """Decorator to add Cache-Control headers to a route.

    Args:
        max_age: Seconds the response can be cached (0 = no cache)
        private: If True, response is for a single user (not shared caches)
        no_store: If True, response must not be stored at all
        must_revalidate: If True, stale responses must be revalidated
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            response = make_response(f(*args, **kwargs))

            if no_store:
                response.headers["Cache-Control"] = "no-store"
            else:
                parts = []
                parts.append("private" if private else "public")
                parts.append(f"max-age={max_age}")
                if must_revalidate:
                    parts.append("must-revalidate")
                response.headers["Cache-Control"] = ", ".join(parts)

            return response
        return decorated
    return decorator


def etag_response(data, status_code: int = 200):
    """Create a JSON response with an ETag header.

    Automatically handles If-None-Match for conditional requests,
    returning 304 Not Modified when the content hasn't changed.

    Args:
        data: Dict/list to serialize as JSON
        status_code: HTTP status code for the response

    Returns:
        Flask response with ETag header, or 304 if unchanged
    """
    body = json.dumps(data, sort_keys=True, default=str)
    etag = hashlib.sha256(body.encode()).hexdigest()[:32]
    etag_value = f'"{etag}"'

    # Check If-None-Match
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match and if_none_match.strip('" ') == etag:
        response = make_response("", 304)
        response.headers["ETag"] = etag_value
        return response

    response = make_response(body, status_code)
    response.headers["Content-Type"] = "application/json"
    response.headers["ETag"] = etag_value
    return response


def register_caching_middleware(app, default_max_age: int = 0):
    """Register global caching middleware on a Flask app.

    Adds sensible Cache-Control defaults:
    - GET requests: private, max-age as specified
    - Mutating requests (POST/PUT/DELETE): no-store
    - Health check endpoints: short cache (10s)
    """

    @app.after_request
    def add_cache_headers(response):
        # Don't override if already set by a route decorator
        if "Cache-Control" in response.headers:
            return response

        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            response.headers["Cache-Control"] = "no-store"
        elif request.path.startswith("/api") and request.path.endswith("/health"):
            response.headers["Cache-Control"] = "public, max-age=10"
        elif request.method == "GET" and response.status_code == 200:
            if default_max_age > 0:
                response.headers["Cache-Control"] = f"private, max-age={default_max_age}, must-revalidate"
            else:
                response.headers["Cache-Control"] = "private, no-cache"

        # Vary on Authorization so caches don't mix user responses
        if request.headers.get("Authorization"):
            response.headers["Vary"] = "Authorization, Accept"

        return response
