from .. import *

def send_receipt_email(recipient_email, recipient_name, amount, donation_type, transaction_ref, payment_method):
    """Send a donation receipt email."""
    # Validate email address before attempting to send
    if not recipient_email or not isinstance(recipient_email, str):
        logger.debug("No recipient email provided, skipping receipt")
        return False

    recipient_email = recipient_email.strip()
    if not recipient_email or '@' not in recipient_email:
        logger.debug(f"Invalid email address: {recipient_email}, skipping receipt")
        return False

    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email

        from education_system.systems.university.infrastructure.email.template_utils import render_template
        subject, body = render_template("campus_services/community/church_donation_receipt", {
            "recipient_name": recipient_name,
            "transaction_ref": transaction_ref,
            "donation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "donation_type": donation_type,
            "payment_method": payment_method,
            "amount": f"{amount:.2f}"
        })
        if not subject or not body:
            raise RuntimeError("church_donation_receipt template is empty")
        result = send_email(recipient_email, subject, body)
        if result:
            logger.info(f"Donation receipt sent to {recipient_email}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to send receipt email: {e}")
        return False
