"""Alumni records: the profile, contact consent and suppression, deaths,
directory privacy, data export and erasure, and the move from graduate to
alumnus.

* **Directory** listing is opt-in: with no settings row an alumnus is not
  listed. Contact details appear only when the alumnus chose to show them;
  date of birth and home address never appear.
* **Consent**: ``marketing_consent`` is NULL until asked; newsletters go
  only to those who said yes and are not suppressed (``do_not_contact``,
  deceased, erased, bounced).
* **Deceased**: suppresses all contact, removes them from the directory,
  ends mentoring and cancels pledges.
* **Erasure** anonymises the record. Gift amounts stay for the accounts and
  Gift Aid declarations stay for six years after the last claim (HMRC).
* **The transition** (:func:`on_conferral`) runs inside the graduation
  conferral: profile, access change, account check, consent request and the
  Graduate Outcomes survey date (15 months after the award).

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.alumni import access as aa

SELF_FIELDS = ("title", "first_name", "middle_name", "last_name", "email_address", "phone",
               "address", "city", "country", "current_employer", "job_title", "industry",
               "linkedin_url", "bio", "skills")
DIRECTORY_SETTINGS = ("searchable", "show_contact_info", "show_employment", "show_education",
                      "networking_available", "mentor_available")
TRANSITION_STEPS = ("alumni_profile", "access_change", "account_settlement", "consent_capture",
                    "graduate_outcomes")
GIFT_AID_RETENTION_YEARS = 6


def _office(who):
    return who is not None and who.is_office


def _self_or_office(who, alumni_id):
    aa.require_self_or(who, alumni_id, _office)


# ── profile ─────────────────────────────────────────────────────────────


def register(conn, who, student_id=None, data=None) -> str:
    """Create an alumni record from a student record (or by hand for a
    graduate who never had one here)."""
    aa.ensure(conn)
    aa.require(_office(who), "Only the alumni office can add alumni")
    data = dict(data or {})
    if student_id:
        st = aa.one(conn, "SELECT * FROM students WHERE student_id = ?", (student_id,))
        if not st:
            raise ValueError(f"No student {student_id}")
        base = {"first_name": st.get("first_name"), "last_name": st.get("last_name"),
                "email_address": st.get("personal_email") or st.get("email_address"),
                "dob": st.get("date_of_birth") or st.get("dob")}
        alumni_id = student_id
    else:
        alumni_id = aa.text(data.pop("alumni_id", None), "Alumni id", True)
        base = {}
    if conn.execute("SELECT 1 FROM alumni WHERE alumni_id = ?", (alumni_id,)).fetchone():
        raise ValueError(f"{alumni_id} already has an alumni record")
    base.update({k: aa.text(v, k) for k, v in data.items() if k in SELF_FIELDS})
    if not base.get("last_name"):
        raise ValueError("Last name is required")
    year = data.get("graduation_year")
    conn.execute(
        f"INSERT INTO alumni (alumni_id, student_id, graduation_year, degree_earned, "
        f"date_registered, updated_by, {', '.join(base)}) VALUES (?, ?, ?, ?, datetime('now'), "
        f"?, {', '.join('?' * len(base))})",
        (alumni_id, student_id, int(year) if year else None, data.get("degree_earned"),
         who.username, *base.values()))
    aa.audit(conn, who, "alumni", alumni_id, "registered")
    return alumni_id


def profile(conn, who, alumni_id) -> dict:
    """The full record for the alumnus themselves or the office; others get
    the directory view."""
    row = aa.alumnus(conn, alumni_id)
    if who is not None and (who.alumni_id == alumni_id or who.is_staff_role):
        row["directory"] = directory_settings(conn, alumni_id)
        row["history"] = aa.history(conn, "alumni", alumni_id) if who.is_office else []
        row["transition"] = transition_status(conn, alumni_id)
        return row
    listing = _directory_entry(row, directory_settings(conn, alumni_id))
    if listing is None:
        raise PermissionError("This alumnus is not listed in the directory")
    return listing


def update_profile(conn, who, alumni_id, data) -> None:
    row = aa.alumnus(conn, alumni_id)
    _self_or_office(who, alumni_id)
    if row.get("anonymised_at"):
        raise ValueError("This record has been erased")
    fields = {k: aa.text(v, k.replace("_", " ")) for k, v in data.items() if k in SELF_FIELDS}
    if "email_address" in fields and fields["email_address"] and "@" not in fields[
            "email_address"]:
        raise ValueError("That is not an e-mail address")
    if not fields:
        return
    if "email_address" in fields:
        fields["email_bounced"] = 0
    conn.execute(f"UPDATE alumni SET {', '.join(f'{k} = ?' for k in fields)}, updated_at = ?, "
                 "updated_by = ? WHERE alumni_id = ?",
                 (*fields.values(), aa.now(), who.username, alumni_id))
    aa.audit(conn, who, "alumni", alumni_id, "profile_updated", {"fields": sorted(fields)})


# ── consent and suppression ─────────────────────────────────────────────


def set_consent(conn, who, alumni_id, consent, source="") -> None:
    """Marketing / newsletter consent. The alumnus gives it themselves; the
    office records consent given another way, saying how."""
    aa.alumnus(conn, alumni_id)
    _self_or_office(who, alumni_id)
    if who.alumni_id != alumni_id:
        source = aa.text(source, "How the consent was given", True)
    conn.execute("UPDATE alumni SET marketing_consent = ?, consent_updated_at = ?, "
                 "consent_source = ? WHERE alumni_id = ?",
                 (int(bool(consent)), aa.now(), source or "alumnus", alumni_id))
    aa.audit(conn, who, "alumni", alumni_id, "consent", {"consent": bool(consent),
                                                         "source": source or "alumnus"})


def set_do_not_contact(conn, who, alumni_id, flag, reason) -> None:
    aa.alumnus(conn, alumni_id)
    aa.require(_office(who), "Only the alumni office can set do-not-contact")
    conn.execute("UPDATE alumni SET do_not_contact = ? WHERE alumni_id = ?",
                 (int(bool(flag)), alumni_id))
    aa.audit(conn, who, "alumni", alumni_id, "do_not_contact",
             {"flag": bool(flag), "reason": aa.text(reason, "Reason", True)})


def record_deceased(conn, who, alumni_id, on_date, source) -> None:
    row = aa.alumnus(conn, alumni_id)
    aa.require(_office(who), "Only the alumni office can record a death")
    if row.get("deceased_at"):
        raise ValueError("A death is already recorded")
    day = aa.iso_date(on_date, "Date of death", True)
    conn.execute("UPDATE alumni SET deceased_at = ?, do_not_contact = 1, updated_at = ?, "
                 "updated_by = ? WHERE alumni_id = ?", (day, aa.now(), who.username, alumni_id))
    conn.execute("DELETE FROM alumni_directory_settings WHERE alumni_id = ?", (alumni_id,))
    if aa.has_table(conn, "mentorships"):
        conn.execute("UPDATE mentorships SET status = 'ended', end_date = ?, ended_by = ?, "
                     "ended_reason = 'mentor died' WHERE mentor_id = ? AND COALESCE(status, "
                     "'active') NOT IN ('ended', 'completed')", (day, who.username, alumni_id))
    conn.execute("UPDATE donation_pledges SET status = 'cancelled', cancelled_reason = 'died' "
                 "WHERE alumni_id = ? AND status = 'active'", (alumni_id,))
    conn.execute("DELETE FROM chapter_memberships WHERE alumni_id = ?", (alumni_id,))
    aa.audit(conn, who, "alumni", alumni_id, "deceased",
             {"date": day, "source": aa.text(source, "Source", True)})


# ── directory ───────────────────────────────────────────────────────────


def directory_settings(conn, alumni_id) -> dict:
    aa.ensure(conn)
    row = aa.one(conn, "SELECT * FROM alumni_directory_settings WHERE alumni_id = ?",
                 (alumni_id,))
    if not row:
        return {k: 0 for k in DIRECTORY_SETTINGS} | {"alumni_id": alumni_id, "saved": False}
    return {**row, "saved": True}


def save_directory_settings(conn, who, alumni_id, settings) -> None:
    row = aa.alumnus(conn, alumni_id)
    aa.require(who is not None and who.alumni_id == alumni_id,
               "Only the alumnus can choose how they appear in the directory")
    if row.get("deceased_at") or row.get("anonymised_at"):
        raise ValueError("This record cannot be listed")
    values = [int(bool(settings.get(k))) for k in DIRECTORY_SETTINGS]
    conn.execute(f"INSERT INTO alumni_directory_settings (alumni_id, "
                 f"{', '.join(DIRECTORY_SETTINGS)}) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT "
                 f"(alumni_id) DO UPDATE SET "
                 + ", ".join(f"{k} = excluded.{k}" for k in DIRECTORY_SETTINGS),
                 (alumni_id, *values))
    aa.audit(conn, who, "alumni", alumni_id, "directory_settings",
             dict(zip(DIRECTORY_SETTINGS, values)))


def _directory_entry(row, settings) -> dict | None:
    if not settings.get("searchable") or row.get("deceased_at") or row.get("anonymised_at"):
        return None
    entry = {"alumni_id": row["alumni_id"], "name": " ".join(
        p for p in (row.get("first_name"), row.get("last_name")) if p),
             "graduation_year": row.get("graduation_year"), "country": row.get("country")}
    if settings.get("show_education"):
        entry["degree_earned"] = row.get("degree_earned")
    if settings.get("show_employment"):
        entry.update(current_employer=row.get("current_employer"),
                     job_title=row.get("job_title"), industry=row.get("industry"),
                     skills=row.get("skills"))
    if settings.get("show_contact_info"):
        entry.update(email_address=row.get("email_address"), phone=row.get("phone"),
                     linkedin_url=row.get("linkedin_url"), city=row.get("city"))
    entry["networking_available"] = bool(settings.get("networking_available"))
    entry["mentor_available"] = bool(settings.get("mentor_available"))
    return entry


def search_directory(conn, who, name=None, year=None, industry=None, country=None, skills=None,
                     location=None) -> list[dict]:
    """Listed alumni only, showing only what each chose to show — and
    searching only what each chose to show: skills (comma-separated, every
    one must match) are searched only for alumni who show their employment,
    and a location matches the country, or the city of alumni who show
    their contact details."""
    aa.ensure(conn)
    aa.require(who is not None, "Sign in to use the directory")
    where, params = ["d.searchable = 1", "a.deceased_at IS NULL", "a.anonymised_at IS NULL"], []
    if name:
        like = f"%{str(name).lower()}%"
        where.append("(LOWER(COALESCE(a.first_name, '')) LIKE ? OR LOWER(COALESCE(a.last_name, "
                     "'')) LIKE ?)")
        params += [like, like]
    if year:
        where.append("a.graduation_year = ?")
        params.append(int(year))
    if industry:
        where.append("d.show_employment = 1 AND LOWER(COALESCE(a.industry, '')) LIKE ?")
        params.append(f"%{str(industry).lower()}%")
    if country:
        where.append("LOWER(COALESCE(a.country, '')) = ?")
        params.append(str(country).lower())
    for skill in [p.strip().lower() for p in str(skills or "").split(",") if p.strip()]:
        where.append("d.show_employment = 1 AND LOWER(COALESCE(a.skills, '')) LIKE ? ESCAPE '\\'")
        params.append(f"%{_like(skill)}%")
    if location and str(location).strip():
        place = f"%{_like(str(location).strip().lower())}%"
        where.append("(LOWER(COALESCE(a.country, '')) LIKE ? ESCAPE '\\' OR (d.show_contact_info "
                     "= 1 AND LOWER(COALESCE(a.city, '')) LIKE ? ESCAPE '\\'))")
        params += [place, place]
    rows = aa.dicts(conn.execute(
        "SELECT a.*, d.searchable, d.show_contact_info, d.show_employment, d.show_education, "
        "d.networking_available, d.mentor_available FROM alumni a JOIN "
        "alumni_directory_settings d ON d.alumni_id = a.alumni_id WHERE " + " AND ".join(where)
        + " ORDER BY a.last_name, a.first_name", params))
    return [e for e in (_directory_entry(r, r) for r in rows) if e]


def _like(text) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ── data requests ───────────────────────────────────────────────────────


def export(conn, who, alumni_id) -> dict:
    """Everything held about the alumnus (subject access)."""
    row = aa.alumnus(conn, alumni_id)
    _self_or_office(who, alumni_id)
    out = {"profile": row, "directory_settings": directory_settings(conn, alumni_id)}
    queries = {
        "gifts": ("donations", "SELECT * FROM donations WHERE alumni_id = ?"),
        "gift_aid_declarations": ("gift_aid_declarations",
                                  "SELECT * FROM gift_aid_declarations WHERE alumni_id = ?"),
        "pledges": ("donation_pledges", "SELECT * FROM donation_pledges WHERE alumni_id = ?"),
        "chapters": ("chapter_memberships",
                     "SELECT * FROM chapter_memberships WHERE alumni_id = ?"),
        "mentoring": ("mentorships", "SELECT * FROM mentorships WHERE mentor_id = ?"),
        "mentor_vetting": ("mentor_vetting", "SELECT * FROM mentor_vetting WHERE alumni_id = ?"),
        "stories": ("alumni_stories", "SELECT * FROM alumni_stories WHERE alumni_id = ?"),
        "forum_posts": ("alumni_forum", "SELECT * FROM alumni_forum WHERE author_id = ?"),
        "newsletters_sent": ("newsletter_deliveries",
                             "SELECT * FROM newsletter_deliveries WHERE alumni_id = ?"),
        "history": ("alumni_audit", "SELECT at, actor, action, detail FROM alumni_audit WHERE "
                                    "entity = 'alumni' AND entity_id = ?"),
    }
    for key, (table, sql) in queries.items():
        out[key] = aa.dicts(conn.execute(sql, (alumni_id,))) if aa.has_table(conn, table) else []
    conn.execute("INSERT INTO alumni_data_requests (alumni_id, kind, requested_by, status, "
                 "completed_by, completed_at) VALUES (?, 'export', ?, 'completed', ?, ?)",
                 (alumni_id, who.username, who.username, aa.now()))
    aa.audit(conn, who, "alumni", alumni_id, "exported")
    return out


def request_erasure(conn, who, alumni_id, note="") -> int:
    aa.alumnus(conn, alumni_id)
    _self_or_office(who, alumni_id)
    rid = conn.execute("INSERT INTO alumni_data_requests (alumni_id, kind, requested_by, note) "
                       "VALUES (?, 'erasure', ?, ?)", (alumni_id, who.username,
                                                        note or None)).lastrowid
    aa.audit(conn, who, "alumni", alumni_id, "erasure_requested")
    aa.notify(conn, aa.holders(conn, "alumni_office"), "Alumni erasure request",
              f"{alumni_id} asked for their alumni record to be erased.")
    return int(rid)


def gift_aid_hold_until(conn, alumni_id) -> str | None:
    """Gift Aid records must be kept six years after the last claimed gift."""
    row = conn.execute("SELECT MAX(c.period_to) FROM donations d JOIN gift_aid_claims c ON "
                       "c.claim_id = d.gift_aid_claim_id WHERE d.alumni_id = ?",
                       (alumni_id,)).fetchone()
    if not row or not row[0]:
        return None
    last = date.fromisoformat(row[0][:10])
    return date(last.year + GIFT_AID_RETENTION_YEARS, last.month, min(last.day, 28)).isoformat()


def erase(conn, who, alumni_id, reason) -> dict:
    """Anonymise the alumni record (the office acts on a request)."""
    row = aa.alumnus(conn, alumni_id)
    aa.require(_office(who), "Only the alumni office can erase a record")
    if row.get("anonymised_at"):
        raise ValueError("This record is already erased")
    reason = aa.text(reason, "Reason", True)
    blank = ("title", "first_name", "middle_name", "email_address", "phone", "address", "city",
             "linkedin_url", "bio", "skills", "achievements", "dob", "gender", "profile_photo",
             "social_media_links", "current_employer", "job_title")
    conn.execute(f"UPDATE alumni SET {', '.join(f'{k} = NULL' for k in blank)}, last_name = "
                 "'Erased', anonymised_at = ?, do_not_contact = 1, marketing_consent = 0, "
                 "updated_at = ?, updated_by = ? WHERE alumni_id = ?",
                 (aa.now(), aa.now(), who.username, alumni_id))
    for sql in ("DELETE FROM alumni_directory_settings WHERE alumni_id = ?",
                "DELETE FROM chapter_memberships WHERE alumni_id = ?",
                "DELETE FROM mentor_vetting WHERE alumni_id = ?",
                "DELETE FROM alumni_unsubscribe_tokens WHERE alumni_id = ?",
                "UPDATE donation_pledges SET status = 'cancelled', cancelled_reason = 'erased' "
                "WHERE alumni_id = ? AND status = 'active'"):
        conn.execute(sql, (alumni_id,))
    if aa.has_table(conn, "alumni_stories"):
        conn.execute("UPDATE alumni_stories SET status = 'withdrawn' WHERE alumni_id = ?",
                     (alumni_id,))
    keep_until = gift_aid_hold_until(conn, alumni_id)
    if keep_until is None:
        conn.execute("UPDATE gift_aid_declarations SET full_name = 'Erased', house = '', "
                     "postcode = '' WHERE alumni_id = ?", (alumni_id,))
    conn.execute("UPDATE alumni_data_requests SET status = 'completed', completed_by = ?, "
                 "completed_at = ? WHERE alumni_id = ? AND kind = 'erasure' AND status = 'open'",
                 (who.username, aa.now(), alumni_id))
    aa.audit(conn, who, "alumni", alumni_id, "erased", {"reason": reason,
                                                        "gift_aid_kept_until": keep_until})
    return {"alumni_id": alumni_id, "gift_aid_kept_until": keep_until}


def data_requests(conn, who, status="open") -> list[dict]:
    aa.require(_office(who), "Only the alumni office can see data requests")
    aa.ensure(conn)
    return aa.dicts(conn.execute("SELECT * FROM alumni_data_requests" +
                                 (" WHERE status = ?" if status else "") +
                                 " ORDER BY requested_at", (status,) if status else ()))


# ── the move from graduate to alumnus ───────────────────────────────────


def _step(conn, student_id, step, details) -> None:
    import json
    conn.execute("INSERT OR IGNORE INTO alumni_transition_steps (student_id, step_name, status, "
                 "details_json) VALUES (?, ?, 'completed', ?)",
                 (student_id, step, json.dumps(details, sort_keys=True, default=str)))


def on_conferral(conn, student_id, conferral_date) -> None:
    """Called inside the award conferral: record the transition steps."""
    aa.ensure(conn)
    if not aa.has_table(conn, "alumni_transition_steps"):
        return
    day = date.fromisoformat(conferral_date[:10])
    due = date(day.year + (day.month + 15 - 1) // 12, (day.month + 15 - 1) % 12 + 1,
               min(day.day, 28)).isoformat()
    conn.execute("UPDATE alumni SET graduate_outcomes_due = COALESCE(graduate_outcomes_due, ?) "
                 "WHERE alumni_id = ?", (due, student_id))
    balance = None
    if aa.has_table(conn, "student_finance_accounts"):
        row = conn.execute("SELECT balance FROM student_finance_accounts WHERE student_id = ?",
                           (student_id,)).fetchone()
        balance = float(row[0] or 0) if row else 0.0
    _step(conn, student_id, "alumni_profile", {"alumni_id": student_id})
    _step(conn, student_id, "access_change", {"role": "alumni", "when": "after commit"})
    _step(conn, student_id, "account_settlement", {"balance": balance,
                                                   "settled": not balance or balance <= 0})
    _step(conn, student_id, "consent_capture", {"asked": True})
    _step(conn, student_id, "graduate_outcomes", {"survey_due": due})
    aa.notify(conn, [student_id], "Welcome to the alumni community",
              "Choose whether we may keep in touch, and how you appear in the alumni "
              "directory, in the alumni portal. You are not listed until you choose to be.")


def transition_status(conn, alumni_id) -> list[dict]:
    if not aa.has_table(conn, "alumni_transition_steps"):
        return []
    done = {r["step_name"]: r for r in aa.dicts(conn.execute(
        "SELECT * FROM alumni_transition_steps WHERE student_id = ?", (alumni_id,)))}
    return [{"step": s, "done": s in done, "at": done.get(s, {}).get("completed_at"),
             "details": done.get(s, {}).get("details_json")} for s in TRANSITION_STEPS]


def listing(conn, who, search=None, filter_=None) -> list[dict]:
    """Office list: everyone, with suppression flags."""
    aa.ensure(conn)
    aa.require(who is not None and who.is_staff_role, "Only alumni staff can list alumni")
    where, params = [], []
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(alumni_id) LIKE ? OR LOWER(COALESCE(first_name, '')) LIKE ? OR "
                     "LOWER(COALESCE(last_name, '')) LIKE ? OR LOWER(COALESCE(email_address, "
                     "'')) LIKE ?)")
        params += [like] * 4
    filters = {"consented": "marketing_consent = 1", "not_asked": "marketing_consent IS NULL",
               "suppressed": "(do_not_contact = 1 OR deceased_at IS NOT NULL OR anonymised_at "
                             "IS NOT NULL)", "deceased": "deceased_at IS NOT NULL"}
    if filter_ in filters:
        where.append(filters[filter_])
    return aa.dicts(conn.execute("SELECT * FROM alumni" + (" WHERE " + " AND ".join(where)
                                                           if where else "")
                                 + " ORDER BY last_name, first_name", params))
