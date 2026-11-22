"""Online payments for the Sixth Form System: parents and students pay
fees, trips and catering top-ups by card.

Tables (``sixthform.db``):

* ``online_payment_requests`` — one row per attempt to pay something:
  what (a fee item, a trip booking or a catering top-up), how much (in
  **pence**), who is paying, the provider's checkout session and, once
  paid, the provider's transaction id and the payment it was posted as.
  Status: Pending → Paid / Failed / Cancelled; Paid → Refunded.
* ``online_payment_events`` — an append-only log of what happened to each
  request (created, checkout opened, status checked, posted, refunded …).
* ``online_payment_settings`` — the return web address the card page
  sends the payer back to.

One truth for balances and receipts
-----------------------------------
A paid request is *posted* through the existing modules, never written
around them: a fee payment through ``fees.create_payment``, a trip
payment through ``trips.add_payment``, a catering top-up through
``cashless.credit_from_online_payment``; the receipt through
``receipts.receipt_from_fee_payment`` / ``receipt_from_trip_payment``.
So fee statements, trip balances and the receipt book all move together.

Idempotent posting
------------------
A provider transaction id can be posted **once**. Posting first *claims*
the request (a conditional UPDATE that only one caller can win, and a
unique index on ``provider_txn_id`` so one transaction can never back
two requests), then posts, then records what it posted. The posted
payment and its receipt carry the reference ``<OP-ref>/<txn id>``; if a
crash ever leaves a request claimed-but-unrecorded, the retry finds that
payment / receipt by reference and adopts it instead of posting again —
which also avoids ``receipts.receipt_from_*`` creating a second receipt
for the same payment (those helpers do not check for one themselves).

No webhook
----------
This is a desktop app with no public address, so the provider cannot
tell us a payment finished. :func:`check_status` polls the provider for
a pending request; :func:`check_pending` does every pending request.

Permissions (per action, via ``access.current()``): FINANCE for staff
actions (offline payments, refunds, reconciliation, settings, acting
for a family). A student may pay and see only their own items; a parent
only items for students linked to their parent-portal account.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
    providers as _prov,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

CURRENCY = "GBP"
CURRENCY_SYMBOL = "£"

KIND_FEE = "fee"
KIND_TRIP = "trip"
KIND_CATERING = "catering"
ITEM_KINDS: tuple[str, ...] = (KIND_FEE, KIND_TRIP, KIND_CATERING)
ITEM_KIND_LABELS = {KIND_FEE: "Fee", KIND_TRIP: "Trip",
                    KIND_CATERING: "Catering top-up"}

PAYER_PARENT = "parent"
PAYER_STUDENT = "student"
PAYER_STAFF = "staff"
PAYER_KINDS: tuple[str, ...] = (PAYER_PARENT, PAYER_STUDENT, PAYER_STAFF)

PENDING = "Pending"
PAID = "Paid"
FAILED = "Failed"
CANCELLED = "Cancelled"
REFUNDED = "Refunded"
STATUSES: tuple[str, ...] = (PENDING, PAID, FAILED, CANCELLED, REFUNDED)

PROVIDER_OFFLINE = "Offline"

OFFLINE_METHODS: tuple[str, ...] = (
    "Cash", "Cheque", "Bank Transfer", "Card", "Other")
# Fee and trip modules have their own method lists; map ours onto them.
_FEE_METHOD = {"Cash": "Cash", "Cheque": "Cheque",
               "Bank Transfer": "Bank Transfer", "Card": "Card",
               "Other": "Other", "Online": "Online Portal"}
_TRIP_METHOD = _FEE_METHOD
_TRIP_REFUND_METHOD = {"Online": "Card", "Card": "Card", "Cash": "Cash",
                       "Cheque": "Cheque", "Bank Transfer": "Bank Transfer",
                       "Other": "Other"}

#: Smallest card payment we will start (card fees make tiny ones silly).
MIN_ONLINE_PENCE = 100
#: A pending request older than this is flagged in reconciliation.
STALE_PENDING_HOURS = 24

_REF_RE = re.compile(r"^OP-(\d{4})-(\d{5})$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS online_payment_requests (
    request_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reference           TEXT NOT NULL UNIQUE,
    item_kind           TEXT NOT NULL
        CHECK (item_kind IN ('fee', 'trip', 'catering')),
    fee_id              INTEGER,
    booking_id          INTEGER,
    student_id          TEXT NOT NULL,
    description         TEXT NOT NULL,
    amount_pence        INTEGER NOT NULL CHECK (amount_pence > 0),
    currency            TEXT NOT NULL DEFAULT 'GBP',
    payer_kind          TEXT NOT NULL
        CHECK (payer_kind IN ('parent', 'student', 'staff')),
    payer_ref           TEXT NOT NULL,
    payer_name          TEXT,
    status              TEXT NOT NULL DEFAULT 'Pending',
    provider            TEXT NOT NULL,
    provider_session_id TEXT,
    checkout_url        TEXT,
    checkout_attempts   INTEGER NOT NULL DEFAULT 0,
    provider_txn_id     TEXT,
    provider_amount_pence INTEGER,
    provider_state      TEXT,
    offline_method      TEXT,
    posting_state       TEXT NOT NULL DEFAULT '',
    posted_payment_id   INTEGER,
    receipt_id          INTEGER,
    failure_reason      TEXT,
    refunded_pence      INTEGER NOT NULL DEFAULT 0,
    refund_ref          TEXT,
    created_by          TEXT,
    paid_at             TEXT,
    last_checked_at     TEXT,
    expires_at          TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_opr_txn
    ON online_payment_requests(provider_txn_id)
    WHERE provider_txn_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_opr_student ON online_payment_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_opr_status  ON online_payment_requests(status);
CREATE INDEX IF NOT EXISTS idx_opr_fee     ON online_payment_requests(fee_id);
CREATE INDEX IF NOT EXISTS idx_opr_booking ON online_payment_requests(booking_id);

CREATE TABLE IF NOT EXISTS online_payment_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    event       TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT,
    FOREIGN KEY (request_id) REFERENCES online_payment_requests(request_id)
);
CREATE INDEX IF NOT EXISTS idx_ope_request ON online_payment_events(request_id);

CREATE TABLE IF NOT EXISTS online_payment_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_by  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class PaymentRequest:
    request_id: int
    reference: str
    item_kind: str
    fee_id: int | None
    booking_id: int | None
    student_id: str
    description: str
    amount_pence: int
    currency: str
    payer_kind: str
    payer_ref: str
    payer_name: str | None
    status: str
    provider: str
    provider_session_id: str | None
    checkout_url: str | None
    checkout_attempts: int
    provider_txn_id: str | None
    provider_amount_pence: int | None
    provider_state: str | None
    offline_method: str | None
    posting_state: str
    posted_payment_id: int | None
    receipt_id: int | None
    failure_reason: str | None
    refunded_pence: int
    refund_ref: str | None
    created_by: str | None
    paid_at: str | None
    last_checked_at: str | None
    expires_at: str | None
    created_at: str
    updated_at: str
    student_name: str | None = None

    @property
    def amount(self) -> float:
        return self.amount_pence / 100

    @property
    def is_offline(self) -> bool:
        return self.provider == PROVIDER_OFFLINE

    @property
    def is_posted(self) -> bool:
        return self.posting_state == "Posted"

    @property
    def kind_label(self) -> str:
        return ITEM_KIND_LABELS.get(self.item_kind, self.item_kind)

    @property
    def payment_reference(self) -> str | None:
        """Reference carried by the posted payment and its receipt."""
        if not self.provider_txn_id:
            return None
        return f"{self.reference}/{self.provider_txn_id}"


@dataclass
class PayableItem:
    """Something a payer can pay now."""
    item_kind: str
    target_id: int | None          # fee_id / booking_id; None for catering
    student_id: str
    student_name: str
    description: str
    balance_pence: int | None      # None for a catering top-up (any amount)
    due_date: str | None = None
    pending_reference: str | None = None

    @property
    def key(self) -> str:
        return f"{self.item_kind}:{self.target_id or self.student_id}"


@dataclass
class ReconRow:
    request: PaymentRequest
    posted_amount_pence: int | None
    posted_status: str | None
    receipt_number: str | None
    issues: list[str] = field(default_factory=list)


@dataclass
class OnlineSummary:
    by_status: dict[str, int] = field(default_factory=dict)
    paid_pence: int = 0
    refunded_pence: int = 0
    pending_pence: int = 0
    online_paid_pence: int = 0
    offline_paid_pence: int = 0
    by_kind_pence: dict[str, int] = field(default_factory=dict)
    issues: int = 0


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Online payments schema ready at %s", DB_PATH)
    _DB_READY = True


_SELECT = ("SELECT r.*, s.first_name AS s_first, s.last_name AS s_last "
           "FROM online_payment_requests r "
           "LEFT JOIN students s ON s.student_id = r.student_id")


def _row(r: _sql.Row) -> PaymentRequest:
    keys = r.keys()
    name = None
    if "s_first" in keys and r["s_first"] is not None:
        name = f"{r['s_first']} {r['s_last'] or ''}".strip()
    return PaymentRequest(
        request_id=r["request_id"], reference=r["reference"],
        item_kind=r["item_kind"], fee_id=r["fee_id"],
        booking_id=r["booking_id"], student_id=r["student_id"],
        description=r["description"], amount_pence=int(r["amount_pence"]),
        currency=r["currency"], payer_kind=r["payer_kind"],
        payer_ref=r["payer_ref"], payer_name=r["payer_name"],
        status=r["status"], provider=r["provider"],
        provider_session_id=r["provider_session_id"],
        checkout_url=r["checkout_url"],
        checkout_attempts=int(r["checkout_attempts"] or 0),
        provider_txn_id=r["provider_txn_id"],
        provider_amount_pence=r["provider_amount_pence"],
        provider_state=r["provider_state"],
        offline_method=r["offline_method"],
        posting_state=r["posting_state"] or "",
        posted_payment_id=r["posted_payment_id"],
        receipt_id=r["receipt_id"], failure_reason=r["failure_reason"],
        refunded_pence=int(r["refunded_pence"] or 0),
        refund_ref=r["refund_ref"], created_by=r["created_by"],
        paid_at=r["paid_at"], last_checked_at=r["last_checked_at"],
        expires_at=r["expires_at"], created_at=r["created_at"],
        updated_at=r["updated_at"], student_name=name)


def _log(conn: _sql.Connection, request_id: int, event: str,
         detail: str | None = None, actor: str | None = None) -> None:
    conn.execute(
        "INSERT INTO online_payment_events (request_id, event, detail, actor)"
        " VALUES (?, ?, ?, ?)", (request_id, event, detail, actor))


def _event(request_id: int, event: str, detail: str | None = None) -> None:
    with _connect() as conn:
        _log(conn, request_id, event, detail, _actor())


# ── Helpers ─────────────────────────────────────────────────────────

def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _actor() -> str:
    p = _access().current()
    return p.username or "system"


def _require_finance(action: str) -> None:
    a = _access()
    a.current().require(a.FINANCE, action)


def to_pence(value: Any, label: str = "Amount") -> int:
    """Pounds (``"12.50"``, ``12.5``) → whole pence, validated."""
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip().lstrip(CURRENCY_SYMBOL).replace(",", "")
    try:
        d = Decimal(s)
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be an amount in pounds") from None
    if d.as_tuple().exponent < -2:
        raise ValidationError(f"{label} must have at most 2 decimal places")
    if d <= 0:
        raise ValidationError(f"{label} must be more than zero")
    return int((d * 100).to_integral_value())


def money(pence: int | None) -> str:
    if pence is None:
        return ""
    sign = "-" if pence < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL}{abs(pence) / 100:,.2f}"


def _pounds(pence: int) -> float:
    return float((Decimal(pence) / 100).quantize(Decimal("0.01")))


def _now() -> str:
    return _dt.datetime.now().isoformat(sep=" ", timespec="seconds")


def _student_on_roll(student_id: str) -> bool:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _students.get_student(student_id)
    return bool(s and s.on_roll)


def _student_name(student_id: str) -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _students.get_student(student_id)
    return s.full_name if s else student_id


# ── Settings / provider status ──────────────────────────────────────

def get_setting(key: str) -> str | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM online_payment_settings "
                         "WHERE key = ?", (key,)).fetchone()
    return r["value"] if r and r["value"] else None


def return_url() -> str | None:
    return get_setting("return_url")


def set_return_url(url: str) -> str:
    """The page the card provider sends the payer back to afterwards
    (the college website's "thank you" page, for instance). Must be an
    https address."""
    _require_finance("online payment settings")
    init_db()
    u = (url or "").strip()
    if not re.match(r"^https://[^\s/]+\.[^\s]+$", u):
        raise ValidationError(
            "Return address must be a full https:// web address, e.g. "
            "https://www.example-college.ac.uk/payment-complete")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO online_payment_settings (key, value, updated_by) "
            "VALUES ('return_url', ?, ?) ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, updated_by = excluded.updated_by, "
            "updated_at = datetime('now')", (u, _actor()))
    logger.info("Online payment return URL set by %s", _actor())
    return u


@dataclass
class ProviderState:
    ready: bool
    message: str
    provider: str | None = None
    mode: str | None = None
    return_url: str | None = None


def provider_state() -> ProviderState:
    """Whether card payments can be taken right now, and why not."""
    p = _prov.get_provider()
    url = return_url()
    if p is None:
        return ProviderState(False, _prov.NOT_SET_UP_MESSAGE, return_url=url)
    info = p.info()
    if not url:
        return ProviderState(
            False, "Online payments are not set up: the finance office "
            "still needs to set the return web address (Online Payments → "
            "Provider).", info.name, info.mode, None)
    msg = f"{info.name} card payments are available ({info.mode} mode)."
    if info.mode == "test":
        msg += " TEST MODE: no real money is taken."
    return ProviderState(True, msg, info.name, info.mode, url)


def _ready_provider() -> _prov.PaymentProvider:
    st = provider_state()
    if not st.ready:
        raise _prov.ProviderNotConfigured(st.message)
    return _prov.require_provider()


# ── Payer authorisation ─────────────────────────────────────────────

@dataclass
class Payer:
    kind: str
    ref: str
    name: str
    email: str | None
    student_ids: list[str]


def _parent_portal():
    from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
        parent_portal,
    )
    return parent_portal


def resolve_payer(payer_kind: str, payer_id: Any) -> Payer:
    """Check the signed-in principal may act as this payer.

    * student — the signed-in student themself (``principal.student_id``),
      or FINANCE staff acting for them;
    * parent — the signed-in parent whose portal account this is, or
      FINANCE staff; the payer may pay only for linked students;
    * staff — FINANCE staff raising a request for any student.
    """
    a = _access()
    p = a.current()
    kind = (payer_kind or "").strip().lower()
    if kind not in PAYER_KINDS:
        raise ValidationError(
            f"Payer must be one of: {', '.join(PAYER_KINDS)}")
    if kind == PAYER_STUDENT:
        sid = str(payer_id or "").strip()
        if not sid:
            raise ValidationError("Student is required")
        if not (p.is_student and p.student_id == sid) and not p.can(a.FINANCE):
            raise a.AccessDenied("You can only pay for your own items.")
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        s = _students.get_student(sid)
        if s is None:
            raise ValidationError(f"No student with id {sid}")
        return Payer(kind, sid, s.full_name, s.personal_email or s.email,
                     [sid])
    if kind == PAYER_PARENT:
        pp = _parent_portal()
        try:
            account_id = int(payer_id)
        except (TypeError, ValueError):
            raise ValidationError("Parent account is required") from None
        acct = pp.get_account(account_id)
        if acct is None or not acct.is_active:
            raise ValidationError("That parent portal account is not active.")
        if not (p.is_parent and p.username == acct.username) \
                and not p.can(a.FINANCE):
            raise a.AccessDenied(
                "You can only pay from your own parent account.")
        kids = [c["student_id"] for c in pp.linked_students(account_id)]
        return Payer(kind, str(account_id), acct.full_name,
                     pp.resolved_email(account_id), kids)
    p.require(a.FINANCE, "raising payment requests for families")
    return Payer(kind, p.username or "staff", p.staff_name or p.username,
                 None, [])


def _payer_may_pay_for(payer: Payer, student_id: str) -> None:
    if payer.kind == PAYER_STAFF:
        return
    if student_id not in payer.student_ids:
        raise _access().AccessDenied(
            "That student is not linked to this payer.")


def _can_see_request(req: PaymentRequest) -> bool:
    a = _access()
    p = a.current()
    if p.can(a.FINANCE):
        return True
    if p.is_student:
        return bool(p.student_id) and p.student_id == req.student_id
    if p.is_parent:
        acct = _parent_portal().account_for_username(p.username)
        return acct is not None and _parent_portal().is_linked(
            acct.account_id, req.student_id)
    return False


def _require_visible(req: PaymentRequest) -> None:
    if not _can_see_request(req):
        raise _access().AccessDenied(
            f"You are not allowed to see payment {req.reference}.")


# ── What can be paid ────────────────────────────────────────────────

def _pending_for(item_kind: str, target_id: int | None,
                 student_id: str) -> PaymentRequest | None:
    init_db()
    if item_kind == KIND_FEE:
        where, arg = "r.fee_id = ?", target_id
    elif item_kind == KIND_TRIP:
        where, arg = "r.booking_id = ?", target_id
    else:
        where, arg = "r.student_id = ?", student_id
    with _connect() as conn:
        # db-audit: ignore[DBW001] - where is one of three literals above
        r = conn.execute(
            f"{_SELECT} WHERE r.item_kind = ? AND {where} "
            "AND r.status = 'Pending' ORDER BY r.request_id DESC",
            (item_kind, arg)).fetchone()
    return _row(r) if r else None


def _fee_target(fee_id: int):
    from education_system.systems.sixth_form.domains.finance.domain.fees import fees as _fees
    v = _fees.view_item(int(fee_id))
    if v is None:
        raise ValidationError(f"No fee #{fee_id}")
    if not v.is_active or v.balance <= 0:
        raise ValidationError(
            f"Fee #{fee_id} has nothing to pay ({v.effective_status})")
    return v


_CLOSED_TRIP = ("Cancelled", "Completed")


def _trip_target(booking_id: int):
    from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _trips
    v = _trips.view_booking(int(booking_id))
    if v is None:
        raise ValidationError(f"No trip booking #{booking_id}")
    if not v.is_active or v.trip.status in _CLOSED_TRIP:
        raise ValidationError(
            f"{v.trip.name}: this booking can no longer be paid "
            f"({v.booking.status}, trip {v.trip.status})")
    if v.balance <= 0:
        raise ValidationError(f"{v.trip.name}: nothing left to pay")
    return v


def payable_items(payer_kind: str, payer_id: Any) -> list[PayableItem]:
    """Every fee, trip balance and catering top-up this payer may pay."""
    payer = resolve_payer(payer_kind, payer_id)
    return _payable_for(payer.student_ids)


def payable_for_student(student_id: str) -> list[PayableItem]:
    """Staff view of what a student owes and can pay (FINANCE)."""
    _require_finance("payable items")
    return _payable_for([student_id])


def _payable_for(student_ids: list[str]) -> list[PayableItem]:
    from education_system.systems.sixth_form.domains.finance.domain.fees import fees as _fees
    from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _trips
    from education_system.systems.sixth_form.domains.operations.domain.catering import (
        cashless as _cashless,
    )
    init_db()
    with _connect() as conn:
        pend = conn.execute(
            "SELECT item_kind, fee_id, booking_id, student_id, reference "
            "FROM online_payment_requests WHERE status = 'Pending'").fetchall()
    pending = {}
    for r in pend:
        key = (r["item_kind"], r["fee_id"] or r["booking_id"] or r["student_id"])
        pending[key] = r["reference"]
    out: list[PayableItem] = []
    for sid in student_ids:
        name = _student_name(sid)
        for v in _fees.list_views(student_id=sid, active_only=True):
            if v.balance <= 0:
                continue
            out.append(PayableItem(
                KIND_FEE, v.item.fee_id, sid, name,
                f"{v.item.category}: {v.item.description}",
                int(round(v.balance * 100)), v.item.due_date,
                pending.get((KIND_FEE, v.item.fee_id))))
        for b in _trips.list_booking_views(student_id=sid, active_only=True):
            if b.balance <= 0 or b.trip.status in _CLOSED_TRIP:
                continue
            out.append(PayableItem(
                KIND_TRIP, b.booking.booking_id, sid, name,
                f"Trip: {b.trip.name} ({b.trip.start_date})",
                int(round(b.balance * 100)), b.trip.payment_due,
                pending.get((KIND_TRIP, b.booking.booking_id))))
        acct = _cashless.get_account(sid)
        if _student_on_roll(sid) and (acct is None or acct.is_open):
            bal = _cashless.balance_pence(sid)
            out.append(PayableItem(
                KIND_CATERING, None, sid, name,
                f"Catering top-up (balance {money(bal)})", None, None,
                pending.get((KIND_CATERING, sid))))
    return out


# ── Creating requests / starting card payment ───────────────────────

def _next_reference(conn: _sql.Connection) -> str:
    year = _dt.date.today().year
    r = conn.execute(
        "SELECT reference FROM online_payment_requests WHERE reference LIKE ?"
        " ORDER BY reference DESC LIMIT 1", (f"OP-{year}-%",)).fetchone()
    n = 1
    if r is not None:
        m = _REF_RE.match(r["reference"])
        n = int(m.group(2)) + 1 if m else 1
    return f"OP-{year}-{n:05d}"


def _validate_target(item_kind: str, target_id: Any, student_id: Any,
                     amount_pence: int) -> tuple[int | None, int | None, str, str]:
    """→ (fee_id, booking_id, student_id, description)."""
    kind = (item_kind or "").strip().lower()
    if kind not in ITEM_KINDS:
        raise ValidationError(
            f"Item must be one of: {', '.join(ITEM_KINDS)}")
    if kind == KIND_FEE:
        v = _fee_target(_int(target_id, "Fee"))
        bal = int(round(v.balance * 100))
        if amount_pence > bal:
            raise ValidationError(
                f"Amount is more than the {money(bal)} still owed")
        return (v.item.fee_id, None, v.item.student_id,
                f"{v.item.category}: {v.item.description}")
    if kind == KIND_TRIP:
        v = _trip_target(_int(target_id, "Trip booking"))
        bal = int(round(v.balance * 100))
        if amount_pence > bal:
            raise ValidationError(
                f"Amount is more than the {money(bal)} still owed")
        return (None, v.booking.booking_id, v.booking.student_id,
                f"Trip: {v.trip.name}")
    from education_system.systems.sixth_form.domains.operations.domain.catering import (
        cashless as _cashless,
    )
    sid = str(student_id or "").strip()
    if not sid:
        raise ValidationError("Student is required for a catering top-up")
    _cashless.validate_topup_amount(sid, amount_pence)
    return None, None, sid, "Catering top-up"


def _int(v: Any, label: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} is required") from None


def _insert_request(*, kind: str, fee_id: int | None, booking_id: int | None,
                    student_id: str, description: str, amount_pence: int,
                    payer: Payer, provider: str,
                    offline_method: str | None = None) -> PaymentRequest:
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ref = _next_reference(conn)
        cur = conn.execute(
            "INSERT INTO online_payment_requests (reference, item_kind, "
            "fee_id, booking_id, student_id, description, amount_pence, "
            "currency, payer_kind, payer_ref, payer_name, status, provider, "
            "offline_method, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)",
            (ref, kind, fee_id, booking_id, student_id, description,
             amount_pence, CURRENCY, payer.kind, payer.ref, payer.name,
             provider, offline_method, _actor()))
        rid = int(cur.lastrowid)
        _log(conn, rid, "Created",
             f"{ITEM_KIND_LABELS[kind]} {money(amount_pence)} for "
             f"{student_id} by {payer.kind} {payer.name}", _actor())
    out = get_request(rid, _check=False)
    assert out is not None
    return out


def start_payment(payer_kind: str, payer_id: Any, item_kind: str, *,
                  amount: Any, target_id: Any = None,
                  student_id: Any = None) -> PaymentRequest:
    """Create a request and open a card checkout for it.

    Refuses up front (``ProviderNotConfigured``) when online payment is
    not set up — no request is left behind pretending to be payable.
    Returns the request; ``checkout_url`` is the page to open.
    """
    init_db()
    provider = _ready_provider()
    payer = resolve_payer(payer_kind, payer_id)
    amount_pence = to_pence(amount)
    if amount_pence < MIN_ONLINE_PENCE:
        raise ValidationError(
            f"The smallest card payment is {money(MIN_ONLINE_PENCE)}")
    fee_id, booking_id, sid, desc = _validate_target(
        item_kind, target_id, student_id, amount_pence)
    _payer_may_pay_for(payer, sid)
    kind = item_kind.strip().lower()
    existing = _pending_for(kind, fee_id or booking_id, sid)
    if existing is not None:
        raise ValidationError(
            f"A payment for this is already in progress ({existing.reference}"
            f", {money(existing.amount_pence)}). Check its status, or cancel "
            "it, before starting another.")
    req = _insert_request(kind=kind, fee_id=fee_id, booking_id=booking_id,
                          student_id=sid, description=desc,
                          amount_pence=amount_pence, payer=payer,
                          provider=provider.name)
    return _open_checkout(req, provider, payer.email)


def _open_checkout(req: PaymentRequest, provider: _prov.PaymentProvider,
                   email: str | None) -> PaymentRequest:
    attempt = req.checkout_attempts + 1
    url = return_url() or ""
    try:
        session = provider.create_checkout(
            reference=req.reference,
            description=f"{_student_name(req.student_id)} - {req.description}",
            amount_pence=req.amount_pence, currency=req.currency,
            payer_email=email, return_url=url,
            idempotency_key=f"sixthform-{req.reference}-{attempt}")
    except _prov.ProviderError as e:
        with _connect() as conn:
            conn.execute(
                "UPDATE online_payment_requests SET status = 'Failed', "
                "failure_reason = ?, checkout_attempts = ?, "
                "updated_at = datetime('now') WHERE request_id = ? "
                "AND status = 'Pending'",
                (str(e)[:300], attempt, req.request_id))
            _log(conn, req.request_id, "Checkout failed", str(e)[:300],
                 _actor())
        raise
    with _connect() as conn:
        conn.execute(
            "UPDATE online_payment_requests SET provider_session_id = ?, "
            "checkout_url = ?, expires_at = ?, checkout_attempts = ?, "
            "provider_state = 'open', updated_at = datetime('now') "
            "WHERE request_id = ?",
            (session.session_id, session.url, session.expires_at, attempt,
             req.request_id))
        _log(conn, req.request_id, "Checkout opened",
             f"{provider.name} session {session.session_id}", _actor())
    out = get_request(req.request_id, _check=False)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_request(request_id: int, *, _check: bool = True) -> PaymentRequest | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE r.request_id = ?",
                         (int(request_id),)).fetchone()
    req = _row(r) if r else None
    if req is not None and _check:
        _require_visible(req)
    return req


def get_by_reference(reference: str) -> PaymentRequest | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE r.reference = ?",
                         ((reference or "").strip().upper(),)).fetchone()
    req = _row(r) if r else None
    if req is not None:
        _require_visible(req)
    return req


def _require_request(request_id: int) -> PaymentRequest:
    req = get_request(request_id)
    if req is None:
        raise ValidationError(f"No payment request #{request_id}")
    return req


def list_requests(*, status: str | None = None, student_id: str | None = None,
                  item_kind: str | None = None, provider: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  search: str | None = None) -> list[PaymentRequest]:
    """Staff list (FINANCE)."""
    _require_finance("online payments")
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        if status not in STATUSES:
            raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("r.status = ?")
        args.append(status)
    if student_id:
        clauses.append("r.student_id = ?")
        args.append(student_id.strip())
    if item_kind:
        clauses.append("r.item_kind = ?")
        args.append(item_kind.strip().lower())
    if provider:
        clauses.append("r.provider = ?")
        args.append(provider)
    if date_from:
        clauses.append("date(r.created_at) >= ?")
        args.append(date_from)
    if date_to:
        clauses.append("date(r.created_at) <= ?")
        args.append(date_to)
    if search:
        like = f"%{search.strip()}%"
        clauses.append("(r.reference LIKE ? OR r.description LIKE ? OR "
                       "r.payer_name LIKE ? OR r.provider_txn_id LIKE ? OR "
                       "s.first_name || ' ' || s.last_name LIKE ?)")
        args += [like] * 5
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        # db-audit: ignore[DBW001] - where joins fixed clause literals only
        rows = conn.execute(
            f"{_SELECT} {where} ORDER BY r.request_id DESC", args).fetchall()
    return [_row(r) for r in rows]


def requests_for_payer(payer_kind: str, payer_id: Any) -> list[PaymentRequest]:
    """A payer's own view: requests for the students they may pay for."""
    payer = resolve_payer(payer_kind, payer_id)
    if not payer.student_ids:
        return []
    init_db()
    marks = ",".join("?" * len(payer.student_ids))
    with _connect() as conn:
        # db-audit: ignore[DBW001] - only placeholders are interpolated
        rows = conn.execute(
            f"{_SELECT} WHERE r.student_id IN ({marks}) "
            "ORDER BY r.request_id DESC", payer.student_ids).fetchall()
    return [_row(r) for r in rows]


def events(request_id: int) -> list[dict[str, Any]]:
    req = _require_request(request_id)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT at, event, detail, actor FROM online_payment_events "
            "WHERE request_id = ? ORDER BY event_id", (req.request_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Status polling ──────────────────────────────────────────────────

def check_status(request_id: int) -> PaymentRequest:
    """Ask the provider what happened to this request's checkout, and
    post the payment if it was paid. Safe to call any number of times."""
    req = _require_request(request_id)
    if req.is_offline:
        return req
    if req.status == PAID and req.is_posted:
        return req
    if req.status == PAID and not req.is_posted:
        # Paid but posting was interrupted: finish it.
        return _post(req.request_id, req.provider_txn_id or "",
                     provider_amount=req.provider_amount_pence)
    if not req.provider_session_id:
        return req
    if req.status not in (PENDING, FAILED, CANCELLED):
        return req
    provider = _prov.require_provider()
    st = provider.fetch_status(req.provider_session_id)
    return _apply_status(req, st)


def _apply_status(req: PaymentRequest,
                  st: _prov.CheckoutStatus) -> PaymentRequest:
    with _connect() as conn:
        conn.execute(
            "UPDATE online_payment_requests SET provider_state = ?, "
            "provider_amount_pence = COALESCE(?, provider_amount_pence), "
            "last_checked_at = ?, updated_at = datetime('now') "
            "WHERE request_id = ?",
            (st.state, st.amount_pence, _now(), req.request_id))
        _log(conn, req.request_id, "Status checked",
             f"{st.state} ({st.raw_status})", _actor())
    if st.state == _prov.STATE_PAID:
        if not st.txn_id:
            raise _prov.ProviderError(
                "The provider says this was paid but gave no transaction id")
        if st.reference and st.reference != req.reference:
            raise _prov.ProviderError(
                f"Provider session belongs to {st.reference}, "
                f"not {req.reference}")
        return _post(req.request_id, st.txn_id,
                     provider_amount=st.amount_pence)
    if req.status == PENDING and st.state in (_prov.STATE_EXPIRED,
                                              _prov.STATE_FAILED):
        reason = ("Checkout expired without payment"
                  if st.state == _prov.STATE_EXPIRED
                  else f"Payment failed ({st.raw_status})")
        with _connect() as conn:
            conn.execute(
                "UPDATE online_payment_requests SET status = 'Failed', "
                "failure_reason = ?, updated_at = datetime('now') "
                "WHERE request_id = ? AND status = 'Pending'",
                (reason, req.request_id))
            _log(conn, req.request_id, "Failed", reason, _actor())
    out = get_request(req.request_id, _check=False)
    assert out is not None
    return out


def check_pending(*, payer_kind: str | None = None,
                  payer_id: Any = None) -> dict[str, int]:
    """Poll every pending request (staff), or a payer's own pending ones.

    Returns counts: checked / paid / failed / still_pending / errors.
    """
    if payer_kind:
        reqs = [r for r in requests_for_payer(payer_kind, payer_id)
                if r.status == PENDING]
    else:
        reqs = list_requests(status=PENDING)
        # Also finish anything paid but not posted.
        reqs += [r for r in list_requests(status=PAID) if not r.is_posted]
    counts = {"checked": 0, "paid": 0, "failed": 0, "still_pending": 0,
              "errors": 0}
    online = [r for r in reqs if not r.is_offline]
    if online:
        _prov.require_provider()
    for r in online:
        try:
            out = check_status(r.request_id)
        except (_prov.ProviderError, ValidationError) as e:
            logger.warning("Status check for %s failed: %s", r.reference, e)
            counts["errors"] += 1
            continue
        except Exception:  # noqa: BLE001 - one bad reply must not stop the rest
            logger.exception("Status check for %s failed", r.reference)
            counts["errors"] += 1
            continue
        counts["checked"] += 1
        if out.status == PAID:
            counts["paid"] += 1
        elif out.status == FAILED:
            counts["failed"] += 1
        else:
            counts["still_pending"] += 1
    return counts


# ── Posting (idempotent) ────────────────────────────────────────────

def _claim(request_id: int, txn_id: str, provider_amount: int | None) -> bool:
    """Win the right to post *txn_id* for this request (once only)."""
    try:
        with _connect() as conn:
            cur = conn.execute(
                "UPDATE online_payment_requests SET status = 'Paid', "
                "posting_state = 'Claimed', provider_txn_id = ?, "
                "provider_amount_pence = COALESCE(?, provider_amount_pence), "
                "paid_at = COALESCE(paid_at, ?), failure_reason = NULL, "
                "updated_at = datetime('now') "
                "WHERE request_id = ? AND posting_state = '' "
                "AND status IN ('Pending', 'Failed', 'Cancelled')",
                (txn_id, provider_amount, _now(), request_id))
            if cur.rowcount:
                _log(conn, request_id, "Paid", f"transaction {txn_id}",
                     _actor())
            return bool(cur.rowcount)
    except _sql.IntegrityError:
        with _connect() as conn:
            other = conn.execute(
                "SELECT reference FROM online_payment_requests "
                "WHERE provider_txn_id = ?", (txn_id,)).fetchone()
        raise ValidationError(
            f"Transaction {txn_id} is already recorded against "
            f"{other['reference'] if other else 'another request'}") from None


def _post(request_id: int, txn_id: str, *,
          provider_amount: int | None = None) -> PaymentRequest:
    if not txn_id:
        raise ValidationError("No transaction id to post")
    _claim(request_id, txn_id, provider_amount)
    req = get_request(request_id, _check=False)
    assert req is not None
    if req.provider_txn_id != txn_id:
        raise ValidationError(
            f"{req.reference} is already paid by transaction "
            f"{req.provider_txn_id}; {txn_id} was not posted again")
    if req.is_posted:
        return req
    if (provider_amount is not None and not req.is_offline
            and provider_amount != req.amount_pence):
        # Money taken differs from what we asked for: post what was taken
        # would hide the problem; post nothing and flag it instead.
        _event(req.request_id, "Amount mismatch",
               f"provider {money(provider_amount)} vs requested "
               f"{money(req.amount_pence)}; not posted")
        raise ValidationError(
            f"{req.reference}: the provider took {money(provider_amount)} "
            f"but {money(req.amount_pence)} was requested — not posted; "
            "see Reconciliation.")
    payment_id = _post_payment(req)
    receipt_id = _receipt(req, payment_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE online_payment_requests SET posting_state = 'Posted', "
            "posted_payment_id = ?, receipt_id = ?, "
            "updated_at = datetime('now') WHERE request_id = ?",
            (payment_id, receipt_id, req.request_id))
        _log(conn, req.request_id, "Posted",
             f"{req.kind_label} payment #{payment_id}"
             + (f", receipt #{receipt_id}" if receipt_id else ""), _actor())
    logger.info("Online payment %s posted (%s #%s)", req.reference,
                req.item_kind, payment_id)
    out = get_request(req.request_id, _check=False)
    assert out is not None
    return out


def _method(req: PaymentRequest) -> str:
    return req.offline_method if req.is_offline and req.offline_method \
        else "Online"


def _post_payment(req: PaymentRequest) -> int:
    """Post through the owning module, adopting an earlier post of the
    same transaction if a previous attempt got that far."""
    ref = req.payment_reference
    assert ref is not None
    notes = (f"{'Offline' if req.is_offline else 'Online'} payment "
             f"{req.reference} ({req.provider}) from {req.payer_name or req.payer_kind}")
    by = req.created_by or _actor()
    if req.item_kind == KIND_FEE:
        from education_system.systems.sixth_form.domains.finance.domain.fees import fees as _fees
        assert req.fee_id is not None
        for p in _fees.list_payments(fee_id=req.fee_id):
            if p.reference == ref:
                return p.payment_id
        return _fees.create_payment(req.fee_id, {
            "amount": _pounds(req.amount_pence),
            "method": _FEE_METHOD.get(_method(req), "Other"),
            "status": "Cleared", "reference": ref,
            "recorded_by": by, "notes": notes}).payment_id
    if req.item_kind == KIND_TRIP:
        from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _trips
        assert req.booking_id is not None
        for p in _trips.list_payments(booking_id=req.booking_id):
            if p.reference == ref:
                return p.payment_id
        return _trips.add_payment(req.booking_id, {
            "amount": _pounds(req.amount_pence),
            "method": _TRIP_METHOD.get(_method(req), "Other"),
            "status": "Cleared", "reference": ref,
            "recorded_by": by, "notes": notes}).payment_id
    from education_system.systems.sixth_form.domains.operations.domain.catering import (
        cashless as _cashless,
    )
    return _cashless.credit_from_online_payment(req.request_id).txn_id


def _receipt(req: PaymentRequest, payment_id: int) -> int | None:
    from education_system.systems.sixth_form.domains.finance.domain.receipts import (
        receipts as _rc,
    )
    ref = req.payment_reference
    if req.receipt_id:
        return req.receipt_id
    for r in _rc.search_receipts(ref or ""):
        if r.reference == ref and r.status != "Voided":
            return r.receipt_id
    by = req.created_by or _actor()
    try:
        if req.item_kind == KIND_FEE:
            return _rc.receipt_from_fee_payment(payment_id, received_by=by).receipt_id
        if req.item_kind == KIND_TRIP:
            return _rc.receipt_from_trip_payment(payment_id, received_by=by).receipt_id
        method = "Online Portal" if not req.is_offline else (
            req.offline_method if req.offline_method in _rc.PAYMENT_METHODS
            else "Other")
        return _rc.create_receipt(
            {"payer_name": req.payer_name or _student_name(req.student_id),
             "student_id": req.student_id, "method": method,
             "status": "Issued", "received_by": by, "reference": ref,
             "notes": f"Catering top-up {req.reference}"},
            [{"description": "Catering account top-up",
              "amount": _pounds(req.amount_pence), "kind": "lunch",
              "source_id": payment_id}]).receipt_id
    except ValueError as e:
        # The payment stands; a missing receipt shows in reconciliation.
        logger.warning("Receipt for %s not created: %s", req.reference, e)
        _event(req.request_id, "Receipt not created", str(e)[:300])
        return None


def repair(request_id: int) -> PaymentRequest:
    """Finish posting a request that is Paid but not posted (FINANCE)."""
    _require_finance("repairing online payments")
    req = _require_request(request_id)
    if req.status != PAID or req.is_posted:
        raise ValidationError(f"{req.reference} does not need repair")
    return _post(req.request_id, req.provider_txn_id or "",
                 provider_amount=(None if req.is_offline
                                  else req.provider_amount_pence))


# ── Cancel ──────────────────────────────────────────────────────────

def cancel(request_id: int, *, reason: str = "") -> PaymentRequest:
    """Cancel a pending request (the payer, or FINANCE).

    The provider's checkout is expired first so it cannot be paid later;
    if it turns out it *was* paid, the payment is posted instead.
    """
    req = _require_request(request_id)
    a = _access()
    p = a.current()
    if req.status != PENDING:
        raise ValidationError(f"{req.reference} is {req.status}, not Pending")
    if not p.can(a.FINANCE) and not _can_see_request(req):
        raise a.AccessDenied("You cannot cancel this payment.")
    if req.provider_session_id and not req.is_offline:
        provider = _prov.get_provider()
        if provider is None:
            raise _prov.ProviderNotConfigured(
                "The card provider is not configured, so the checkout cannot "
                "be closed safely. " + _prov.NOT_SET_UP_MESSAGE)
        st = provider.cancel_checkout(req.provider_session_id)
        if st.state == _prov.STATE_PAID:
            return _apply_status(req, st)
    why = (reason or "").strip() or "Cancelled"
    with _connect() as conn:
        conn.execute(
            "UPDATE online_payment_requests SET status = 'Cancelled', "
            "failure_reason = ?, updated_at = datetime('now') "
            "WHERE request_id = ? AND status = 'Pending'",
            (why, req.request_id))
        _log(conn, req.request_id, "Cancelled", why, _actor())
    out = get_request(req.request_id, _check=False)
    assert out is not None
    return out


def retry_checkout(request_id: int) -> PaymentRequest:
    """Open a fresh checkout for a Failed request (same amount, same item)."""
    req = _require_request(request_id)
    if req.status != FAILED or req.is_offline:
        raise ValidationError(f"{req.reference} is {req.status}; only a "
                              "failed card payment can be retried")
    provider = _ready_provider()
    if req.payer_kind != PAYER_STAFF:
        payer = resolve_payer(req.payer_kind, req.payer_ref)
        email = payer.email
    else:
        _require_finance("retrying payment requests")
        email = None
    _validate_target(req.item_kind, req.fee_id or req.booking_id,
                     req.student_id, req.amount_pence)
    existing = _pending_for(req.item_kind, req.fee_id or req.booking_id,
                            req.student_id)
    if existing is not None:
        raise ValidationError(f"{existing.reference} is already in progress")
    with _connect() as conn:
        conn.execute(
            "UPDATE online_payment_requests SET status = 'Pending', "
            "failure_reason = NULL, updated_at = datetime('now') "
            "WHERE request_id = ? AND status = 'Failed' "
            "AND posting_state = ''", (req.request_id,))
        _log(conn, req.request_id, "Retry", None, _actor())
    fresh = get_request(req.request_id, _check=False)
    assert fresh is not None
    return _open_checkout(fresh, provider, email)


# ── Offline payments (staff) ────────────────────────────────────────

def record_offline_payment(item_kind: str, *, amount: Any, method: str,
                           target_id: Any = None, student_id: Any = None,
                           reference: str | None = None,
                           payer_name: str | None = None,
                           request_id: int | None = None) -> PaymentRequest:
    """Record money taken at the office (cash, cheque, bank transfer …).

    Goes through the same posting path as a card payment, so balances,
    receipts and reconciliation stay one record. With ``request_id`` it
    settles that pending request instead (its checkout is closed first).
    ``reference`` (cheque number, bank reference …) is required for
    anything but cash and must not have been recorded before.
    """
    _require_finance("recording offline payments")
    init_db()
    m = (method or "").strip()
    if m not in OFFLINE_METHODS:
        raise ValidationError(
            f"Method must be one of: {', '.join(OFFLINE_METHODS)}")
    ref = (reference or "").strip() or None
    if m != "Cash" and not ref:
        raise ValidationError(f"A reference is required for {m} payments")
    if request_id is not None:
        req = _require_request(int(request_id))
        if req.status != PENDING:
            raise ValidationError(f"{req.reference} is {req.status}")
        if req.provider_session_id and not req.is_offline:
            provider = _prov.get_provider()
            if provider is not None:
                st = provider.cancel_checkout(req.provider_session_id)
                if st.state == _prov.STATE_PAID:
                    _apply_status(req, st)
                    raise ValidationError(
                        f"{req.reference} had already been paid by card — "
                        "posted that instead; do not take the money again.")
        with _connect() as conn:
            conn.execute(
                "UPDATE online_payment_requests SET provider = ?, "
                "offline_method = ?, updated_at = datetime('now') "
                "WHERE request_id = ?", (PROVIDER_OFFLINE, m, req.request_id))
            _log(conn, req.request_id, "Settled offline", m, _actor())
    else:
        amount_pence = to_pence(amount)
        fee_id, booking_id, sid, desc = _validate_target(
            item_kind, target_id, student_id, amount_pence)
        if ref:
            with _connect() as conn:
                dup = conn.execute(
                    "SELECT reference FROM online_payment_requests WHERE "
                    "provider_txn_id = ?", (_offline_txn(m, ref, ""),)
                ).fetchone()
            if dup is not None:
                raise ValidationError(
                    f"{m} {ref} is already recorded ({dup['reference']})")
        kind = item_kind.strip().lower()
        a = _access()
        p = a.current()
        payer = Payer(PAYER_STAFF, p.username or "staff",
                      (payer_name or "").strip() or _student_name(sid), None,
                      [sid])
        req = _insert_request(kind=kind, fee_id=fee_id,
                              booking_id=booking_id, student_id=sid,
                              description=desc, amount_pence=amount_pence,
                              payer=payer, provider=PROVIDER_OFFLINE,
                              offline_method=m)
    txn = _offline_txn(m, ref, req.reference)
    try:
        return _post(req.request_id, txn)
    except ValidationError as e:
        if request_id is None:
            # Nothing was taken for this new request: don't leave it pending.
            with _connect() as conn:
                conn.execute(
                    "UPDATE online_payment_requests SET status = 'Cancelled', "
                    "failure_reason = ?, updated_at = datetime('now') "
                    "WHERE request_id = ? AND posting_state = ''",
                    (f"Not recorded: {e}"[:300], req.request_id))
        raise


def _offline_txn(method: str, ref: str | None, fallback: str) -> str:
    return f"OFFLINE-{method.upper().replace(' ', '')}-{ref or fallback}"


# ── Refunds (FINANCE) ───────────────────────────────────────────────

def refund(request_id: int, *, reason: str, amount: Any = None,
           method: str | None = None) -> PaymentRequest:
    """Give money back on a paid request.

    A card payment is refunded through the provider first (the money
    really goes back), then the local records follow: a fee payment is
    marked Refunded (fees has no part-refunds, so it is the whole amount),
    a trip refund is recorded through ``trips.add_refund`` (part-refunds
    allowed), a catering top-up is debited from the balance. An offline
    payment needs ``method`` for how the money was handed back.
    """
    _require_finance("refunding payments")
    req = _require_request(request_id)
    why = (reason or "").strip()
    if not why:
        raise ValidationError("A refund reason is required")
    if req.status != PAID or not req.is_posted:
        raise ValidationError(f"{req.reference} is {req.status}; only a "
                              "posted payment can be refunded")
    remaining = req.amount_pence - req.refunded_pence
    pence = remaining if amount in (None, "") else to_pence(amount, "Refund")
    if pence > remaining:
        raise ValidationError(f"Only {money(remaining)} can still be refunded")
    if req.item_kind == KIND_FEE and pence != remaining:
        raise ValidationError(
            "Fee payments are refunded in full (the fees ledger has no "
            "part-refunds)")
    if req.item_kind == KIND_CATERING:
        from education_system.systems.sixth_form.domains.operations.domain.catering import (
            cashless as _cashless,
        )
        bal = _cashless.balance_pence(req.student_id)
        if bal < pence:
            raise ValidationError(
                f"The catering balance is only {money(bal)}; that much has "
                "already been spent")
    if req.is_offline:
        m = (method or "").strip()
        if m not in OFFLINE_METHODS:
            raise ValidationError(
                "Say how the money was given back: "
                + ", ".join(OFFLINE_METHODS))
        refund_ref = f"Offline {m}"
    else:
        m = "Online"
        provider = _prov.require_provider()
        n = 1 + len([e for e in events(req.request_id)
                     if e["event"] == "Refunded"])
        pr = provider.refund(req.provider_txn_id or "", pence,
                             idempotency_key=f"sixthform-{req.reference}-refund-{n}")
        refund_ref = pr.refund_id
        # Record the provider side straight away so a local failure below
        # still leaves a trace that money went back.
        with _connect() as conn:
            conn.execute(
                "UPDATE online_payment_requests SET refunded_pence = "
                "refunded_pence + ?, refund_ref = ?, "
                "updated_at = datetime('now') WHERE request_id = ?",
                (pence, refund_ref, req.request_id))
            _log(conn, req.request_id, "Refunded",
                 f"{money(pence)} at provider ({refund_ref}): {why}", _actor())
    _local_refund(req, pence, m, why, refund_ref)
    full = (req.refunded_pence + pence) >= req.amount_pence
    with _connect() as conn:
        if req.is_offline:
            conn.execute(
                "UPDATE online_payment_requests SET refunded_pence = "
                "refunded_pence + ?, refund_ref = ?, "
                "updated_at = datetime('now') WHERE request_id = ?",
                (pence, refund_ref, req.request_id))
            _log(conn, req.request_id, "Refunded",
                 f"{money(pence)} {refund_ref}: {why}", _actor())
        if full:
            conn.execute(
                "UPDATE online_payment_requests SET status = 'Refunded', "
                "updated_at = datetime('now') WHERE request_id = ?",
                (req.request_id,))
    if full and req.receipt_id:
        from education_system.systems.sixth_form.domains.finance.domain.receipts import (
            receipts as _rc,
        )
        try:
            _rc.void_receipt(req.receipt_id, f"Refunded: {why}")
        except ValueError as e:
            logger.warning("Could not void receipt for %s: %s", req.reference, e)
    out = get_request(req.request_id, _check=False)
    assert out is not None
    return out


def _local_refund(req: PaymentRequest, pence: int, method: str, why: str,
                  refund_ref: str) -> None:
    by = _actor()
    if req.item_kind == KIND_FEE:
        from education_system.systems.sixth_form.domains.finance.domain.fees import fees as _fees
        assert req.posted_payment_id is not None
        _fees.update_payment(req.posted_payment_id, {
            "status": "Refunded",
            "notes": f"Refunded {money(pence)} ({refund_ref}) by {by}: {why}"})
    elif req.item_kind == KIND_TRIP:
        from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _trips
        assert req.booking_id is not None
        _trips.add_refund(req.booking_id, {
            "amount": _pounds(pence),
            "method": _TRIP_REFUND_METHOD.get(method, "Other"),
            "reason": why, "refunded_by": by, "reference": refund_ref,
            "payment_id": req.posted_payment_id})
    else:
        from education_system.systems.sixth_form.domains.operations.domain.catering import (
            cashless as _cashless,
        )
        _cashless.debit_for_online_refund(req.request_id, pence,
                                          reason=f"{why} ({refund_ref})")


# ── Reconciliation (FINANCE) ────────────────────────────────────────

def _posted_record(req: PaymentRequest) -> tuple[int | None, str | None]:
    """(amount posted in pence, its status) for the request's payment."""
    if not req.posted_payment_id:
        return None, None
    if req.item_kind == KIND_FEE:
        from education_system.systems.sixth_form.domains.finance.domain.fees import fees as _fees
        p = _fees.get_payment(req.posted_payment_id)
        return ((int(round(p.amount * 100)), p.status) if p else (None, "Missing"))
    if req.item_kind == KIND_TRIP:
        from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _trips
        p = _trips.get_payment(req.posted_payment_id)
        return ((int(round(p.amount * 100)), p.status) if p else (None, "Missing"))
    from education_system.systems.sixth_form.domains.operations.domain.catering import (
        cashless as _cashless,
    )
    t = _cashless.get_transaction(req.posted_payment_id)
    return ((t.amount_pence, "Cleared") if t else (None, "Missing"))


def reconciliation(*, date_from: str | None = None,
                   date_to: str | None = None,
                   issues_only: bool = False) -> list[ReconRow]:
    """Provider payments vs what was posted, one row per request."""
    from education_system.systems.sixth_form.domains.finance.domain.receipts import (
        receipts as _rc,
    )
    rows = list_requests(date_from=date_from, date_to=date_to)
    stale_before = (_dt.datetime.utcnow()
                    - _dt.timedelta(hours=STALE_PENDING_HOURS)
                    ).isoformat(sep=" ", timespec="seconds")
    out: list[ReconRow] = []
    for r in rows:
        issues: list[str] = []
        amt, pstat = _posted_record(r)
        rnum = None
        if r.receipt_id:
            rc = _rc.get_receipt(r.receipt_id)
            rnum = rc.receipt_number if rc else None
            if rc is None:
                issues.append("Receipt missing")
            elif rc.status == "Voided" and r.status != REFUNDED:
                issues.append("Receipt voided but payment stands")
        if r.status == PAID and not r.is_posted:
            issues.append("Paid but not posted — use Repair")
        if r.is_posted:
            if pstat == "Missing":
                issues.append("Posted payment has been deleted")
            elif amt is not None and amt != r.amount_pence:
                issues.append(f"Posted {money(amt)} ≠ paid {money(r.amount_pence)}")
            if r.status == PAID and r.item_kind != KIND_CATERING \
                    and pstat not in (None, "Cleared"):
                issues.append(f"Posted payment is now {pstat}")
            if r.status == REFUNDED and r.item_kind == KIND_FEE \
                    and pstat == "Cleared":
                issues.append("Refunded but fee payment still Cleared")
            if r.status in (PAID, REFUNDED) and not r.receipt_id:
                issues.append("No receipt")
        if (r.provider_amount_pence is not None and not r.is_offline
                and r.provider_amount_pence != r.amount_pence):
            issues.append(f"Provider took {money(r.provider_amount_pence)}")
        if r.status == PENDING and r.created_at < stale_before:
            issues.append(f"Pending over {STALE_PENDING_HOURS}h — check status")
        if r.refunded_pence and r.status == PAID \
                and r.refunded_pence >= r.amount_pence:
            issues.append("Refunded at provider, local records not updated")
        if issues_only and not issues:
            continue
        out.append(ReconRow(r, amt, pstat, rnum, issues))
    return out


def compare_with_provider(days: int = 7) -> list[dict[str, Any]]:
    """Paid checkouts at the provider in the last *days* that are not a
    posted Paid/Refunded request here (a network call; FINANCE)."""
    _require_finance("payment reconciliation")
    provider = _prov.require_provider()
    try:
        days = max(1, min(90, int(days)))
    except (TypeError, ValueError):
        raise ValidationError("Days must be a whole number") from None
    since = int((_dt.datetime.now() - _dt.timedelta(days=days)).timestamp())
    init_db()
    out: list[dict[str, Any]] = []
    for st in provider.recent_checkouts(since_epoch=since, limit=500):
        if st.state != _prov.STATE_PAID:
            continue
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM online_payment_requests WHERE "
                "provider_session_id = ? OR provider_txn_id = ? OR reference = ?",
                (st.session_id, st.txn_id, st.reference or "")).fetchone()
        req = _row(r) if r else None
        if req is not None and req.is_posted and req.status in (PAID, REFUNDED):
            continue
        out.append({
            "session_id": st.session_id, "txn_id": st.txn_id,
            "reference": st.reference, "amount_pence": st.amount_pence,
            "created_at": st.created_at,
            "request_id": req.request_id if req else None,
            "local_status": req.status if req else None,
            "issue": ("Paid at provider, not posted here — Check status"
                      if req else "Paid at provider, no matching request")})
    return out


def summary(*, date_from: str | None = None,
            date_to: str | None = None) -> OnlineSummary:
    rows = list_requests(date_from=date_from, date_to=date_to)
    s = OnlineSummary(by_status={k: 0 for k in STATUSES},
                      by_kind_pence={k: 0 for k in ITEM_KINDS})
    for r in rows:
        s.by_status[r.status] = s.by_status.get(r.status, 0) + 1
        if r.status in (PAID, REFUNDED):
            s.paid_pence += r.amount_pence
            s.refunded_pence += r.refunded_pence
            s.by_kind_pence[r.item_kind] += r.amount_pence - r.refunded_pence
            if r.is_offline:
                s.offline_paid_pence += r.amount_pence
            else:
                s.online_paid_pence += r.amount_pence
        elif r.status == PENDING:
            s.pending_pence += r.amount_pence
    s.issues = sum(1 for x in reconciliation(date_from=date_from,
                                             date_to=date_to) if x.issues)
    return s
