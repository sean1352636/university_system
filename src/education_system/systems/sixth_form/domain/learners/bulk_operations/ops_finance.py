"""Sixth Form bulk operations — finance (bursaries, invoices, discounts,
payment import, statements).

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

import datetime as _dt
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    ValidationError,
    _log_job,
    _validate_targets,
)

# ── Operation: bulk bursary award ─────────────────────────────────

def bulk_bursary_award(
    student_ids: list[str],
    *,
    bursary_type: str,
    amount_awarded: float,
    academic_year: str | None = None,
    eligibility_basis: str | None = None,
    decision_note: str | None = None,
    assessed_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _br,
    )
    today = _dt.date.today().isoformat()
    result = BulkResult(operation="bursary_award",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _br.create_application({
                "student_id":        sid,
                "bursary_type":      bursary_type,
                "academic_year":     academic_year,
                "application_date":  today,
                "amount_requested":  amount_awarded,
                "amount_awarded":    amount_awarded,
                "eligibility_basis": eligibility_basis,
                "status":            "Approved",
                "assessed_by":       assessed_by,
                "assessed_on":       today,
                "decision_note":     decision_note,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Awarded {bursary_type} (£{amount_awarded:.2f}) to "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="bursary_award", summary=summary_text,
        params={"bursary_type": bursary_type,
                "amount_awarded": amount_awarded,
                "academic_year": academic_year,
                "eligibility_basis": eligibility_basis},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk raise invoices ────────────────────────────────

def bulk_raise_invoices(
    student_ids: list[str],
    *,
    description: str,
    category: str,
    amount: float,
    issued_date: str | None = None,
    due_date: str | None = None,
    academic_year: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fees as _fees,
    )
    issued = issued_date or _dt.date.today().isoformat()
    result = BulkResult(operation="raise_invoices",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _fees.create_item({
                "student_id":   sid,
                "description":  description,
                "category":     category,
                "amount":       amount,
                "issued_date":  issued,
                "due_date":     due_date,
                "academic_year": academic_year,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Raised £{amount:.2f} {category} invoice for "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="raise_invoices", summary=summary_text,
        params={"description": description, "category": category,
                "amount": amount, "issued_date": issued,
                "due_date": due_date,
                "academic_year": academic_year},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk fee discount / waiver ─────────────────────────

def bulk_fee_discount(
    student_ids: list[str],
    *,
    description: str,
    amount: float,
    category: str = "Other",
    issued_date: str | None = None,
    academic_year: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Apply a credit (negative-amount fee item) per student. Pass
    ``amount`` as a positive number; it's stored as a credit (-amount)."""
    if amount <= 0:
        raise ValidationError("Discount amount must be positive")
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fees as _fees,
    )
    issued = issued_date or _dt.date.today().isoformat()
    result = BulkResult(operation="fee_discount",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _fees.create_item({
                "student_id":   sid,
                "description":  f"Discount: {description}",
                "category":     category,
                "amount":       -float(amount),
                "issued_date":  issued,
                "academic_year": academic_year,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Applied −£{amount:.2f} {category} credit to "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="fee_discount", summary=summary_text,
        params={"description": description, "amount": amount,
                "category": category, "issued_date": issued,
                "academic_year": academic_year},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk payment import from CSV ───────────────────────

def bulk_import_payments(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """CSV columns: fee_id, amount, paid_on, method, reference?, notes?."""
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fees as _fees,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        required = {"fee_id", "amount", "paid_on", "method"}
        missing = required - set(h.strip() for h in (reader.fieldnames or []))
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    result = BulkResult(operation="import_payments",
                         target_count=len(rows))
    if dry_run:
        return result
    for i, r in enumerate(rows, start=2):
        try:
            fee_id = int(r["fee_id"])
            _fees.create_payment(fee_id, {
                "amount":     r.get("amount"),
                "paid_on":    r.get("paid_on"),
                "method":     r.get("method"),
                "reference":  r.get("reference") or None,
                "notes":      r.get("notes") or None,
            })
            result.success_ids.append(f"L{i}:fee#{fee_id}")
        except Exception as e:
            result.failures.append((f"L{i}", str(e)))
    summary_text = (f"Imported {result.success_count}/{result.target_count} "
                    f"payments from {os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_payments", summary=summary_text,
        params={"csv_path": csv_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk financial statements (text) ───────────────────

def bulk_financial_statements(
    student_ids: list[str],
    *,
    output_dir: str,
    academic_year: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    import os
    targets = _validate_targets(student_ids)
    if not output_dir:
        raise ValidationError("output_dir is required")
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fees as _fees,
    )
    result = BulkResult(operation="financial_statements",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            items = _fees.list_items(student_id=sid,
                                       academic_year=academic_year)
            total_charged = sum(getattr(i, "amount", 0) or 0 for i in items)
            lines = [
                f"Financial statement — {sid}",
                f"Academic year: {academic_year or 'All'}",
                f"Generated: {_dt.datetime.now().isoformat(sep=' ', timespec='seconds')}",
                "",
                "Fees:",
            ]
            for it in items:
                lines.append(
                    f"  #{it.fee_id:<5} {it.issued_date}  "
                    f"{it.category:<12}  £{it.amount or 0:>10.2f}  "
                    f"{it.description}"
                )
            lines.append("")
            lines.append(f"Total charged: £{total_charged:.2f}")
            path = os.path.join(output_dir, f"statement_{sid}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            result.success_ids.append(f"{sid}:{path}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Wrote {result.success_count}/{result.target_count} "
                    f"financial statements to {output_dir}")
    result.job_id = _log_job(
        operation="financial_statements", summary=summary_text,
        params={"output_dir": output_dir,
                "academic_year": academic_year},
        result=result, ran_by=ran_by,
    )
    return result
