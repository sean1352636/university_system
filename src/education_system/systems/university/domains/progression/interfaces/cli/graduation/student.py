"""My graduation: what a student can do for themselves — check where they
stand, confirm the certificate name, reply to a ceremony with named guests,
move to a later ceremony, order and pay for a gown, share their transcript
with an employer, add HEAR achievements, save the HEAR and ask for a
replacement certificate.
"""

from __future__ import annotations

from education_system.systems.university.application.graduation import ceremonies as gcer
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.application.graduation import eligibility as ge
from education_system.systems.university.application.graduation import transcripts as gt
from education_system.systems.university.domains.progression.interfaces.cli.graduation import (
    office,
    records,
)
from education_system.systems.university.domains.progression.interfaces.cli.graduation._io import (
    ask,
    ask_choice,
    ask_int,
    confirm,
    menu,
    run,
    section,
    table,
    write_file,
)


def _mine(cli) -> dict | None:
    rows = run(gc.listing, cli.who, status="conferred", write=False) or []
    if not rows:
        print("\n  Your award has not been conferred yet.")
        return None
    return rows[0]


def where_i_stand(cli) -> None:
    records.eligibility(cli, cli.who.student_id)


def confirm_name(cli) -> None:
    section("The name on my certificate")
    current = run(ge.certificate_name, cli.who.student_id, write=False)
    if not current:
        return
    print(f"  Currently: {current['certificate_name']}"
          + ("  (confirmed)" if current["confirmed"] else ""))
    name = ask("Name exactly as it should be printed", current["certificate_name"])
    if run(ge.confirm_name, cli.who, cli.who.student_id, name) is not None:
        print("\n✓ Saved. A change from your record is checked by the graduation office.")


def reply(cli) -> None:
    from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (  # noqa: E501
        CeremonyManager,
    )
    for c in CeremonyManager.list_ceremonies("scheduled"):
        print(f"  [{c['ceremony_id']}] {c['ceremony_name']} {c['ceremony_date']} "
              f"{c.get('ceremony_time', '')} — reply by {c.get('rsvp_deadline') or '—'}")
    cli.current_ceremony_id = ask_int("Ceremony id")
    if cli.current_ceremony_id:
        office.record_rsvp(cli, student_id=cli.who.student_id)


def move(cli) -> None:
    section("Move to a later ceremony")
    old = ask_int("The ceremony you can't attend (id)")
    new = ask_int("The ceremony to move to (id)")
    if old and new and run(gcer.transfer, cli.who, old, cli.who.student_id, new,
                           ask("Why (optional)")) is not None:
        print("\n✓ Moved. Please reply to the new ceremony.")


def gown(cli) -> None:
    section("My gown")
    sid = cli.who.student_id
    rows = run(gcer.my_ceremonies, cli.who, sid, write=False) or []
    going = [c for c in rows if c.get("rsvp_status") == "going"]
    if not going:
        print("\n  Reply that you are coming to a ceremony first.")
        return
    for c in going:
        g = c["gown_order"]
        state = "no order" if not g else (f"{g['gown_size']}, £{float(g['cost'] or 0):.2f}, "
                                          f"{g['status']}, {g['payment_status']}")
        print(f"  [{c['ceremony_id']}] {c['ceremony_name']} {c['ceremony_date']} — order by "
              f"{c.get('gown_order_deadline') or c['ceremony_date']} — {state}")
    cid = ask_int("Ceremony id", going[0]["ceremony_id"] if len(going) == 1 else None)
    c = next((x for x in going if x["ceremony_id"] == cid), None)
    if not c:
        return
    order = c["gown_order"]
    if order and order.get("payment_status") == "paid" and order.get("status") != "cancelled":
        print("\n" + gcer.gown_receipt(order))
        return
    if not order or order.get("status") == "cancelled" or confirm("Change your order?"):
        options = gcer.gown_options()
        fees = options["fees"]
        print(f"  Gown hire £{fees['gown']:.2f}; hat £{fees['hat']:.2f}; hood "
              f"£{fees['hood']:.2f}")
        size = ask_choice("Gown size", tuple(x.lower() for x in options["gown_sizes"]),
                          (order or {}).get("gown_size", "").lower())
        if not size:
            return
        hat = ask_choice("Hat size (blank = none)", tuple(options["hat_sizes"]),
                         (order or {}).get("hat_size", ""))
        hood = ask("Hood subject (blank = none)", (order or {}).get("hood_subject", ""))
        price = gcer.gown_quote(size, hood, hat)
        if not confirm(f"Order this gown for £{price:.2f}?"):
            return
        order = run(gcer.order_gown, cli.who, cid, sid, gown_size=size, hat_size=hat,
                    hood_subject=hood)
        if not order:
            return
        print(f"\n✓ Gown ordered: £{float(order['cost']):.2f}.")
    if confirm("Pay now from your student finance account? (or pay at the gown desk)"):
        result = run(gcer.pay_gown_order, cli.who, order["order_id"], "student_finance_account")
        if result:
            gcer.after_gown_payment(result, cli.who.username)
            left = result.get("balance_remaining")
            print(f"\n✓ Paid £{result['amount']:.2f} (ref {result['reference']})."
                  + (f" Balance now £{left:.2f}." if left is not None else "")
                  + " A receipt has been e-mailed to you.")


