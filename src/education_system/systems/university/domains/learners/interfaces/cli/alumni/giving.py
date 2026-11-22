"""Giving menus: gifts, refunds, Gift Aid declarations and claims, pledges
and campaigns (fundraising staff), plus the alumnus's own giving."""

from __future__ import annotations

from education_system.systems.university.application.alumni import giving as ag
from education_system.systems.university.domains.learners.interfaces.cli.alumni import _io

_GIFT_COLS = [("donation_id", "Id", 6), ("donation_date", "Date", 12),
              ("alumni_id", "Alumni", 12), ("amount", "Amount", 10),
              ("campaign_name", "Campaign", 20), ("is_gift_aided", "GA", 4),
              ("status", "Status", 10), ("receipt_number", "Receipt", 16)]
_PLEDGE_COLS = [("pledge_id", "Id", 5), ("alumni_id", "Alumni", 12), ("amount", "Amount", 9),
                ("frequency", "Every", 10), ("paid_instalments", "Paid", 6),
                ("instalments", "Of", 5), ("next_due", "Next due", 12), ("status", "Status", 10)]


def _money(label):
    raw = _io.ask(label)
    try:
        return float(raw)
    except ValueError:
        print("  Enter an amount like 25.00")
        return None


# ── gifts ───────────────────────────────────────────────────────────────


def list_gifts(ctx) -> None:
    rows = _io.read(ag.gifts, ctx.who, _io.ask("Alumni id (blank = all)") or None, None,
                    _io.ask("Search (name / receipt)") or None)
    if rows is not None:
        _io.table(rows, _GIFT_COLS)


def record_gift(ctx) -> None:
    alumni_id = _io.ask("Alumni id")
    amount = _money("Amount (£)")
    if amount is None:
        return
    result = _io.run(ag.record_gift, ctx.who, alumni_id, amount,
                     gift_date=_io.ask("Gift date (blank = today)") or None,
                     campaign_id=_io.ask_int("Campaign id (blank = none)"),
                     method=_io.ask_choice("Method", list(ag.METHODS), "card") or "card",
                     gift_aid=_io.confirm("Claim Gift Aid on it?"),
                     notes=_io.ask("Notes"))
    if result:
        ag.post_to_finance(result, ctx.who.username)
        print(f"\n✅ Gift {result['receipt_number']} recorded"
              + (" with Gift Aid." if result["gift_aided"] else ".") + " Receipt sent.")


def refund(ctx) -> None:
    did = _io.ask_int("Gift id")
    if did is None:
        return
    result = _io.run(ag.refund_gift, ctx.who, did, _io.ask("Reason"))
    if result:
        owed = result["gift_aid_to_repay"]
        print("\n✅ Refunded." + (f" £{owed:,.2f} Gift Aid already claimed comes off the next "
                                 "claim." if owed else ""))


# ── Gift Aid ────────────────────────────────────────────────────────────


def declarations(ctx, alumni_id=None) -> None:
    alumni_id = alumni_id or _io.ask("Alumni id")
    rows = _io.read(ag.declarations, alumni_id)
    if rows is not None:
        _io.table(rows, [("declaration_id", "Id", 5), ("full_name", "Name", 22),
                         ("postcode", "Postcode", 10), ("method", "Method", 9),
                         ("made_on", "Made", 12), ("covers_past_four_years", "Past 4y", 8),
                         ("cancelled_at", "Cancelled", 20)])


def add_declaration(ctx, alumni_id=None) -> None:
    alumni_id = alumni_id or _io.ask("Alumni id")
    print("  Gift Aid: the donor must pay at least as much UK Income and/or Capital Gains Tax as")
    print("  all charities and CASCs will reclaim on their gifts in the tax year.")
    result = _io.run(ag.add_declaration, ctx.who, alumni_id,
                     full_name=_io.ask("Full name"), house=_io.ask("House name or number"),
                     postcode=_io.ask("Postcode"),
                     method=_io.ask_choice("How was it made", ["written", "oral", "online"],
                                           "written") or "written",
                     made_on=_io.ask("Made on (blank = today)") or None,
                     covers_past_four_years=_io.confirm("Cover gifts in the past four years?"),
                     taxpayer_confirmed=_io.confirm("Donor confirms they are a UK taxpayer?"))
    if result:
        print(f"\n✅ Declaration {result} recorded.")


