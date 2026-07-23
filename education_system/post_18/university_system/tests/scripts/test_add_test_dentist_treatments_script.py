"""Smoke tests for scripts.add_test_dentist_treatments."""
from unittest.mock import MagicMock, patch

from education_system.post_18.university_system.scripts import add_test_dentist_treatments as script


class TestModuleSurface:
    def test_add_test_treatments_is_callable(self):
        assert callable(script.add_test_treatments)


class TestAddTestTreatments:
    def test_returns_false_when_no_patient(self):
        fake_conn = MagicMock()
        fake_conn.execute.return_value.fetchone.return_value = None
        cm = MagicMock()
        cm.__enter__.return_value = fake_conn
        cm.__exit__.return_value = False
        with patch.object(script, "get_connection", return_value=cm):
            assert script.add_test_treatments() is False

    def test_returns_false_on_exception(self):
        with patch.object(script, "get_connection", side_effect=RuntimeError("db down")):
            assert script.add_test_treatments() is False

    def test_inserts_treatments_when_patient_exists(self):
        # First connection: read patient
        read_conn = MagicMock()
        read_conn.execute.return_value.fetchone.return_value = (1, 42)
        read_cm = MagicMock()
        read_cm.__enter__.return_value = read_conn
        read_cm.__exit__.return_value = False

        # Transaction: insert rows
        tx_conn = MagicMock()
        tx_cm = MagicMock()
        tx_cm.__enter__.return_value = tx_conn
        tx_cm.__exit__.return_value = False

        fake_types = {
            "checkup": {"name": "Routine Check-up", "fee": 30.0},
            "cleaning": {"name": "Cleaning", "fee": 40.0},
            "filling": {"name": "Filling", "fee": 80.0},
            "xray": {"name": "X-Ray", "fee": 25.0},
            "consultation": {"name": "Consultation", "fee": 20.0},
        }

        with patch.object(script, "get_connection", return_value=read_cm), \
             patch.object(script, "transaction", return_value=tx_cm), \
             patch.dict(
                 "sys.modules",
                 {"education_system.post_18.university_system.modules.domain.health.dentist.services.dentist_core":
                     MagicMock(TREATMENT_TYPES=fake_types)},
             ):
            # The real import path is at function scope; patching sys.modules covers it
            result = script.add_test_treatments()

        assert result is True
        assert tx_conn.execute.call_count == 5