def shares(cli) -> None:
    section("Transcript shares")
    rows = run(gt.shares, cli.who, cli.who.student_id, write=False) or []
    table(rows, [("token_id", "Id", 5), ("employer_name", "Employer", 22),
                 ("employer_email", "E-mail", 26), ("expires_at", "Expires", 12),
                 ("access_count", "Opened", 8), ("revoked", "Revoked", 8)])


def share(cli) -> None:
    section("Share my transcript with an employer")
    mine = _mine(cli)
    if not mine:
        return
    result = run(gt.share, cli.who, mine["conferral_id"], ask("Employer"),
                 ask("Employer e-mail"), ask("Purpose (optional)"),
                 days=ask_int("Days the link lasts", 30) or 30)
    if result:
        print(f"\n✓ Link sent to the employer (expires {result['expires_at']}):\n  {result['url']}")


def revoke_share(cli) -> None:
    tid = ask_int("Share id to withdraw")
    if tid and run(gt.revoke_share, cli.who, tid) is not None:
        print("\n✓ Withdrawn.")


def achievements(cli) -> None:
    section("HEAR achievements")
    sid = cli.who.student_id
    table(run(gt.achievements, cli.who, sid, write=False) or [],
          [("achievement_id", "Id", 5), ("category", "Category", 18),
           ("description", "Description", 40), ("verified_at", "Verified", 20)])
    if confirm("Add one?"):
        cat = ask_choice("Category", tuple(c.lower() for c in gt.ACHIEVEMENT_CATEGORIES))
        category = next((c for c in gt.ACHIEVEMENT_CATEGORIES if c.lower() == cat), None)
        if category and run(gt.add_achievement, cli.who, sid, category,
                            ask("Description")) is not None:
            print("\n✓ Added; the graduation office verifies it before it appears on the HEAR.")


def save_hear(cli) -> None:
    html = run(gt.hear_html, cli.who, cli.who.student_id, write=False)
    if html:
        path = ask("Save as", f"HEAR_{cli.who.student_id}.html")
        if write_file(path, html):
            print(f"\n✓ Saved {path}")


def replacement(cli) -> None:
    section("Ask for a replacement certificate")
    mine = _mine(cli)
    if not mine:
        return
    delivery = ask_choice("Delivery", ("post", "collect"), "post")
    address = ask("Postal address") if delivery == "post" else None
    print(f"  There is a £{gc.REPLACEMENT_FEE:.2f} fee, added to your account.")
    if not confirm("Ask for a replacement?"):
        return
    result = run(gc.replace_certificate, cli.who, mine["conferral_id"], ask("Why"),
                 delivery=delivery, address=address)
    if result:
        gc.charge_replacement_fee(result, cli.who.username)
        print(f"\n✓ Replacement {result['certificate_number']} ordered.")


def main(cli) -> None:
    menu("🎓 MY GRADUATION", [
        ("Where I stand", lambda: where_i_stand(cli)),
        ("Confirm the name on my certificate", lambda: confirm_name(cli)),
        ("Reply to a ceremony (guests, access needs)", lambda: reply(cli)),
        ("Move to a later ceremony", lambda: move(cli)),
        ("My transcript shares", lambda: shares(cli)),
        ("Share my transcript with an employer", lambda: share(cli)),
        ("Withdraw a share", lambda: revoke_share(cli)),
        ("HEAR achievements", lambda: achievements(cli)),
        ("Save my HEAR (HTML)", lambda: save_hear(cli)),
        ("Ask for a replacement certificate", lambda: replacement(cli)),
        ("Order / pay for my gown", lambda: gown(cli)),
    ])
