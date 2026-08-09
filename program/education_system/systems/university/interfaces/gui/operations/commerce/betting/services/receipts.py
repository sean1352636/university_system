"""Receipt mixin."""

from ..shared import *


class ReceiptMixin:
    def send_withdrawal_receipt(self, amount: float, method: str, transaction_id: int,
                                old_balance: float = None, new_balance: float = None,
                                withdrawal_ref: str = None):
        """Send withdrawal confirmation email"""
        user_email = self.user_email or self.account.get('email', '')
        if not EMAIL_AVAILABLE or not user_email or '@' not in user_email:
            logger.info(f"Withdrawal receipt email skipped - invalid email: {user_email}")
            return

        # Build conditional sections
        withdrawal_ref_line = f"Withdrawal Reference:  {withdrawal_ref}" if withdrawal_ref else ""

        student_account_section = ""
        if method == 'Student Finance Account' and old_balance is not None and new_balance is not None:
            student_account_section = f"""
------------------------------------------------------------
            STUDENT FINANCE ACCOUNT
------------------------------------------------------------
Previous Balance:      GBP {old_balance:.2f}
Withdrawal Amount:     GBP {amount:.2f}
New Balance:           GBP {new_balance:.2f}
"""

        method_note = "The funds have been added to your student finance account." if method == 'Student Finance Account' else f"Your funds will be transferred to your {method}."

        # Try to render from template
        subject = None
        body = None
        if render_template:
            subject, body = render_template('commerce/betting/withdrawal_confirmation', {
                'user_name': self.user_name,
                'transaction_id': transaction_id,
                'withdrawal_ref_line': withdrawal_ref_line,
                'withdrawal_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'amount': f"GBP {amount:.2f}",
                'method': method,
                'betting_balance': f"GBP {self.account['balance']:.2f}",
                'student_account_section': student_account_section,
                'method_note': method_note
            })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Withdrawal Confirmation - GBP {amount:.2f}"
            body = f"""
Dear {self.user_name},

This confirms your withdrawal from your University Betting Shop account.

{'='*60}
                    WITHDRAWAL CONFIRMATION
{'='*60}

Transaction ID:        {transaction_id}
{withdrawal_ref_line}
Date:                  {datetime.now().strftime('%Y-%m-%d %H:%M')}
Amount:                GBP {amount:.2f}
Withdrawal Method:     {method}
Betting Account Balance: GBP {self.account['balance']:.2f}
{student_account_section}
{'='*60}

Your withdrawal has been processed successfully.
{method_note}

Please gamble responsibly.

University Betting Shop

---
This is an automated message. Please do not reply.
"""

        # Send email
        try:
            result = send_email(
                recipient_email=user_email,
                subject=subject,
                body=body
            )

            if result:
                logger.info(f"Withdrawal receipt email sent to {user_email}")
            else:
                logger.warning(f"Failed to send withdrawal receipt email to {user_email}")

        except Exception as e:
            logger.error(f"Error sending withdrawal receipt email: {e}")

    def send_deposit_receipt(self, amount: float, method: str, transaction_id: int):
        """Send deposit receipt email"""
        user_email = self.user_email or self.account.get('email', '')
        if not EMAIL_AVAILABLE or not user_email or '@' not in user_email:
            logger.info(f"Deposit receipt email skipped - invalid email: {user_email}")
            return

        # Try to render from template
        subject = None
        body = None
        if render_template:
            subject, body = render_template('commerce/betting/deposit_confirmation', {
                'user_name': self.user_name,
                'transaction_id': transaction_id,
                'deposit_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'amount': f"GBP {amount:.2f}",
                'method': method,
                'new_balance': f"GBP {self.account['balance'] + amount:.2f}"
            })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Deposit Confirmation - GBP {amount:.2f}"
            body = f"""
Dear {self.user_name},

This confirms your deposit to your University Betting Shop account.

{'='*50}
                    DEPOSIT RECEIPT
{'='*50}

Transaction ID:   {transaction_id}
Date:             {datetime.now().strftime('%Y-%m-%d %H:%M')}
Amount:           GBP {amount:.2f}
Payment Method:   {method}
New Balance:      GBP {self.account['balance'] + amount:.2f}

{'='*50}

Please gamble responsibly.

University Betting Shop
"""

        send_email(
            recipient_email=user_email,
            subject=subject,
            body=body
        )
        logger.info(f"Deposit receipt email sent to {user_email}")

    def send_bet_receipt(self, bet_id: int, bet_type: str, stake: float):
        """Send bet receipt email"""
        user_email = self.user_email or self.account.get('email', '')
        if not EMAIL_AVAILABLE or not user_email or '@' not in user_email:
            logger.info(f"Bet receipt email skipped - invalid email: {user_email}")
            return

        # Try to render from template
        subject = None
        body = None
        if render_template:
            subject, body = render_template('commerce/betting/bet_confirmation', {
                'user_name': self.user_name,
                'bet_id': bet_id,
                'bet_type': f"{bet_type.title()} Bet",
                'bet_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'stake': f"GBP {stake:.2f}"
            })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Bet Confirmation - #{bet_id}"
            body = f"""
Dear {self.user_name},

This confirms your bet placement.

{'='*50}
                    BET RECEIPT
{'='*50}

Bet ID:           {bet_id}
Type:             {bet_type.title()} Bet
Date:             {datetime.now().strftime('%Y-%m-%d %H:%M')}
Stake:            GBP {stake:.2f}

{'='*50}

Good luck! Please gamble responsibly.

University Betting Shop
"""

        send_email(
            recipient_email=user_email,
            subject=subject,
            body=body
        )
        logger.info(f"Bet receipt email sent to {user_email}")