def cancel_declaration(ctx) -> None:
    if _io.run(ag.cancel_declaration, ctx.who, _io.ask_int("Declaration id")):
        print("\n✅ Cancelled; later gifts will not have Gift Aid.")


def list_claims(ctx) -> None:
    rows = _io.read(ag.claims)
    if rows is not None:
        _io.table(rows, [("claim_id", "Id", 5), ("period_from", "From", 12),
                         ("period_to", "To", 12), ("gift_count", "Gifts", 6),
                         ("donations_total", "Gifts £", 10), ("adjustments_total", "Less £", 8),
                         ("claim_total", "Claim £", 10), ("status", "Status", 10),
                         ("hmrc_reference", "HMRC ref", 14)])


def build_claim(ctx) -> None:
    result = _io.run(ag.build_claim, ctx.who, _io.ask("Period from (YYYY-MM-DD)"),
                     _io.ask("Period to (YYYY-MM-DD)"))
    if result:
        _io.show([("Draft claim", result["claim_id"]), ("Gifts", result["gifts"]),
                  ("Gift total", f"£{result['donations_total']:,.2f}"),
                  ("Refund adjustments", f"£{result['adjustments']:,.2f}"),
                  ("Claim", f"£{result['claim_total']:,.2f}")])


def claim_status(ctx) -> None:
    cid = _io.ask_int("Claim id")
    action = _io.ask_choice("Action", ["submit", "paid", "delete"])
    if action == "submit":
        ok = _io.run(ag.submit_claim, ctx.who, cid, _io.ask("HMRC reference"))
    elif action == "paid":
        ok = _io.run(ag.mark_claim_paid, ctx.who, cid)
    elif action == "delete":
        ok = _io.run(ag.delete_draft_claim, ctx.who, cid)
    else:
        return
    if ok:
        print("\n✅ Done.")


# ── pledges ─────────────────────────────────────────────────────────────


def list_pledges(ctx, alumni_id=None) -> None:
    rows = _io.read(ag.pledges, ctx.who, alumni_id or (_io.ask("Alumni id (blank = all)")
                                                       or None))
    if rows is not None:
        _io.table(rows, _PLEDGE_COLS)


def overdue(ctx) -> None:
    rows = _io.read(ag.overdue_pledges)
    if rows is not None:
        _io.table(rows, _PLEDGE_COLS)


def create_pledge(ctx, alumni_id=None) -> None:
    alumni_id = alumni_id or _io.ask("Alumni id")
    amount = _money("Amount per instalment (£)")
    if amount is None:
        return
    freq = _io.ask_choice("Frequency", list(ag.FREQUENCIES), "monthly") or "monthly"
    count = 1 if freq == "one_off" else (_io.ask_int("Number of instalments", 12) or 1)
    result = _io.run(ag.create_pledge, ctx.who, alumni_id, amount, freq, count,
                     start=_io.ask("First payment date (blank = today)") or None,
                     campaign_id=_io.ask_int("Campaign id (blank = none)"))
    if result:
        print(f"\n✅ Pledge {result} set up.")


def pledge_payment(ctx) -> None:
    pid = _io.ask_int("Pledge id")
    result = _io.run(ag.record_pledge_payment, ctx.who, pid,
                     method=_io.ask_choice("Method", list(ag.METHODS), "direct_debit")
                     or "direct_debit",
                     paid_on=_io.ask("Paid on (blank = today)") or None,
                     gift_aid=_io.confirm("Claim Gift Aid on it?"))
    if result:
        ag.post_to_finance(result, ctx.who.username)
        print(f"\n✅ Payment {result['receipt_number']} recorded."
              + (" Pledge complete." if result["pledge_completed"]
                 else f" Next due {result['next_due']}."))


