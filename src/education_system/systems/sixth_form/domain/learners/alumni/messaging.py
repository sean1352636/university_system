"""Sixth-form alumni — Comms extensions (#20-#26): templates, drips, A/B tests, SMS (owns ``_sms_sender``), postal merge, newsletters, tracking.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import secrets
from dataclasses import dataclass
from typing import Any
from typing import Callable
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    DRIP_STATUSES,
    TRACK_KINDS,
    _log_action,
    logger,
)
from .db import (
    IntegrationError,
    NotFoundError,
    ValidationError,
    _connect,
    init_db,
)


# ── #20 Email templates library ──────────────────────────────────

@dataclass
class EmailTemplate:
    template_id: int
    name: str
    version: int
    subject: str
    body: str
    category: str | None
    created_at: str


def _row_template(r: db.Row) -> EmailTemplate:
    return EmailTemplate(
        template_id=r["template_id"], name=r["name"],
        version=int(r["version"]),
        subject=r["subject"], body=r["body"],
        category=r["category"], created_at=r["created_at"])


def create_email_template(name: str, subject: str, body: str, *,
                             category: str | None = None,
                             actor: str | None = None
                             ) -> EmailTemplate:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Template name is required")
    if not (subject or "").strip():
        raise ValidationError("Subject is required")
    if not (body or "").strip():
        raise ValidationError("Body is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT MAX(version) AS v FROM alumni_email_templates "
            "WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        next_v = int(r["v"] or 0) + 1
        cur = conn.execute(
            """INSERT INTO alumni_email_templates
                   (name, version, subject, body, category)
               VALUES (?, ?, ?, ?, ?)""",
            (name, next_v, subject.strip(), body,
             (category or "").strip() or None))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_email_templates "
            "WHERE template_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("template.create", actor=actor, name=name,
                  version=next_v)
    return _row_template(row)


def list_email_templates(*, category: str | None = None,
                              latest_only: bool = True
                              ) -> list[EmailTemplate]:
    init_db()
    if latest_only:
        sql = ("""SELECT t.* FROM alumni_email_templates t
                    JOIN (SELECT name, MAX(version) AS v
                           FROM alumni_email_templates
                           GROUP BY name) m
                      ON m.name = t.name AND m.v = t.version""")
        params: list[Any] = []
        if category:
            sql += " WHERE t.category = ?"; params.append(category)
        sql += " ORDER BY t.name COLLATE NOCASE"
    else:
        sql = "SELECT * FROM alumni_email_templates"
        params = []
        if category:
            sql += " WHERE category = ?"; params.append(category)
        sql += " ORDER BY name COLLATE NOCASE, version DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_template(r) for r in rows]


def get_email_template(name: str, *,
                          version: int | None = None
                          ) -> EmailTemplate | None:
    init_db()
    with _connect() as conn:
        if version is None:
            r = conn.execute(
                "SELECT * FROM alumni_email_templates "
                "WHERE name = ? COLLATE NOCASE "
                "ORDER BY version DESC LIMIT 1",
                (name,)).fetchone()
        else:
            r = conn.execute(
                "SELECT * FROM alumni_email_templates "
                "WHERE name = ? COLLATE NOCASE AND version = ?",
                (name, version)).fetchone()
    return _row_template(r) if r else None


def delete_email_template(template_id: int, *,
                              actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_email_templates "
            "WHERE template_id = ?", (template_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("template.delete", actor=actor,
                      template_id=template_id)
    return cur.rowcount > 0


def render_template(template: EmailTemplate, alumni_id: int
                       ) -> tuple[str, str]:
    """Render a template's subject and body against ``alumni_id``,
    using the same context builder as the existing send_email helpers
    (so merge fields stay consistent)."""
    init_db()
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    ctx = _alumnus_context(a)
    return _render(template.subject, ctx), _render(template.body, ctx)


# ── #21 Drip campaigns ───────────────────────────────────────────

@dataclass
class DripCampaign:
    drip_id: int
    name: str
    description: str | None
    status: str
    created_at: str


@dataclass
class DripStep:
    step_id: int
    drip_id: int
    position: int
    delay_days: int
    template_id: int | None
    subject: str | None
    body: str | None


@dataclass
class DripEnrollment:
    enrollment_id: int
    drip_id: int
    alumni_id: int
    enrolled_at: str
    next_send_at: str | None
    current_step: int
    status: str


def _row_drip(r: db.Row) -> DripCampaign:
    return DripCampaign(
        drip_id=r["drip_id"], name=r["name"],
        description=r["description"], status=r["status"],
        created_at=r["created_at"])


def _row_drip_step(r: db.Row) -> DripStep:
    return DripStep(
        step_id=r["step_id"], drip_id=r["drip_id"],
        position=int(r["position"]),
        delay_days=int(r["delay_days"]),
        template_id=r["template_id"], subject=r["subject"],
        body=r["body"])


def _row_enrollment(r: db.Row) -> DripEnrollment:
    return DripEnrollment(
        enrollment_id=r["enrollment_id"], drip_id=r["drip_id"],
        alumni_id=r["alumni_id"],
        enrolled_at=r["enrolled_at"],
        next_send_at=r["next_send_at"],
        current_step=int(r["current_step"]),
        status=r["status"])


def create_drip_campaign(name: str, *,
                            description: str | None = None,
                            actor: str | None = None) -> DripCampaign:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Drip campaign name is required")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_drip_campaigns
                       (name, description) VALUES (?, ?)""",
                (name, (description or "").strip() or None))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"A drip campaign named {name!r} already exists"
            ) from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_drip_campaigns WHERE drip_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("drip.create", actor=actor, name=name)
    return _row_drip(r)


