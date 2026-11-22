"""Research outputs: the record, its authors, and the REF open-access check.

Outputs live on ``research_publications``; authors, in order, on
``research_output_authors`` (``username`` set for the university's own staff).
An author or the research office may edit an output.

Open access (REF policy): journal articles and conference papers with an
ISSN must be deposited in a repository within three months of acceptance,
unless an exception is recorded. Everything else is out of scope.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.research import access as ra

TYPES = ("Journal article", "Conference paper", "Book", "Book chapter", "Report",
         "Dataset", "Software", "Patent", "Exhibition", "Other")
OA_ROUTES = ("gold", "green", "none")
OA_EXCEPTIONS = ("deposit", "access", "technical", "other")
DEPOSIT_DAYS = 92
_FIELDS = ("title", "publication_type", "venue", "journal_name", "conference_name",
           "publication_date", "acceptance_date", "deposit_date", "doi", "url", "issn",
           "repository_url", "oa_route", "oa_exception", "abstract", "keywords", "uoa",
           "is_peer_reviewed", "project_id")


def output(conn, publication_id) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM research_publications WHERE publication_id = ?",
                 (publication_id,))
    if not row:
        raise ValueError("No such output")
    return row


def authors(conn, publication_id) -> list[dict]:
    return ra.dicts(conn.execute("SELECT position, name, username FROM research_output_authors "
                                 "WHERE publication_id = ? ORDER BY position", (publication_id,)))


def _internal(conn, publication_id) -> set:
    return {r[0] for r in conn.execute("SELECT username FROM research_output_authors WHERE "
                                       "publication_id = ? AND username IS NOT NULL",
                                       (publication_id,))}


def can_edit(conn, who, row) -> bool:
    return who.is_office or who.leads_ref(row.get("uoa")) or \
        who.username in _internal(conn, row["publication_id"]) or \
        who.username == row.get("created_by")


def _clean(conn, data) -> dict:
    out = {}
    for key in _FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key.endswith("_date"):
            value = ra.iso_date(value, key.replace("_", " ").capitalize())
        elif key == "publication_type" and value not in TYPES:
            raise ValueError("Output type must be one of " + ", ".join(TYPES))
        elif key == "oa_route" and value not in (None, "") and value not in OA_ROUTES:
            raise ValueError("Open-access route must be gold, green or none")
        elif key == "oa_exception" and value not in (None, "") and value not in OA_EXCEPTIONS:
            raise ValueError("Exception must be one of " + ", ".join(OA_EXCEPTIONS))
        elif key == "is_peer_reviewed":
            value = int(bool(value))
        elif key == "project_id":
            value = int(value) if value not in (None, "") else None
        elif key == "doi" and value:
            value = str(value).strip().removeprefix("https://doi.org/").removeprefix("doi:")
        else:
            value = ra.text(value, key)
        out[key] = value
    if out.get("acceptance_date") and out.get("deposit_date") and \
            out["deposit_date"] < out["acceptance_date"]:
        raise ValueError("An output cannot be deposited before it is accepted")
    return out


def _parse_authors(conn, value) -> list[tuple[str, str | None]]:
    """``"Smith, J. [jsmith]; Jones, K."`` → [(name, username), …]. A
    username in square brackets marks the university's own staff."""
    items = value if isinstance(value, list) else [
        a.strip() for a in str(value or "").replace("\n", ";").split(";") if a.strip()]
    out = []
    for item in items:
        if isinstance(item, (tuple, list)):
            name, username = item[0], (item[1] or None)
        elif "[" in item and item.endswith("]"):
            name, username = item[:item.index("[")].strip(), item[item.index("[") + 1:-1].strip()
        else:
            name, username = item, None
        if username:
            ra.staff_ref(conn, username, "Author")
            name = name or ra.person_name(conn, username)
        if not name:
            raise ValueError("Every author needs a name")
        out.append((name, username or None))
    if not out:
        raise ValueError("List at least one author")
    return out


def _set_authors(conn, publication_id, author_list) -> None:
    conn.execute("DELETE FROM research_output_authors WHERE publication_id = ?",
                 (publication_id,))
    for n, (name, username) in enumerate(author_list, 1):
        conn.execute("INSERT INTO research_output_authors (publication_id, position, name, "
                     "username) VALUES (?, ?, ?, ?)", (publication_id, n, name, username))
    lead = next((u for _, u in author_list if u), None)
    conn.execute("UPDATE research_publications SET authors = ?, lead_author_id = ? WHERE "
                 "publication_id = ?",
                 ("; ".join(n for n, _ in author_list), lead, publication_id))


def create(conn, who, data, author_list) -> int:
    ra.ensure(conn)
    ra.require_staff(who)
    fields = _clean(conn, data)
    if not fields.get("title") or not fields.get("publication_type"):
        raise ValueError("Title and output type are required")
    people = _parse_authors(conn, author_list)
    if who.username not in {u for _, u in people} and not who.is_office:
        raise ValueError("Add yourself as an author (Name [username]) — or ask the research "
                         "office to record it")
    if fields.get("doi") and conn.execute("SELECT 1 FROM research_publications WHERE "
                                          "LOWER(doi) = LOWER(?)", (fields["doi"],)).fetchone():
        raise ValueError("An output with this DOI is already recorded")
    cols = ["authors", "created_by", "updated_at", *fields]
    pid = conn.execute(
        f"INSERT INTO research_publications ({', '.join(cols)}) VALUES "
        f"({', '.join('?' * len(cols))})", ["", who.username, ra.now(), *fields.values()]
    ).lastrowid
    _set_authors(conn, pid, people)
    _sync_open_access(conn, pid)
    ra.audit(conn, who, "output", pid, "created")
    return int(pid)


