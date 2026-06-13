"""
Grant Budget Manager

Provides functionality for:
- Budget category management for grant funding
- Allocation tracking per grant application and category
- Expense submission, approval, and rejection workflows
- Funding threshold alerts and resolution
- Budget transfer requests between allocations
- Reporting: summaries, category breakdowns, and spending timelines
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class GrantBudgetManager:
    """Manager for grant budget categories, allocations, expenses, alerts,
    transfers, and reporting."""

    # ==================== CATEGORY MANAGEMENT ====================

    @staticmethod
    def get_categories(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all grant budget categories.

        Args:
            active_only: If True, return only categories where
                is_active = 1. If False, return all categories.

        Returns:
            A list of category dicts ordered by sort_order.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM grant_budget_categories WHERE 1=1'
            params: list = []

            if active_only:
                query += ' AND is_active = 1'

            query += ' ORDER BY sort_order'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_category(name: str, description: str,
                        sort_order: int = None) -> int:
        """Create a new grant budget category.

        Args:
            name: Unique category name.
            description: Description of what the category covers.
            sort_order: Display order position. If None, the category
                is placed after all existing categories.

        Returns:
            The ID of the newly created category.
        """
        with transaction() as conn:
            if sort_order is None:
                row = conn.execute('''
                    SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order
                    FROM grant_budget_categories
                ''').fetchone()
                sort_order = row['next_order']

            cursor = conn.execute('''
                INSERT INTO grant_budget_categories (
                    name, description, sort_order, is_active,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)
            ''', (
                name, description, sort_order,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            category_id = cursor.lastrowid
            log_activity('create', 'grant_budget_category', details={
                'category_id': category_id, 'name': name,
            })
            return category_id

    # ==================== ALLOCATION MANAGEMENT ====================

    @staticmethod
    def create_allocation(grant_application_id: int, category_id: int,
                          allocated_amount: float,
                          notes: str = None) -> int:
        """Create a budget allocation for a grant application.

        The remaining_amount is initialised to equal the allocated_amount.

        Args:
            grant_application_id: The grant application this allocation
                belongs to.
            category_id: The budget category being allocated.
            allocated_amount: Total amount allocated to this category.
            notes: Optional notes about the allocation.

        Returns:
            The ID of the newly created allocation.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO grant_budget_allocations (
                    grant_application_id, category_id,
                    allocated_amount, spent_amount, committed_amount,
                    remaining_amount, alert_threshold_pct,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, 0, 0, ?, 80, ?, ?, ?)
            ''', (
                grant_application_id, category_id,
                allocated_amount, allocated_amount,
                notes,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            allocation_id = cursor.lastrowid
            log_activity('create', 'grant_budget_allocation', details={
                'allocation_id': allocation_id,
                'grant_application_id': grant_application_id,
                'category_id': category_id,
                'allocated_amount': allocated_amount,
            })
            return allocation_id

    @staticmethod
    def get_allocations(grant_application_id: int) -> List[Dict[str, Any]]:
        """Get all allocations for a grant application with category names.

        Args:
            grant_application_id: The grant application to retrieve
                allocations for.

        Returns:
            A list of allocation dicts, each including the joined
            category name.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT a.*, c.name AS category_name
                FROM grant_budget_allocations a
                JOIN grant_budget_categories c
                    ON a.category_id = c.category_id
                WHERE a.grant_application_id = ?
                ORDER BY c.sort_order
            ''', (grant_application_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_allocation(allocation_id: int) -> Optional[Dict[str, Any]]:
        """Get a single allocation by ID.

        Args:
            allocation_id: The allocation's primary key.

        Returns:
            A dict of the allocation row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM grant_budget_allocations
                WHERE allocation_id = ?
            ''', (allocation_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_allocation(allocation_id: int, **data) -> None:
        """Update allowed fields on an allocation.

        Allowed fields: allocated_amount, alert_threshold_pct, notes.
        If allocated_amount is changed the remaining_amount is
        automatically recalculated.

        Args:
            allocation_id: The allocation to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'allocated_amount', 'alert_threshold_pct', 'notes',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(allocation_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE grant_budget_allocations SET '
                + ', '.join(fields) + ' WHERE allocation_id = ?',
                values)

            if 'allocated_amount' in data:
                GrantBudgetManager._recalculate_allocation(
                    conn, allocation_id)

            log_activity('update', 'grant_budget_allocation', details={
                'allocation_id': allocation_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def _recalculate_allocation(conn, allocation_id: int) -> None:
        """Recalculate the remaining_amount for an allocation.

        Sets remaining = allocated - spent - committed using the
        current values stored on the allocation row.

        This is an internal helper and expects to be called within an
        existing transaction (the caller provides the connection).

        Args:
            conn: An active database connection (inside a transaction).
            allocation_id: The allocation to recalculate.
        """
        conn.execute('''
            UPDATE grant_budget_allocations
            SET remaining_amount = allocated_amount - spent_amount
                                   - committed_amount,
                updated_at = ?
            WHERE allocation_id = ?
        ''', (datetime.now().isoformat(), allocation_id))

    # ==================== EXPENSE MANAGEMENT ====================

    @staticmethod
    def submit_expense(grant_application_id: int, allocation_id: int,
                       category_id: int, description: str,
                       amount: float, expense_date: str,
                       vendor: str, receipt_path: str,
                       invoice_number: str, submitted_by: str,
                       notes: str = None) -> int:
        """Submit a new expense item for review.

        The expense is created with status 'submitted'.

        Args:
            grant_application_id: The grant application the expense
                belongs to.
            allocation_id: The budget allocation to charge against.
            category_id: The budget category for the expense.
            description: Brief description of the expense.
            amount: Monetary amount of the expense.
            expense_date: Date the expense was incurred (ISO format).
            vendor: Name of the vendor or payee.
            receipt_path: File path to the uploaded receipt.
            invoice_number: Vendor invoice or reference number.
            submitted_by: User ID of the person submitting.
            notes: Optional additional notes.

        Returns:
            The ID of the newly created expense item.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO grant_expense_items (
                    grant_application_id, allocation_id, category_id,
                    description, amount, expense_date, vendor,
                    receipt_path, invoice_number, submitted_by,
                    notes, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?)
            ''', (
                grant_application_id, allocation_id, category_id,
                description, amount, expense_date, vendor,
                receipt_path, invoice_number, submitted_by,
                notes,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            expense_id = cursor.lastrowid
            log_activity('create', 'grant_expense_item', details={
                'expense_id': expense_id,
                'grant_application_id': grant_application_id,
                'allocation_id': allocation_id,
                'amount': amount,
                'submitted_by': submitted_by,
            })
            return expense_id

    @staticmethod
    def get_expense(expense_id: int) -> Optional[Dict[str, Any]]:
        """Get a single expense item by ID.

        Args:
            expense_id: The expense item's primary key.

        Returns:
            A dict of the expense row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM grant_expense_items
                WHERE expense_id = ?
            ''', (expense_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_expenses(grant_application_id: int = None,
                     status: str = None,
                     submitted_by: str = None) -> List[Dict[str, Any]]:
        """Get expense items with optional filters.

        Args:
            grant_application_id: Filter by grant application.
            status: Filter by expense status (e.g. 'submitted',
                'approved', 'rejected').
            submitted_by: Filter by the user who submitted the expense.

        Returns:
            A list of expense dicts ordered by expense_date descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM grant_expense_items WHERE 1=1'
            params: list = []

            if grant_application_id:
                query += ' AND grant_application_id = ?'
                params.append(grant_application_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            if submitted_by:
                query += ' AND submitted_by = ?'
                params.append(submitted_by)

            query += ' ORDER BY expense_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_expense(expense_id: int, **data) -> None:
        """Update allowed fields on an expense item.

        Allowed fields: description, amount, expense_date, vendor,
        receipt_path, invoice_number, notes.

        Args:
            expense_id: The expense item to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'description', 'amount', 'expense_date', 'vendor',
            'receipt_path', 'invoice_number', 'notes',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(expense_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE grant_expense_items SET '
                + ', '.join(fields) + ' WHERE expense_id = ?',
                values)
            log_activity('update', 'grant_expense_item', details={
                'expense_id': expense_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def approve_expense(expense_id: int, approved_by: str) -> None:
        """Approve a submitted expense item.

        Sets the status to 'approved', records the approver and
        timestamp, adds the expense amount to the allocation's
        spent_amount, recalculates the allocation's remaining_amount,
        and checks whether any threshold alerts should be created.

        Args:
            expense_id: The expense item to approve.
            approved_by: User ID of the approver.
        """
        with transaction() as conn:
            row = conn.execute('''
                SELECT * FROM grant_expense_items
                WHERE expense_id = ?
            ''', (expense_id,)).fetchone()

            if not row:
                raise ValueError(f"Expense {expense_id} not found")

            expense = dict(row)

            conn.execute('''
                UPDATE grant_expense_items
                SET status = 'approved', approved_by = ?, approved_at = ?,
                    updated_at = ?
                WHERE expense_id = ?
            ''', (
                approved_by, datetime.now().isoformat(),
                datetime.now().isoformat(), expense_id,
            ))

            conn.execute('''
                UPDATE grant_budget_allocations
                SET spent_amount = spent_amount + ?,
                    updated_at = ?
                WHERE allocation_id = ?
            ''', (
                expense['amount'], datetime.now().isoformat(),
                expense['allocation_id'],
            ))

            GrantBudgetManager._recalculate_allocation(
                conn, expense['allocation_id'])

            log_activity('update', 'grant_expense_item', details={
                'expense_id': expense_id, 'action': 'approved',
                'approved_by': approved_by,
                'amount': expense['amount'],
            })

        GrantBudgetManager.check_threshold_alerts(
            expense['grant_application_id'])

    @staticmethod
    def reject_expense(expense_id: int, approved_by: str) -> None:
        """Reject a submitted expense item.

        Sets the status to 'rejected' and records who rejected it.

        Args:
            expense_id: The expense item to reject.
            approved_by: User ID of the person rejecting the expense.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE grant_expense_items
                SET status = 'rejected', approved_by = ?, approved_at = ?,
                    updated_at = ?
                WHERE expense_id = ?
            ''', (
                approved_by, datetime.now().isoformat(),
                datetime.now().isoformat(), expense_id,
            ))
            log_activity('update', 'grant_expense_item', details={
                'expense_id': expense_id, 'action': 'rejected',
                'approved_by': approved_by,
            })

    # ==================== ALERT MANAGEMENT ====================

    @staticmethod
    def get_alerts(grant_application_id: int = None,
                   is_read: bool = None) -> List[Dict[str, Any]]:
        """Get funding alerts with optional filters.

        Args:
            grant_application_id: Filter by grant application.
            is_read: Filter by read status (True/False). If None,
                all alerts are returned.

        Returns:
            A list of alert dicts ordered by created_at descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM grant_funding_alerts WHERE 1=1'
            params: list = []

            if grant_application_id:
                query += ' AND grant_application_id = ?'
                params.append(grant_application_id)

            if is_read is not None:
                query += ' AND is_read = ?'
                params.append(int(is_read))

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_alert(grant_application_id: int, allocation_id: int,
                     alert_type: str, severity: str,
                     message: str) -> int:
        """Create a new funding alert.

        Args:
            grant_application_id: The grant application the alert
                pertains to.
            allocation_id: The allocation that triggered the alert.
            alert_type: Type of alert (e.g. 'threshold_exceeded',
                'over_budget').
            severity: Severity level (e.g. 'info', 'warning',
                'critical').
            message: Human-readable alert message.

        Returns:
            The ID of the newly created alert.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO grant_funding_alerts (
                    grant_application_id, allocation_id,
                    alert_type, severity, message,
                    is_read, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?)
            ''', (
                grant_application_id, allocation_id,
                alert_type, severity, message,
                datetime.now().isoformat(),
            ))
            alert_id = cursor.lastrowid
            log_activity('create', 'grant_funding_alert', details={
                'alert_id': alert_id,
                'grant_application_id': grant_application_id,
                'allocation_id': allocation_id,
                'alert_type': alert_type,
                'severity': severity,
            })
            return alert_id

    @staticmethod
    def mark_alert_read(alert_id: int) -> None:
        """Mark a funding alert as read.

        Args:
            alert_id: The alert to mark as read.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE grant_funding_alerts
                SET is_read = 1
                WHERE alert_id = ?
            ''', (alert_id,))
            log_activity('update', 'grant_funding_alert', details={
                'alert_id': alert_id, 'action': 'mark_read',
            })

    @staticmethod
    def resolve_alert(alert_id: int, resolved_by: str) -> None:
        """Resolve a funding alert.

        Args:
            alert_id: The alert to resolve.
            resolved_by: User ID of the person resolving the alert.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE grant_funding_alerts
                SET is_read = 1, resolved_by = ?, resolved_at = ?
                WHERE alert_id = ?
            ''', (
                resolved_by, datetime.now().isoformat(), alert_id,
            ))
            log_activity('update', 'grant_funding_alert', details={
                'alert_id': alert_id, 'action': 'resolved',
                'resolved_by': resolved_by,
            })

    @staticmethod
    def check_threshold_alerts(
            grant_application_id: int) -> List[int]:
        """Check all allocations for a grant and create alerts where
        the percentage spent meets or exceeds the alert threshold.

        For each allocation, the spent percentage is computed as
        (spent_amount / allocated_amount) * 100. If this value is
        greater than or equal to alert_threshold_pct, a new
        'threshold_exceeded' alert is created.

        Args:
            grant_application_id: The grant application to check.

        Returns:
            A list of newly created alert IDs.
        """
        new_alert_ids: List[int] = []

        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM grant_budget_allocations
                WHERE grant_application_id = ?
                  AND allocated_amount > 0
            ''', (grant_application_id,)).fetchall()

        for row in rows:
            alloc = dict(row)
            spent_pct = (
                alloc['spent_amount'] / alloc['allocated_amount']
            ) * 100

            if spent_pct >= alloc['alert_threshold_pct']:
                severity = 'critical' if spent_pct >= 100 else 'warning'
                message = (
                    f"Allocation {alloc['allocation_id']} has reached "
                    f"{spent_pct:.1f}% of its budget "
                    f"(threshold: {alloc['alert_threshold_pct']}%)"
                )
                alert_id = GrantBudgetManager.create_alert(
                    grant_application_id=grant_application_id,
                    allocation_id=alloc['allocation_id'],
                    alert_type='threshold_exceeded',
                    severity=severity,
                    message=message,
                )
                new_alert_ids.append(alert_id)

        return new_alert_ids

    # ==================== TRANSFER MANAGEMENT ====================

    @staticmethod
    def request_transfer(grant_application_id: int,
                         from_allocation_id: int,
                         to_allocation_id: int,
                         amount: float, reason: str,
                         requested_by: str) -> int:
        """Request a budget transfer between two allocations.

        The transfer is created with status 'pending' and must be
        approved before funds are moved.

        Args:
            grant_application_id: The grant application the transfer
                belongs to.
            from_allocation_id: The source allocation to deduct from.
            to_allocation_id: The destination allocation to add to.
            amount: The monetary amount to transfer.
            reason: Justification for the transfer.
            requested_by: User ID of the person requesting.

        Returns:
            The ID of the newly created transfer request.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO grant_budget_transfers (
                    grant_application_id, from_allocation_id,
                    to_allocation_id, amount, reason,
                    requested_by, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ''', (
                grant_application_id, from_allocation_id,
                to_allocation_id, amount, reason,
                requested_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            transfer_id = cursor.lastrowid
            log_activity('create', 'grant_budget_transfer', details={
                'transfer_id': transfer_id,
                'grant_application_id': grant_application_id,
                'from_allocation_id': from_allocation_id,
                'to_allocation_id': to_allocation_id,
                'amount': amount,
                'requested_by': requested_by,
            })
            return transfer_id

    @staticmethod
    def approve_transfer(transfer_id: int, approved_by: str) -> None:
        """Approve a pending budget transfer.

        Subtracts the transfer amount from the source allocation's
        allocated_amount, adds it to the destination allocation's
        allocated_amount, and recalculates remaining_amount for both.

        Args:
            transfer_id: The transfer to approve.
            approved_by: User ID of the approver.
        """
        with transaction() as conn:
            row = conn.execute('''
                SELECT * FROM grant_budget_transfers
                WHERE transfer_id = ?
            ''', (transfer_id,)).fetchone()

            if not row:
                raise ValueError(f"Transfer {transfer_id} not found")

            transfer = dict(row)

            conn.execute('''
                UPDATE grant_budget_transfers
                SET status = 'approved', approved_by = ?, approved_at = ?,
                    updated_at = ?
                WHERE transfer_id = ?
            ''', (
                approved_by, datetime.now().isoformat(),
                datetime.now().isoformat(), transfer_id,
            ))

            conn.execute('''
                UPDATE grant_budget_allocations
                SET allocated_amount = allocated_amount - ?,
                    updated_at = ?
                WHERE allocation_id = ?
            ''', (
                transfer['amount'], datetime.now().isoformat(),
                transfer['from_allocation_id'],
            ))

            conn.execute('''
                UPDATE grant_budget_allocations
                SET allocated_amount = allocated_amount + ?,
                    updated_at = ?
                WHERE allocation_id = ?
            ''', (
                transfer['amount'], datetime.now().isoformat(),
                transfer['to_allocation_id'],
            ))

            GrantBudgetManager._recalculate_allocation(
                conn, transfer['from_allocation_id'])
            GrantBudgetManager._recalculate_allocation(
                conn, transfer['to_allocation_id'])

            log_activity('update', 'grant_budget_transfer', details={
                'transfer_id': transfer_id, 'action': 'approved',
                'approved_by': approved_by,
                'amount': transfer['amount'],
            })

    @staticmethod
    def reject_transfer(transfer_id: int, approved_by: str) -> None:
        """Reject a pending budget transfer.

        Args:
            transfer_id: The transfer to reject.
            approved_by: User ID of the person rejecting the transfer.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE grant_budget_transfers
                SET status = 'rejected', approved_by = ?, approved_at = ?,
                    updated_at = ?
                WHERE transfer_id = ?
            ''', (
                approved_by, datetime.now().isoformat(),
                datetime.now().isoformat(), transfer_id,
            ))
            log_activity('update', 'grant_budget_transfer', details={
                'transfer_id': transfer_id, 'action': 'rejected',
                'approved_by': approved_by,
            })

    @staticmethod
    def get_transfers(grant_application_id: int = None,
                      status: str = None) -> List[Dict[str, Any]]:
        """Get budget transfers with optional filters.

        Args:
            grant_application_id: Filter by grant application.
            status: Filter by transfer status (e.g. 'pending',
                'approved', 'rejected').

        Returns:
            A list of transfer dicts ordered by created_at descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM grant_budget_transfers WHERE 1=1'
            params: list = []

            if grant_application_id:
                query += ' AND grant_application_id = ?'
                params.append(grant_application_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTING ====================

    @staticmethod
    def get_grant_budget_summary(
            grant_application_id: int) -> Dict[str, Any]:
        """Get a full budget summary for a grant application.

        Returns aggregate totals (allocated, spent, committed,
        remaining) as well as a per-category breakdown.

        Args:
            grant_application_id: The grant application to summarise.

        Returns:
            A dict with keys 'grant_application_id', 'total_allocated',
            'total_spent', 'total_committed', 'total_remaining', and
            'categories' (a list of per-category dicts).
        """
        with get_connection() as conn:
            totals_row = conn.execute('''
                SELECT
                    COALESCE(SUM(allocated_amount), 0) AS total_allocated,
                    COALESCE(SUM(spent_amount), 0)     AS total_spent,
                    COALESCE(SUM(committed_amount), 0)  AS total_committed,
                    COALESCE(SUM(remaining_amount), 0)  AS total_remaining
                FROM grant_budget_allocations
                WHERE grant_application_id = ?
            ''', (grant_application_id,)).fetchone()

            totals = dict(totals_row) if totals_row else {
                'total_allocated': 0,
                'total_spent': 0,
                'total_committed': 0,
                'total_remaining': 0,
            }

            rows = conn.execute('''
                SELECT a.allocation_id, c.name AS category_name,
                       a.allocated_amount, a.spent_amount,
                       a.committed_amount, a.remaining_amount,
                       a.alert_threshold_pct
                FROM grant_budget_allocations a
                JOIN grant_budget_categories c
                    ON a.category_id = c.category_id
                WHERE a.grant_application_id = ?
                ORDER BY c.sort_order
            ''', (grant_application_id,)).fetchall()

            categories = [dict(row) for row in rows]

            return {
                'grant_application_id': grant_application_id,
                'total_allocated': totals['total_allocated'],
                'total_spent': totals['total_spent'],
                'total_committed': totals['total_committed'],
                'total_remaining': totals['total_remaining'],
                'categories': categories,
            }

    @staticmethod
    def get_spending_by_category(
            grant_application_id: int) -> List[Dict[str, Any]]:
        """Get spending breakdown by category for a grant application.

        For each category with an allocation, returns the category
        name, allocated amount, spent amount, and the percentage of
        the allocation that has been spent.

        Args:
            grant_application_id: The grant application to report on.

        Returns:
            A list of dicts with keys 'category_name',
            'allocated_amount', 'spent_amount', and 'spent_pct'.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.name AS category_name,
                       a.allocated_amount,
                       a.spent_amount,
                       CASE
                           WHEN a.allocated_amount > 0
                           THEN ROUND(
                               (a.spent_amount * 100.0
                                / a.allocated_amount), 2)
                           ELSE 0
                       END AS spent_pct
                FROM grant_budget_allocations a
                JOIN grant_budget_categories c
                    ON a.category_id = c.category_id
                WHERE a.grant_application_id = ?
                ORDER BY c.sort_order
            ''', (grant_application_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_spending_timeline(
            grant_application_id: int) -> List[Dict[str, Any]]:
        """Get monthly spending timeline for a grant application.

        Groups approved expenses by month (YYYY-MM) and returns
        the total spending per month.

        Args:
            grant_application_id: The grant application to report on.

        Returns:
            A list of dicts with keys 'month' (YYYY-MM format) and
            'total_spent', ordered chronologically.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT
                    SUBSTR(expense_date, 1, 7) AS month,
                    SUM(amount) AS total_spent
                FROM grant_expense_items
                WHERE grant_application_id = ?
                  AND status = 'approved'
                GROUP BY SUBSTR(expense_date, 1, 7)
                ORDER BY month
            ''', (grant_application_id,)).fetchall()
            return [dict(row) for row in rows]