def add_drip_step(drip_id: int, *,
                     position: int, delay_days: int,
                     template_id: int | None = None,
                     subject: str | None = None,
                     body: str | None = None,
                     actor: str | None = None) -> DripStep:
    init_db()
    if position < 1:
        raise ValidationError("Position must be ≥ 1")
    if delay_days < 0:
        raise ValidationError("delay_days must be ≥ 0")
    if not template_id and not ((subject or "").strip()
                                  and (body or "").strip()):
        raise ValidationError(
            "Provide either a template_id or both subject + body")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_drip_campaigns WHERE drip_id = ?",
            (drip_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No drip #{drip_id}")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_drip_steps
                       (drip_id, position, delay_days, template_id,
                        subject, body)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (drip_id, position, delay_days, template_id,
                 (subject or "").strip() or None,
                 (body or "").strip() or None))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"Position {position} already exists in drip "
                f"#{drip_id}") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_drip_steps WHERE step_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("drip.step.add", actor=actor, drip_id=drip_id,
                  position=position)
    return _row_drip_step(row)


def list_drip_campaigns() -> list[DripCampaign]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_drip_campaigns "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_drip(r) for r in rows]


def list_drip_steps(drip_id: int) -> list[DripStep]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_drip_steps "
            "WHERE drip_id = ? ORDER BY position",
            (drip_id,)).fetchall()
    return [_row_drip_step(r) for r in rows]


def set_drip_status(drip_id: int, status: str, *,
                       actor: str | None = None) -> DripCampaign:
    init_db()
    if status not in DRIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(DRIP_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_drip_campaigns SET status = ? "
            "WHERE drip_id = ?", (status, drip_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No drip #{drip_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_drip_campaigns WHERE drip_id = ?",
            (drip_id,)).fetchone()
    _log_action("drip.status", actor=actor, drip_id=drip_id,
                  status=status)
    return _row_drip(r)


def enroll_in_drip(drip_id: int, alumni_id: int, *,
                       actor: str | None = None) -> DripEnrollment:
    init_db()
    with _connect() as conn:
        d = conn.execute(
            "SELECT status FROM alumni_drip_campaigns "
            "WHERE drip_id = ?", (drip_id,)).fetchone()
        if d is None:
            raise ValidationError(f"No drip #{drip_id}")
        _require_alumnus(conn, alumni_id)
        first_step = conn.execute(
            "SELECT delay_days FROM alumni_drip_steps "
            "WHERE drip_id = ? ORDER BY position LIMIT 1",
            (drip_id,)).fetchone()
        next_at = None
        if first_step is not None:
            when = _dt.date.today() + _dt.timedelta(
                days=int(first_step["delay_days"]))
            next_at = when.isoformat()
        try:
            cur = conn.execute(
                """INSERT INTO alumni_drip_enrollments
                       (drip_id, alumni_id, next_send_at)
                   VALUES (?, ?, ?)""",
                (drip_id, alumni_id, next_at))
        except db.IntegrityError as exc:
            raise ValidationError(
                "Already enrolled in this drip") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_drip_enrollments "
            "WHERE enrollment_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("drip.enroll", actor=actor,
                  drip_id=drip_id, alumni_id=alumni_id)
    return _row_enrollment(row)