def update(conn, who, publication_id, data, author_list=None) -> None:
    row = output(conn, publication_id)
    ra.require(can_edit(conn, who, row), "Only an author can edit this output")
    fields = _clean(conn, data)
    if fields.get("doi") and conn.execute(
            "SELECT 1 FROM research_publications WHERE LOWER(doi) = LOWER(?) AND "
            "publication_id <> ?", (fields["doi"], publication_id)).fetchone():
        raise ValueError("Another output already has this DOI")
    if fields:
        conn.execute(f"UPDATE research_publications SET {', '.join(f'{k} = ?' for k in fields)}, "
                     "updated_at = ? WHERE publication_id = ?",
                     (*fields.values(), ra.now(), publication_id))
    if author_list is not None:
        _set_authors(conn, publication_id, _parse_authors(conn, author_list))
    _sync_open_access(conn, publication_id)
    ra.audit(conn, who, "output", publication_id, "edited", {"fields": sorted(fields)})


def remove(conn, who, publication_id, reason) -> None:
    """Outputs are removed only by the research office, with a reason, and
    never once selected for REF."""
    row = output(conn, publication_id)
    ra.require(who.is_office, "Only the research office can remove an output")
    if row.get("ref_submitted"):
        raise ValueError("Take the output out of the REF selection first")
    reason = ra.text(reason, "Reason", True)
    ra.audit(conn, who, "output", publication_id, "removed",
             {"title": row["title"], "doi": row.get("doi"), "reason": reason})
    conn.execute("DELETE FROM research_publications WHERE publication_id = ?", (publication_id,))


# ── open access ─────────────────────────────────────────────────────────


def in_scope(row) -> bool:
    kind = row.get("publication_type")
    return kind == "Journal article" or (kind == "Conference paper" and bool(row.get("issn")))


def oa_status(row) -> str:
    """compliant / exception / not in scope / no acceptance date /
    not deposited / late deposit / deposit due by YYYY-MM-DD."""
    if not in_scope(row):
        return "not in scope"
    if row.get("oa_exception"):
        return "exception"
    if row.get("oa_route") == "gold" and row.get("deposit_date"):
        return "compliant"
    accepted = row.get("acceptance_date")
    if not accepted:
        return "no acceptance date"
    deadline = date.fromisoformat(accepted) + timedelta(days=DEPOSIT_DAYS)
    deposited = row.get("deposit_date")
    if deposited:
        return "compliant" if date.fromisoformat(deposited) <= deadline else "late deposit"
    if date.today() <= deadline:
        return f"deposit due by {deadline.isoformat()}"
    return "not deposited"


def oa_ok(row) -> bool:
    return oa_status(row) in ("compliant", "exception", "not in scope")


def _sync_open_access(conn, publication_id) -> None:
    row = output(conn, publication_id)
    conn.execute("UPDATE research_publications SET open_access = ? WHERE publication_id = ?",
                 (int(oa_status(row) in ("compliant", "exception")), publication_id))


def oa_problems(conn, who=None) -> list[dict]:
    """In-scope outputs that are not (yet) compliant."""
    out = []
    for row in listing(conn, who):
        status = oa_status(row)
        if status not in ("compliant", "exception", "not in scope"):
            out.append({**row, "oa_status": status})
    return out


# ── lists ───────────────────────────────────────────────────────────────


def listing(conn, who=None, search=None, uoa=None, mine=False) -> list[dict]:
    ra.ensure(conn)
    where, params = [], []
    if mine and who is not None:
        where.append("p.publication_id IN (SELECT publication_id FROM research_output_authors "
                     "WHERE username = ?)")
        params.append(who.username)
    if uoa:
        where.append("p.uoa = ?")
        params.append(uoa)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(p.title) LIKE ? OR LOWER(COALESCE(p.authors, '')) LIKE ? OR "
                     "LOWER(COALESCE(p.doi, '')) LIKE ? OR LOWER(COALESCE(p.venue, '')) LIKE ?)")
        params += [like] * 4
    rows = ra.dicts(conn.execute(
        "SELECT p.* FROM research_publications p" + (" WHERE " + " AND ".join(where)
                                                     if where else "")
        + " ORDER BY COALESCE(p.publication_date, p.acceptance_date, p.created_at) DESC", params))
    for row in rows:
        row["oa_status"] = oa_status(row)
    return rows


def record(conn, who, publication_id) -> dict:
    row = output(conn, publication_id)
    row["authors_list"] = authors(conn, publication_id)
    row["oa_status"] = oa_status(row)
    row["can_edit"] = can_edit(conn, who, row)
    row["history"] = ra.history(conn, "output", publication_id)
    return row
