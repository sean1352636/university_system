"""Training requests: learners a linked apprenticeship provider or FE college
asked this provider to train.

The sender asks through the platform
(``platform.cross_system.training_provider_requests``). The adapter finds
the learner (or adds them) and records the request here, with who pays
(``bill_to``: the sender or the employer, set up as a client). The provider
then works it:

* **Declined** or **Withdrawn** (with the reason) goes back to the sender;
* booking the learner on a session marks it **Booked** (or *Waiting list*)
  and tells the sender; a new booking bills ``bill_to`` unless another
  client is chosen;
* a certificate marks it **Certificated**, a fail **Not passed**, a no-show
  **Did not attend** - each goes back to the sender (an apprenticeship
  provider gets the certificate as off-the-job hours awaiting approval).

A request can also be recorded by hand (a sender not on the platform): it
is the same record without a platform link.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.modules import learners

STATUSES = ("New", "Contacted", "Waiting list", "Booked", "Certificated", "Did not attend",
            "Not passed", "Declined", "Withdrawn")
#: A request in one of these can be booked (again).
OPEN_STATUSES = ("New", "Contacted", "Waiting list", "Did not attend", "Not passed")
CLOSED_STATUSES = ("Declined", "Withdrawn")
SOURCES = {"apprenticeships": "Apprenticeships", "fe_college": "FE College"}
PAYERS = ("Sender pays (purchase order)", "Employer pays", "Learner pays",
          "Funded (grant / skills fund)")


def _today() -> str:
    return date.today().isoformat()


def _check(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    received = r.to_date(r.parse_date(merged.get("received")))
    if received and received > date.today():
        raise ValidationError("The date received can't be in the future.")
    if merged.get("status") in CLOSED_STATUSES and not (merged.get("decision_reason")
                                                         or "").strip():
        raise ValidationError(f"Say why the request is {merged['status'].lower()} - the "
                              "sender is told.")
    was = (old or {}).get("status")
    if was in CLOSED_STATUSES and merged.get("status") != was and \
            merged.get("transition_id"):
        raise ValidationError(f"This request is {was.lower()} and the sender has been "
                              "told. Record a new request instead.")


def _source_label(row: dict) -> str:
    return SOURCES.get(row.get("source_system") or "", "")


TRAINING_REQUESTS = RecordType(
    key="training_requests", title="Training Requests", singular="training request",
    order_by="received DESC, id DESC", check=_check, filters=("status", "payer"),
    after_commit=learners.platform_hook("request_saved"),
    describe=lambda row: f"{row.get('course') or 'Request'} ({row.get('status')})",
    computed=(("Linked sender", _source_label),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("received", "Received", "date", required=True, default=_today),
        Field("sender", "From", required=True),
        Field("course", "Course asked for", required=True),
        Field("course_id", "Our course", "ref", ref="courses", listed=False,
              on_delete="SET NULL"),
        Field("reason", "Why", "long", listed=False),
        Field("needed_by", "Needed by", "date"),
        Field("payer", "Who pays", "choice", PAYERS, required=True, default=PAYERS[0]),
        Field("bill_to", "Bill to (client)", "ref", ref="clients", listed=False,
              on_delete="SET NULL"),
        Field("po_number", "PO number", listed=False),
        Field("referrer", "Requested by (name)", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="New"),
        Field("decision_reason", "Declined / withdrawn because", listed=False),
        Field("session_id", "Booked session", "ref", ref="sessions", form=False,
              listed=False, on_delete="SET NULL"),
        # Set by the platform for a linked sender's request.
        Field("source_system", "Linked sender", form=False, listed=False),
        Field("transition_id", "Platform request", form=False, listed=False),
        Field("consent_to_share", "Learner consented to sharing", "bool", form=False,
              listed=False),
        Field("safeguarding_ref", "Safeguarding file reference", form=False, listed=False),
    ),
)


def for_transition(transition_id: str) -> dict | None:
    rows = r.list_records(TRAINING_REQUESTS, equals={"transition_id": transition_id})
    return rows[0] if rows else None


def linked_for(learner_id: int, statuses: tuple[str, ...] = OPEN_STATUSES) -> list[dict]:
    """The learner's platform-linked requests in *statuses*, oldest first."""
    rows = [x for x in r.list_records(TRAINING_REQUESTS, learner_id=learner_id)
            if x.get("transition_id") and x.get("status") in statuses]
    return sorted(rows, key=lambda x: x["id"])


def billing_for(conn, learner_id: int) -> tuple[int | None, str | None]:
    """``(bill_to, po_number)`` of the learner's oldest open request with a
    payer set up - what a new booking bills by default. Called from the
    booking check with its connection (this table may not exist yet)."""
    try:
        row = conn.execute(
            "SELECT bill_to, po_number FROM training_requests WHERE learner_id = ? AND "
            f"status IN ({', '.join('?' * len(OPEN_STATUSES))}) AND bill_to IS NOT NULL "
            "ORDER BY id LIMIT 1", (learner_id, *OPEN_STATUSES)).fetchone()
    except Exception:  # noqa: BLE001 - no requests table: nothing to default from
        return None, None
    return (row[0], row[1]) if row else (None, None)
