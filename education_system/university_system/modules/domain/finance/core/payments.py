from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
import base64
import qrcode

from education_system.university_system.modules.domain.finance.core.finance_context import (
    PAYMENT_GATEWAYS,
    SUPPORTED_CURRENCIES,
    get_connection,
)
from education_system.university_system.modules.domain.finance.core.security_automation import send_email_notification

def manual_rate_update(cursor, base_currency):
    """Manually update exchange rates"""
    print(f"\nManual exchange rate update (base currency: {base_currency})")

    for currency in SUPPORTED_CURRENCIES:
        if currency != base_currency:
            while True:
                try:
                    rate = float(input(f"Enter exchange rate for {base_currency}/{currency}: "))
                    if rate <= 0:
                        print("Exchange rate must be greater than zero.")
                        continue
                    break
                except ValueError:
                    print("Invalid input. Please enter a valid exchange rate.")

            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT OR REPLACE INTO exchange_rates 
            (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (base_currency, currency, rate, current_date, 'manual', current_time))

            print(f"Set {base_currency}/{currency}: {rate}")

def process_stripe_payment(amount, currency, payment_method_id, student_id):
    """Process payment through Stripe"""
    try:
        # In production, use actual Stripe API
        import stripe
        stripe.api_key = PAYMENT_GATEWAYS['stripe']['secret_key']

        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe uses cents
            currency=currency.lower(),
            payment_method=payment_method_id,
            confirmation_method='manual',
            confirm=True,
            metadata={'student_id': student_id}
        )

        if intent.status == 'succeeded':
            return {
                'success': True,
                'transaction_id': intent.id,
                'amount': amount,
                'currency': currency
            }
        else:
            return {
                'success': False,
                'error': f'Payment failed with status: {intent.status}'
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def generate_qr_payment_code(student_id, amount, currency='GBP'):
    """Generate QR code for mobile payments"""
    try:
        # Create payment URL with embedded data
        payment_url = f"https://your-domain.com/pay?student_id={student_id}&amount={amount}&currency={currency}"

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(payment_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64 for web display
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return {
            'qr_code': img_str,
            'payment_url': payment_url,
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        }

    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None
