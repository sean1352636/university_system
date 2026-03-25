"""
Tests for Financial Reports Module

This module contains unit tests for financial reporting functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from education_system.university_system.modules.domain.finance.reporting.financial_reports import (
    FinancialAlertSystem,
    PaymentPredictionML,
    AnomalyDetector,
    CashFlowForecaster,
    set_auth
)


class TestAuthSetup:
    """Test authentication setup"""

    def test_set_auth(self):
        """Test set_auth function"""
        mock_auth = Mock()
        set_auth(mock_auth)

        from education_system.university_system.modules.domain.finance.reporting.financial_reports import auth
        assert auth == mock_auth


class TestFinancialAlertSystem:
    """Test FinancialAlertSystem class"""

    def test_init(self):
        """Test FinancialAlertSystem initialization"""
        alert_system = FinancialAlertSystem()

        assert alert_system.alert_thresholds is not None
        assert isinstance(alert_system.alert_thresholds, dict)
        assert 'collection_rate_min' in alert_system.alert_thresholds

    @patch('education_system.university_system.modules.domain.finance.reporting.financial_reports.get_connection')
    def test_check_collection_rate_alert(self, mock_get_conn):
        """Test check_collection_rate_alert method"""
        alert_system = FinancialAlertSystem()

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (80000.0, 100000.0)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Should not raise exception
        alert_system.check_collection_rate_alert()

    @patch('education_system.university_system.modules.domain.finance.reporting.financial_reports.get_connection')
    def test_log_alert(self, mock_get_conn):
        """Test log_alert method"""
        alert_system = FinancialAlertSystem()

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        alert_system.log_alert('TEST_ALERT', 'Test message', {'key': 'value'})

        mock_cursor.execute.assert_called()

    def test_get_current_academic_year(self):
        """Test get_current_academic_year method"""
        alert_system = FinancialAlertSystem()
        year = alert_system.get_current_academic_year()

        assert isinstance(year, str)
        assert '-' in year


class TestPaymentPredictionML:
    """Test PaymentPredictionML class"""

    def test_init(self):
        """Test PaymentPredictionML initialization"""
        predictor = PaymentPredictionML()

        assert predictor.model is None
        assert predictor.scaler is not None
        assert isinstance(predictor.feature_columns, list)

    @patch('education_system.university_system.modules.domain.finance.reporting.financial_reports.get_connection')
    def test_prepare_training_data_insufficient(self, mock_get_conn):
        """Test prepare_training_data with insufficient data"""
        predictor = PaymentPredictionML()

        mock_conn = Mock()
        # Return empty DataFrame
        with patch('pandas.read_sql_query') as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame()
            mock_get_conn.return_value = mock_conn

            X, y = predictor.prepare_training_data()

            assert X is None
            assert y is None

    def test_train_model_insufficient_data(self):
        """Test train_model with insufficient data"""
        predictor = PaymentPredictionML()

        with patch.object(predictor, 'prepare_training_data', return_value=(None, None)):
            result = predictor.train_model()

            assert result is False


class TestAnomalyDetector:
    """Test AnomalyDetector class"""

    def test_init(self):
        """Test AnomalyDetector initialization"""
        detector = AnomalyDetector()

        assert detector.isolation_forest is not None

    @patch('education_system.university_system.modules.domain.finance.reporting.financial_reports.get_connection')
    def test_detect_payment_anomalies_insufficient_data(self, mock_get_conn):
        """Test detect_payment_anomalies with insufficient data"""
        detector = AnomalyDetector()

        mock_conn = Mock()
        with patch('pandas.read_sql_query') as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame()
            mock_get_conn.return_value = mock_conn

            result = detector.detect_payment_anomalies()

            assert result == []


class TestCashFlowForecaster:
    """Test CashFlowForecaster class"""

    def test_init(self):
        """Test CashFlowForecaster initialization"""
        forecaster = CashFlowForecaster()

        assert forecaster.seasonal_factors is not None
        assert isinstance(forecaster.seasonal_factors, dict)
        assert '09' in forecaster.seasonal_factors

    @patch('education_system.university_system.modules.domain.finance.reporting.financial_reports.get_connection')
    def test_generate_cash_flow_forecast(self, mock_get_conn):
        """Test generate_cash_flow_forecast method"""
        forecaster = CashFlowForecaster()

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Should not raise exception with empty data
        forecaster.generate_cash_flow_forecast(months_ahead=3)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