def unsubscribe_from_drip(drip_id: int, alumni_id: int, *,
                              actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_drip_enrollments SET status = 'Unsubscribed' "
            "WHERE drip_id = ? AND alumni_id = ?",
            (drip_id, alumni_id))
        conn.commit()
    if cur.rowcount:
        _log_action("drip.unsubscribe", actor=actor,
                      drip_id=drip_id, alumni_id=alumni_id)
    return cur.rowcount > 0


@dataclass
class DripTick:
    enrollment_id: int
    alumni_id: int
    step_id: int
    subject: str
    body: str


def _send_drip_email(alumni_id: int, subject: str, body: str) -> None:
    """Default drip sender: through the outbox (respects opt-in and the
    delivery mode). Raises when the e-mail cannot be handed over, so
    the enrolment stays on this step and is tried again next tick."""
    from .comms import send_email_to_alumnus
    out = send_email_to_alumnus(alumni_id, subject, body)
    if out.status == "Failed":
        raise ValidationError(f"E-mail to alumnus #{alumni_id} failed")


def tick_drip(*, today: _dt.date | None = None,
                 send: Callable[[int, str, str], None] | None = None
                 ) -> list[DripTick]:
    """Iterate every Active enrollment whose ``next_send_at`` is
    today or earlier, send its current step, advance it by one step
    and schedule the next send. Returns the list of ticks dispatched.

    ``send(alumni_id, subject, body)`` delivers a step; by default the
    e-mail goes through the sixth form outbox, so it obeys the platform
    delivery mode (nothing leaves unless that mode is live). A step
    whose send raises is not advanced and is retried on the next tick;
    an alumnus who has opted out or has no e-mail address is
    unsubscribed from the campaign rather than retried for ever."""
    init_db()
    if send is None:
        send = _send_drip_email
    today = today or _dt.date.today()
    out: list[DripTick] = []
    with _connect() as conn:
        rows = conn.execute(
            """SELECT e.* FROM alumni_drip_enrollments e
                 JOIN alumni_drip_campaigns d ON d.drip_id = e.drip_id
                WHERE e.status = 'Active'
                  AND d.status = 'Active'
                  AND e.next_send_at IS NOT NULL
                  AND e.next_send_at <= ?""",
            (today.isoformat(),)).fetchall()
    for r in rows:
        e = _row_enrollment(r)
        steps = list_drip_steps(e.drip_id)
        # current_step is 0-based: the next step to send.
        if e.current_step >= len(steps):
            with _connect() as conn:
                conn.execute(
                    "UPDATE alumni_drip_enrollments "
                    "SET status = 'Completed', next_send_at = NULL "
                    "WHERE enrollment_id = ?", (e.enrollment_id,))
                conn.commit()
            continue
        step = steps[e.current_step]
        subject, body = _resolve_drip_step_content(step, e.alumni_id)
        try:
            send(e.alumni_id, subject, body)
        except ValidationError as exc:
            text = str(exc)
            if "opted out" in text or "no primary email" in text.lower():
                with _connect() as conn:
                    conn.execute(
                        "UPDATE alumni_drip_enrollments SET status = "
                        "'Unsubscribed', next_send_at = NULL "
                        "WHERE enrollment_id = ?", (e.enrollment_id,))
                    conn.commit()
                logger.info("Drip enrolment #%d stopped: %s",
                            e.enrollment_id, text)
            else:
                logger.warning("drip send failed alumni=%s step=%s: %s",
                               e.alumni_id, step.step_id, text)
            continue
        except Exception:
            logger.exception("drip send failed alumni=%s step=%s",
                               e.alumni_id, step.step_id)
            continue
        out.append(DripTick(
            enrollment_id=e.enrollment_id, alumni_id=e.alumni_id,
            step_id=step.step_id, subject=subject, body=body))
        new_step_idx = e.current_step + 1
        if new_step_idx < len(steps):
            nxt_when = today + _dt.timedelta(
                days=int(steps[new_step_idx].delay_days))
            next_at = nxt_when.isoformat()
            new_status = "Active"
        else:
            next_at = None
            new_status = "Completed"
        with _connect() as conn:
            conn.execute(
                "UPDATE alumni_drip_enrollments "
                "SET current_step = ?, next_send_at = ?, status = ? "
                "WHERE enrollment_id = ?",
                (new_step_idx, next_at, new_status, e.enrollment_id))
            conn.commit()
    return out


def _resolve_drip_step_content(step: DripStep, alumni_id: int
                                    ) -> tuple[str, str]:
    if step.template_id:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM alumni_email_templates "
                "WHERE template_id = ?", (step.template_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"Drip step #{step.step_id} references missing "
                f"template #{step.template_id}")
        return render_template(_row_template(r), alumni_id)
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    ctx = _alumnus_context(a)
    return (_render(step.subject or "", ctx),
              _render(step.body or "", ctx))


