"""Can this student graduate? The award, the programme's credit rule,
graduation holds and the name on the certificate.

* **The award** is the gate: an assessment board must have ratified the
  award and authorised its release (``ratified_student_awards``). A student
  whose status merely says "Graduated" is not eligible on that alone.
* **Credits** are shown against the programme's final award
  (``course_exit_awards``), else the course's own credit total — advisory,
  because the board has already applied the rules.
* **Holds** stop graduation: open graduation holds (appeals, registry,
  other) and academic integrity cases not yet settled
  (``integrity_review.blocking_cases``: undecided, decided with an appeal
  waiting, or sent to the misconduct panel). A case still open in the old
  ``academic_misconduct_cases`` table that was never copied across is
  counted too. Money owed is shown as a
  warning only: the OfS / CMA position is that an award should not be
  withheld for debt.
* **The certificate name** must be confirmed by the student, or set by the
  graduation office with evidence, before the award is conferred.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.application.graduation import access as ga

HOLD_KINDS = ("appeal", "misconduct", "registry", "finance", "other")
CLOSED_MISCONDUCT = ("resolved", "closed", "dismissed", "no case", "no_case", "withdrawn")
DEFAULT_CREDITS = 360


def award(conn, student_id) -> dict | None:
    """The latest ratified, released award."""
    if not ga.has_table(conn, "ratified_student_awards"):
        return None
    return ga.one(conn, "SELECT * FROM ratified_student_awards WHERE student_id = ? AND status = "
                        "'ratified' AND release_authorised = 1 ORDER BY ratified_at DESC, award_id "
                        "DESC LIMIT 1", (student_id,))


def award_under_correction(conn, student_id) -> dict | None:
    if not ga.has_table(conn, "ratified_student_awards"):
        return None
    return ga.one(conn, "SELECT * FROM ratified_student_awards WHERE student_id = ? AND (status "
                        "<> 'ratified' OR release_authorised = 0) AND superseded_by_award_id IS "
                        "NULL ORDER BY ratified_at DESC LIMIT 1", (student_id,))


def required_credits(conn, course) -> tuple[int, str]:
    """``(credits, where the figure came from)``."""
    if course and ga.has_table(conn, "course_exit_awards"):
        row = conn.execute("SELECT total_credits, award_name FROM course_exit_awards WHERE "
                           "course_code = ? ORDER BY is_final DESC, total_credits DESC LIMIT 1",
                           (course,)).fetchone()
        if row:
            return int(row[0]), f"programme award ({row[1]})"
    try:
        from education_system.systems.university.domains.progression.domain.degree_audit.progress import (  # noqa: E501
            required_credits_for_course,
        )
        credits = required_credits_for_course(conn, course, default=None)
        if credits:
            return int(credits), "course credit total"
    except Exception:
        pass
    return DEFAULT_CREDITS, "no programme rule set (UK honours default)"


def _earned(conn, student_id) -> dict:
    try:
        from education_system.systems.university.domains.progression.domain.degree_audit.progress import (  # noqa: E501
            earned_progress,
        )
        return earned_progress(conn, student_id)
    except Exception:
        return {"credits_earned": 0.0, "modules_completed": 0, "gpa": 0.0}


# ── holds ───────────────────────────────────────────────────────────────


def holds(conn, student_id, open_only=True) -> list[dict]:
    ga.ensure(conn)
    return ga.dicts(conn.execute(
        "SELECT * FROM graduation_holds WHERE student_id = ?" +
        (" AND released_at IS NULL" if open_only else "") + " ORDER BY placed_at DESC",
        (student_id,)))


def place_hold(conn, who, student_id, kind, reason) -> int:
    ga.ensure(conn)
    ga.require_office(who)
    ga.student(conn, student_id)
    if kind not in HOLD_KINDS:
        raise ValueError("Hold must be one of " + ", ".join(HOLD_KINDS))
    hid = conn.execute("INSERT INTO graduation_holds (student_id, kind, reason, placed_by) VALUES "
                       "(?, ?, ?, ?)", (student_id, kind, ga.text(reason, "Reason", True),
                                        who.username)).lastrowid
    ga.audit(conn, who, "hold", student_id, "placed", {"kind": kind, "reason": reason})
    return int(hid)


def release_hold(conn, who, hold_id, note) -> None:
    ga.require_office(who)
    row = ga.one(conn, "SELECT * FROM graduation_holds WHERE hold_id = ?", (hold_id,))
    if not row or row["released_at"]:
        raise ValueError("No such open hold")
    conn.execute("UPDATE graduation_holds SET released_by = ?, released_at = ?, release_note = ? "
                 "WHERE hold_id = ?", (who.username, ga.now(), ga.text(note, "Note", True),
                                       hold_id))
    ga.audit(conn, who, "hold", row["student_id"], "released", {"hold": hold_id, "note": note})


def all_open_holds(conn) -> list[dict]:
    ga.ensure(conn)
    return ga.dicts(conn.execute("SELECT * FROM graduation_holds WHERE released_at IS NULL ORDER "
                                 "BY placed_at DESC"))


def _misconduct(conn, student_id) -> list[str]:
    from education_system.systems.university.application.integrity import (
        review as integrity_review,
    )
    found = [f"Academic integrity case {c['id']} is not settled ({c['stage']})"
             for c in integrity_review.blocking_cases(conn, student_id)]
    if not ga.has_table(conn, "academic_misconduct_cases"):
        return found
    copied = ("AND NOT EXISTS (SELECT 1 FROM integrity_cases i WHERE i.legacy_case_id = "
              "CAST(COALESCE(m.case_id, m.id) AS TEXT))"
              if ga.has_table(conn, "integrity_cases") else "")
    rows = conn.execute("SELECT COALESCE(m.case_id, m.id), m.status FROM "  # nosec B608
                        f"academic_misconduct_cases m WHERE m.student_id = ? {copied}",
                        (student_id,)).fetchall()
    return found + [f"Academic misconduct case {r[0]} is open ({r[1]})" for r in rows
                    if str(r[1] or "").strip().lower() not in CLOSED_MISCONDUCT]


def _money_warnings(conn, student_id) -> list[str]:
    out = []
    if ga.has_table(conn, "student_finance_accounts"):
        row = conn.execute("SELECT COALESCE(balance, 0) FROM student_finance_accounts WHERE "
                           "student_id = ?", (student_id,)).fetchone()
        if row and float(row[0] or 0) > 0:
            out.append(f"Owes £{float(row[0]):,.2f} (shown only: the award is not withheld "
                       "for debt)")
    if ga.has_table(conn, "finance_holds") and conn.execute(
            "SELECT 1 FROM finance_holds WHERE student_id = ? AND is_active = 1",
            (student_id,)).fetchone():
        out.append("Has an active finance hold (enrolment only; it does not stop graduation)")
    return out


# ── the certificate name ────────────────────────────────────────────────


def certificate_name(conn, student_id) -> dict:
    ga.ensure(conn)
    row = ga.one(conn, "SELECT * FROM certificate_names WHERE student_id = ?", (student_id,))
    if row:
        row["confirmed"] = bool(row["confirmed_by_student"] or row.get("evidence"))
        return row
    st = ga.student(conn, student_id)
    full = " ".join(p for p in (st.get("first_name"), st.get("middle_name"),
                                st.get("last_name")) if p)
    return {"student_id": student_id, "certificate_name": full or st["name"],
            "confirmed": False, "confirmed_by_student": 0}


def confirm_name(conn, who, student_id, name) -> None:
    """The student confirms (or corrects) the name printed on the certificate.
    A correction that differs from the record needs the office to check it."""
    ga.ensure(conn)
    ga.require(who.is_student and who.student_id == student_id,
               "Only the student can confirm their certificate name")
    name = ga.text(name, "Certificate name", True)
    if len(name) > 120:
        raise ValueError("That name is too long for the certificate")
    record = certificate_name(conn, student_id)
    same = " ".join(name.split()).lower() == " ".join(
        str(record["certificate_name"]).split()).lower()
    conn.execute("INSERT INTO certificate_names (student_id, certificate_name, "
                 "confirmed_by_student, confirmed_at, set_by) VALUES (?, ?, ?, ?, ?) ON "
                 "CONFLICT (student_id) DO UPDATE SET certificate_name = excluded.certificate_name, "
                 "confirmed_by_student = excluded.confirmed_by_student, confirmed_at = "
                 "excluded.confirmed_at, set_by = excluded.set_by, evidence = NULL, updated_at = "
                 "datetime('now')", (student_id, name, int(same), ga.now() if same else None,
                                     who.username))
    ga.audit(conn, who, "certificate_name", student_id, "confirmed" if same else "change_requested",
             {"name": name})
    if not same:
        ga.notify(conn, ga.office_usernames(conn), "Certificate name change to check",
                  f"{student_id} asked for their certificate name to read {name!r}.")


def set_name(conn, who, student_id, name, evidence) -> None:
    """The office sets the certificate name on documentary evidence."""
    ga.ensure(conn)
    ga.require_office(who)
    ga.student(conn, student_id)
    name = ga.text(name, "Certificate name", True)
    evidence = ga.text(evidence, "Evidence (e.g. deed poll seen)", True)
    conn.execute("INSERT INTO certificate_names (student_id, certificate_name, "
                 "confirmed_by_student, set_by, evidence) VALUES (?, ?, 0, ?, ?) ON CONFLICT "
                 "(student_id) DO UPDATE SET certificate_name = excluded.certificate_name, set_by = "
                 "excluded.set_by, evidence = excluded.evidence, updated_at = datetime('now')",
                 (student_id, name, who.username, evidence))
    ga.audit(conn, who, "certificate_name", student_id, "set", {"name": name,
                                                                "evidence": evidence})


# ── the check ───────────────────────────────────────────────────────────


def _conferred(conn, student_id) -> dict | None:
    ga.ensure(conn)
    return ga.one(conn, "SELECT * FROM graduation_conferrals WHERE student_id = ? AND status IN "
                        "('conferred', 'suspended') ORDER BY conferral_id DESC LIMIT 1",
                  (student_id,))


_CLASS_ALIASES = {"first class": "first", "upper second": "2:1", "2.1": "2:1",
                  "lower second": "2:2", "2.2": "2:2", "third class": "third"}


def _same_class(a, b) -> bool:
    def norm(v):
        v = " ".join(str(v).lower().replace("honours", "").split())
        return _CLASS_ALIASES.get(v, v)
    return norm(a) == norm(b)


def _classification_check(conn, student_id, the_award) -> tuple[dict | None, list[str]]:
    """The student's classification rules, and a warning when the ratified
    classification differs from what those rules give today (advisory: the
    board's ratification stands; a difference usually means marks changed)."""
    try:
        from education_system.systems.university.application.assessment import (
            classification_rules,
        )
        result = classification_rules.classify(conn, student_id)
    except Exception:
        return None, []
    rules = {"rule_set": result.get("rule_set"), "scheme": result.get("scheme"),
             "basis": result.get("basis"), "calculated": result.get("classification"),
             "average": result.get("average")}
    ratified = (the_award or {}).get("classification")
    is_exit = (the_award or {}).get("award_name") in {
        a["name"] for a in classification_rules.UG_EXIT_AWARDS + classification_rules.PG_EXIT_AWARDS}
    if not ratified or is_exit or not rules["calculated"] or _same_class(ratified, rules["calculated"]):
        return rules, []
    return rules, [f"Ratified classification {ratified!r} differs from {rules['calculated']!r} "
                   f"under {rules['rule_set']} ({rules['basis']}); the board's ratification "
                   "stands — refer to the board if marks have changed"]


def check(conn, student_id) -> dict:
    """Everything about whether ``student_id`` can graduate.

    ``eligible`` – a released award and nothing blocking;
    ``blockers`` – why not; ``warnings`` – shown but not blocking."""
    ga.ensure(conn)
    st = ga.student(conn, student_id)
    the_award = award(conn, student_id)
    need, source = required_credits(conn, st.get("course"))
    earned = _earned(conn, student_id)
    blockers, warnings = [], _money_warnings(conn, student_id)
    if the_award is None:
        corrected = award_under_correction(conn, student_id)
        blockers.append("The award is back with the assessment board for correction"
                        if corrected else "No assessment board has ratified and released an "
                                          "award yet")
    blockers += [f"Graduation hold ({h['kind']}): {h['reason']}" for h in holds(conn, student_id)]
    blockers += _misconduct(conn, student_id)
    if float(earned.get("credits_earned") or 0) < need:
        warnings.append(f"{earned.get('credits_earned', 0):.0f} of {need} credits recorded "
                        f"({source}); the board's ratification stands")
    rules, rule_warnings = _classification_check(conn, student_id, the_award)
    warnings += rule_warnings
    name = certificate_name(conn, student_id)
    conferral = _conferred(conn, student_id)
    return {
        "student_id": student_id, "student_name": st["name"], "status": st.get("status"),
        "course": st.get("course"), "award": the_award, "eligible": the_award is not None and
        not blockers, "blockers": blockers, "warnings": warnings,
        "credits_earned": float(earned.get("credits_earned") or 0), "credits_required": need,
        "credits_source": source, "certificate_name": name["certificate_name"],
        "name_confirmed": name["confirmed"], "conferral": conferral,
        "classification_rules": rules,
    }
