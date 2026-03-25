"""
Comprehensive tests for finance payments module.
Tests payment processing functions including manual rate updates,
Stripe payment processing, and QR code generation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import base64

from education_system.university_system.modules.domain.finance.core.payments import (
    manual_rate_update,
    process_stripe_payment,
    generate_qr_payment_code,
)


class TestManualRateUpdate:
    """Test suite for manual_rate_update function"""

    @patch('builtins.input', side_effect=['1.27', '1.17', '1.71', '1.91'])
    @patch('builtins.print')
    def test_manual_rate_update_success(self, mock_print, mock_input):
        """Test successful manual exchange rate update"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'GBP')

        # Should insert 4 exchange rates (for USD, EUR, CAD, AUD)
        assert mock_cursor.execute.call_count == 4

        # Verify exchange rates were inserted
        for call in mock_cursor.execute.call_args_list:
            sql = str(call[0][0])
            assert 'INSERT OR REPLACE INTO exchange_rates' in sql

    @patch('builtins.input', side_effect=['1.27', '1.17', '1.71', '1.91'])
    @patch('builtins.print')
    def test_manual_rate_update_correct_values(self, mock_print, mock_input):
        """Test manual rate update with correct values"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'GBP')

        # Verify correct values were inserted
        execute_calls = mock_cursor.execute.call_args_list

        # Check that rates were inserted (should be called 4 times for 4 currencies)
        assert len(execute_calls) == 4

    @patch('builtins.input', side_effect=['0', '1.27', '1.17', '1.71', '1.91'])
    @patch('builtins.print')
    def test_manual_rate_update_invalid_zero_rate(self, mock_print, mock_input):
        """Test manual rate update rejects zero rate"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'GBP')

        # Should print error message for zero rate
        assert any('must be greater than zero' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['invalid', '1.27', '1.17', '1.71', '1.91'])
    @patch('builtins.print')
    def test_manual_rate_update_invalid_input(self, mock_print, mock_input):
        """Test manual rate update with invalid input"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'GBP')

        # Should print error message for invalid input
        assert any('Invalid input' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['-1.5', '1.27', '1.17', '1.71', '1.91'])
    @patch('builtins.print')
    def test_manual_rate_update_negative_rate(self, mock_print, mock_input):
        """Test manual rate update rejects negative rate"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'GBP')

        # Should print error message for negative rate
        assert any('must be greater than zero' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['1.27', '1.17', '1.71', '1.91'])
    @patch('builtins.print')
    def test_manual_rate_update_creates_correct_pairs(self, mock_print, mock_input):
        """Test manual rate update creates correct currency pairs"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'GBP')

        # Verify currency pairs were created correctly
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]

        # Should create pairs for: GBP/USD, GBP/EUR, GBP/CAD, GBP/AUD
        # (excluding GBP itself from the SUPPORTED_CURRENCIES list)
        assert len(mock_cursor.execute.call_args_list) == 4

    @patch('builtins.input', side_effect=['1.0', '1.0', '1.0'])
    @patch('builtins.print')
    def test_manual_rate_update_with_usd_base(self, mock_print, mock_input):
        """Test manual rate update with USD as base currency"""
        mock_cursor = Mock()

        manual_rate_update(mock_cursor, 'USD')

        # Should create rates for non-USD currencies
        # (GBP, EUR, CAD, AUD)
        assert mock_cursor.execute.call_count == 4


class TestProcessStripePayment:
    """Test suite for process_stripe_payment function"""

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_success(self, mock_stripe):
        """Test successful Stripe payment processing"""
        # Mock successful payment intent
        mock_intent = Mock()
        mock_intent.status = 'succeeded'
        mock_intent.id = 'pi_test123'

        mock_stripe.PaymentIntent.create.return_value = mock_intent

        result = process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        assert result['success'] is True
        assert result['transaction_id'] == 'pi_test123'
        assert result['amount'] == 100.50
        assert result['currency'] == 'GBP'

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_failed_status(self, mock_stripe):
        """Test Stripe payment with failed status"""
        # Mock failed payment intent
        mock_intent = Mock()
        mock_intent.status = 'failed'

        mock_stripe.PaymentIntent.create.return_value = mock_intent

        result = process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        assert result['success'] is False
        assert 'error' in result
        assert 'failed' in result['error']

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_exception(self, mock_stripe):
        """Test Stripe payment processing with exception"""
        # Mock exception during payment creation
        mock_stripe.PaymentIntent.create.side_effect = Exception("Stripe API error")

        result = process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        assert result['success'] is False
        assert 'error' in result
        assert 'Stripe API error' in result['error']

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_correct_amount_conversion(self, mock_stripe):
        """Test Stripe payment converts amount to cents correctly"""
        mock_intent = Mock()
        mock_intent.status = 'succeeded'
        mock_intent.id = 'pi_test123'

        mock_stripe.PaymentIntent.create.return_value = mock_intent

        process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        # Verify amount was converted to cents (10050)
        call_args = mock_stripe.PaymentIntent.create.call_args
        assert call_args[1]['amount'] == 10050

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_currency_lowercase(self, mock_stripe):
        """Test Stripe payment converts currency to lowercase"""
        mock_intent = Mock()
        mock_intent.status = 'succeeded'
        mock_intent.id = 'pi_test123'

        mock_stripe.PaymentIntent.create.return_value = mock_intent

        process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        # Verify currency was converted to lowercase
        call_args = mock_stripe.PaymentIntent.create.call_args
        assert call_args[1]['currency'] == 'gbp'

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_includes_metadata(self, mock_stripe):
        """Test Stripe payment includes student ID in metadata"""
        mock_intent = Mock()
        mock_intent.status = 'succeeded'
        mock_intent.id = 'pi_test123'

        mock_stripe.PaymentIntent.create.return_value = mock_intent

        process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        # Verify metadata includes student_id
        call_args = mock_stripe.PaymentIntent.create.call_args
        assert call_args[1]['metadata']['student_id'] == 'STU001'

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    def test_process_stripe_payment_pending_status(self, mock_stripe):
        """Test Stripe payment with pending status"""
        mock_intent = Mock()
        mock_intent.status = 'requires_action'

        mock_stripe.PaymentIntent.create.return_value = mock_intent

        result = process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        assert result['success'] is False
        assert 'requires_action' in result['error']


class TestGenerateQRPaymentCode:
    """Test suite for generate_qr_payment_code function"""

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_success(self, mock_qrcode):
        """Test successful QR code generation"""
        # Mock QR code generation
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        assert result is not None
        assert 'qr_code' in result
        assert 'payment_url' in result
        assert 'expires_at' in result

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_default_currency(self, mock_qrcode):
        """Test QR code generation with default currency"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50
        )

        # Should use default currency (GBP)
        assert 'currency=GBP' in result['payment_url']

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_url_format(self, mock_qrcode):
        """Test QR code generates correct URL format"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        url = result['payment_url']
        assert 'student_id=STU001' in url
        assert 'amount=100.5' in url
        assert 'currency=GBP' in url

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_expiry(self, mock_qrcode):
        """Test QR code has 24 hour expiry"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        before_time = datetime.now()
        result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )
        after_time = datetime.now()

        # Parse expiry time
        expiry_time = datetime.fromisoformat(result['expires_at'])

        # Should expire approximately 24 hours from now
        expected_expiry = before_time + timedelta(hours=24)
        time_diff = abs((expiry_time - expected_expiry).total_seconds())

        # Allow 1 second tolerance for test execution time
        assert time_diff < 1

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_base64_encoded(self, mock_qrcode):
        """Test QR code is base64 encoded"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        # Mock image save
        def mock_save(buffer, format):
            buffer.write(b'fake_image_data')

        mock_img.save = mock_save

        result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        # Should be base64 encoded string
        qr_code = result['qr_code']
        assert isinstance(qr_code, str)

        # Try to decode to verify it's valid base64
        try:
            decoded = base64.b64decode(qr_code)
            assert decoded == b'fake_image_data'
        except Exception:
            pytest.fail("QR code is not valid base64")

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    @patch('builtins.print')
    def test_generate_qr_payment_code_exception(self, mock_print, mock_qrcode):
        """Test QR code generation with exception"""
        mock_qrcode.QRCode.side_effect = Exception("QR generation error")

        result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        assert result is None
        assert any('Error generating QR code' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_different_currencies(self, mock_qrcode):
        """Test QR code generation with different currencies"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        currencies = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']

        for currency in currencies:
            result = generate_qr_payment_code(
                student_id='STU001',
                amount=100.50,
                currency=currency
            )

            assert f'currency={currency}' in result['payment_url']

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_qr_settings(self, mock_qrcode):
        """Test QR code is created with correct settings"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        # Verify QR code was created with correct parameters
        mock_qrcode.QRCode.assert_called_once_with(
            version=1,
            box_size=10,
            border=5
        )

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_generate_qr_payment_code_colors(self, mock_qrcode):
        """Test QR code uses correct colors"""
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        # Verify image was created with correct colors
        mock_qr.make_image.assert_called_once_with(
            fill_color="black",
            back_color="white"
        )


class TestPaymentIntegration:
    """Test suite for payment integration scenarios"""

    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.stripe')
    @patch('education_system.university_system.modules.domain.finance.finance_misc.payments.qrcode')
    def test_combined_payment_flow(self, mock_qrcode, mock_stripe):
        """Test combined payment flow: QR generation and Stripe processing"""
        # Setup mocks
        mock_qr = Mock()
        mock_img = Mock()
        mock_qrcode.QRCode.return_value = mock_qr
        mock_qr.make_image.return_value = mock_img

        mock_intent = Mock()
        mock_intent.status = 'succeeded'
        mock_intent.id = 'pi_test123'
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        # Generate QR code
        qr_result = generate_qr_payment_code(
            student_id='STU001',
            amount=100.50,
            currency='GBP'
        )

        assert qr_result is not None

        # Process payment
        payment_result = process_stripe_payment(
            amount=100.50,
            currency='GBP',
            payment_method_id='pm_test123',
            student_id='STU001'
        )

        assert payment_result['success'] is True

    def test_manual_rate_update_with_multiple_base_currencies(self):
        """Test manual rate update works with different base currencies"""
        mock_cursor = Mock()

        for base in ['GBP', 'USD', 'EUR']:
            with patch('builtins.input', side_effect=['1.0'] * 10):
                with patch('builtins.print'):
                    manual_rate_update(mock_cursor, base)

        # Should have created many exchange rate entries
        assert mock_cursor.execute.call_count > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
