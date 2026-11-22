"""Card-payment provider boundary for Sixth Form online payments.

The domain talks to a provider only through :class:`PaymentProvider`.
The one real implementation is Stripe Checkout
(:mod:`...infrastructure.payments.stripe_checkout`), configured by a
secret key read lazily from the environment or the owner-only secrets
file. With no key there is **no provider**: :func:`get_provider` returns
``None`` and callers say "online payments are not set up" — nothing here
ever pretends a payment succeeded.

This desktop app has no public web address, so the provider cannot call
us back (no webhook). Instead a pending request is *polled*:
:meth:`PaymentProvider.fetch_status` asks the provider what happened to
the checkout it opened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Checkout states a provider reports back, provider-neutral.
STATE_OPEN = "open"          # payer has not finished yet
STATE_PAID = "paid"          # money taken; txn_id is set
STATE_EXPIRED = "expired"    # checkout closed without payment
STATE_FAILED = "failed"      # provider refused / payment failed
CHECKOUT_STATES: tuple[str, ...] = (
    STATE_OPEN, STATE_PAID, STATE_EXPIRED, STATE_FAILED)

NOT_SET_UP_MESSAGE = (
    "Online payments are not set up. The finance office needs to add the "
    "card provider's secret key (SIXTH_FORM_STRIPE_SECRET_KEY, or the "
    "owner-only file var/secrets/sixth_form_stripe_secret_key) and a "
    "return web address before parents and students can pay by card. "
    "Payments can still be made at the college office.")


class ProviderNotConfigured(ValueError):
    """No card provider is configured — online payment is unavailable."""


class ProviderError(RuntimeError):
    """The provider could not be reached or refused the request."""


@dataclass(frozen=True)
class CheckoutSession:
    """A hosted checkout the payer is sent to."""
    session_id: str
    url: str
    expires_at: str | None = None


@dataclass(frozen=True)
class CheckoutStatus:
    """What the provider says about one checkout session."""
    session_id: str
    state: str                       # one of CHECKOUT_STATES
    txn_id: str | None = None        # provider's payment id once paid
    amount_pence: int | None = None
    currency: str | None = None
    raw_status: str = ""
    reference: str | None = None     # our request reference, echoed back
    created_at: str | None = None


@dataclass(frozen=True)
class ProviderRefund:
    refund_id: str
    status: str
    amount_pence: int


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    mode: str                        # "test" or "live"
    details: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class PaymentProvider(Protocol):
    """What the online-payments domain needs from a card provider."""

    name: str

    def info(self) -> ProviderInfo: ...

    def create_checkout(self, *, reference: str, description: str,
                        amount_pence: int, currency: str,
                        payer_email: str | None, return_url: str,
                        idempotency_key: str) -> CheckoutSession: ...

    def fetch_status(self, session_id: str) -> CheckoutStatus: ...

    def cancel_checkout(self, session_id: str) -> CheckoutStatus: ...

    def refund(self, txn_id: str, amount_pence: int, *,
               idempotency_key: str) -> ProviderRefund: ...

    def recent_checkouts(self, *, since_epoch: int,
                         limit: int = 100) -> list[CheckoutStatus]: ...


_override: PaymentProvider | None = None
_override_set: bool = False


def use_provider(provider: PaymentProvider | None) -> None:
    """Install a provider explicitly (or ``None`` for "none configured").

    For a host that builds its own provider object; :func:`reset_provider`
    goes back to reading the configuration.
    """
    global _override, _override_set
    if provider is not None and not isinstance(provider, PaymentProvider):
        raise TypeError("provider does not implement PaymentProvider")
    _override = provider
    _override_set = True


def reset_provider() -> None:
    global _override, _override_set
    _override = None
    _override_set = False


def get_provider() -> PaymentProvider | None:
    """The configured provider, or ``None`` when online payment is off.

    Read on every call (never at import), so adding or removing the key
    takes effect without a restart.
    """
    if _override_set:
        return _override
    from education_system.systems.sixth_form.domains.finance.infrastructure.payments import (
        stripe_checkout,
    )
    return stripe_checkout.from_config()


def require_provider() -> PaymentProvider:
    p = get_provider()
    if p is None:
        raise ProviderNotConfigured(NOT_SET_UP_MESSAGE)
    return p