# ── #22 A/B test send ────────────────────────────────────────────

@dataclass
class ABTest:
    test_id: int
    name: str
    description: str | None
    filters_json: str | None
    sent_at: str | None
    created_at: str


@dataclass
class ABVariant:
    variant_id: int
    test_id: int
    label: str
    subject: str
    body: str
    sent_count: int
    open_count: int
    click_count: int


def _row_ab_test(r: db.Row) -> ABTest:
    return ABTest(
        test_id=r["test_id"], name=r["name"],
        description=r["description"],
        filters_json=r["filters_json"],
        sent_at=r["sent_at"], created_at=r["created_at"])


def _row_ab_variant(r: db.Row) -> ABVariant:
    return ABVariant(
        variant_id=r["variant_id"], test_id=r["test_id"],
        label=r["label"], subject=r["subject"], body=r["body"],
        sent_count=int(r["sent_count"]),
        open_count=int(r["open_count"]),
        click_count=int(r["click_count"]))


def create_ab_test(name: str, *,
                      description: str | None = None,
                      filters: dict[str, Any] | None = None,
                      actor: str | None = None) -> ABTest:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("A/B test name is required")
    import json as _json
    fjson = _json.dumps(filters) if filters else None
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_ab_tests
                       (name, description, filters_json)
                   VALUES (?, ?, ?)""",
                (name, (description or "").strip() or None, fjson))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"A/B test {name!r} already exists") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_ab_tests WHERE test_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("ab.create", actor=actor, name=name)
    return _row_ab_test(r)


def add_ab_variant(test_id: int, *,
                       label: str, subject: str, body: str,
                       actor: str | None = None) -> ABVariant:
    init_db()
    label = (label or "").strip()
    if not label:
        raise ValidationError("Variant label is required")
    if not (subject or "").strip():
        raise ValidationError("Subject is required")
    if not (body or "").strip():
        raise ValidationError("Body is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_ab_tests WHERE test_id = ?",
            (test_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No A/B test #{test_id}")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_ab_variants
                       (test_id, label, subject, body)
                   VALUES (?, ?, ?, ?)""",
                (test_id, label, subject.strip(), body))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"Variant {label!r} already exists for this test"
            ) from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_ab_variants WHERE variant_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("ab.variant", actor=actor, test_id=test_id,
                  label=label)
    return _row_ab_variant(row)


def list_ab_variants(test_id: int) -> list[ABVariant]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_ab_variants WHERE test_id = ? "
            "ORDER BY variant_id", (test_id,)).fetchall()
    return [_row_ab_variant(r) for r in rows]


def assign_ab_audience(test_id: int, *,
                          filters: dict[str, Any] | None = None,
                          actor: str | None = None) -> dict[str, int]:
    """Stably hash each candidate alumnus to a variant. Returns the
    per-variant assignment counts."""
    init_db()
    import hashlib as _h
    variants = list_ab_variants(test_id)
    if not variants:
        raise ValidationError(
            f"A/B test #{test_id} has no variants")
    try:
        audience = list_alumni(**(filters or {}))
    except TypeError as exc:
        raise ValidationError(
            f"Invalid filter for A/B audience: {exc}") from exc
    counts: dict[str, int] = {v.label: 0 for v in variants}
    with _connect() as conn:
        for a in audience:
            h = int(_h.md5(
                f"{test_id}:{a.alumni_id}".encode()).hexdigest(), 16)
            v = variants[h % len(variants)]
            conn.execute(
                """INSERT OR REPLACE INTO alumni_ab_assignments
                       (test_id, alumni_id, variant_id)
                   VALUES (?, ?, ?)""",
                (test_id, a.alumni_id, v.variant_id))
            counts[v.label] += 1
        conn.commit()
    _log_action("ab.assign", actor=actor, test_id=test_id,
                  audience=len(audience))
    return counts


def record_ab_event(test_id: int, alumni_id: int, kind: str, *,
                       actor: str | None = None) -> None:
    """Bump send/open/click counters on the variant the alumnus is
    assigned to. ``kind`` must be 'send' | 'open' | 'click'."""
    init_db()
    if kind not in ("send", "open", "click"):
        raise ValidationError(
            "Kind must be 'send', 'open', or 'click'")
    col = {"send": "sent_count", "open": "open_count",
            "click": "click_count"}[kind]
    with _connect() as conn:
        r = conn.execute(
            "SELECT variant_id FROM alumni_ab_assignments "
            "WHERE test_id = ? AND alumni_id = ?",
            (test_id, alumni_id)).fetchone()
        if r is None:
            return
        conn.execute(
            f"UPDATE alumni_ab_variants SET {col} = {col} + 1 "
            f"WHERE variant_id = ?", (r["variant_id"],))
        conn.commit()
    _log_action(f"ab.{kind}", actor=actor, test_id=test_id,
                  alumni_id=alumni_id)


