"""
Expense Manager - Expense claims and reimbursements management.

Provides functionality for:
- Submit expense claims with receipts
- Multi-level approval workflow
- Category-based limits
- Reimbursement tracking
- Monthly expense reports
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class ExpenseManager:
    """Manager for expense claims and reimbursements."""

    # ==================== EXPENSE CATEGORIES ====================

    @staticmethod
    def get_categories(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all expense categories."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM expense_categories
                    WHERE is_active = 1
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM expense_categories ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_category(category_id: int) -> Optional[Dict[str, Any]]:
        """Get a category by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM expense_categories WHERE category_id = ?
            ''', (category_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_category(**data) -> int:
        """Create a new expense category."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO expense_categories (
                    name, description, max_amount, requires_receipt,
                    requires_approval, approval_threshold, gl_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('name'),
                data.get('description'),
                data.get('max_amount'),
                data.get('requires_receipt', True),
                data.get('requires_approval', True),
                data.get('approval_threshold'),
                data.get('gl_code'),
            ))
            category_id = cursor.lastrowid
            log_activity('create', 'expense_category', details={'category_id': category_id})
            return category_id

    # ==================== EXPENSE CLAIMS CRUD ====================

    @staticmethod
    def create_claim(user_id: str, **data) -> int:
        """Create a new expense claim."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO expense_claims (
                    user_id, category_id, amount, currency, description,
                    expense_date, receipt_path, receipt_number, project_code,
                    cost_center, status, notes, mileage_miles, mileage_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('category_id'),
                data.get('amount'),
                data.get('currency', 'GBP'),
                data.get('description'),
                data.get('expense_date'),
                data.get('receipt_path'),
                data.get('receipt_number'),
                data.get('project_code'),
                data.get('cost_center'),
                data.get('status', 'draft'),
                data.get('notes'),
                data.get('mileage_miles'),
                data.get('mileage_rate'),
            ))
            claim_id = cursor.lastrowid
            log_activity('create', 'expense_claim', details={
                'claim_id': claim_id, 'user_id': user_id, 'amount': data.get('amount')
            })
            return claim_id

    @staticmethod
    def get_claim(claim_id: int) -> Optional[Dict[str, Any]]:
        """Get a claim by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT c.*, cat.name as category_name
                FROM expense_claims c
                LEFT JOIN expense_categories cat ON c.category_id = cat.category_id
                WHERE c.claim_id = ?
            ''', (claim_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_claims(user_id: str, status: str = None,
                       from_date: str = None, to_date: str = None) -> List[Dict[str, Any]]:
        """Get all claims for a user with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT c.*, cat.name as category_name
                FROM expense_claims c
                LEFT JOIN expense_categories cat ON c.category_id = cat.category_id
                WHERE c.user_id = ?
            '''
            params = [user_id]

            if status:
                query += ' AND c.status = ?'
                params.append(status)

            if from_date:
                query += ' AND c.expense_date >= ?'
                params.append(from_date)

            if to_date:
                query += ' AND c.expense_date <= ?'
                params.append(to_date)

            query += ' ORDER BY c.expense_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_claim(claim_id: int, **data) -> bool:
        """Update an expense claim."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('claim_id', 'created_at', 'user_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(claim_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE expense_claims SET ' + ', '.join(fields) + ' WHERE claim_id = ?',
                values)
            log_activity('update', 'expense_claim', details={
                'claim_id': claim_id, 'updated_fields': list(data.keys())
            })
            return True

    @staticmethod
    def delete_claim(claim_id: int) -> bool:
        """Delete a draft claim."""
        with transaction() as conn:
            # Only allow deletion of draft claims
            conn.execute('''
                DELETE FROM expense_claims
                WHERE claim_id = ? AND status = 'draft'
            ''', (claim_id,))
            log_activity('delete', 'expense_claim', details={'claim_id': claim_id})
            return True

    @staticmethod
    def submit_claim(claim_id: int) -> bool:
        """Submit a claim for approval."""
        with transaction() as conn:
            conn.execute('''
                UPDATE expense_claims
                SET status = 'submitted', submitted_date = ?, updated_at = ?
                WHERE claim_id = ? AND status = 'draft'
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), claim_id))
            log_activity('update', 'expense_claim', details={
                'claim_id': claim_id, 'action': 'submitted'
            })
            return True

    # ==================== APPROVAL WORKFLOW ====================

    @staticmethod
    def get_pending_approvals(approver_id: str = None) -> List[Dict[str, Any]]:
        """Get claims pending approval."""
        with get_connection() as conn:
            query = '''
                SELECT c.*, cat.name as category_name, p.employee_id
                FROM expense_claims c
                LEFT JOIN expense_categories cat ON c.category_id = cat.category_id
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                WHERE c.status = 'submitted'
            '''
            params = []

            if approver_id:
                # Get claims from staff where this person is manager
                query += '''
                    AND c.user_id IN (
                        SELECT user_id FROM staff_profiles WHERE manager_id = ?
                    )
                '''
                params.append(approver_id)

            query += ' ORDER BY c.submitted_date ASC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_claim(claim_id: int, approver_id: str,
                     amount_approved: float = None, comments: str = None) -> bool:
        """Approve an expense claim."""
        with transaction() as conn:
            # Get claim details
            claim = conn.execute('''
                SELECT * FROM expense_claims WHERE claim_id = ?
            ''', (claim_id,)).fetchone()

            if not claim:
                return False

            # Create approval record
            conn.execute('''
                INSERT INTO expense_approvals (
                    claim_id, approver_id, decision, comments,
                    decision_date, amount_approved
                ) VALUES (?, ?, 'approved', ?, ?, ?)
            ''', (
                claim_id, approver_id, comments,
                datetime.now().isoformat(),
                amount_approved or claim['amount']
            ))

            # Update claim status
            conn.execute('''
                UPDATE expense_claims
                SET status = 'approved', updated_at = ?
                WHERE claim_id = ?
            ''', (datetime.now().isoformat(), claim_id))

            log_activity('update', 'expense_claim', details={
                'claim_id': claim_id, 'action': 'approved', 'approver': approver_id
            })
            return True

    @staticmethod
    def reject_claim(claim_id: int, approver_id: str, comments: str = None, reason: str = None) -> bool:
        """Reject an expense claim."""
        if comments is None and reason is not None:
            comments = reason
        with transaction() as conn:
            # Create approval record
            conn.execute('''
                INSERT INTO expense_approvals (
                    claim_id, approver_id, decision, comments, decision_date
                ) VALUES (?, ?, 'rejected', ?, ?)
            ''', (claim_id, approver_id, comments, datetime.now().isoformat()))

            # Update claim status
            conn.execute('''
                UPDATE expense_claims
                SET status = 'rejected', updated_at = ?
                WHERE claim_id = ?
            ''', (datetime.now().isoformat(), claim_id))

            log_activity('update', 'expense_claim', details={
                'claim_id': claim_id, 'action': 'rejected', 'approver': approver_id
            })
            return True

    @staticmethod
    def return_for_revision(claim_id: int, approver_id: str, comments: str) -> bool:
        """Return a claim for revision."""
        with transaction() as conn:
            conn.execute('''
                INSERT INTO expense_approvals (
                    claim_id, approver_id, decision, comments, decision_date
                ) VALUES (?, ?, 'returned', ?, ?)
            ''', (claim_id, approver_id, comments, datetime.now().isoformat()))

            conn.execute('''
                UPDATE expense_claims
                SET status = 'returned', updated_at = ?
                WHERE claim_id = ?
            ''', (datetime.now().isoformat(), claim_id))

            log_activity('update', 'expense_claim', details={
                'claim_id': claim_id, 'action': 'returned_for_revision'
            })
            return True

    @staticmethod
    def get_claim_approvals(claim_id: int) -> List[Dict[str, Any]]:
        """Get approval history for a claim."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM expense_approvals
                WHERE claim_id = ?
                ORDER BY decision_date DESC
            ''', (claim_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== REIMBURSEMENTS ====================

    @staticmethod
    def create_reimbursement(claim_id: int, **data) -> int:
        """Create a reimbursement for an approved claim."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO reimbursements (
                    claim_id, amount, currency, payment_date, payment_method,
                    reference_number, bank_account_last4, status, processed_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                claim_id,
                data.get('amount'),
                data.get('currency', 'GBP'),
                data.get('payment_date'),
                data.get('payment_method'),
                data.get('reference_number'),
                data.get('bank_account_last4'),
                data.get('status', 'pending'),
                data.get('processed_by'),
                data.get('notes'),
            ))
            reimbursement_id = cursor.lastrowid

            # Update claim status
            conn.execute('''
                UPDATE expense_claims SET status = 'reimbursed', updated_at = ?
                WHERE claim_id = ?
            ''', (datetime.now().isoformat(), claim_id))

            log_activity('create', 'reimbursement', details={
                'reimbursement_id': reimbursement_id, 'claim_id': claim_id
            })
            return reimbursement_id

    @staticmethod
    def get_reimbursement(reimbursement_id: int) -> Optional[Dict[str, Any]]:
        """Get a reimbursement by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT r.*, c.user_id, c.description as claim_description
                FROM reimbursements r
                JOIN expense_claims c ON r.claim_id = c.claim_id
                WHERE r.reimbursement_id = ?
            ''', (reimbursement_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_pending_reimbursements() -> List[Dict[str, Any]]:
        """Get all pending reimbursements."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.*, cat.name as category_name
                FROM expense_claims c
                LEFT JOIN expense_categories cat ON c.category_id = cat.category_id
                WHERE c.status = 'approved'
                ORDER BY c.submitted_date ASC
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def process_reimbursement(reimbursement_id: int, processed_by: str = None,
                              payment_method: str = None, reference_number: str = None,
                              amount: float = None, **kwargs):
        """Mark a reimbursement as processed or create one when needed."""
        # If amount is provided, treat the first argument as claim_id and create a reimbursement.
        if amount is not None:
            return ExpenseManager.create_reimbursement(
                reimbursement_id,
                amount=amount,
                payment_date=datetime.now().isoformat(),
                payment_method=payment_method,
                reference_number=reference_number,
                status='processed',
                processed_by=processed_by,
            )

        # Otherwise, update an existing reimbursement record.
        with transaction() as conn:
            conn.execute('''
                UPDATE reimbursements
                SET status = 'processed', payment_date = ?, processed_by = ?,
                    payment_method = ?, reference_number = ?
                WHERE reimbursement_id = ?
            ''', (datetime.now().isoformat(), processed_by, payment_method,
                  reference_number, reimbursement_id))

            log_activity('update', 'reimbursement', details={
                'reimbursement_id': reimbursement_id, 'action': 'processed'
            })
            return True

    # ==================== EXPENSE POLICIES ====================

    @staticmethod
    def get_active_policy() -> Optional[Dict[str, Any]]:
        """Get the active expense policy."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM expense_policies
                WHERE is_active = 1
                ORDER BY effective_from DESC LIMIT 1
            ''').fetchone()
            return dict(row) if row else None

    @staticmethod
    def validate_claim(claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a claim against the expense policy."""
        result = {'valid': True, 'warnings': [], 'errors': []}

        policy = ExpenseManager.get_active_policy()
        if not policy:
            return result

        amount = claim_data.get('amount', 0)
        category_id = claim_data.get('category_id')

        # Check single claim limit
        if policy.get('max_single_claim') and amount > policy['max_single_claim']:
            result['errors'].append(
                f"Amount exceeds maximum single claim limit of {policy['max_single_claim']}"
            )
            result['valid'] = False

        # Check if pre-approval is needed
        if policy.get('requires_pre_approval_above') and amount > policy['requires_pre_approval_above']:
            result['warnings'].append(
                f"Claims over {policy['requires_pre_approval_above']} require pre-approval"
            )

        # Check category limits
        if category_id:
            category = ExpenseManager.get_category(category_id)
            if category and category.get('max_amount') and amount > category['max_amount']:
                result['errors'].append(
                    f"Amount exceeds category limit of {category['max_amount']}"
                )
                result['valid'] = False

        return result

    # ==================== REPORTING ====================

    @staticmethod
    def get_expense_statistics(user_id: str = None, period: str = None) -> Dict[str, Any]:
        """Get expense statistics."""
        with get_connection() as conn:
            stats = {}
            params = []

            where_clause = '1=1'
            if user_id:
                where_clause += ' AND user_id = ?'
                params.append(user_id)

            if period:
                where_clause += ' AND expense_date LIKE ?'
                params.append(f'{period}%')

            # Total claimed
            row = conn.execute(
                'SELECT SUM(amount) as total, COUNT(*) as count'
                ' FROM expense_claims WHERE ' + where_clause,
                params).fetchone()
            stats['total_claimed'] = row['total'] or 0
            stats['claim_count'] = row['count'] or 0
            # Backwards-compatible aliases expected by tests
            stats['total_amount'] = stats['total_claimed']
            stats['total_claims'] = stats['claim_count']

            # By status
            rows = conn.execute(
                'SELECT status, SUM(amount) as total, COUNT(*) as count'
                ' FROM expense_claims WHERE ' + where_clause +
                ' GROUP BY status',
                params).fetchall()
            stats['by_status'] = {row['status']: {
                'total': row['total'], 'count': row['count']
            } for row in rows}

            # By category
            cat_where = where_clause.replace('user_id', 'c.user_id').replace('expense_date', 'c.expense_date')
            rows = conn.execute(
                'SELECT cat.name, SUM(c.amount) as total, COUNT(*) as count'
                ' FROM expense_claims c'
                ' JOIN expense_categories cat ON c.category_id = cat.category_id'
                ' WHERE ' + cat_where +
                ' GROUP BY cat.name',
                params).fetchall()
            stats['by_category'] = {row['name']: {
                'total': row['total'], 'count': row['count']
            } for row in rows}

            return stats

    @staticmethod
    def get_monthly_report(year: int, month: int, department: str = None) -> Dict[str, Any]:
        """Get monthly expense report."""
        with get_connection() as conn:
            period = f'{year}-{month:02d}'

            query = '''
                SELECT c.*, cat.name as category_name, p.department, p.employee_id
                FROM expense_claims c
                LEFT JOIN expense_categories cat ON c.category_id = cat.category_id
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                WHERE c.expense_date LIKE ?
            '''
            params = [f'{period}%']

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' ORDER BY c.expense_date'
            rows = conn.execute(query, params).fetchall()

            claims = [dict(row) for row in rows]
            total = sum(c['amount'] for c in claims)

            return {
                'period': period,
                'claims': claims,
                'total_amount': total,
                'claim_count': len(claims)
            }

    @staticmethod
    def get_user_expense_summary(user_id: str, year: int = None) -> Dict[str, Any]:
        """Get expense summary for a user."""
        with get_connection() as conn:
            if not year:
                year = datetime.now().year

            period_start = f'{year}-01-01'
            period_end = f'{year}-12-31'

            # Total for year
            row = conn.execute('''
                SELECT SUM(amount) as total, COUNT(*) as count
                FROM expense_claims
                WHERE user_id = ?
                AND expense_date BETWEEN ? AND ?
                AND status IN ('approved', 'reimbursed')
            ''', (user_id, period_start, period_end)).fetchone()

            # Monthly breakdown
            rows = conn.execute('''
                SELECT strftime('%Y-%m', expense_date) as month,
                       SUM(amount) as total, COUNT(*) as count
                FROM expense_claims
                WHERE user_id = ?
                AND expense_date BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', expense_date)
                ORDER BY month
            ''', (user_id, period_start, period_end)).fetchall()

            return {
                'year': year,
                'total': row['total'] or 0,
                'count': row['count'] or 0,
                'monthly': [dict(r) for r in rows]
            }

    # ==================== ADDITIONAL METHODS FOR CLI COMPATIBILITY ====================

    @staticmethod
    def get_all_categories() -> List[Dict[str, Any]]:
        """Get all expense categories (alias for get_categories)."""
        return ExpenseManager.get_categories(active_only=False)

    @staticmethod
    def update_category(category_id: int, **data) -> bool:
        """Update an expense category."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('category_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        values.append(category_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE expense_categories SET ' + ', '.join(fields) + ' WHERE category_id = ?',
                values)
            log_activity('update', 'expense_category', details={'category_id': category_id})
            return True

    @staticmethod
    def search_claims(status: str = None, category_id: int = None,
                     user_id: str = None, start_date: str = None,
                     end_date: str = None) -> List[Dict[str, Any]]:
        """Search expense claims with filters."""
        with get_connection() as conn:
            query = '''
                SELECT c.*, cat.name as category_name
                FROM expense_claims c
                LEFT JOIN expense_categories cat ON c.category_id = cat.category_id
                WHERE 1=1
            '''
            params = []

            if status:
                query += ' AND c.status = ?'
                params.append(status)

            if category_id:
                query += ' AND c.category_id = ?'
                params.append(category_id)

            if user_id:
                query += ' AND c.user_id = ?'
                params.append(user_id)

            if start_date:
                query += ' AND c.expense_date >= ?'
                params.append(start_date)

            if end_date:
                query += ' AND c.expense_date <= ?'
                params.append(end_date)

            query += ' ORDER BY c.expense_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_all_policies() -> List[Dict[str, Any]]:
        """Get all expense policies."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM expense_policies ORDER BY is_active DESC, name
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_policy(**data) -> int:
        """Create a new expense policy."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO expense_policies (
                    name, description, max_daily_amount, max_single_claim,
                    requires_pre_approval_above, mileage_rate, subsistence_rate,
                    applies_to_roles, effective_from, effective_to, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('name'),
                data.get('description'),
                data.get('max_daily_amount'),
                data.get('max_single_claim') or data.get('max_single_expense'),
                data.get('requires_pre_approval_above'),
                data.get('mileage_rate', 0.45),
                data.get('subsistence_rate'),
                data.get('applies_to_roles'),
                data.get('effective_from'),
                data.get('effective_to'),
                data.get('is_active', True),
            ))
            policy_id = cursor.lastrowid
            log_activity('create', 'expense_policy', details={'policy_id': policy_id})
            return policy_id

    @staticmethod
    def update_policy(policy_id: int, **data) -> bool:
        """Update an expense policy."""
        if not data:
            return False

        # Map CLI field names to schema field names
        if 'max_single_expense' in data and 'max_single_claim' not in data:
            data['max_single_claim'] = data.pop('max_single_expense')
        if 'max_monthly_total' in data and 'max_daily_amount' not in data:
            data['max_daily_amount'] = data.pop('max_monthly_total')

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('policy_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        values.append(policy_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE expense_policies SET ' + ', '.join(fields) + ' WHERE policy_id = ?',
                values)
            log_activity('update', 'expense_policy', details={'policy_id': policy_id})
            return True

    @staticmethod
    def get_claims_for_reimbursement() -> List[Dict[str, Any]]:
        """Get approved claims ready for reimbursement (alias)."""
        return ExpenseManager.get_pending_reimbursements()

    @staticmethod
    def check_policy_compliance() -> List[Dict[str, Any]]:
        """Check for policy compliance violations."""
        violations = []
        policy = ExpenseManager.get_active_policy()

        if not policy:
            return violations

        with get_connection() as conn:
            # Check for claims over single limit
            if policy.get('max_single_claim'):
                rows = conn.execute('''
                    SELECT user_id, claim_id, amount
                    FROM expense_claims
                    WHERE amount > ? AND status NOT IN ('rejected', 'cancelled')
                ''', (policy['max_single_claim'],)).fetchall()
                for row in rows:
                    violations.append({
                        'user_id': row['user_id'],
                        'claim_id': row['claim_id'],
                        'violation_type': 'Over single claim limit',
                        'details': f"Claim £{row['amount']:.2f} exceeds limit of £{policy['max_single_claim']:.2f}"
                    })

            # Check for high frequency claims
            rows = conn.execute('''
                SELECT user_id, COUNT(*) as claim_count, SUM(amount) as total
                FROM expense_claims
                WHERE expense_date >= date('now', '-30 days')
                AND status NOT IN ('rejected', 'cancelled')
                GROUP BY user_id
                HAVING claim_count > 10 OR total > 2000
            ''').fetchall()
            for row in rows:
                violations.append({
                    'user_id': row['user_id'],
                    'violation_type': 'High frequency/volume',
                    'details': f"{row['claim_count']} claims totaling £{row['total']:.2f} in 30 days"
                })

        return violations
