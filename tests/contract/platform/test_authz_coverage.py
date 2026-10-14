"""Every mounted route must be gated, and the IDOR backlog may only shrink.

Two separate guarantees:

* **Authentication** — every mounted route requires a token. No exceptions
  list: an unauthenticated route is a bug, not a backlog item.
* **Authorization** — every route that addresses a specific object (i.e. has
  a path parameter) must also prove the caller may touch *that* object.
  Hundreds of routes predate that rule, so they sit in a baseline file that
  can only get smaller.

The enumeration comes from ``registry.py``, not from grepping decorator
names, so a route that is mounted is checked — there is nowhere to hide.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from authz_helpers import (  # noqa: E402  (tests/contract/platform on sys.path)
    build_app,
    is_authenticated,
    is_authorized,
    object_scoped_rules,
    route_id,
)

BASELINE_PATH = Path(__file__).with_name("authz_baseline.json")

#: Routes that are unauthenticated *by design*, each with the reason.
#: Being on this list is a deliberate declaration, not an oversight — a public
#: route must also be rate limited, which is asserted below.
PUBLIC_ROUTES = {
    "GET /api/v1/university/blockchain/credentials/verify/<string:credential_hash>":
        "Public credential verification: an employer checking a degree should "
        "not need a university login. Returns a redacted public view.",
    "GET /api/v1/university/credentials/blockchain/verify/<blockchain_hash>":
        "Public credential verification (progression domain), same rationale.",
}


@pytest.fixture(scope="module")
def mounted():
    app, mount = build_app("university")
    assert mount.error is None, f"university mount failed: {mount.error}"
    return app


@pytest.fixture(scope="module")
def baseline() -> set[str]:
    return set(json.loads(BASELINE_PATH.read_text())["routes"])


def test_the_mount_actually_produced_routes(mounted):
    """Guard the guard: an empty mount would make everything below vacuous."""
    rules = [r for r in mounted.url_map.iter_rules() if "static" not in str(r)]
    assert len(rules) > 100, f"only {len(rules)} routes mounted — did the mount break?"


def test_every_route_requires_authentication(mounted):
    naked = sorted(
        route_id(rule)
        for rule in mounted.url_map.iter_rules()
        if "static" not in str(rule)
        and not is_authenticated(mounted, rule)
        and route_id(rule) not in PUBLIC_ROUTES
    )
    assert not naked, (
        "These routes are reachable without a token:\n  "
        + "\n  ".join(naked)
        + "\n\nAdd @token_required from "
        "platform/delivery/api/security/decorators.py."
    )


def test_no_new_object_routes_without_an_authorization_gate(mounted, baseline):
    """A new ungated object route fails immediately — the backlog cannot grow."""
    ungated = {route_id(r) for r in object_scoped_rules(mounted)
               if not is_authorized(mounted, r)}
    new = sorted(ungated - baseline)
    assert not new, (
        "New object-scoped route(s) with no authorization gate:\n  "
        + "\n  ".join(new)
        + "\n\nAny signed-in user could address another user's object. Add a "
        "gate (authorize_object / scoped_to / require_staff) from "
        "platform/delivery/api/security/decorators.py."
    )


def test_baseline_has_no_stale_entries(mounted, baseline):
    """A gated route must be deleted from the baseline, so it keeps shrinking."""
    ungated = {route_id(r) for r in object_scoped_rules(mounted)
               if not is_authorized(mounted, r)}
    fixed = sorted(baseline - ungated)
    assert not fixed, (
        "These routes now carry a gate — delete them from "
        f"{BASELINE_PATH.name} so the backlog reflects reality:\n  "
        + "\n  ".join(fixed)
    )


def test_baseline_is_shrinking_not_growing(baseline):
    """A tripwire on the headline number, so progress is visible in review."""
    assert len(baseline) <= 279, (
        f"The IDOR backlog grew to {len(baseline)}. It is allowed to shrink "
        "only; lower this ceiling as routes are gated."
    )


def test_declared_public_routes_are_still_public_and_rate_limited(mounted):
    """A public route must exist, stay unauthenticated, and be rate limited.

    If one is later gated, the entry is stale and should be removed. If one
    loses its rate limit, an unauthenticated endpoint becomes a free
    amplifier — worth failing the build over.
    """
    from authz_helpers import gate_names

    live = {route_id(r): r for r in mounted.url_map.iter_rules()}
    for declared in sorted(PUBLIC_ROUTES):
        assert declared in live, (
            f"{declared} is declared public but is not mounted — remove the "
            "entry or restore the route.")
        rule = live[declared]
        assert not is_authenticated(mounted, rule), (
            f"{declared} now requires a token; delete it from PUBLIC_ROUTES.")
        assert "limit" in gate_names(mounted.view_functions[rule.endpoint]), (
            f"{declared} is public but carries no rate limit.")