@dataclass
class ABResult:
    label: str
    sent: int
    opens: int
    clicks: int
    open_rate: float
    click_rate: float


def ab_test_results(test_id: int) -> list[ABResult]:
    init_db()
    out: list[ABResult] = []
    for v in list_ab_variants(test_id):
        opens = v.open_count
        clicks = v.click_count
        sent = max(v.sent_count, 1)
        out.append(ABResult(
            label=v.label, sent=v.sent_count,
            opens=opens, clicks=clicks,
            open_rate=round(100 * opens / sent, 2),
            click_rate=round(100 * clicks / sent, 2)))
    return out


# ── #23 SMS channel ──────────────────────────────────────────────

@dataclass
class SMSMessage:
    sms_id: int
    alumni_id: int
    body: str
    sent_at: str
    status: str
    error: str | None


def _row_sms(r: db.Row) -> SMSMessage:
    return SMSMessage(
        sms_id=r["sms_id"], alumni_id=r["alumni_id"],
        body=r["body"], sent_at=r["sent_at"],
        status=r["status"], error=r["error"])


# Pluggable SMS sender (tests / a direct gateway). With none installed
# the text goes through the sixth form outbox (messages.delivery), which
# uses the configured SMS provider and the platform delivery mode — and
# says "Queued (no SMS provider configured)" rather than "Sent" when
# there is no provider.
_sms_sender: Callable[[str, str], None] | None = None


def set_sms_sender(fn: Callable[[str, str], None] | None) -> None:
    """Install a callable ``fn(phone, body)`` invoked from
    :func:`send_sms_to_alumnus`. Pass ``None`` to clear and go back to
    the outbox."""
    global _sms_sender
    _sms_sender = fn


def send_sms_to_alumnus(alumni_id: int, body: str, *,
                           actor: str | None = None) -> SMSMessage:
    init_db()
    if not (body or "").strip():
        raise ValidationError("SMS body is required")
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    prefs = get_channel_prefs(alumni_id)
    if not prefs.opt_in_sms:
        raise ValidationError(
            "Alumnus has not opted-in to SMS")
    phone = a.phone or ""
    if not phone:
        raise ValidationError("No phone on file")
    status = "Sent"
    error: str | None = None
    if _sms_sender is not None:
        try:
            _sms_sender(phone, body)
        except Exception as exc:
            status = "Failed"
            error = str(exc)[:240]
    else:
        status, error = _sms_via_outbox(a, phone, body.strip(), actor)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_sms_messages
                   (alumni_id, body, status, error)
               VALUES (?, ?, ?, ?)""",
            (alumni_id, body.strip(), status, error))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_sms_messages WHERE sms_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("sms.send", actor=actor, alumni_id=alumni_id,
                  status=status)
    return _row_sms(r)


def _sms_via_outbox(a, phone: str, body: str,
                    actor: str | None) -> tuple[str, str | None]:
    """Hand an alumni text to the sixth form outbox. Returns
    ``(status, note)``: ``Sent`` only when the provider accepted it,
    ``Queued`` while it waits (no provider, held by the delivery mode,
    retrying), ``Failed`` otherwise."""
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    try:
        m = _msg.create_message({
            "direction": "Outgoing", "channel": "SMS", "category": "General",
            "status": "Queued", "subject": "SMS", "body": body,
            "alumni_id": a.alumni_id, "to_name": a.full_name,
            "to_address": phone,
            "notes": f"Sent by {actor}" if actor else None,
        })
        m = _msg.send_message(m.message_id)
    except Exception as exc:  # noqa: BLE001 - recorded on the SMS row
        return "Failed", str(exc)[:240]
    d = _msg.delivery_status(m.message_id)
    note = (d.detail or d.last_error) if d else None
    if m.status in _msg.SENT_STATUSES:
        return "Sent", None
    if m.status == "Failed":
        return "Failed", (note or "not delivered")[:240]
    return "Queued", (note or "waiting in the outbox")[:240]


def list_sms_for(alumni_id: int) -> list[SMSMessage]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_sms_messages "
            "WHERE alumni_id = ? ORDER BY sent_at DESC",
            (alumni_id,)).fetchall()
    return [_row_sms(r) for r in rows]


# ── #24 Postal mail merge ────────────────────────────────────────

@dataclass
class PostalLetter:
    letter_id: int
    alumni_id: int
    subject: str
    body: str
    pdf_path: str | None
    generated_at: str


def _row_letter(r: db.Row) -> PostalLetter:
    return PostalLetter(
        letter_id=r["letter_id"], alumni_id=r["alumni_id"],
        subject=r["subject"], body=r["body"],
        pdf_path=r["pdf_path"], generated_at=r["generated_at"])


def generate_postal_letter(alumni_id: int, *,
                              subject: str, body: str,
                              out_dir: str | None = None,
                              actor: str | None = None
                              ) -> PostalLetter:
    """Render a letter against ``alumni_id``, persist its text + a
    plain ``.txt`` artefact in ``out_dir`` (or current dir), and
    return the row. We deliberately don't depend on a PDF library:
    consumers that want PDF can post-process the saved ``.txt``."""
    init_db()
    from pathlib import Path as _Path
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    if not a.address:
        raise ValidationError(
            f"No postal address on file for #{alumni_id}")
    ctx = _alumnus_context(a)
    s = _render(subject, ctx)
    b = _render(body, ctx)
    out_path: str | None = None
    if out_dir:
        d = _Path(out_dir)
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / (
                f"letter-{alumni_id}-"
                f"{int(_dt.datetime.now().timestamp())}.txt")
            p.write_text(
                f"To:\n{a.full_name}\n{a.address}\n\n"
                f"Subject: {s}\n\n{b}\n",
                encoding="utf-8")
        except OSError as exc:
            raise IntegrationError(
                f"Could not write letter to {d}: {exc}") from exc
        out_path = str(p)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_postal_letters
                   (alumni_id, subject, body, pdf_path)
               VALUES (?, ?, ?, ?)""",
            (alumni_id, s, b, out_path))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_postal_letters WHERE letter_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("postal.generate", actor=actor,
                  alumni_id=alumni_id, path=out_path)
    return _row_letter(row)


