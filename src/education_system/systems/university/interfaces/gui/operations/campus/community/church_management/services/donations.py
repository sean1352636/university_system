from .payments import process_student_payment, record_revenue

def record_donation_payment(student_id, amount, description, transaction_ref, payment_method):
    process_student_payment(student_id, amount, description, transaction_ref)
    return record_revenue(student_id, amount, "Church Donation", transaction_ref, payment_method)
