"""Sixth-form alumni — Campaigns, donations, pledges and the fundraising extensions (#31-#36).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    BEQUEST_STATUSES,
    CAMPAIGN_STATUSES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_PLEDGE_STATUS,
    DONOR_STAGES,
    PAYMENT_METHODS,
    PLEDGE_STATUSES,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    _log_action,
)
from .db import (
    IntegrationError,
    ValidationError,
    _connect,
    _require,
    _validate_date,
    _validate_email,
    init_db,
)


# ── Campaigns / donations / pledges ──────────────────────────────

@dataclass
class Campaign:
    campaign_id: int
    name: str
    description: str | None
    target_pence: int | None
    start_on: str | None
    end_on: str | None
    status: str
    created_at: str


@dataclass
class Donation:
    donation_id: int
    alumni_id: int
    campaign_id: int | None
    donation_date: str
    amount_pence: int
    gift_aid: bool
    payment_method: str | None
    anonymous: bool
    restricted_to: str | None
    notes: str | None
    created_at: str


@dataclass
class Pledge:
    pledge_id: int
    alumni_id: int
    campaign_id: int | None
    pledged_on: str
    amount_pence: int
    due_by: str | None
    status: str
    notes: str | None
    created_at: str


def _row_campaign(r: db.Row) -> Campaign:
    return Campaign(
        campaign_id=r["campaign_id"], name=r["name"],
        description=r["description"],
        target_pence=(int(r["target_pence"])
                        if r["target_pence"] is not None else None),
        start_on=r["start_on"], end_on=r["end_on"],
        status=r["status"], created_at=r["created_at"],
    )


def _row_donation(r: db.Row) -> Donation:
    return Donation(
        donation_id=r["donation_id"], alumni_id=r["alumni_id"],
        campaign_id=r["campaign_id"],
        donation_date=r["donation_date"],
        amount_pence=int(r["amount_pence"]),
        gift_aid=bool(r["gift_aid"]),
        payment_method=r["payment_method"],
        anonymous=bool(r["anonymous"]),
        restricted_to=r["restricted_to"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_pledge(r: db.Row) -> Pledge:
    return Pledge(
        pledge_id=r["pledge_id"], alumni_id=r["alumni_id"],
        campaign_id=r["campaign_id"],
        pledged_on=r["pledged_on"],
        amount_pence=int(r["amount_pence"]),
        due_by=r["due_by"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"],
    )


def create_campaign(payload: dict[str, Any]) -> Campaign:
    init_db()
    name = _require(payload.get("name"), "Campaign name").strip()
    status = (payload.get("status") or DEFAULT_CAMPAIGN_STATUS).strip()
    if status not in CAMPAIGN_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(CAMPAIGN_STATUSES)}")
    has_target = (payload.get("target_pence") not in (None, "")
                    or payload.get("target") not in (None, ""))
    target_pence = (_resolve_money(payload, "target_pence", "target",
                                       "Target", allow_zero=True,
                                       required=False)
                      if has_target else None)
    start = _validate_date(payload.get("start_on"), "Start")
    end   = _validate_date(payload.get("end_on"), "End")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_campaigns
                       (name, description, target_pence, start_on,
                        end_on, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name,
                 (payload.get("description") or "").strip() or None,
                 target_pence, start, end, status))
            conn.commit()
        except db.IntegrityError:
            raise ValidationError(
                f"A campaign called '{name}' already exists") \
                from None
        r = conn.execute(
            "SELECT * FROM alumni_campaigns WHERE campaign_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_campaign(r)
    _log_action("campaign.create", campaign_id=out.campaign_id,
                  name=out.name,
                  target_pence=out.target_pence,
                  status=out.status)
    return out


def get_campaign(campaign_id: int) -> Campaign | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_campaigns WHERE campaign_id = ?",
            (campaign_id,)).fetchone()
    return _row_campaign(r) if r else None


def list_campaigns(*, status: str | None = None) -> list[Campaign]:
    init_db()
    sql = "SELECT * FROM alumni_campaigns"
    args: list[Any] = []
    if status:
        if status not in CAMPAIGN_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(CAMPAIGN_STATUSES)}")
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        return [_row_campaign(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_campaign_status(campaign_id: int, status: str) -> Campaign:
    if status not in CAMPAIGN_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(CAMPAIGN_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_campaigns SET status = ? "
            "WHERE campaign_id = ?", (status, campaign_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No campaign #{campaign_id}")
        r = conn.execute(
            "SELECT * FROM alumni_campaigns WHERE campaign_id = ?",
            (campaign_id,)).fetchone()
    return _row_campaign(r)


def delete_campaign(campaign_id: int) -> bool:
    """Deletes the campaign and (via FK SET NULL) leaves donations
    and pledges intact but no longer associated with a campaign."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_campaigns WHERE campaign_id = ?",
            (campaign_id,))
        conn.commit()
        return cur.rowcount > 0


