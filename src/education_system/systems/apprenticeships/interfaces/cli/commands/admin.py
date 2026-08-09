"""Provider administration: staff caseloads, funding and compliance.

Exposes: staff_menu, funding_menu, compliance_menu.

Three unrelated areas share a module because each is one menu's worth of
administrator work rather than a domain of its own — splitting them into
three files would give two of them a single caller and no shared code.

The staff commands talk to ``staff_repository`` directly. There is no
staff service, so the permission check a service would have done has to
happen here; every other command in this file goes through a service and
does not repeat one.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    validate_check_key,
    validate_doc_key,
)
from education_system.systems.apprenticeships.domain.staff.assessors import validate_staff_role
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import compliance_service, funding_service
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied

logger = logging.getLogger(__name__)

_CASELOAD_COLUMNS = (
    ("Staff", 24), ("Role", 18), ("Caseload", -9), ("Active", -7), ("At gateway", -11),
    ("Reviews overdue", -16), ("Behind on OTJ", -14), ("To assess", -10), ("RAG", 6),
)

_PAYMENT_COLUMNS = (
    ("Due", 12), ("Amount", -12), ("Type", 12), ("Status", 12),
    ("Claimed", 12), ("Paid", 12), ("Notes", 26),
)


# ═════════════════════════════════════════════════════════════════════
# Staff and caseloads
# ═════════════════════════════════════════════════════════════════════

def staff_menu(actor: Actor) -> None:
    _require(actor, "staff.view", "see the provider's staff records")
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Caseload pressure", partial(_caseloads, actor)),
        ("Open one caseload", partial(_caseload, actor)),
    ]
    if actor.can("staff.manage"):
        entries += [
            ("Add a member of staff", partial(_create_staff, actor)),
            ("Edit a staff record", partial(_edit_staff, actor)),
            ("Deactivate a staff record", partial(_deactivate_staff, actor)),
        ]
    prompts.run_menu("Staff & Caseloads", entries)


def _caseloads(actor: Actor) -> None:
    _require(actor, "staff.view", "see the provider's staff records")
    rows = staff_repository.list_caseloads()
    prompts.title("Caseload pressure")
    prompts.note(
        "A tutor over the threshold stops seeing people long before the missed "
        f"reviews show up as a compliance problem. Warning at "
        f"{config.CASELOAD_WARNING_THRESHOLD}, capacity {config.CASELOAD_MAXIMUM}."
    )
    prompts.table(
        _CASELOAD_COLUMNS,
        rows,
        lambda c: (c.name, c.staff.staff_role, c.total, c.active, c.at_gateway,
                   c.reviews_overdue, c.otj_behind, c.evidence_awaiting_assessment,
                   c.rag_rating),
        noun="caseload",
        empty="no active staff are recorded",
    )
    prompts.pause()


def _caseload(actor: Actor) -> None:
    _require(actor, "staff.view", "see the provider's staff records")
    member = _pick_staff("Whose caseload?")
    caseload = staff_repository.build_caseload(member.staff_id, with_members=True)
    if caseload is None:
        prompts.fail("That staff record could not be opened.")
        prompts.pause()
        return

    prompts.title(f"{member.full_name} — caseload")
    prompts.details([
        ("Role", member.staff_role),
        ("Email", member.email),
        ("Phone", member.phone),
        ("Login", member.username),
        ("Specialisms", member.specialisms),
        ("Active apprentices", caseload.active),
        ("Total", caseload.total),
        ("At gateway", caseload.at_gateway),
        ("Reviews overdue", caseload.reviews_overdue),
        ("Behind on off-the-job", caseload.otj_behind),
        ("Evidence to assess", caseload.evidence_awaiting_assessment),
        ("RAG", caseload.rag_rating),
        ("Headroom", f"{caseload.headroom} more before capacity"),
    ])
    apprentices.table(list(caseload.members))
    prompts.pause()


def _create_staff(actor: Actor) -> None:
    _require(actor, "staff.manage", "add staff records")
    prompts.title("Add a member of staff")
    staff_id = staff_repository.create({**_staff_payload(None), "active": 1})
    prompts.ok(f"Added staff record {staff_id}.")
    prompts.note(
        "Set their login username on the record so their caseload screens scope to "
        "them — an unlinked login sees an empty caseload, not an error."
    )
    prompts.pause()


def _edit_staff(actor: Actor) -> None:
    _require(actor, "staff.manage", "edit staff records")
    member = _pick_staff("Staff record to edit")
    prompts.title(f"Edit {member.full_name}")
    staff_repository.update(member.staff_id, _staff_payload(member))
    prompts.ok(f"Updated {member.full_name}.")
    prompts.pause()


def _deactivate_staff(actor: Actor) -> None:
    _require(actor, "staff.manage", "deactivate staff records")
    member = _pick_staff("Staff record to deactivate")
    prompts.note(
        "Their apprentices keep the record and surface as unassigned, so the "
        "reassignment is visible rather than silent."
    )
    if not prompts.ask_yes_no(f"Deactivate {member.full_name}?"):
        raise prompts.Abort
    staff_repository.update(member.staff_id, {"active": 0})
    prompts.ok(f"{member.full_name} is deactivated.")
    prompts.pause()


def _pick_staff(heading: str):
    return prompts.choose(
        heading, staff_repository.list_all(),
        render=lambda s: (
            f"{s.full_name} — {s.staff_role}" + ("" if s.active else " (inactive)")
        ),
    )


def _staff_payload(member) -> dict[str, object]:
    return {
        "full_name": prompts.ask(
            "Name", default=member.full_name if member else "", required=True
        ),
        "staff_role": validate_staff_role(prompts.choose_value(
            "Role", config.STAFF_ROLES, default=member.staff_role if member else "Tutor"
        )),
        "email": prompts.ask("Email", default=(member.email if member else "") or "") or None,
        "phone": prompts.ask("Phone", default=(member.phone if member else "") or "") or None,
        "username": prompts.ask(
            "Login username", default=(member.username if member else "") or ""
        ) or None,
        "specialisms": prompts.ask(
            "Specialisms (comma-separated)",
            default=(member.specialisms if member else "") or "",
        ) or None,
    }


# ═════════════════════════════════════════════════════════════════════
# Funding
# ═════════════════════════════════════════════════════════════════════

def funding_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Funding dashboard", partial(_funding_dashboard, actor)),
        ("List funding records", partial(_list_funding, actor)),
        ("One apprenticeship's funding", partial(_funding_detail, actor)),
        ("Payments", partial(_payments, actor)),
    ]
    if actor.can("funding.manage"):
        entries += [
            ("Agree or re-negotiate a price", partial(_set_funding, actor)),
            ("Rebuild a payment schedule", partial(_regenerate, actor)),
            ("Claim an instalment", partial(_claim, actor)),
            ("Mark an instalment paid", partial(_mark_paid, actor)),
            ("Withhold an instalment", partial(_withhold, actor)),
            ("Claw money back", partial(_claw_back, actor)),
            ("Claim everything due", partial(_bulk_claim, actor)),
        ]
    prompts.run_menu("Funding", entries)


def _funding_dashboard(actor: Actor) -> None:
    data = funding_service.funding_dashboard(actor)
    totals = data["totals"]
    prompts.title("Funding")
    prompts.details([
        ("Contracted value", prompts.money(data["contracted_value"])),
        ("Scheduled", prompts.money(totals["scheduled"])),
        ("Claimed", prompts.money(totals["claimed"])),
        ("Paid", prompts.money(totals["paid"])),
        ("Withheld or clawed back", prompts.money(totals["withheld"])),
        ("Overdue", f"{prompts.money(data['overdue_value'])} "
                    f"across {data['overdue_count']} instalment(s)"),
    ])
    prompts.note("\nOverdue instalments:")
    _payment_table(data["overdue_payments"], empty="nothing overdue")
    prompts.pause()


def _list_funding(actor: Actor) -> None:
    model = prompts.choose("Funding model filter", config.FUNDING_MODELS, allow_blank=True)
    rows = funding_service.list_funding(actor, funding_model=model)
    prompts.title("Funding records")
    prompts.table(
        (("Apprentice", 22), ("Employer", 20), ("Programme", 22), ("Model", 14),
         ("Band", -5), ("Price", -11), ("Employer £", -11), ("Gov £", -11), ("Paid", -11)),
        rows,
        lambda r: (r["apprentice_name"], r["employer_name"], r["programme_title"],
                   r["funding_model"], r["band"], prompts.money(r["negotiated_price"]),
                   prompts.money(r["employer_contribution"]),
                   prompts.money(r["government_contribution"]),
                   prompts.money(r["paid_to_date"])),
        noun="record",
        empty="no funding has been agreed yet",
    )
    prompts.pause()


def _funding_detail(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    show_funding(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


def show_funding(actor: Actor, apprentice_id: int, name: str) -> None:
    """One apprenticeship's price, split and instalment plan."""
    summary = funding_service.get_funding(actor, apprentice_id)
    prompts.title(f"Funding — {name}")
    record = summary.record
    if record is None:
        prompts.note("No price has been agreed for this apprenticeship yet.")
        return

    prompts.details([
        ("Funding model", record.funding_model),
        ("Band", f"{record.band} (cap {prompts.money(record.band_maximum)})"),
        ("Negotiated price", prompts.money(record.negotiated_price)),
        ("Headroom under the cap", prompts.money(record.headroom)),
        ("Employer contribution", prompts.money(record.employer_contribution)),
        ("Government contribution", prompts.money(record.government_contribution)),
        ("Additional payments", prompts.money(record.additional_payments)),
        ("Total value", prompts.money(record.total_value)),
        ("Scheduled", prompts.money(summary.scheduled_total)),
        ("Claimed", prompts.money(summary.claimed_total)),
        ("Paid", prompts.money(summary.paid_total)),
        ("Withheld", prompts.money(summary.withheld_total)),
        ("Outstanding", prompts.money(summary.outstanding_total)),
        ("Notes", record.notes),
    ])
    prompts.note("\nPayment schedule:")
    _payment_table(summary.payments)
    overdue = summary.overdue_payments
    if overdue:
        prompts.note(f"  ! {len(overdue)} instalment(s) are past their due date.")