def generate_postal_bulk(filters: dict[str, Any], *,
                            subject: str, body: str,
                            out_dir: str,
                            actor: str | None = None
                            ) -> list[PostalLetter]:
    """Mail-merge bulk-render letters for everyone matching
    ``filters`` who also has a postal address."""
    init_db()
    out: list[PostalLetter] = []
    try:
        audience = list_alumni(**filters)
    except TypeError as exc:
        raise ValidationError(
            f"Invalid filter for bulk postal: {exc}") from exc
    for a in audience:
        if not a.address:
            continue
        try:
            out.append(generate_postal_letter(
                a.alumni_id, subject=subject, body=body,
                out_dir=out_dir, actor=actor))
        except ValidationError:
            continue
    _log_action("postal.bulk", actor=actor,
                  count=len(out), out_dir=out_dir)
    return out


# ── #25 Newsletter issues ────────────────────────────────────────

@dataclass
class Newsletter:
    newsletter_id: int
    issue: str
    title: str
    status: str
    published_at: str | None
    distribution_filters_json: str | None
    created_at: str


@dataclass
class NewsletterSection:
    section_id: int
    newsletter_id: int
    position: int
    heading: str
    body: str


def _row_newsletter(r: db.Row) -> Newsletter:
    return Newsletter(
        newsletter_id=r["newsletter_id"], issue=r["issue"],
        title=r["title"], status=r["status"],
        published_at=r["published_at"],
        distribution_filters_json=r["distribution_filters_json"],
        created_at=r["created_at"])


def _row_section(r: db.Row) -> NewsletterSection:
    return NewsletterSection(
        section_id=r["section_id"],
        newsletter_id=r["newsletter_id"],
        position=int(r["position"]),
        heading=r["heading"], body=r["body"])


