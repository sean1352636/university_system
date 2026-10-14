"""Outbound webhooks must resist SSRF and sign deliveries against replay.

Covers task 17.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def _mod():
    from education_system.platform.integrations.webhooks import webhook_service
    return webhook_service


def test_http_scheme_rejected_in_production(as_production):
    mod = _mod()
    with as_production():
        with pytest.raises(mod.WebhookURLError):
            mod.validate_webhook_url("http://example.com/hook")


def test_loopback_rejected_in_production(as_production):
    mod = _mod()
    with as_production():
        with pytest.raises(mod.WebhookURLError):
            mod.validate_webhook_url("https://127.0.0.1/hook")


def test_link_local_metadata_endpoint_rejected(as_production):
    mod = _mod()
    with as_production():
        with pytest.raises(mod.WebhookURLError):
            mod.validate_webhook_url("https://169.254.169.254/latest/meta-data/")


def test_non_http_scheme_rejected():
    mod = _mod()
    with pytest.raises(mod.WebhookURLError):
        mod.validate_webhook_url("file:///etc/passwd")


def test_public_https_url_accepted():
    mod = _mod()
    # A routable public address, validated without any network egress.
    assert mod.validate_webhook_url("https://93.184.216.34/hook").startswith("https://")


def test_subscribe_requires_secret(tmp_path):
    mod = _mod()
    svc = mod.WebhookService(db_path=str(tmp_path / "wh.db"))
    with pytest.raises(mod.WebhookURLError):
        svc.subscribe("https://93.184.216.34/hook", secret=None)


def test_listing_masks_secret(tmp_path):
    mod = _mod()
    svc = mod.WebhookService(db_path=str(tmp_path / "wh.db"))
    svc.subscribe("https://93.184.216.34/hook", secret="s3cr3t-value")
    subs = svc.list_subscriptions(active_only=False)
    assert subs, "subscription should have been stored"
    assert all(s.get("secret") in (None, "***") for s in subs), "secret must be masked in listings"