def cancel_pledge(ctx) -> None:
    if _io.run(ag.cancel_pledge, ctx.who, _io.ask_int("Pledge id"), _io.ask("Reason")):
        print("\n✅ Cancelled.")


# ── campaigns ───────────────────────────────────────────────────────────


def list_campaigns(ctx) -> None:
    rows = _io.read(ag.campaigns)
    if rows is not None:
        _io.table(rows, [("campaign_id", "Id", 5), ("campaign_name", "Campaign", 28),
                         ("goal_amount", "Goal £", 10), ("raised", "Raised £", 10),
                         ("progress_pct", "%", 6), ("start_date", "Start", 12),
                         ("end_date", "End", 12), ("status", "Status", 8)])


def save_campaign(ctx) -> None:
    cid = _io.ask_int("Campaign id to edit (blank = new)")
    data = {"campaign_name": _io.ask("Name"), "description": _io.ask("Description"),
            "goal_amount": _io.ask("Goal (£)") or 0, "start_date": _io.ask("Start date"),
            "end_date": _io.ask("End date"), "category": _io.ask("Category")}
    if cid:
        data = {k: v for k, v in data.items() if v not in ("", 0)}
    result = _io.run(ag.save_campaign, ctx.who, data, cid)
    if result:
        print(f"\n✅ Campaign {result} saved.")


def close_campaign(ctx) -> None:
    if _io.run(ag.close_campaign, ctx.who, _io.ask_int("Campaign id")):
        print("\n✅ Closed.")


def giving_menu(ctx) -> str:
    return _io.menu("Giving", [
        ("Gifts", lambda: list_gifts(ctx)),
        ("Record a gift", lambda: record_gift(ctx)),
        ("Refund a gift", lambda: refund(ctx)),
        ("Gift Aid declarations", lambda: declarations(ctx)),
        ("Record a Gift Aid declaration", lambda: add_declaration(ctx)),
        ("Cancel a declaration", lambda: cancel_declaration(ctx)),
        ("Gift Aid claims", lambda: list_claims(ctx)),
        ("Build a claim", lambda: build_claim(ctx)),
        ("Submit / paid / delete a claim", lambda: claim_status(ctx)),
        ("Pledges", lambda: list_pledges(ctx)),
        ("Overdue pledges", lambda: overdue(ctx)),
        ("Set up a pledge", lambda: create_pledge(ctx)),
        ("Record a pledge payment", lambda: pledge_payment(ctx)),
        ("Cancel a pledge", lambda: cancel_pledge(ctx)),
        ("Campaigns", lambda: list_campaigns(ctx)),
        ("New / edit campaign", lambda: save_campaign(ctx)),
        ("Close a campaign", lambda: close_campaign(ctx)),
    ])


# ── the alumnus's own giving ────────────────────────────────────────────


def my_giving(ctx) -> str:
    me = ctx.who.alumni_id

    def summary():
        result = _io.read(ag.donor_summary, ctx.who, me)
        if result:
            _io.show([("Total given", f"£{result['total']:,.2f}"), ("Gifts", result["gifts"]),
                      ("Last gift", result["last_gift"]), ("Recognition", result["recognition"]),
                      ("Gift Aid declaration", _io.yes_no(result["gift_aid_declared"])),
                      ("Active pledges", len(result["active_pledges"]))])

    def gifts():
        rows = _io.read(ag.gifts, ctx.who)
        if rows is not None:
            _io.table(rows, _GIFT_COLS)

    def cancel_mine():
        if _io.run(ag.cancel_pledge, ctx.who, _io.ask_int("Pledge id"), _io.ask("Reason")):
            print("\n✅ Cancelled.")

    return _io.menu("My giving", [
        ("Summary", summary), ("My gifts", gifts),
        ("My Gift Aid declarations", lambda: declarations(ctx, me)),
        ("Make a Gift Aid declaration", lambda: add_declaration(ctx, me)),
        ("Cancel a declaration", lambda: cancel_declaration(ctx)),
        ("My pledges", lambda: list_pledges(ctx, me)),
        ("Make a pledge", lambda: create_pledge(ctx, me)),
        ("Cancel a pledge", cancel_mine),
    ])
