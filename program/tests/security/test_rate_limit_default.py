"""A global default rate limit must throttle every endpoint (task 16).

Endpoints without an explicit @limit decorator still get a per-user+IP DoS
floor; health/metrics are exempt so monitoring is not throttled.
"""

from __future__ import annotations

import os

import pytest
from flask import Flask, jsonify

from education_system.platform.delivery.api.rate_limiter import RateLimiter

pytestmark = pytest.mark.security


def _app(rate="3/minute"):
    os.environ["API_DEFAULT_RATE_LIMIT"] = rate
    app = Flask(__name__)
    app.config["TESTING"] = False  # limiter no-ops under TESTING
    RateLimiter().init_app(app)

    @app.route("/api/v1/university/thing")
    def thing():
        return jsonify(ok=True)

    @app.route("/api/v1/health")
    def health():
        return jsonify(ok=True)

    return app


def test_endpoint_is_throttled_past_the_default():
    c = _app("3/minute").test_client()
    codes = [c.get("/api/v1/university/thing").status_code for _ in range(5)]
    assert codes.count(200) == 3
    assert codes.count(429) == 2


def test_health_is_exempt():
    c = _app("3/minute").test_client()
    codes = [c.get("/api/v1/health").status_code for _ in range(10)]
    assert 429 not in codes


def test_off_disables_global_limit():
    c = _app("off").test_client()
    codes = [c.get("/api/v1/university/thing").status_code for _ in range(10)]
    assert 429 not in codes