def _payments(actor: Actor) -> None:
    status = prompts.choose("Status filter", config.PAYMENT_STATUSES, allow_blank=True)
    overdue = status is None and prompts.ask_yes_no("Overdue only?")
    rows = funding_service.list_payments(actor, status=status, overdue_only=overdue)
    prompts.title("Payments")
    _payment_table(rows)
    prompts.note(f"\n  {prompts.money(sum(p.amount for p in rows))} in this selection.")
    prompts.pause()


def _set_funding(actor: Actor) -> None:
    """Agree the price. Band and route are derived unless overridden."""
    summary = apprentices.pick(actor, heading="Whose funding?")
    apprentice_id = summary.apprentice.apprentice_id
    show_funding(actor, apprentice_id, summary.full_name)

    prompts.title(f"Agree a price — {summary.full_name}")
    prompts.note(
        "The band comes from the standard and the route from the employer's levy and "
        "headcount position. Leave both blank to take those; the price is still "
        "checked against the band cap, because the excess above it is unfundable."
    )
    payload: dict[str, object] = {
        "negotiated_price": prompts.ask_float("Negotiated price", required=True),
        "band": prompts.ask_int("Band override (blank to take the standard's)"),
        "additional_payments": prompts.ask_float("Additional payments", default=0.0),
        "notes": prompts.ask("Notes"),
    }
    model = prompts.choose(
        "Funding model override", config.FUNDING_MODELS, allow_blank=True
    )
    if model:
        payload["funding_model"] = model

    record = funding_service.set_funding(actor, apprentice_id, payload)
    prompts.ok(
        f"{record.funding_model}, band {record.band}, "
        f"{prompts.money(record.negotiated_price)}."
    )
    prompts.note(
        f"Employer {prompts.money(record.employer_contribution)} · "
        f"government {prompts.money(record.government_contribution)}."
    )
    prompts.pause()


