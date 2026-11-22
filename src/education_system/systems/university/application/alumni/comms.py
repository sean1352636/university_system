"""Alumni newsletters: audiences built from fixed filters (never SQL text),
sent only to alumni who said yes and are not suppressed, each with a
one-click unsubscribe link.

Suppressed: no consent (or never asked), do-not-contact, deceased, erased,
e-mail bounced, no e-mail address. Every recipient's outcome is recorded in
``newsletter_deliveries``. Unsubscribe tokens are random; only their SHA-256
is stored.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets

from education_system.systems.university.application.alumni import access as aa

AUDIENCE_KEYS = ("year_from", "year_to", "degree_contains", "country", "chapter_id",
                 "donors_only")


def _office(who):
    return who is not None and who.is_office


def _hash(token) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def unsubscribe_url(token) -> str:
    base = os.environ.get("UNIVERSITY_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    return f"{base}/api/v1/university/alumni/unsubscribe/{token}"


def _clean_audience(audience) -> dict:
    audience = {k: v for k, v in (audience or {}).items() if k in AUDIENCE_KEYS and
                v not in (None, "", False)}
    for key in ("year_from", "year_to", "chapter_id"):
        if key in audience:
            audience[key] = int(audience[key])
    return audience


def _matching(conn, audience) -> list[dict]:
    where, params = [], []
    if "year_from" in audience:
        where.append("a.graduation_year >= ?")
        params.append(audience["year_from"])
    if "year_to" in audience:
        where.append("a.graduation_year <= ?")
        params.append(audience["year_to"])
    if "degree_contains" in audience:
        where.append("LOWER(COALESCE(a.degree_earned, '')) LIKE ?")
        params.append(f"%{str(audience['degree_contains']).lower()}%")
    if "country" in audience:
        where.append("LOWER(COALESCE(a.country, '')) = ?")
        params.append(str(audience["country"]).lower())
    if "chapter_id" in audience:
        where.append("a.alumni_id IN (SELECT alumni_id FROM chapter_memberships WHERE chapter_id "
                     "= ?)")
        params.append(audience["chapter_id"])
    if audience.get("donors_only"):
        where.append("a.alumni_id IN (SELECT alumni_id FROM donations WHERE COALESCE(status, "
                     "'received') = 'received')")
    return aa.dicts(conn.execute("SELECT a.* FROM alumni a" + (" WHERE " + " AND ".join(where)
                                                               if where else "")
                                 + " ORDER BY a.alumni_id", params))


def suppression_reason(row) -> str | None:
    if row.get("anonymised_at"):
        return "erased"
    if row.get("deceased_at"):
        return "deceased"
    if row.get("do_not_contact"):
        return "do not contact"
    if row.get("marketing_consent") is None:
        return "consent not asked"
    if not row.get("marketing_consent"):
        return "no consent"
    if row.get("email_bounced"):
        return "e-mail bounced"
    if not (row.get("email_address") or "").strip() or "@" not in row["email_address"]:
        return "no e-mail address"
    return None


def preview(conn, who, audience) -> dict:
    aa.ensure(conn)
    aa.require(_office(who), "Only the alumni office can send newsletters")
    rows = _matching(conn, _clean_audience(audience))
    reasons: dict[str, int] = {}
    send = 0
    for row in rows:
        why = suppression_reason(row)
        if why:
            reasons[why] = reasons.get(why, 0) + 1
        else:
            send += 1
    return {"matching": len(rows), "will_send": send, "suppressed": reasons}


def create(conn, who, title, content, audience) -> int:
    aa.ensure(conn)
    aa.require(_office(who), "Only the alumni office can write newsletters")
    nid = conn.execute("INSERT INTO newsletters (title, content, target_audience, audience_json, "
                       "created_date, created_by, status) VALUES (?, ?, ?, ?, ?, ?, 'draft')",
                       (aa.text(title, "Title", True), aa.text(content, "Content", True),
                        "filtered" if audience else "all consenting alumni",
                        json.dumps(_clean_audience(audience)), aa.now(),
                        who.username)).lastrowid
    aa.audit(conn, who, "newsletter", nid, "created")
    return int(nid)


def newsletters(conn) -> list[dict]:
    aa.ensure(conn)
    return aa.dicts(conn.execute("SELECT * FROM newsletters ORDER BY newsletter_id DESC"))


def send(conn, who, newsletter_id) -> dict:
    """Send to the consenting, unsuppressed audience. Returns
    ``{"sent", "suppressed", "emails"}`` (e-mails go out after commit)."""
    aa.ensure(conn)
    aa.require(_office(who), "Only the alumni office can send newsletters")
    row = aa.one(conn, "SELECT * FROM newsletters WHERE newsletter_id = ?", (newsletter_id,))
    if not row:
        raise ValueError("No such newsletter")
    if row.get("status") == "sent":
        raise ValueError("This newsletter has already been sent")
    audience = json.loads(row.get("audience_json") or "{}")
    emails, sent, suppressed = [], 0, 0
    for person in _matching(conn, audience):
        why = suppression_reason(person)
        conn.execute("INSERT OR REPLACE INTO newsletter_deliveries (newsletter_id, alumni_id, "
                     "outcome) VALUES (?, ?, ?)",
                     (newsletter_id, person["alumni_id"], f"suppressed: {why}" if why else
                      "sent"))
        if why:
            suppressed += 1
            continue
        token = secrets.token_urlsafe(24)
        conn.execute("INSERT INTO alumni_unsubscribe_tokens (token_hash, alumni_id, "
                     "newsletter_id) VALUES (?, ?, ?)",
                     (_hash(token), person["alumni_id"], newsletter_id))
        name = person.get("first_name") or "graduate"
        emails.append((person["email_address"], row["title"],
                       f"Dear {name},\n\n{row['content']}\n\n—\nYou receive this because you "
                       f"agreed to hear from us. Unsubscribe: {unsubscribe_url(token)}"))
        sent += 1
    conn.execute("UPDATE newsletters SET status = 'sent', sent_at = ?, sent_by = ?, sent_count = "
                 "?, suppressed_count = ?, send_date = ? WHERE newsletter_id = ?",
                 (aa.now(), who.username, sent, suppressed, aa.today(), newsletter_id))
    aa.audit(conn, who, "newsletter", newsletter_id, "sent", {"sent": sent,
                                                               "suppressed": suppressed})
    return {"sent": sent, "suppressed": suppressed, "emails": emails}


def deliveries(conn, newsletter_id) -> list[dict]:
    aa.ensure(conn)
    return aa.dicts(conn.execute("SELECT * FROM newsletter_deliveries WHERE newsletter_id = ? "
                                 "ORDER BY outcome, alumni_id", (newsletter_id,)))


def unsubscribe(conn, token) -> dict:
    """The link in a newsletter. Public; withdraws newsletter consent."""
    aa.ensure(conn)
    row = aa.one(conn, "SELECT * FROM alumni_unsubscribe_tokens WHERE token_hash = ?",
                 (_hash(token),))
    if not row:
        return {"ok": False, "message": "This unsubscribe link is not valid."}
    conn.execute("UPDATE alumni SET marketing_consent = 0, consent_updated_at = ?, "
                 "consent_source = 'unsubscribe link' WHERE alumni_id = ?",
                 (aa.now(), row["alumni_id"]))
    conn.execute("UPDATE alumni_unsubscribe_tokens SET used_at = COALESCE(used_at, ?) WHERE "
                 "token_hash = ?", (aa.now(), row["token_hash"]))
    aa.audit(conn, "unsubscribe link", "alumni", row["alumni_id"], "consent",
             {"consent": False, "source": "unsubscribe link"})
    return {"ok": True, "message": "You have been unsubscribed from alumni newsletters."}


def mark_bounced(conn, who, alumni_id) -> None:
    aa.alumnus(conn, alumni_id)
    aa.require(_office(who), "Only the alumni office can do this")
    conn.execute("UPDATE alumni SET email_bounced = 1 WHERE alumni_id = ?", (alumni_id,))
    aa.audit(conn, who, "alumni", alumni_id, "email_bounced")
