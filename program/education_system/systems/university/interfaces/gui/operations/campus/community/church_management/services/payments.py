from .. import *

def get_student_account_balance(student_id):
    """Get student's finance account balance."""
    try:
        from education_system.systems.university.infrastructure.utils.finance_integration import get_student_finance_account_balance
        return get_student_finance_account_balance(student_id)
    except ImportError:
        return None

def process_student_payment(student_id, amount, description, transaction_ref):
    """Process payment from student account."""
    try:
        from education_system.systems.university.infrastructure.utils.finance_integration import process_student_finance_account_payment
        return process_student_finance_account_payment(
            student_id=student_id,
            amount=amount,
            description=description,
            transaction_source="Church",
            transaction_ref=transaction_ref
        )
    except ImportError:
        return {'success': False, 'message': 'Finance integration not available'}

def record_revenue(student_id, amount, category, transaction_ref, payment_method, notes=None):
    """Record revenue to the central finance system."""
    try:
        from education_system.systems.university.infrastructure.utils.finance_integration import record_revenue_to_finance
        return record_revenue_to_finance(
            student_id=student_id or "EXTERNAL",
            amount=amount,
            revenue_category=category,
            transaction_source="Church",
            transaction_ref=transaction_ref,
            payment_method=payment_method,
            notes=notes
        )
    except ImportError:
        logger.warning("Finance integration not available for revenue recording")
        return None