def create_newsletter(issue: str, title: str, *,
                          actor: str | None = None) -> Newsletter:
    init_db()
    issue = (issue or "").strip()
    if not issue:
        raise ValidationError("Issue label is required")
    if not (title or "").strip():
        raise ValidationError("Title is required")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_newsletters
                       (issue, title) VALUES (?, ?)""",
                (issue, title.strip()))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"Newsletter issue {issue!r} already exists"
            ) from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_newsletters "
            "WHERE newsletter_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("newsletter.create", actor=actor, issue=issue)
    return _row_newsletter(r)


def add_newsletter_section(newsletter_id: int, *,
                                heading: str, body: str,
                                position: int | None = None,
                                actor: str | None = None
                                ) -> NewsletterSection:
    init_db()
    if not (heading or "").strip():
        raise ValidationError("Heading is required")
    if not (body or "").strip():
        raise ValidationError("Body is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_newsletters WHERE newsletter_id = ?",
            (newsletter_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"No newsletter #{newsletter_id}")
        if position is None:
            r2 = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS p "
                "FROM alumni_newsletter_sections "
                "WHERE newsletter_id = ?",
                (newsletter_id,)).fetchone()
            position = int(r2["p"])
        try:
            cur = conn.execute(
                """INSERT INTO alumni_newsletter_sections
                       (newsletter_id, position, heading, body)
                   VALUES (?, ?, ?, ?)""",
                (newsletter_id, position, heading.strip(), body))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"Position {position} already used") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_newsletter_sections "
            "WHERE section_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("newsletter.section", actor=actor,
                  newsletter_id=newsletter_id, position=position)
    return _row_section(row)


def list_newsletters() -> list[Newsletter]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_newsletters "
            "ORDER BY created_at DESC").fetchall()
    return [_row_newsletter(r) for r in rows]


def list_newsletter_sections(newsletter_id: int
                                  ) -> list[NewsletterSection]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_newsletter_sections "
            "WHERE newsletter_id = ? ORDER BY position",
            (newsletter_id,)).fetchall()
    return [_row_section(r) for r in rows]


def publish_newsletter(newsletter_id: int, *,
                          distribution_filters: dict[str, Any]
                              | None = None,
                          actor: str | None = None) -> Newsletter:
    init_db()
    import json as _json
    fjson = _json.dumps(distribution_filters) \
        if distribution_filters else None
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE alumni_newsletters
                  SET status = 'Published',
                      published_at = ?,
                      distribution_filters_json = ?
                WHERE newsletter_id = ?""",
            (now, fjson, newsletter_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No newsletter #{newsletter_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_newsletters "
            "WHERE newsletter_id = ?", (newsletter_id,)).fetchone()
    _log_action("newsletter.publish", actor=actor,
                  newsletter_id=newsletter_id)
    return _row_newsletter(r)


def render_newsletter_html(newsletter_id: int) -> str:
    n = next((x for x in list_newsletters()
                if x.newsletter_id == newsletter_id), None)
    if n is None:
        raise ValidationError(
            f"No newsletter #{newsletter_id}")
    parts = [f"<h1>{n.title}</h1>",
                f"<p><em>{n.issue}</em></p>"]
    for s in list_newsletter_sections(newsletter_id):
        parts.append(f"<h2>{s.heading}</h2>")
        parts.append(f"<div>{s.body}</div>")
    return "\n".join(parts)


def newsletter_audience(newsletter_id: int) -> list[Alumnus]:
    init_db()
    import json as _json
    with _connect() as conn:
        r = conn.execute(
            "SELECT distribution_filters_json FROM alumni_newsletters "
            "WHERE newsletter_id = ?", (newsletter_id,)).fetchone()
    if r is None:
        raise NotFoundError(f"No newsletter #{newsletter_id}")
    raw = r["distribution_filters_json"]
    if not raw:
        return list_alumni()
    try:
        filters = _json.loads(raw)
    except (ValueError, TypeError) as exc:
        # Stored JSON is corrupt — log loudly and fall back to no
        # filtering rather than 500-ing the audience tab.
        logger.warning(
            "Newsletter #%d has malformed filters_json: %s",
            newsletter_id, exc)
        return list_alumni()
    if not isinstance(filters, dict):
        logger.warning(
            "Newsletter #%d filters_json is not an object: %r",
            newsletter_id, type(filters))
        return list_alumni()
    try:
        return list_alumni(**filters)
    except TypeError as exc:
        # Stored filter key no longer exists on list_alumni — surface
        # as a ValidationError so the UI can show "stale filter" to
        # the user rather than crashing.
        raise ValidationError(
            f"Newsletter #{newsletter_id} stored filters are no "
            f"longer compatible: {exc}") from exc


# ── #26 Open/click tracking ──────────────────────────────────────

def _new_track_token() -> str:
    return secrets.token_urlsafe(16)