def _regenerate(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Whose schedule?")
    prompts.note(
        "Instalments already claimed or paid survive — they are real financial "
        "events, not a projection to recalculate."
    )
    count = funding_service.regenerate_schedule(actor, summary.apprentice.apprentice_id)
    prompts.ok(f"{count} instalment(s) scheduled for {summary.full_name}.")
    prompts.pause()


def _claim(actor: Actor) -> None:
    payment = _pick_payment(actor, "Instalment to claim", status="Scheduled")
    updated = funding_service.claim_payment(actor, payment.payment_id)
    prompts.ok(f"Claimed {prompts.money(updated.amount)} due {updated.due_date}.")
    prompts.pause()


def _mark_paid(actor: Actor) -> None:
    payment = _pick_payment(actor, "Instalment that has landed", status="Claimed")
    updated = funding_service.mark_paid(actor, payment.payment_id)
    prompts.ok(f"Reconciled {prompts.money(updated.amount)} due {updated.due_date}.")
    prompts.pause()


def _withhold(actor: Actor) -> None:
    payment = _pick_payment(actor, "Instalment to hold back")
    reason = prompts.ask("Reason for withholding", required=True)
    updated = funding_service.withhold_payment(actor, payment.payment_id, reason=reason)
    prompts.ok(f"Withheld {prompts.money(updated.amount)} due {updated.due_date}.")
    prompts.pause()


def _claw_back(actor: Actor) -> None:
    payment = _pick_payment(actor, "Payment to recover", status="Paid")
    prompts.note(
        "Money that has moved cannot be un-moved, only recovered and recorded as "
        "such. This is terminal."
    )
    reason = prompts.ask("Reason", required=True)
    if not prompts.ask_yes_no(f"Claw back {prompts.money(payment.amount)}?"):
        raise prompts.Abort
    funding_service.claw_back(actor, payment.payment_id, reason=reason)
    prompts.ok(f"Clawed back {prompts.money(payment.amount)}.")
    prompts.pause()


def _bulk_claim(actor: Actor) -> None:
    rows = funding_service.list_payments(actor, status="Scheduled")
    due = [p for p in rows if p.due_date <= date.today().isoformat()]
    if not due:
        prompts.ok("No scheduled instalment has fallen due yet.")
        prompts.pause()
        return

    prompts.title("Claim everything due")
    _payment_table(due)
    total = sum(p.amount for p in due)
    if not prompts.ask_yes_no(
        f"Claim all {len(due)} instalment(s), totalling {prompts.money(total)}?"
    ):
        raise prompts.Abort

    claimed = funding_service.bulk_claim(actor, [p.payment_id for p in due])
    prompts.ok(f"{claimed} of {len(due)} instalment(s) claimed.")
    if claimed < len(due):
        prompts.note("The rest had already been claimed by somebody else.")
    prompts.pause()


def _payment_table(rows: list, *, empty: str | None = None) -> None:
    prompts.table(
        _PAYMENT_COLUMNS,
        rows,
        lambda p: (
            f"{p.due_date}{' !' if p.is_overdue else ''}", prompts.money(p.amount),
            p.payment_type, p.status, p.claimed_at, p.paid_at, p.notes,
        ),
        noun="instalment",
        empty=empty,
    )


def _pick_payment(actor: Actor, heading: str, *, status: str | None = None):
    rows = funding_service.list_payments(actor, status=status)
    if not rows:
        prompts.fail(
            f"There are no {status.lower()} instalments." if status
            else "There are no instalments."
        )
        raise prompts.Abort
    names = apprentices.names(actor)
    return prompts.choose(
        heading, rows,
        render=lambda p: (
            f"{names.get(p.apprentice_id, f'#{p.apprentice_id}')} — "
            f"{p.due_date} {prompts.money(p.amount)} ({p.payment_type}, {p.status})"
        ),
    )


# ═════════════════════════════════════════════════════════════════════
# Compliance
# ═════════════════════════════════════════════════════════════════════

def compliance_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Compliance dashboard", partial(_compliance_dashboard, actor)),
        ("One apprentice's position", partial(_compliance_record, actor)),
    ]
    if actor.can("compliance.manage"):
        entries += [
            ("Record an eligibility check", partial(_set_eligibility, actor)),
            ("Record a document", partial(_set_document, actor)),
            ("Record English or Maths", partial(_set_functional_skill, actor)),
        ]
    if actor.is_admin:
        entries += [
            ("Audit trail", partial(_audit, actor)),
            ("Retention report", partial(_retention, actor)),
        ]
    prompts.run_menu("Compliance", entries)