def _original_record_donation(alumni_id: int,
                     payload: dict[str, Any]) -> Donation:
    init_db()
    amount_pence = _resolve_money(payload, "amount_pence", "amount",
                                       "Amount")
    method = (payload.get("payment_method") or "").strip()
    if method and method not in PAYMENT_METHODS:
        raise ValidationError(
            f"Payment method must be one of: "
            f"{', '.join(PAYMENT_METHODS)}")
    day = _validate_date(payload.get("donation_date")
                            or _dt.date.today().isoformat(),
                          "Donation date", required=True)
    cid = payload.get("campaign_id")
    if cid in (None, ""):
        cid = None
    else:
        cid = int(cid)
        if get_campaign(cid) is None:
            raise ValidationError(f"No campaign #{cid}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_donations
                   (alumni_id, campaign_id, donation_date, amount_pence,
                    gift_aid, payment_method, anonymous,
                    restricted_to, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, cid, day, amount_pence,
             1 if payload.get("gift_aid") else 0,
             method or None,
             1 if payload.get("anonymous") else 0,
             (payload.get("restricted_to") or "").strip() or None,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_donations WHERE donation_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_donation(r)
    _log_action("donation.record", alumni_id=alumni_id,
                  donation_id=out.donation_id,
                  amount_pence=out.amount_pence,
                  campaign_id=out.campaign_id,
                  gift_aid=out.gift_aid)
    return out


def list_donations(*, alumni_id: int | None = None,
                      campaign_id: int | None = None
                      ) -> list[Donation]:
    init_db()
    clauses, args = [], []
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if campaign_id is not None:
        clauses.append("campaign_id = ?")
        args.append(int(campaign_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_donations {where} "
            "ORDER BY donation_date DESC, donation_id DESC")
    with _connect() as conn:
        return [_row_donation(r)
                  for r in conn.execute(sql, args).fetchall()]


def delete_donation(donation_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_donations WHERE donation_id = ?",
            (donation_id,))
        conn.commit()
        return cur.rowcount > 0


def add_pledge(alumni_id: int, payload: dict[str, Any]) -> Pledge:
    init_db()
    amount_pence = _resolve_money(payload, "amount_pence", "amount",
                                       "Pledge amount")
    pledged = _validate_date(payload.get("pledged_on")
                                 or _dt.date.today().isoformat(),
                               "Pledged on", required=True)
    due_by = _validate_date(payload.get("due_by"), "Due by")
    status = (payload.get("status") or DEFAULT_PLEDGE_STATUS).strip()
    if status not in PLEDGE_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PLEDGE_STATUSES)}")
    cid = payload.get("campaign_id")
    if cid in (None, ""):
        cid = None
    else:
        cid = int(cid)
        if get_campaign(cid) is None:
            raise ValidationError(f"No campaign #{cid}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_pledges
                   (alumni_id, campaign_id, pledged_on, amount_pence,
                    due_by, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, cid, pledged, amount_pence, due_by, status,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_pledges WHERE pledge_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_pledge(r)


def list_pledges(*, alumni_id: int | None = None,
                    campaign_id: int | None = None,
                    open_only: bool = False) -> list[Pledge]:
    init_db()
    clauses, args = [], []
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if campaign_id is not None:
        clauses.append("campaign_id = ?")
        args.append(int(campaign_id))
    if open_only:
        clauses.append("status = 'Open'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_pledges {where} "
            "ORDER BY pledged_on DESC, pledge_id DESC")
    with _connect() as conn:
        return [_row_pledge(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_pledge_status(pledge_id: int, status: str) -> Pledge:
    if status not in PLEDGE_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PLEDGE_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_pledges SET status = ? "
            "WHERE pledge_id = ?", (status, pledge_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No pledge #{pledge_id}")
        r = conn.execute(
            "SELECT * FROM alumni_pledges WHERE pledge_id = ?",
            (pledge_id,)).fetchone()
    return _row_pledge(r)


def delete_pledge(pledge_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_pledges WHERE pledge_id = ?",
            (pledge_id,))
        conn.commit()
        return cur.rowcount > 0


@dataclass
class CampaignTotals:
    campaign_id: int
    name: str
    target_pence: int | None
    raised_pence: int       # actual donations
    pledged_open_pence: int  # outstanding pledges (status=Open)
    donor_count: int


def campaign_totals(campaign_id: int) -> CampaignTotals:
    c = get_campaign(campaign_id)
    if c is None:
        raise ValidationError(f"No campaign #{campaign_id}")
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) AS raised, "
            "COUNT(DISTINCT alumni_id) AS donors "
            "FROM alumni_donations WHERE campaign_id = ?",
            (campaign_id,)).fetchone()
        p = conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) AS open "
            "FROM alumni_pledges "
            "WHERE campaign_id = ? AND status = 'Open'",
            (campaign_id,)).fetchone()
    return CampaignTotals(
        campaign_id=c.campaign_id, name=c.name,
        target_pence=c.target_pence,
        raised_pence=int(r["raised"]),
        pledged_open_pence=int(p["open"]),
        donor_count=int(r["donors"]))


# ── #31 Gift-Aid declarations ────────────────────────────────────

@dataclass
class GiftAidDeclaration:
    declaration_id: int
    alumni_id: int
    valid_from: str
    valid_until: str | None
    full_name: str
    address: str
    postcode: str
    signed_at: str
    withdrawn_at: str | None
    notes: str | None


def _row_gad(r: db.Row) -> GiftAidDeclaration:
    return GiftAidDeclaration(
        declaration_id=r["declaration_id"], alumni_id=r["alumni_id"],
        valid_from=r["valid_from"], valid_until=r["valid_until"],
        full_name=r["full_name"], address=r["address"],
        postcode=r["postcode"], signed_at=r["signed_at"],
        withdrawn_at=r["withdrawn_at"], notes=r["notes"])


def add_gift_aid_declaration(alumni_id: int, *,
                                  valid_from: str,
                                  full_name: str, address: str,
                                  postcode: str,
                                  valid_until: str | None = None,
                                  notes: str | None = None,
                                  actor: str | None = None
                                  ) -> GiftAidDeclaration:
    init_db()
    vfrom = _validate_date(valid_from, "Valid from", required=True)
    vuntil = _validate_date(valid_until, "Valid until", required=False)
    if not (full_name or "").strip():
        raise ValidationError("Full name is required")
    if not (address or "").strip():
        raise ValidationError("Address is required")
    if not (postcode or "").strip():
        raise ValidationError("Postcode is required")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_gift_aid_declarations
                   (alumni_id, valid_from, valid_until,
                    full_name, address, postcode, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, vfrom, vuntil,
             full_name.strip(), address.strip(), postcode.strip(),
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_gift_aid_declarations "
            "WHERE declaration_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("gad.add", actor=actor, alumni_id=alumni_id)
    return _row_gad(r)


def withdraw_gift_aid_declaration(declaration_id: int, *,
                                       when: str | None = None,
                                       actor: str | None = None
                                       ) -> GiftAidDeclaration:
    init_db()
    when_iso = when or _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_gift_aid_declarations "
            "SET withdrawn_at = ? WHERE declaration_id = ? "
            "  AND withdrawn_at IS NULL",
            (when_iso, declaration_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No active declaration #{declaration_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_gift_aid_declarations "
            "WHERE declaration_id = ?",
            (declaration_id,)).fetchone()
    _log_action("gad.withdraw", actor=actor,
                  declaration_id=declaration_id)
    return _row_gad(r)


def get_active_gift_aid(alumni_id: int, on: str | None = None
                              ) -> GiftAidDeclaration | None:
    init_db()
    on = on or _dt.date.today().isoformat()
    with _connect() as conn:
        r = conn.execute(
            """SELECT * FROM alumni_gift_aid_declarations
                WHERE alumni_id = ?
                  AND valid_from <= ?
                  AND (valid_until IS NULL OR valid_until >= ?)
                  AND withdrawn_at IS NULL
                ORDER BY valid_from DESC LIMIT 1""",
            (alumni_id, on, on)).fetchone()
    return _row_gad(r) if r else None


def export_r68_csv(out_path: str | Path,  # type: ignore[name-defined]
                       *, year_start: str, year_end: str,
                       actor: str | None = None) -> int:
    """Write an HMRC R68-style CSV of every donation flagged
    ``gift_aid=1`` and covered by an active declaration in the
    window. Returns the number of rows written."""
    init_db()
    from pathlib import Path as _Path
    import csv as _csv
    yfrom = _validate_date(year_start, "Year start", required=True)
    yto = _validate_date(year_end, "Year end", required=True)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT d.donation_id, d.donation_date, d.amount_pence,
                       a.first_name, a.last_name, a.address,
                       d.alumni_id
                  FROM alumni_donations d
                  JOIN alumni a ON a.alumni_id = d.alumni_id
                 WHERE d.gift_aid = 1
                   AND d.donation_date BETWEEN ? AND ?""",
            (yfrom, yto)).fetchall()
    p = _Path(out_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrationError(
            f"Cannot create output directory {p.parent}: {exc}") from exc
    count = 0
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["Title", "First name", "Last name",
                          "House no/name", "Postcode",
                          "Aggregated donations", "Sponsored event",
                          "Donation date", "Amount (£)"])
            for r in rows:
                gad = get_active_gift_aid(
                    r["alumni_id"], on=r["donation_date"])
                if gad is None:
                    continue
                postcode = gad.postcode
                house = gad.address.split(",")[0].strip()
                amount = int(r["amount_pence"]) / 100
                w.writerow(["", r["first_name"], r["last_name"],
                              house, postcode, "", "",
                              r["donation_date"], f"{amount:.2f}"])
                count += 1
    except OSError as exc:
        raise IntegrationError(
            f"Could not write {p}: {exc}") from exc
    _log_action("gad.r68", actor=actor, path=str(p), rows=count)
    return count


# ── #32 Recurring donations ──────────────────────────────────────

@dataclass
class RecurringSchedule:
    schedule_id: int
    alumni_id: int
    campaign_id: int | None
    amount_pence: int
    frequency: str
    next_charge_on: str
    status: str
    failure_count: int
    fund_code: str | None
    payment_method: str | None
    started_on: str
    cancelled_on: str | None
    notes: str | None


def _row_rec(r: db.Row) -> RecurringSchedule:
    return RecurringSchedule(
        schedule_id=r["schedule_id"], alumni_id=r["alumni_id"],
        campaign_id=r["campaign_id"],
        amount_pence=int(r["amount_pence"]),
        frequency=r["frequency"], next_charge_on=r["next_charge_on"],
        status=r["status"],
        failure_count=int(r["failure_count"]),
        fund_code=r["fund_code"], payment_method=r["payment_method"],
        started_on=r["started_on"], cancelled_on=r["cancelled_on"],
        notes=r["notes"])


def _advance_date(d: _dt.date, frequency: str) -> _dt.date:
    if frequency == "Monthly":
        m = d.month + 1
        y = d.year + (1 if m > 12 else 0)
        m = ((m - 1) % 12) + 1
        # Clamp day to the new month's last day.
        for day in (d.day, 28, 29, 30, 31):
            try:
                return _dt.date(y, m, min(day, 28))
            except ValueError:
                continue
        return _dt.date(y, m, 28)
    if frequency == "Quarterly":
        return _advance_date(_advance_date(_advance_date(d, "Monthly"),
                                                "Monthly"), "Monthly")
    if frequency == "Annually":
        try:
            return d.replace(year=d.year + 1)
        except ValueError:
            return _dt.date(d.year + 1, 2, 28)
    raise ValidationError(f"Unknown frequency {frequency!r}")


def create_recurring(alumni_id: int, *,
                          amount_pence: int, frequency: str = "Monthly",
                          next_charge_on: str | None = None,
                          campaign_id: int | None = None,
                          fund_code: str | None = None,
                          payment_method: str | None = None,
                          notes: str | None = None,
                          actor: str | None = None
                          ) -> RecurringSchedule:
    init_db()
    if amount_pence <= 0:
        raise ValidationError("amount_pence must be > 0")
    if frequency not in RECURRING_FREQS:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(RECURRING_FREQS)}")
    nxt = _validate_date(next_charge_on, "Next charge",
                             required=False) \
        or _dt.date.today().isoformat()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_recurring_donations
                   (alumni_id, campaign_id, amount_pence, frequency,
                    next_charge_on, fund_code, payment_method, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, campaign_id, amount_pence, frequency, nxt,
             (fund_code or "").strip() or None,
             (payment_method or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_recurring_donations "
            "WHERE schedule_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("recurring.create", actor=actor,
                  alumni_id=alumni_id,
                  amount_pence=amount_pence, frequency=frequency)
    return _row_rec(r)


def list_recurring(*, alumni_id: int | None = None,
                        status: str | None = None
                        ) -> list[RecurringSchedule]:
    init_db()
    sql = "SELECT * FROM alumni_recurring_donations WHERE 1=1"
    params: list[Any] = []
    if alumni_id is not None:
        sql += " AND alumni_id = ?"; params.append(alumni_id)
    if status:
        sql += " AND status = ?"; params.append(status)
    sql += " ORDER BY next_charge_on"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_rec(r) for r in rows]


def set_recurring_status(schedule_id: int, status: str, *,
                              actor: str | None = None
                              ) -> RecurringSchedule:
    init_db()
    if status not in RECURRING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(RECURRING_STATUSES)}")
    cancelled = _dt.date.today().isoformat() \
        if status == "Cancelled" else None
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_recurring_donations "
            "SET status = ?, cancelled_on = COALESCE(?, cancelled_on) "
            "WHERE schedule_id = ?",
            (status, cancelled, schedule_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No schedule #{schedule_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_recurring_donations "
            "WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
    _log_action("recurring.status", actor=actor,
                  schedule_id=schedule_id, status=status)
    return _row_rec(r)


@dataclass
class RecurringTick:
    schedule_id: int
    alumni_id: int
    amount_pence: int
    donation_id: int | None
    success: bool
    error: str | None


def tick_recurring(*, today: _dt.date | None = None,
                        charge: Callable[[RecurringSchedule], bool]
                        | None = None,
                        actor: str | None = None
                        ) -> list[RecurringTick]:
    """Charge every Active schedule whose ``next_charge_on`` ≤ today.
    Default behaviour (``charge=None``) treats each charge as a
    success and records a corresponding ``alumni_donations`` row.
    Pass a callable to integrate with a real PSP — return ``True`` on
    success and ``False`` (raise) on failure. Three consecutive
    failures auto-flips the status to 'Failed'."""
    init_db()
    today = today or _dt.date.today()
    out: list[RecurringTick] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_recurring_donations "
            "WHERE status = 'Active' AND next_charge_on <= ?",
            (today.isoformat(),)).fetchall()
    for r in rows:
        sched = _row_rec(r)
        ok = True
        error: str | None = None
        if charge is not None:
            try:
                ok = bool(charge(sched))
            except Exception as exc:
                ok = False
                error = str(exc)[:200]
        donation_id: int | None = None
        if ok:
            d = record_donation(sched.alumni_id, {
                "donation_date": today.isoformat(),
                "amount_pence": sched.amount_pence,
                "campaign_id": sched.campaign_id,
                "payment_method": sched.payment_method or "Direct Debit",
                "notes": f"Recurring schedule #{sched.schedule_id}",
            })
            donation_id = d.donation_id
            with _connect() as conn:
                nxt = _advance_date(_dt.date.fromisoformat(
                    sched.next_charge_on), sched.frequency)
                conn.execute(
                    "UPDATE alumni_recurring_donations "
                    "SET next_charge_on = ?, failure_count = 0 "
                    "WHERE schedule_id = ?",
                    (nxt.isoformat(), sched.schedule_id))
                conn.commit()
        else:
            with _connect() as conn:
                new_fails = sched.failure_count + 1
                new_status = "Failed" if new_fails >= 3 else "Active"
                conn.execute(
                    "UPDATE alumni_recurring_donations "
                    "SET failure_count = ?, status = ? "
                    "WHERE schedule_id = ?",
                    (new_fails, new_status, sched.schedule_id))
                conn.commit()
        out.append(RecurringTick(
            schedule_id=sched.schedule_id,
            alumni_id=sched.alumni_id,
            amount_pence=sched.amount_pence,
            donation_id=donation_id, success=ok, error=error))
    _log_action("recurring.tick", actor=actor,
                  processed=len(out),
                  failed=sum(1 for t in out if not t.success))
    return out


# ── #33 Donor pipeline (CRM stages) ──────────────────────────────

@dataclass
class DonorPipeline:
    alumni_id: int
    stage: str
    owner_staff_id: str | None
    next_action: str | None
    next_action_on: str | None
    capacity_pence: int | None
    notes: str | None
    updated_at: str


def _row_pipeline(r: db.Row) -> DonorPipeline:
    return DonorPipeline(
        alumni_id=r["alumni_id"], stage=r["stage"],
        owner_staff_id=r["owner_staff_id"],
        next_action=r["next_action"],
        next_action_on=r["next_action_on"],
        capacity_pence=r["capacity_pence"],
        notes=r["notes"], updated_at=r["updated_at"])


def set_donor_stage(alumni_id: int, stage: str, *,
                        owner_staff_id: str | None = None,
                        next_action: str | None = None,
                        next_action_on: str | None = None,
                        capacity_pence: int | None = None,
                        notes: str | None = None,
                        actor: str | None = None) -> DonorPipeline:
    init_db()
    if stage not in DONOR_STAGES:
        raise ValidationError(
            f"Stage must be one of: {', '.join(DONOR_STAGES)}")
    nxt = _validate_date(next_action_on, "Next action on",
                             required=False)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        prev = conn.execute(
            "SELECT stage FROM alumni_donor_pipeline "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
        prev_stage = prev["stage"] if prev else None
        conn.execute(
            """INSERT INTO alumni_donor_pipeline
                   (alumni_id, stage, owner_staff_id, next_action,
                    next_action_on, capacity_pence, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id) DO UPDATE SET
                   stage          = excluded.stage,
                   owner_staff_id = excluded.owner_staff_id,
                   next_action    = excluded.next_action,
                   next_action_on = excluded.next_action_on,
                   capacity_pence = excluded.capacity_pence,
                   notes          = excluded.notes,
                   updated_at     = excluded.updated_at""",
            (alumni_id, stage,
             (owner_staff_id or "").strip() or None,
             (next_action or "").strip() or None, nxt,
             capacity_pence, (notes or "").strip() or None, now))
        if prev_stage != stage:
            conn.execute(
                """INSERT INTO alumni_donor_pipeline_log
                       (alumni_id, from_stage, to_stage,
                        changed_by, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (alumni_id, prev_stage, stage, actor,
                 (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_donor_pipeline "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    _log_action("pipeline.stage", actor=actor,
                  alumni_id=alumni_id, stage=stage,
                  from_stage=prev_stage)
    return _row_pipeline(r)


def get_donor_pipeline(alumni_id: int) -> DonorPipeline | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_donor_pipeline "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    return _row_pipeline(r) if r else None


def list_donor_pipeline(*, stage: str | None = None,
                              owner_staff_id: str | None = None
                              ) -> list[DonorPipeline]:
    init_db()
    sql = "SELECT * FROM alumni_donor_pipeline WHERE 1=1"
    params: list[Any] = []
    if stage:
        sql += " AND stage = ?"; params.append(stage)
    if owner_staff_id:
        sql += " AND owner_staff_id = ?"; params.append(owner_staff_id)
    sql += " ORDER BY next_action_on ASC NULLS LAST"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_pipeline(r) for r in rows]


# ── #34 Funds (restricted vs unrestricted) ───────────────────────

@dataclass
class Fund:
    fund_id: int
    code: str
    name: str
    restricted: bool
    description: str | None
    created_at: str


def _row_fund(r: db.Row) -> Fund:
    return Fund(
        fund_id=r["fund_id"], code=r["code"], name=r["name"],
        restricted=bool(r["restricted"]),
        description=r["description"], created_at=r["created_at"])


def upsert_fund(code: str, name: str, *,
                    restricted: bool = False,
                    description: str | None = None,
                    actor: str | None = None) -> Fund:
    init_db()
    code = (code or "").strip()
    if not code:
        raise ValidationError("Fund code is required")
    if not (name or "").strip():
        raise ValidationError("Fund name is required")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_funds
                   (code, name, restricted, description)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET
                   name        = excluded.name,
                   restricted  = excluded.restricted,
                   description = excluded.description""",
            (code, name.strip(), 1 if restricted else 0,
             (description or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_funds WHERE code = ?",
            (code,)).fetchone()
    _log_action("fund.upsert", actor=actor, code=code,
                  restricted=restricted)
    return _row_fund(r)


def list_funds() -> list[Fund]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_funds "
            "ORDER BY restricted DESC, code COLLATE NOCASE"
            ).fetchall()
    return [_row_fund(r) for r in rows]


def tag_donation_fund(donation_id: int, fund_code: str, *,
                          actor: str | None = None) -> None:
    init_db()
    fund_code = (fund_code or "").strip()
    if not fund_code:
        raise ValidationError("Fund code is required")
    with _connect() as conn:
        f = conn.execute(
            "SELECT 1 FROM alumni_funds WHERE code = ?",
            (fund_code,)).fetchone()
        if f is None:
            raise ValidationError(f"No fund {fund_code!r}")
        cur = conn.execute(
            "UPDATE alumni_donations SET fund_code = ? "
            "WHERE donation_id = ?", (fund_code, donation_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No donation #{donation_id}")
        conn.commit()
    _log_action("fund.tag", actor=actor,
                  donation_id=donation_id, fund_code=fund_code)


@dataclass
class FundTotals:
    fund_code: str
    fund_name: str
    restricted: bool
    raised_pence: int


def fund_totals(*, campaign_id: int | None = None
                     ) -> list[FundTotals]:
    init_db()
    sql = ("""SELECT COALESCE(d.fund_code, '(unallocated)') AS code,
                     COALESCE(f.name, '(unallocated)') AS name,
                     COALESCE(f.restricted, 0) AS restricted,
                     COALESCE(SUM(d.amount_pence), 0) AS total
                FROM alumni_donations d
                LEFT JOIN alumni_funds f ON f.code = d.fund_code""")
    params: list[Any] = []
    if campaign_id is not None:
        sql += " WHERE d.campaign_id = ?"; params.append(campaign_id)
    sql += " GROUP BY code, name, restricted ORDER BY total DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [FundTotals(
        fund_code=r["code"], fund_name=r["name"],
        restricted=bool(r["restricted"]),
        raised_pence=int(r["total"])) for r in rows]


# ── #35 Bequests / legacy register ───────────────────────────────

@dataclass
class Bequest:
    bequest_id: int
    alumni_id: int
    estimated_pence: int | None
    will_mention: bool
    executor_name: str | None
    executor_email: str | None
    executor_phone: str | None
    confirmed_on: str | None
    realised_on: str | None
    status: str
    notes: str | None
    created_at: str


def _row_bequest(r: db.Row) -> Bequest:
    return Bequest(
        bequest_id=r["bequest_id"], alumni_id=r["alumni_id"],
        estimated_pence=r["estimated_pence"],
        will_mention=bool(r["will_mention"]),
        executor_name=r["executor_name"],
        executor_email=r["executor_email"],
        executor_phone=r["executor_phone"],
        confirmed_on=r["confirmed_on"],
        realised_on=r["realised_on"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"])


def add_bequest(alumni_id: int, *,
                    estimated_pence: int | None = None,
                    will_mention: bool = True,
                    executor_name: str | None = None,
                    executor_email: str | None = None,
                    executor_phone: str | None = None,
                    confirmed_on: str | None = None,
                    status: str = "Pledged",
                    notes: str | None = None,
                    actor: str | None = None) -> Bequest:
    init_db()
    if status not in BEQUEST_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BEQUEST_STATUSES)}")
    cdate = _validate_date(confirmed_on, "Confirmed on",
                                required=False)
    if executor_email:
        executor_email = _validate_email(executor_email)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_bequests
                   (alumni_id, estimated_pence, will_mention,
                    executor_name, executor_email, executor_phone,
                    confirmed_on, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, estimated_pence,
             1 if will_mention else 0,
             (executor_name or "").strip() or None,
             executor_email,
             (executor_phone or "").strip() or None,
             cdate, status,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_bequests WHERE bequest_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("bequest.add", actor=actor, alumni_id=alumni_id,
                  status=status)
    return _row_bequest(r)


def list_bequests(*, status: str | None = None
                       ) -> list[Bequest]:
    init_db()
    sql = "SELECT * FROM alumni_bequests WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"; params.append(status)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_bequest(r) for r in rows]


def set_bequest_status(bequest_id: int, status: str, *,
                            realised_on: str | None = None,
                            actor: str | None = None) -> Bequest:
    init_db()
    if status not in BEQUEST_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BEQUEST_STATUSES)}")
    rdate = _validate_date(realised_on, "Realised on", required=False)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_bequests SET status = ?, "
            "    realised_on = COALESCE(?, realised_on) "
            "WHERE bequest_id = ?",
            (status, rdate, bequest_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No bequest #{bequest_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_bequests WHERE bequest_id = ?",
            (bequest_id,)).fetchone()
    _log_action("bequest.status", actor=actor,
                  bequest_id=bequest_id, status=status)
    return _row_bequest(r)


# ── #36 Matched giving ───────────────────────────────────────────

@dataclass
class MatchedScheme:
    scheme_id: int
    employer: str
    multiplier: float
    cap_pence: int | None
    notes: str | None


def _row_scheme(r: db.Row) -> MatchedScheme:
    return MatchedScheme(
        scheme_id=r["scheme_id"], employer=r["employer"],
        multiplier=float(r["multiplier"]),
        cap_pence=r["cap_pence"], notes=r["notes"])


def upsert_matched_scheme(employer: str, *,
                              multiplier: float = 1.0,
                              cap_pence: int | None = None,
                              notes: str | None = None,
                              actor: str | None = None
                              ) -> MatchedScheme:
    init_db()
    employer = (employer or "").strip()
    if not employer:
        raise ValidationError("Employer is required")
    if multiplier <= 0:
        raise ValidationError("Multiplier must be > 0")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_matched_giving_schemes
                   (employer, multiplier, cap_pence, notes)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(employer) DO UPDATE SET
                   multiplier = excluded.multiplier,
                   cap_pence  = excluded.cap_pence,
                   notes      = excluded.notes""",
            (employer, multiplier, cap_pence,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "WHERE employer = ?", (employer,)).fetchone()
    _log_action("matched.upsert", actor=actor,
                  employer=employer, multiplier=multiplier)
    return _row_scheme(r)


def list_matched_schemes() -> list[MatchedScheme]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "ORDER BY employer COLLATE NOCASE").fetchall()
    return [_row_scheme(r) for r in rows]


def find_matched_scheme(employer: str | None
                            ) -> MatchedScheme | None:
    """Look up a matched-giving scheme by employer name. Aliases
    from the normalised employer directory are honoured."""
    init_db()
    if not employer:
        return None
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "WHERE employer = ? COLLATE NOCASE",
            (employer.strip(),)).fetchone()
        if r:
            return _row_scheme(r)
    resolved = resolve_employer(employer)
    if resolved is None:
        return None
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "WHERE employer = ? COLLATE NOCASE",
            (resolved.canonical_name,)).fetchone()
    return _row_scheme(r) if r else None


def auto_apply_matched_giving(donation_id: int, *,
                                   actor: str | None = None) -> int:
    """Look up the donor's current employer, find a matched-giving
    scheme, and write the matched amount onto the donation row.
    Returns the matched amount in pence (0 if no scheme applies)."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT d.donation_id, d.amount_pence,
                       a.current_employer
                  FROM alumni_donations d
                  JOIN alumni a ON a.alumni_id = d.alumni_id
                 WHERE d.donation_id = ?""", (donation_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No donation #{donation_id}")
    scheme = find_matched_scheme(r["current_employer"])
    if scheme is None:
        return 0
    matched = int(int(r["amount_pence"]) * scheme.multiplier)
    if scheme.cap_pence is not None:
        matched = min(matched, scheme.cap_pence)
    with _connect() as conn:
        conn.execute(
            "UPDATE alumni_donations "
            "SET matched_pence = ?, matched_scheme_id = ? "
            "WHERE donation_id = ?",
            (matched, scheme.scheme_id, donation_id))
        conn.commit()
    _log_action("matched.apply", actor=actor,
                  donation_id=donation_id, matched_pence=matched,
                  employer=r["current_employer"])
    return matched


def record_donation(alumni_id: int, payload: dict[str, Any]):
    """Record a donation and publish the ``donation.recorded`` webhook
    (the work is :func:`_original_record_donation`)."""
    d = _original_record_donation(alumni_id, payload)
    _emit_webhook("donation.recorded", {
        "alumni_id": alumni_id,
        "donation_id": getattr(d, "donation_id", None),
        "amount_pence": getattr(d, "amount_pence", None)})
    return d


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
from .linking import (  # noqa: E402,F401
    _resolve_money,
)
from .careers import (  # noqa: E402,F401
    resolve_employer,
)
from .integrations import (  # noqa: E402,F401
    _emit_webhook,
)
