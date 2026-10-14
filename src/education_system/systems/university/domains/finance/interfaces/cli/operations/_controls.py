"""Control sub-menus: approval inbox, fraud investigations, month-end close checklist.

Same ``FinanceOperationsService`` calls as the Finance GUI's operations tabs
(``interfaces/gui/finance/layout/_operations.py``), so both views share data.
"""

from __future__ import annotations

from education_system.systems.university.domains.finance.domain.operations_service import (
    APPROVAL_DECISIONS,
    CLOSE_CHECKLIST_TASKS,
    FRAUD_CASE_DECISIONS,
)
from education_system.systems.university.domains.finance.interfaces.cli.operations._shared import (
    OpsContext,
    ok,
    print_record,
    print_table,
    prompt_choice,
    prompt_float,
    prompt_int,
    prompt_text,
    run_menu,
    t,
)

APPROVAL_COLUMNS = (
    "id",
    "item_type",
    "entity_id",
    "amount",
    "requested_by",
    "status",
    "decision_by",
    "decision_at",
)
FRAUD_COLUMNS = (
    "id",
    "payment_id",
    "risk_score",
    "reason",
    "status",
    "assigned_to",
    "decision",
    "created_at",
)
CLOSE_COLUMNS = ("id", "period_label", "task_name", "owner", "status", "evidence")


# --------------------------------------------------------------------------- #
# Approval inbox
# --------------------------------------------------------------------------- #
def _list_approvals(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_approval_items"),
        APPROVAL_COLUMNS,
        t("approvals.none", default="The approval inbox is empty."),
    )


def _request_approval(ctx: OpsContext) -> None:
    item_type = prompt_text(t("approvals.item_type", default="Item type"), required=True)
    entity_id = prompt_int(t("approvals.entity_id", default="Entity ID"))
    amount = prompt_float(t("amount", default="Amount"), default=0.0)
    new_id = ctx.service.request_approval(item_type, entity_id, amount, ctx.username)
    ok(t("approvals.requested", default="Approval item {id} requested.", id=new_id))


def _decide_approval(ctx: OpsContext, decision: str) -> None:
    item_id = prompt_int(t("approvals.id", default="Approval item ID"))
    notes = prompt_text(t("notes", default="Notes"))
    ctx.service.decide_approval(item_id, decision, ctx.username, notes=notes)
    ok(t("approvals.decided", default="Approval item {id} {decision}.", id=item_id, decision=decision))


def approval_inbox_menu(ctx: OpsContext) -> None:
    approve, reject = APPROVAL_DECISIONS
    run_menu(
        t("approvals.title", default="FINANCE APPROVAL INBOX"),
        [
            (t("approvals.list", default="List approval items"), lambda: _list_approvals(ctx)),
            (t("approvals.request", default="Request approval"), lambda: _request_approval(ctx)),
            (t("approvals.approve", default="Approve item"), lambda: _decide_approval(ctx, approve)),
            (t("approvals.reject", default="Reject item"), lambda: _decide_approval(ctx, reject)),
        ],
    )


# --------------------------------------------------------------------------- #
# Fraud investigations
# --------------------------------------------------------------------------- #
def _list_fraud_cases(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_fraud_cases"),
        FRAUD_COLUMNS,
        t("fraud.none", default="No fraud cases."),
    )


def _view_fraud_case(ctx: OpsContext) -> None:
    case_id = prompt_int(t("fraud.id", default="Fraud case ID"))
    print_record(
        ctx.service.row("finance_fraud_cases", case_id),
        t("fraud.title_one", default="Fraud case {id}", id=case_id),
        t("fraud.not_found", default="Fraud case not found."),
    )


def _open_fraud_case(ctx: OpsContext) -> None:
    payment_id = prompt_int(t("fraud.payment_id", default="Payment ID"))
    score = prompt_float(t("fraud.score", default="Risk score 0-1"))
    reason = prompt_text(t("fraud.reason", default="Reason"))
    new_id = ctx.service.create_fraud_case(payment_id, score, reason)
    ok(t("fraud.opened", default="Fraud case {id} opened.", id=new_id))