def _compliance_dashboard(actor: Actor) -> None:
    data = compliance_service.compliance_dashboard(actor)
    prompts.title("Compliance")
    prompts.note(
        "Funding is conditional on paperwork: an apprentice who was never eligible, "
        "or whose training plan was never signed, is a clawback at audit however "
        "good the training was."
    )
    prompts.details([
        ("Cohort", data["total"]),
        ("Green", data["green"]),
        ("Amber", data["amber"]),
        ("Red", data["red"]),
    ])
    prompts.note("\nFlagged:")
    prompts.table(
        (("Apprentice", 24), ("Status", 16), ("Employer", 20), ("RAG", 6),
         ("Outstanding", 46)),
        data["flagged"],
        lambda r: (r.get("apprentice_name"), r.get("status"), r.get("employer_name"),
                   r.get("rag"),
                   "; ".join([*r.get("failed_checks", []), *r.get("missing", [])])),
        noun="flag",
        empty="nothing flagged",
    )
    prompts.pause()


def _compliance_record(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    show_compliance(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


def show_compliance(actor: Actor, apprentice_id: int, name: str) -> None:
    """One apprentice's eligibility, documents and functional skills."""
    status = compliance_service.get_status(actor, apprentice_id)
    prompts.title(f"Compliance — {name}")
    prompts.details([
        ("RAG", status.rag_rating),
        ("Eligible", status.is_eligible),
        ("Audit ready", status.is_audit_ready),
        ("Eligibility passed", f"{status.eligibility_passed}/{len(status.eligibility)}"),
        ("Documents signed", f"{status.documents_signed}/{len(status.documents)}"),
        ("Functional skills satisfied", status.functional_skills_satisfied),
    ])

    prompts.note("\nEligibility:")
    prompts.table(
        (("Check", 40), ("Passed", 7), ("Checked by", 16), ("When", 12), ("Evidence", 30)),
        status.eligibility,
        lambda c: (c.label, c.passed, c.checked_by, c.checked_at, c.evidence),
        noun="check",
    )

    prompts.note("\nDocuments:")
    prompts.table(
        (("Document", 34), ("Status", 18), ("Signed", 12), ("Expires", 12),
         ("File", 20), ("Notes", 24)),
        status.documents,
        lambda d: (d.label, f"{d.status}{' (expired)' if d.is_expired else ''}",
                   d.signed_date, d.expiry_date, d.file_name, d.notes),
        noun="document",
    )

    prompts.note("\nEnglish and Maths:")
    prompts.table(
        (("Subject", 12), ("Status", 14), ("Level", 12), ("Achieved", 12),
         ("Exemption", 34), ("Satisfied", 10)),
        status.functional_skills,
        lambda s: (s.subject, s.status, s.level, s.achieved_date, s.exemption_reason,
                   s.is_satisfied),
        noun="subject",
    )


def _set_eligibility(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    prompts.note(
        "Who checked it and when are stamped from your login: at audit the question "
        "is who attested to this."
    )
    key = _pick_key(config.ELIGIBILITY_CHECKS, "Eligibility check")
    passed = prompts.ask_yes_no("Does it pass?", default=True)
    evidence = prompts.ask("Evidence seen")

    check = compliance_service.set_eligibility_check(
        actor, summary.apprentice.apprentice_id, validate_check_key(key),
        passed=passed, evidence=evidence or None,
    )
    prompts.ok(f"{check.label}: {'passed' if check.passed else 'not passed'}.")
    prompts.pause()


def _set_document(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    key = _pick_key(config.COMPLIANCE_DOCUMENTS, "Document")
    state = prompts.choose_value("Status", config.DOCUMENT_STATUSES, default="Signed")
    issued = prompts.ask("Issued (YYYY-MM-DD)")
    signed = prompts.ask(
        "Signed (YYYY-MM-DD, blank for today when marking Signed)",
        default=date.today().isoformat() if state == "Signed" else "",
    )
    expires = prompts.ask("Expires (YYYY-MM-DD)")
    notes = prompts.ask("Notes")

    document = compliance_service.set_document(
        actor, summary.apprentice.apprentice_id, validate_doc_key(key),
        status=state, issued_date=issued or None, signed_date=signed or None,
        expiry_date=expires or None, notes=notes or None,
    )
    prompts.ok(f"{document.label}: {document.status}.")
    prompts.pause()


def _set_functional_skill(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    prompts.note(
        "Achieved and Exempt both satisfy the gateway check, so both need their "
        "evidence: a level for an achievement, a recognised reason for an exemption."
    )
    subject = prompts.choose_value("Subject", config.FUNCTIONAL_SKILLS)
    state = prompts.choose_value("Status", config.FUNCTIONAL_SKILL_STATUSES)

    level = achieved = reason = ""
    if state == "Achieved":
        level = prompts.choose_value("Level", config.FUNCTIONAL_SKILL_LEVELS)
        achieved = prompts.ask("Achieved on (YYYY-MM-DD)", default=date.today().isoformat())
    elif state == "Exempt":
        reason = prompts.choose_value("Exemption reason", config.EXEMPTION_REASONS)
    notes = prompts.ask("Notes")

    skill = compliance_service.set_functional_skill(
        actor, summary.apprentice.apprentice_id, subject,
        status=state, level=level or None, achieved_date=achieved or None,
        exemption_reason=reason or None, notes=notes or None,
    )
    prompts.ok(
        f"{skill.subject}: {skill.status}"
        + (f" ({skill.level})" if skill.level else "")
        + (" — satisfies gateway" if skill.is_satisfied else "")
    )
    prompts.pause()


def _audit(actor: Actor) -> None:
    prompts.title("Audit trail")
    prompts.note(
        "Administrators only: the log records what every user did, so a scoped view "
        "would still show a tutor who else touched those records."
    )
    entity = prompts.ask("Entity filter (e.g. otj_entry)")
    action = prompts.choose("Action filter", config.AUDIT_ACTIONS, allow_blank=True)
    who = prompts.ask("Username filter")
    since = prompts.ask("Since (YYYY-MM-DD)")
    limit = prompts.ask_int("How many rows", default=200)

    rows = compliance_service.audit_trail(
        actor, entity=entity or None, action=action, actor_username=who or None,
        since=since or None, limit=limit or 200,
    )
    prompts.table(
        (("When", 20), ("Who", 14), ("Role", 14), ("Action", 10), ("Entity", 20),
         ("Id", 10), ("Detail", 40)),
        rows,
        lambda e: (e.ts, e.actor, e.actor_role, e.action, e.entity, e.entity_id, e.detail),
        noun="entry",
    )
    prompts.pause()


def _retention(actor: Actor) -> None:
    rows = compliance_service.retention_report(actor)
    prompts.title("Records past their retention period")
    prompts.note(
        f"A completed apprentice's record is kept {config.RETENTION_YEARS} years for "
        "audit. These are past it."
    )
    prompts.table(
        (("Apprentice", 26), ("Status", 16), ("Ended", 12), ("Retention expired", 18)),
        rows,
        lambda r: (r.get("apprentice_name"), r.get("status"), r.get("actual_end_date"),
                   r.get("retention_expiry")),
        noun="record",
        empty="nothing is past its retention period",
    )
    prompts.pause()


def _pick_key(pairs: tuple[tuple[str, str], ...], heading: str) -> str:
    """Choose from a ``(key, label)`` list, showing the label."""
    chosen = prompts.choose(heading, list(pairs), render=lambda pair: pair[1])
    return chosen[0]


def _require(actor: Actor, permission: str, what: str) -> None:
    """The check a service would have made, for the repository-backed commands."""
    if not actor.can(permission):
        raise PermissionDenied(f"Your role ({actor.role_label}) may not {what}")
