"""What the Student Union election service can actually do with a ballot.

Elections live in ``elections`` (``title`` is the position); candidates in
``election_candidates``; a single-choice ballot is one
``election_votes`` row and a ranked ballot is one ``ranked_votes`` row
whose ``candidate_preferences`` is a comma-separated list of candidate
ids in preference order (the shape ``services/voting.ranked_choice_voting``
writes). Those are the only two ballot stores, so they are the only two
methods that can be cast and counted:

* ``simple`` — one choice, plurality count over ``election_votes``;
* ``ranked_choice`` — instant-runoff count over ``ranked_votes``
  (:func:`tally_ranked`).

``approval`` appears as a choice for ``default_voting_method`` in the
CLI configuration (``voting_configuration``), but nothing stores or
counts an approval ballot, so screens must present it as configurable
only. Score voting is not implemented anywhere.

Per-election method choices are kept in the existing
``election_voting_config`` table under ``config_name = 'election:<id>'``
(latest row wins); the union-wide default is
``voting_configuration.default_voting_method`` when that table exists.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Optional

SIMPLE, RANKED, APPROVAL, SCORE = "simple", "ranked_choice", "approval", "score"

METHOD_LABELS = {
    SIMPLE: "Standard Voting",
    RANKED: "Ranked Choice",
    APPROVAL: "Approval Voting",
    SCORE: "Score Voting",
}

# What each method can do today, from the code above — not aspiration.
METHOD_SUPPORT = {
    SIMPLE: {"cast": True, "count": True,
             "note": "One choice per election; stored in election_votes; plurality count."},
    RANKED: {"cast": True, "count": True,
             "note": "Voters rank candidates; stored in ranked_votes; instant-runoff count."},
    APPROVAL: {"cast": False, "count": False,
               "note": "Selectable as the union default, but no approval ballot is stored "
                       "or counted yet."},
    SCORE: {"cast": False, "count": False,
            "note": "Not implemented by the election service."},
}

_LABEL_TO_METHOD = {
    "standard voting": SIMPLE, "simple majority": SIMPLE, "simple": SIMPLE,
    "ranked choice": RANKED, "ranked_choice": RANKED, "ranked choice voting": RANKED,
    "approval voting": APPROVAL, "approval": APPROVAL,
    "score voting": SCORE, "score": SCORE,
}


def method_from_label(label: Optional[str]) -> str:
    return _LABEL_TO_METHOD.get((label or "").strip().lower(), SIMPLE)


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def ensure_schema(conn) -> None:
    """The per-election config table (same DDL the configure dialog used)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS election_voting_config (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_name TEXT NOT NULL,
            voting_method TEXT NOT NULL,
            allow_abstain INTEGER DEFAULT 0,
            require_ranked INTEGER DEFAULT 0,
            max_choices INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def union_default(conn) -> dict:
    """Union-wide settings from ``voting_configuration`` (CLI-managed)."""
    out = {"default_method": SIMPLE, "allow_ranked_choice": True}
    if not _table_exists(conn, "voting_configuration"):
        return out
    rows = dict(conn.execute(
        "SELECT config_key, config_value FROM voting_configuration "
        "WHERE config_key IN ('default_voting_method', 'allow_ranked_choice')"
    ).fetchall())
    if rows.get("default_voting_method"):
        out["default_method"] = method_from_label(rows["default_voting_method"])
    if "allow_ranked_choice" in rows:
        out["allow_ranked_choice"] = str(rows["allow_ranked_choice"]).lower() in ("true", "1", "yes")
    return out


def election_config(conn, election_id: int) -> dict:
    """The configured method for one election, falling back to the default."""
    ensure_schema(conn)
    row = conn.execute(
        "SELECT voting_method, allow_abstain, require_ranked, max_choices, created_by, created_at "
        "FROM election_voting_config WHERE config_name = ? "
        "ORDER BY config_id DESC LIMIT 1",
        (f"election:{election_id}",),
    ).fetchone()
    if row:
        return {"method": method_from_label(row[0]), "allow_abstain": bool(row[1]),
                "require_full_ranking": bool(row[2]), "max_choices": int(row[3] or 0),
                "updated_by": row[4], "updated_at": row[5], "configured": True}
    return {"method": union_default(conn)["default_method"], "allow_abstain": False,
            "require_full_ranking": False, "max_choices": 0, "updated_by": None,
            "updated_at": None, "configured": False}


def save_election_config(conn, *, election_id: int, method: str, allow_abstain: bool = False,
                         require_full_ranking: bool = False, max_choices: int = 0,
                         updated_by: Optional[str] = None) -> int:
    """Record the method for an election and commit. Refuses unsupported methods."""
    ensure_schema(conn)
    if method not in METHOD_SUPPORT:
        raise ValueError(f"Unknown voting method: {method}")
    if not METHOD_SUPPORT[method]["cast"]:
        raise ValueError(f"{METHOD_LABELS[method]} cannot be used yet: "
                         f"{METHOD_SUPPORT[method]['note']}")
    if method == RANKED and not union_default(conn)["allow_ranked_choice"]:
        raise ValueError("Ranked choice voting is switched off in the union voting configuration.")
    if not conn.execute("SELECT 1 FROM elections WHERE id = ?",
                        (election_id,)).fetchone():
        raise ValueError("That election no longer exists.")
    if _ballots_cast(conn, election_id):
        current = election_config(conn, election_id)["method"]
        if current != method:
            raise ValueError("Votes have already been cast in this election, so its "
                             "voting method can no longer be changed.")
    cur = conn.execute(
        "INSERT INTO election_voting_config (config_name, voting_method, allow_abstain, "
        "require_ranked, max_choices, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"election:{election_id}", method, int(bool(allow_abstain)),
         int(bool(require_full_ranking)), int(max_choices or 0), updated_by,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    return cur.lastrowid


def _ballots_cast(conn, election_id: int) -> int:
    n = 0
    if _table_exists(conn, "election_votes"):
        n += conn.execute("SELECT COUNT(*) FROM election_votes WHERE election_id = ?",
                          (election_id,)).fetchone()[0]
    if _table_exists(conn, "ranked_votes"):
        n += conn.execute("SELECT COUNT(*) FROM ranked_votes WHERE election_id = ?",
                          (election_id,)).fetchone()[0]
    return n


def elections(conn, *, statuses: Optional[tuple] = None) -> list[dict]:
    """Union elections with their configured method and ballot counts."""
    sql = ("SELECT id AS election_id, title AS position, department, nomination_start, "
           "nomination_end, voting_start, voting_end, status FROM elections")
    params: tuple = ()
    if statuses:
        sql += " WHERE LOWER(COALESCE(status, '')) IN (%s)" % ", ".join("?" for _ in statuses)
        params = tuple(s.lower() for s in statuses)
    sql += " ORDER BY COALESCE(voting_start, nomination_start) DESC, id DESC"
    # db-audit: ignore[DBW001] - placeholders only
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        e = dict(zip(("election_id", "position", "department", "nomination_start",
                      "nomination_end", "voting_start", "voting_end", "status"), tuple(r)))
        cfg = election_config(conn, e["election_id"])
        e["method"] = cfg["method"]
        e["method_label"] = METHOD_LABELS[cfg["method"]]
        e["ballots"] = _ballots_cast(conn, e["election_id"])
        e["candidates"] = conn.execute(
            "SELECT COUNT(*) FROM election_candidates WHERE election_id = ?",
            (e["election_id"],)).fetchone()[0]
        out.append(e)
    return out


def eligible_voters(conn) -> int:
    """Students who could vote — the turnout denominator."""
    if not _table_exists(conn, "students"):
        return 0
    cols = {r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
    if "status" in cols:
        return conn.execute(
            "SELECT COUNT(*) FROM students WHERE LOWER(COALESCE(status, 'active')) "
            "IN ('active', 'enrolled', 'current')").fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]


def method_statistics(conn, *, year: Optional[str] = None) -> dict:
    """Elections per method and mean turnout per method (this year by default)."""
    year = year or datetime.now().strftime("%Y")
    rows = [e for e in elections(conn)
            if str(e["voting_start"] or e["nomination_start"] or "").startswith(year)]
    voters = eligible_voters(conn)
    per = {m: {"elections": 0, "turnouts": []} for m in METHOD_LABELS}
    for e in rows:
        per[e["method"]]["elections"] += 1
        if voters and e["ballots"]:
            per[e["method"]]["turnouts"].append(e["ballots"] / voters * 100)
    return {
        "year": year,
        "total": len(rows),
        "eligible_voters": voters,
        "by_method": {
            m: {"elections": v["elections"],
                "share": (v["elections"] / len(rows) * 100) if rows else 0.0,
                "turnout": (sum(v["turnouts"]) / len(v["turnouts"])) if v["turnouts"] else None}
            for m, v in per.items()
        },
    }


def candidates(conn, election_id: int) -> list[dict]:
    """Real candidates for an election; empty list if there are none."""
    rows = conn.execute(
        """
        SELECT c.id,
               COALESCE(NULLIF(TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')), ''),
                        c.candidate_name, c.student_id) AS name,
               s.course, c.manifesto
        FROM election_candidates c
        LEFT JOIN students s ON s.student_id = c.student_id
        WHERE c.election_id = ?
        ORDER BY name
        """,
        (election_id,),
    ).fetchall()
    out = [dict(zip(("candidate_id", "name", "course", "manifesto"), tuple(r))) for r in rows]
    # Endorsements are keyed by candidate name (candidate_endorsements has no id).
    has_endorsements = _table_exists(conn, "candidate_endorsements")
    for c in out:
        c["endorsements"] = conn.execute(
            "SELECT COUNT(*) FROM candidate_endorsements WHERE candidate_name = ?",
            (c["name"],)).fetchone()[0] if has_endorsements else None
    return out


def is_voting_open(election: dict, today: Optional[str] = None) -> bool:
    today = today or datetime.now().strftime("%Y-%m-%d")
    if (election.get("status") or "").lower() != "voting":
        return False
    start, end = election.get("voting_start"), election.get("voting_end")
    return (not start or str(start)[:10] <= today) and (not end or str(end)[:10] >= today)


def ranked_elections_open_to(conn, voter_id: Optional[str]) -> list[dict]:
    """Elections set to ranked choice, open now, that this voter has not voted in."""
    out = []
    for e in elections(conn, statuses=("voting",)):
        if e["method"] != RANKED or not is_voting_open(e):
            continue
        if voter_id and has_voted(conn, e["election_id"], voter_id):
            continue
        out.append(e)
    return out


def has_voted(conn, election_id: int, voter_id: str) -> bool:
    for table in ("ranked_votes", "election_votes"):
        if _table_exists(conn, table):
            # db-audit: ignore[DBW001] - table is one of two literals
            if conn.execute(f"SELECT 1 FROM {table} WHERE election_id = ? AND voter_id = ? LIMIT 1",
                            (election_id, voter_id)).fetchone():
                return True
    return False


def cast_ranked(conn, *, election_id: int, voter_id: str, ranked_candidate_ids: list[int]) -> int:
    """Store a ranked ballot (preference order) and commit; returns the vote id."""
    if not voter_id:
        raise ValueError("You must be signed in to vote.")
    row = conn.execute(
        "SELECT id, title, status, voting_start, voting_end FROM elections "
        "WHERE id = ?", (election_id,)).fetchone()
    if not row:
        raise ValueError("That election no longer exists.")
    election = dict(zip(("election_id", "position", "status", "voting_start", "voting_end"), tuple(row)))
    if not is_voting_open(election):
        raise ValueError(f"Voting for {election['position']} is not open.")
    cfg = election_config(conn, election_id)
    if cfg["method"] != RANKED:
        raise ValueError(f"{election['position']} uses {METHOD_LABELS[cfg['method']]}, not ranked choice.")
    if has_voted(conn, election_id, voter_id):
        raise ValueError("You have already voted in this election.")
    valid = {c["candidate_id"] for c in candidates(conn, election_id)}
    prefs = [int(c) for c in ranked_candidate_ids]
    if not prefs:
        raise ValueError("Please rank at least one candidate.")
    if len(set(prefs)) != len(prefs):
        raise ValueError("Each candidate can only be ranked once.")
    if not set(prefs) <= valid:
        raise ValueError("The ballot names a candidate who is not standing in this election.")
    if cfg["require_full_ranking"] and len(prefs) != len(valid):
        raise ValueError("This election requires you to rank every candidate.")
    if cfg["max_choices"] and len(prefs) > cfg["max_choices"]:
        raise ValueError(f"You can rank at most {cfg['max_choices']} candidates.")
    cur = conn.execute(
        "INSERT INTO ranked_votes (election_id, voter_id, candidate_preferences, vote_time) "
        "VALUES (?, ?, ?, ?)",
        (election_id, voter_id, ",".join(map(str, prefs)),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    return cur.lastrowid


def tally_ranked(conn, election_id: int) -> dict:
    """Instant-runoff count of ``ranked_votes`` for one election.

    Eliminates the lowest candidate each round (ties broken by fewer
    first-preference votes, then by candidate id) until someone holds a
    majority of the ballots still live. Returns rounds, winner, exhausted.
    """
    names = {c["candidate_id"]: c["name"] for c in candidates(conn, election_id)}
    ballots = []
    if _table_exists(conn, "ranked_votes"):
        for (prefs,) in conn.execute(
                "SELECT candidate_preferences FROM ranked_votes WHERE election_id = ?",
                (election_id,)).fetchall():
            seq = []
            for part in str(prefs or "").split(","):
                part = part.strip()
                if part.isdigit() and int(part) in names and int(part) not in seq:
                    seq.append(int(part))
            ballots.append(seq)
    total = len(ballots)
    if not names:
        return {"total": total, "rounds": [], "winner": None, "names": names,
                "message": "No candidates are standing in this election."}
    if not total:
        return {"total": 0, "rounds": [], "winner": None, "names": names,
                "message": "No ranked ballots have been cast yet."}

    first_prefs = Counter(b[0] for b in ballots if b)
    remaining = set(names)
    rounds = []
    winner = None
    while remaining:
        counts = Counter({c: 0 for c in remaining})
        for b in ballots:
            for c in b:
                if c in remaining:
                    counts[c] += 1
                    break
        live = sum(counts.values())
        exhausted = total - live
        leader, top = max(counts.items(), key=lambda kv: (kv[1], first_prefs[kv[0]], -kv[0]))
        rnd = {"counts": dict(counts), "live": live, "exhausted": exhausted, "eliminated": None}
        rounds.append(rnd)
        if live and top * 2 > live or len(remaining) == 1:
            winner = leader if live else None
            break
        loser = min(counts.items(), key=lambda kv: (kv[1], first_prefs[kv[0]], -kv[0]))[0]
        rnd["eliminated"] = loser
        remaining.discard(loser)
    return {"total": total, "rounds": rounds, "winner": winner, "names": names, "message": None}


def tally_text(position: str, result: dict) -> str:
    """Round-by-round text for the results tab."""
    if result.get("message"):
        return f"RANKED CHOICE VOTING RESULTS\n{position}\n\n{result['message']}\n"
    names = result["names"]
    lines = ["RANKED CHOICE VOTING RESULTS", position, ""]
    for i, rnd in enumerate(result["rounds"], 1):
        lines.append(f"ROUND {i}:")
        live = rnd["live"] or 1
        for cid, n in sorted(rnd["counts"].items(), key=lambda kv: -kv[1]):
            bar = "█" * int(n / live * 30)
            lines.append(f"  {names.get(cid, cid):<24}{n:>6} votes ({n / live * 100:5.1f}%)  {bar}")
        lines.append(f"  {'Live ballots:':<24}{rnd['live']:>6}   exhausted: {rnd['exhausted']}")
        if rnd["eliminated"] is not None:
            lines.append(f"  No majority. {names.get(rnd['eliminated'])} eliminated.")
        lines.append("")
    if result["winner"] is not None:
        lines.append(f"WINNER: {names[result['winner']]} (after {len(result['rounds'])} round(s))")
    else:
        lines.append("No winner could be determined.")
    lines.append(f"Ballots cast: {result['total']}")
    return "\n".join(lines) + "\n"


def practice_ballots(conn) -> list[dict]:
    """Elections with real candidates a voter can rehearse on (open or upcoming)."""
    out = []
    for e in elections(conn):
        if (e["status"] or "").lower() in ("closed", "completed", "cancelled", "archived"):
            continue
        cands = candidates(conn, e["election_id"])
        if cands:
            out.append({**e, "candidate_list": cands})
    return out


__all__ = [
    "SIMPLE", "RANKED", "APPROVAL", "SCORE", "METHOD_LABELS", "METHOD_SUPPORT",
    "method_from_label", "ensure_schema", "union_default", "election_config",
    "save_election_config", "elections", "eligible_voters", "method_statistics",
    "candidates", "is_voting_open", "ranked_elections_open_to", "has_voted",
    "cast_ranked", "tally_ranked", "tally_text", "practice_ballots",
]