def _decide_fraud_case(ctx: OpsContext) -> None:
    case_id = prompt_int(t("fraud.id", default="Fraud case ID"))
    if not ctx.service.row("finance_fraud_cases", case_id):
        raise ValueError(t("fraud.not_found", default="Fraud case not found."))
    decision = prompt_choice(t("fraud.decision", default="Decision"), FRAUD_CASE_DECISIONS)
    ctx.service.decide_fraud_case(case_id, decision, ctx.username)
    ok(t("fraud.decided", default="Fraud case {id} closed as '{decision}'.", id=case_id, decision=decision))


def _reassign_fraud_case(ctx: OpsContext) -> None:
    case_id = prompt_int(t("fraud.id", default="Fraud case ID"))
    assignee = prompt_text(t("fraud.assignee", default="Assign to"), required=True)
    ctx.service.reassign_fraud_case(case_id, assignee)
    ok(t("fraud.reassigned", default="Fraud case {id} assigned to {who}.", id=case_id, who=assignee))


def _reopen_fraud_case(ctx: OpsContext) -> None:
    case_id = prompt_int(t("fraud.id", default="Fraud case ID"))
    ctx.service.reopen_fraud_case(case_id)
    ok(t("fraud.reopened", default="Fraud case {id} reopened.", id=case_id))


def fraud_investigations_menu(ctx: OpsContext) -> None:
    run_menu(
        t("fraud.title", default="FRAUD INVESTIGATIONS"),
        [
            (t("fraud.list", default="List fraud cases"), lambda: _list_fraud_cases(ctx)),
            (t("fraud.view", default="View fraud case"), lambda: _view_fraud_case(ctx)),
            (t("fraud.open", default="Open fraud case"), lambda: _open_fraud_case(ctx)),
            (
                t("fraud.decide", default="Decide case (confirm / false positive / escalate)"),
                lambda: _decide_fraud_case(ctx),
            ),
            (t("fraud.reassign", default="Reassign open case"), lambda: _reassign_fraud_case(ctx)),
            (t("fraud.reopen", default="Reopen closed case"), lambda: _reopen_fraud_case(ctx)),
        ],
    )


# --------------------------------------------------------------------------- #
# Month-end close checklist
# --------------------------------------------------------------------------- #
def _list_close_tasks(ctx: OpsContext) -> None:
    period = prompt_text(t("close.period_filter", default="Period filter (blank = all)"))
    rows = ctx.service.rows("finance_close_tasks")
    if period:
        rows = [r for r in rows if r.get("period_label") == period]
    # Oldest first: the service requires tasks to be completed in id order.
    print_table(
        sorted(rows, key=lambda r: r["id"]),
        CLOSE_COLUMNS,
        t("close.none", default="No close tasks for that period."),
    )


def _seed_close_checklist(ctx: OpsContext) -> None:
    period = prompt_text(t("close.period", default="Period (e.g. 2026-08)"), required=True)
    owner = prompt_text(t("close.owner", default="Owner"), default="finance-team")
    ctx.service.seed_close_checklist(period, owner)
    ok(
        t(
            "close.seeded",
            default="Checklist for {period} ready ({count} standard tasks).",
            period=period,
            count=len(CLOSE_CHECKLIST_TASKS),
        )
    )


def _complete_close_task(ctx: OpsContext) -> None:
    task_id = prompt_int(t("close.id", default="Task ID"))
    evidence = prompt_text(t("close.evidence", default="Evidence/reference"), required=True)
    ctx.service.complete_close_task(task_id, evidence)
    ok(t("close.completed", default="Close task {id} completed.", id=task_id))


def close_checklist_menu(ctx: OpsContext) -> None:
    run_menu(
        t("close.title", default="MONTH-END CLOSE CHECKLIST"),
        [
            (t("close.list", default="List close tasks"), lambda: _list_close_tasks(ctx)),
            (
                t("close.seed", default="Create checklist for a period"),
                lambda: _seed_close_checklist(ctx),
            ),
            (t("close.complete", default="Complete task"), lambda: _complete_close_task(ctx)),
        ],
    )