def create_tracking_pixel(alumni_id: int | None = None, *,
                              campaign_ref: str | None = None) -> str:
    """Mint a unique pixel token. Hosts can serve a 1×1 image at
    ``/track/pixel/<token>`` and call :func:`record_track_event` with
    kind='open' on hit."""
    init_db()
    token = _new_track_token()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_track_links
                   (token, alumni_id, kind, campaign_ref)
               VALUES (?, ?, 'open', ?)""",
            (token, alumni_id,
             (campaign_ref or "").strip() or None))
        conn.commit()
    return token


def create_tracked_link(target_url: str, *,
                            alumni_id: int | None = None,
                            campaign_ref: str | None = None) -> str:
    """Mint a unique redirect token. The host should serve
    ``/track/click/<token>`` by recording a 'click' event then
    302-redirecting to ``target_url``."""
    init_db()
    if not (target_url or "").strip():
        raise ValidationError("target_url is required")
    token = _new_track_token()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_track_links
                   (token, alumni_id, kind, target_url, campaign_ref)
               VALUES (?, ?, 'click', ?, ?)""",
            (token, alumni_id, target_url.strip(),
             (campaign_ref or "").strip() or None))
        conn.commit()
    return token


def record_track_event(token: str, kind: str, *,
                          payload: str | None = None) -> None:
    init_db()
    if kind not in TRACK_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(TRACK_KINDS)}")
    with _connect() as conn:
        link = conn.execute(
            "SELECT alumni_id FROM alumni_track_links "
            "WHERE token = ?", (token,)).fetchone()
        alumni_id = link["alumni_id"] if link else None
        conn.execute(
            """INSERT INTO alumni_track_events
                   (token, alumni_id, kind, payload)
               VALUES (?, ?, ?, ?)""",
            (token, alumni_id, kind, payload))
        conn.commit()


def resolve_tracked_link(token: str) -> tuple[str, str | None]:
    """Return ``(kind, target_url)`` for a tracking token, raising
    if unknown. ``target_url`` is ``None`` for pixel tokens."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT kind, target_url FROM alumni_track_links "
            "WHERE token = ?", (token,)).fetchone()
    if r is None:
        raise ValidationError("Unknown tracking token")
    return r["kind"], r["target_url"]


@dataclass
class TrackingSummary:
    campaign_ref: str | None
    sends: int
    opens: int
    clicks: int
    unique_opens: int


def tracking_summary(*, campaign_ref: str | None = None
                          ) -> TrackingSummary:
    """Aggregate counts. ``campaign_ref`` filters to one campaign tag
    (the column on ``alumni_track_links``); ``None`` aggregates across
    every link."""
    init_db()
    with _connect() as conn:
        if campaign_ref:
            tokens_rows = conn.execute(
                "SELECT token FROM alumni_track_links "
                "WHERE campaign_ref = ?", (campaign_ref,)).fetchall()
            tokens = [r["token"] for r in tokens_rows]
            if not tokens:
                return TrackingSummary(
                    campaign_ref=campaign_ref, sends=0, opens=0,
                    clicks=0, unique_opens=0)
            placeholders = ",".join("?" * len(tokens))
            sends = int(conn.execute(
                f"SELECT COUNT(*) FROM alumni_track_events "
                f"WHERE kind = 'send' AND token IN ({placeholders})",
                tokens).fetchone()[0])
            opens = int(conn.execute(
                f"SELECT COUNT(*) FROM alumni_track_events "
                f"WHERE kind = 'open' AND token IN ({placeholders})",
                tokens).fetchone()[0])
            clicks = int(conn.execute(
                f"SELECT COUNT(*) FROM alumni_track_events "
                f"WHERE kind = 'click' AND token IN ({placeholders})",
                tokens).fetchone()[0])
            uniq = int(conn.execute(
                f"SELECT COUNT(DISTINCT alumni_id) "
                f"FROM alumni_track_events "
                f"WHERE kind = 'open' AND alumni_id IS NOT NULL "
                f"  AND token IN ({placeholders})",
                tokens).fetchone()[0])
        else:
            sends = int(conn.execute(
                "SELECT COUNT(*) FROM alumni_track_events "
                "WHERE kind = 'send'").fetchone()[0])
            opens = int(conn.execute(
                "SELECT COUNT(*) FROM alumni_track_events "
                "WHERE kind = 'open'").fetchone()[0])
            clicks = int(conn.execute(
                "SELECT COUNT(*) FROM alumni_track_events "
                "WHERE kind = 'click'").fetchone()[0])
            uniq = int(conn.execute(
                "SELECT COUNT(DISTINCT alumni_id) "
                "FROM alumni_track_events "
                "WHERE kind = 'open' "
                "  AND alumni_id IS NOT NULL").fetchone()[0])
    return TrackingSummary(
        campaign_ref=campaign_ref, sends=sends, opens=opens,
        clicks=clicks, unique_opens=uniq)


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    get_alumnus,
    list_alumni,
)
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
from .comms import (  # noqa: E402,F401
    _alumnus_context,
    _render,
    get_channel_prefs,
)
