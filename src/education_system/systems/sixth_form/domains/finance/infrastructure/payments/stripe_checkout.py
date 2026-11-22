"""Stripe Checkout adapter for Sixth Form online payments.

Talks to Stripe's HTTPS API with the standard library (``urllib``) — no
SDK dependency. Uses hosted Checkout Sessions in ``payment`` mode: the
payer is sent to Stripe's page, and we poll the session afterwards
(there is no webhook — the desktop app has no public address).

Configuration (read lazily, on every :func:`from_config` call):

* ``SIXTH_FORM_STRIPE_SECRET_KEY`` environment variable, or
* the owner-only file ``var/secrets/sixth_form_stripe_secret_key``
  (``paths.PLATFORM_SECRETS_DIR``), the same place the platform keeps its
  SMTP password.

No key → :func:`from_config` returns ``None`` and online payment is off.
A key that does not look like a Stripe secret/restricted key is refused
the same way (logged), rather than failing later mid-payment.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain.online_payments.providers import (
    STATE_EXPIRED,
    STATE_FAILED,
    STATE_OPEN,
    STATE_PAID,
    CheckoutSession,
    CheckoutStatus,
    ProviderError,
    ProviderInfo,
    ProviderRefund,
)

logger = logging.getLogger(__name__)

ENV_VAR = "SIXTH_FORM_STRIPE_SECRET_KEY"
SECRET_FILE_NAME = "sixth_form_stripe_secret_key"
API_BASE = "https://api.stripe.com/v1"
TIMEOUT_SECONDS = 20
# Our references are echoed in metadata so a provider-side listing can be
# matched back to requests during reconciliation.
METADATA_KEY = "sixth_form_reference"


def secret_file() -> Path:
    return Path(paths.PLATFORM_SECRETS_DIR) / SECRET_FILE_NAME


def _read_key() -> str:
    key = os.environ.get(ENV_VAR, "").strip()
    if key:
        return key
    try:
        return secret_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def from_config() -> "StripeCheckoutProvider | None":
    key = _read_key()
    if not key:
        return None
    if not key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        logger.error("Ignoring %s: it is not a Stripe secret or restricted "
                     "key", ENV_VAR)
        return None
    return StripeCheckoutProvider(key)


def _iso(epoch: Any) -> str | None:
    try:
        return _dt.datetime.fromtimestamp(int(epoch)).isoformat(
            sep=" ", timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


class StripeCheckoutProvider:
    """:class:`PaymentProvider` backed by Stripe Checkout Sessions."""

    name = "Stripe"

    def __init__(self, secret_key: str) -> None:
        self._key = secret_key

    def __repr__(self) -> str:  # never print the key
        return f"<StripeCheckoutProvider {self.info().mode}>"

    def info(self) -> ProviderInfo:
        mode = "live" if "_live_" in self._key else "test"
        return ProviderInfo(name=self.name, mode=mode,
                            details={"api": API_BASE})

    # ── HTTP ────────────────────────────────────────────────────────
    def _request(self, method: str, path: str,
                 params: dict[str, Any] | None = None, *,
                 idempotency_key: str | None = None) -> dict[str, Any]:
        url = f"{API_BASE}{path}"
        body = None
        if params and method == "GET":
            url += "?" + urllib.parse.urlencode(params)
        elif params:
            body = urllib.parse.urlencode(params).encode("ascii")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        if idempotency_key:
            req.add_header("Idempotency-Key", idempotency_key)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 - fixed https host
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}"
            try:
                err = json.loads(e.read().decode("utf-8")).get("error", {})
                msg = err.get("message") or msg
            except Exception:  # noqa: BLE001 - keep the HTTP code
                pass
            raise ProviderError(f"Stripe refused the request: {msg}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(
                f"Could not reach Stripe ({e}). Check the internet "
                "connection and try again.") from None
        except ValueError:
            raise ProviderError("Stripe sent an unreadable reply") from None

    # ── Mapping ─────────────────────────────────────────────────────
    @staticmethod
    def _status(s: dict[str, Any]) -> CheckoutStatus:
        status = s.get("status") or ""
        pay = s.get("payment_status") or ""
        if pay == "paid":
            state = STATE_PAID
        elif status == "expired":
            state = STATE_EXPIRED
        elif status == "complete":
            # Complete but not paid (e.g. delayed method declined).
            state = STATE_FAILED
        else:
            state = STATE_OPEN
        pi = s.get("payment_intent")
        if isinstance(pi, dict):
            pi = pi.get("id")
        meta = s.get("metadata") or {}
        return CheckoutStatus(
            session_id=s.get("id", ""), state=state,
            txn_id=pi if state == STATE_PAID else None,
            amount_pence=s.get("amount_total"),
            currency=(s.get("currency") or "").upper() or None,
            raw_status=f"{status}/{pay}",
            reference=meta.get(METADATA_KEY) or s.get("client_reference_id"),
            created_at=_iso(s.get("created")))

    # ── PaymentProvider ─────────────────────────────────────────────
    def create_checkout(self, *, reference: str, description: str,
                        amount_pence: int, currency: str,
                        payer_email: str | None, return_url: str,
                        idempotency_key: str) -> CheckoutSession:
        sep = "&" if "?" in return_url else "?"
        params: dict[str, Any] = {
            "mode": "payment",
            "client_reference_id": reference,
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": int(amount_pence),
            "line_items[0][price_data][product_data][name]":
                description[:250],
            f"metadata[{METADATA_KEY}]": reference,
            f"payment_intent_data[metadata][{METADATA_KEY}]": reference,
            "payment_intent_data[description]":
                f"{reference} {description}"[:250],
            "success_url": f"{return_url}{sep}paid={reference}",
            "cancel_url": f"{return_url}{sep}cancelled={reference}",
        }
        if payer_email:
            params["customer_email"] = payer_email
        s = self._request("POST", "/checkout/sessions", params,
                          idempotency_key=idempotency_key)
        if not s.get("id") or not s.get("url"):
            raise ProviderError("Stripe did not return a checkout page")
        return CheckoutSession(session_id=s["id"], url=s["url"],
                               expires_at=_iso(s.get("expires_at")))

    def fetch_status(self, session_id: str) -> CheckoutStatus:
        sid = urllib.parse.quote(session_id, safe="")
        return self._status(self._request("GET", f"/checkout/sessions/{sid}"))

    def cancel_checkout(self, session_id: str) -> CheckoutStatus:
        """Expire an open session so it can no longer be paid.

        If it was paid in the meantime Stripe refuses to expire it; the
        current status is returned so the caller can post the payment.
        """
        current = self.fetch_status(session_id)
        if current.state != STATE_OPEN:
            return current
        sid = urllib.parse.quote(session_id, safe="")
        try:
            return self._status(self._request(
                "POST", f"/checkout/sessions/{sid}/expire"))
        except ProviderError:
            return self.fetch_status(session_id)

    def refund(self, txn_id: str, amount_pence: int, *,
               idempotency_key: str) -> ProviderRefund:
        r = self._request("POST", "/refunds",
                          {"payment_intent": txn_id,
                           "amount": int(amount_pence)},
                          idempotency_key=idempotency_key)
        status = r.get("status") or ""
        if status in ("failed", "canceled"):
            raise ProviderError(f"Stripe refund {status}")
        return ProviderRefund(refund_id=r.get("id", ""), status=status,
                              amount_pence=int(r.get("amount") or 0))

    def recent_checkouts(self, *, since_epoch: int,
                         limit: int = 100) -> list[CheckoutStatus]:
        out: list[CheckoutStatus] = []
        params: dict[str, Any] = {"limit": min(100, max(1, limit)),
                                  "created[gte]": int(since_epoch)}
        while len(out) < limit:
            page = self._request("GET", "/checkout/sessions", params)
            data = page.get("data") or []
            out.extend(self._status(s) for s in data)
            if not page.get("has_more") or not data:
                break
            params["starting_after"] = data[-1].get("id")
        return out[:limit]
