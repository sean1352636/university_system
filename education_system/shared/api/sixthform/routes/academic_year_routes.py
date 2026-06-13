"""REST API for Sixth Form Academic Year.

Covers suggestion items 25-31:

* GET  /api/sixthform/academic-year/current
* GET  /api/sixthform/academic-year/<id>/summary
* GET  /api/sixthform/academic-year/lookup?date=YYYY-MM-DD&year_id=N
* POST /api/sixthform/academic-year/import       (JSON body)
* POST /api/sixthform/academic-year/webhooks/subscribe
* GET  /api/sixthform/academic-year/<id>/calendar.ics
* GET  /api/sixthform/academic-year/                     (list)

All read endpoints emit an ETag derived from row counts + latest
``updated_at`` so clients can cache cheaply. Year data changes rarely
so even a 30-second Cache-Control window cuts most repeat reads.

Auth: most endpoints require a valid token; the .ics calendar feed
is allowed without auth (so users can subscribe in Outlook/Google)
but is gated by an opaque ``token`` query-string.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
from typing import Any
from flask import Blueprint, Response, abort, g, jsonify, request

from education_system.sixthform_system.modules.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.sixthform_system.modules.domain.academics.academic_year.academic_year import (
    BREAK_TYPES,
    DEFAULT_BREAK_TYPE,
    ValidationError,
)

logger = logging.getLogger(__name__)

academic_year_bp = Blueprint(
    "sf_academic_year", __name__,
    url_prefix="/api/sixthform/academic-year")


# ── Optional auth shim ────────────────────────────────────────────
#
# The university API uses ``@token_required`` from
# ``shared.api.university.auth``. To stay decoupled from that module,
# we accept either:
#   * a JWT in Authorization: Bearer (validated by ``token_required``
#     if available), or
#   * a header ``X-Sixthform-Token`` matching the env var
#     ``SIXTHFORM_API_TOKEN`` (handy for headless clients / cron).
#
# If neither is set the request is rejected.

def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        # Lightweight fallback when university auth isn't on the path.
        import functools

        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


# ── Helpers ───────────────────────────────────────────────────────

def _etag(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _cache_headers(resp: Response, *, etag: str,
                    seconds: int = 30) -> Response:
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = f"private, max-age={seconds}"
    return resp


def _maybe_304(etag: str) -> Response | None:
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304)
    return None


def _year_etag_inputs(year_id: int) -> list[str]:
    """Cheap fingerprint: year row + count of terms/breaks + max
    updated_at across them. Avoids serialising the whole payload."""
    parts: list[str] = [str(year_id)]
    y = data.get_year(year_id)
    if y is None:
        return ["missing", str(year_id)]
    parts.append(y.updated_at or "")
    terms = data.list_terms(year_id=year_id)
    parts.append(str(len(terms)))
    parts.append(max((t.updated_at or "" for t in terms), default=""))
    breaks = data.list_breaks(year_id=year_id)
    parts.append(str(len(breaks)))
    parts.append(max((b.updated_at or "" for b in breaks), default=""))
    return parts


def _year_dict(y) -> dict:
    return {
        "year_id": y.year_id, "name": y.name,
        "start_date": y.start_date, "end_date": y.end_date,
        "is_current": y.is_current, "status": y.status,
        "campus_id": y.campus_id,
        "approved_at": y.approved_at, "approved_by": y.approved_by,
        "day_count": y.day_count,
    }


def _term_dict(t) -> dict:
    return {
        "term_id": t.term_id, "year_id": t.year_id,
        "name": t.name, "kind": t.kind,
        "start_date": t.start_date, "end_date": t.end_date,
        "day_count": t.day_count,
    }


def _break_dict(b) -> dict:
    return {
        "break_id": b.break_id, "year_id": b.year_id,
        "name": b.name, "type": b.type, "am_pm": b.am_pm,
        "start_date": b.start_date, "end_date": b.end_date,
        "day_count": b.day_count,
    }


# ── List + current ────────────────────────────────────────────────

@academic_year_bp.route("/", methods=["GET"])
@_token_required
def list_years_route():
    status = request.args.get("status")
    campus = request.args.get("campus_id")
    try:
        rows = data.list_years(status=status, campus_id=campus)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    payload = {"years": [_year_dict(y) for y in rows],
                 "count": len(rows)}
    etag = _etag([str(len(rows)),
                    max((y.updated_at or "" for y in rows), default="")])
    not_mod = _maybe_304(etag)
    if not_mod:
        return not_mod
    return _cache_headers(jsonify(payload), etag=etag)


@academic_year_bp.route("/current", methods=["GET"])
@_token_required
def current_year_route():
    campus = request.args.get("campus_id")
    y = data.current_year(campus_id=campus)
    if y is None:
        return jsonify({"current": None}), 200
    today = _dt.date.today().isoformat()
    payload = {
        "current": _year_dict(y),
        "today": today,
        "today_status": _lookup_status(y.year_id, today),
    }
    etag = _etag(_year_etag_inputs(y.year_id) + [today])
    not_mod = _maybe_304(etag)
    if not_mod:
        return not_mod
    return _cache_headers(jsonify(payload), etag=etag)


# ── Summary ──────────────────────────────────────────────────────

@academic_year_bp.route("/<int:year_id>/summary", methods=["GET"])
@_token_required
def year_summary_route(year_id: int):
    try:
        s = data.year_summary(year_id)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 404
    payload = {
        "year": _year_dict(s.year),
        "teaching_days":     s.teaching_days,
        "non_teaching_days": s.non_teaching_days,
        "weekend_days":      s.weekend_days,
        "terms":  [_term_dict(t) for t in s.terms],
        "breaks": [_break_dict(b) for b in s.breaks],
    }
    etag = _etag(_year_etag_inputs(year_id))
    not_mod = _maybe_304(etag)
    if not_mod:
        return not_mod
    return _cache_headers(jsonify(payload), etag=etag)


# ── Lookup ───────────────────────────────────────────────────────

def _lookup_status(year_id: int, date_iso: str) -> dict:
    try:
        d = _dt.date.fromisoformat(date_iso)
    except ValueError as e:
        return {"error": str(e)}
    try:
        term = data.find_term_on(year_id, date_iso)
        brk = data.is_break(year_id, date_iso)
    except ValidationError as e:
        return {"error": str(e)}
    if brk is not None:
        kind = f"break:{brk.type}"
    elif d.weekday() >= 5:
        kind = "weekend"
    elif term is not None:
        kind = "teaching"
    else:
        kind = "outside-year"
    return {
        "date": date_iso,
        "weekday": d.strftime("%A"),
        "kind": kind,
        "term": term.name if term else None,
        "break": {"name": brk.name, "type": brk.type} if brk else None,
    }


@academic_year_bp.route("/lookup", methods=["GET"])
@_token_required
def lookup_route():
    date_iso = (request.args.get("date")
                  or _dt.date.today().isoformat())
    yid_arg = request.args.get("year_id")
    if yid_arg:
        try:
            yid = int(yid_arg)
        except ValueError:
            return jsonify({"error": "year_id must be int"}), 400
    else:
        cur = data.current_year()
        if cur is None:
            return jsonify({"error": "No current year"}), 404
        yid = cur.year_id
    return jsonify(_lookup_status(yid, date_iso))


# ── Import ───────────────────────────────────────────────────────

@academic_year_bp.route("/import", methods=["POST"])
@_token_required
def import_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "year" not in payload:
        return jsonify({"error": "expected {year, terms, breaks}"}), 400
    yp = payload["year"]
    name = yp.get("name", "Imported Year")
    if data.get_year_by_name(name):
        i = 2
        while data.get_year_by_name(f"{name} ({i})"):
            i += 1
        name = f"{name} ({i})"
    actor = g.current_user.get("sub") if hasattr(g, "current_user") else None
    data.CURRENT_ACTOR = actor or "import-api"
    try:
        new_year = data.create_year({
            "name": name,
            "start_date": yp.get("start_date"),
            "end_date": yp.get("end_date"),
            "status": "Planning",
            "is_current": False,
            "notes": yp.get("notes"),
            "campus_id": yp.get("campus_id"),
        })
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    errs: list[str] = []
    for t in payload.get("terms", []):
        try:
            data.create_term({
                "year_id": new_year.year_id,
                "name": t.get("name"),
                "kind": t.get("kind"),
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
                "notes": t.get("notes"),
            })
        except ValidationError as e:
            errs.append(f"term {t.get('name')!r}: {e}")
    for b in payload.get("breaks", []):
        try:
            data.create_break({
                "year_id": new_year.year_id,
                "name": b.get("name"),
                "type": b.get("type", DEFAULT_BREAK_TYPE),
                "am_pm": b.get("am_pm"),
                "start_date": b.get("start_date"),
                "end_date": b.get("end_date"),
                "notes": b.get("notes"),
            })
        except ValidationError as e:
            errs.append(f"break {b.get('name')!r}: {e}")
    data.CURRENT_ACTOR = None
    return jsonify({
        "year_id": new_year.year_id,
        "name": new_year.name,
        "errors": errs,
    }), 201


# ── Webhooks ─────────────────────────────────────────────────────
#
# Minimal in-memory subscription store. A real deployment would
# persist this and run a background dispatcher; for now we record the
# intent and expose a fire helper that other code can call.

_WEBHOOKS: dict[str, list[str]] = {
    "year.current_changed": [],
    "year.status_changed":  [],
}


@academic_year_bp.route("/webhooks/subscribe", methods=["POST"])
@_token_required
def subscribe_route():
    body = request.get_json(silent=True) or {}
    event = body.get("event")
    url = body.get("url")
    if event not in _WEBHOOKS or not url:
        return jsonify({
            "error": "event must be one of "
                       f"{sorted(_WEBHOOKS.keys())} and url is required"
        }), 400
    if url not in _WEBHOOKS[event]:
        _WEBHOOKS[event].append(url)
    return jsonify({"subscribed": event, "subscribers": len(_WEBHOOKS[event])}), 201


@academic_year_bp.route("/webhooks", methods=["GET"])
@_token_required
def list_webhooks_route():
    return jsonify({k: list(v) for k, v in _WEBHOOKS.items()})


def fire_webhook(event: str, payload: dict[str, Any]) -> None:
    """Synchronous fire — for tests, mostly. Real deployment swaps this
    for a queued sender."""
    import urllib.request
    for url in list(_WEBHOOKS.get(event, [])):
        body = json.dumps({"event": event, "data": payload}).encode()
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:
            logger.warning("Webhook %s -> %s failed: %s",
                            event, url, e)


# ── ICS feed (unauth, token-gated) ───────────────────────────────

def _build_ics(year_id: int) -> str:
    summ = data.year_summary(year_id)
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SixthForm//AcademicYear//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{summ.year.name} Academic Year",
    ]
    for t in summ.terms:
        try:
            s = _dt.date.fromisoformat(t.start_date)
            e = (_dt.date.fromisoformat(t.end_date)
                   + _dt.timedelta(days=1))
        except ValueError:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:term-{t.term_id}-y{year_id}@sixthform",
            f"DTSTAMP:{stamp}",
            f"SUMMARY:{t.name} ({summ.year.name})",
            f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
            "END:VEVENT",
        ]
    for b in summ.breaks:
        try:
            s = _dt.date.fromisoformat(b.start_date)
            e = (_dt.date.fromisoformat(b.end_date)
                   + _dt.timedelta(days=1))
        except ValueError:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:break-{b.break_id}-y{year_id}@sixthform",
            f"DTSTAMP:{stamp}",
            f"SUMMARY:{b.name} ({b.type})",
            f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


@academic_year_bp.route("/<int:year_id>/calendar.ics", methods=["GET"])
def calendar_ics_route(year_id: int):
    expected = os.environ.get("SIXTHFORM_ICS_TOKEN")
    if expected:
        if request.args.get("token") != expected:
            return abort(401)
    try:
        body = _build_ics(year_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    etag = _etag(_year_etag_inputs(year_id) + ["ics"])
    not_mod = _maybe_304(etag)
    if not_mod:
        return not_mod
    resp = Response(body, mimetype="text/calendar; charset=utf-8")
    return _cache_headers(resp, etag=etag, seconds=300)
