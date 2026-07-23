"""Interaction tests for the commerce/carrental CLI.

``CarRentalCLI`` is a thin, ``input()``/``print()``-driven shell over the four
``carrental_core`` managers. Rather than stand up a database, we patch the
manager classes *as imported into the CLI module* with mocks and drive each
handler through a scripted ``input`` sequence, asserting on both the calls made
into the service layer and the text printed back to the operator.

The menu loops (``run``/``_vehicles_menu``/...) are exercised by feeding a
choice followed by ``'0'`` so the loop dispatches once and exits; every loop
also issues a trailing "Press Enter to continue" prompt, which the input script
accounts for.
"""

import builtins

import pytest

CLI_MODULE = (
    "education_system.post_18.university_system.modules.domain."
    "commerce.carrental.cli.carrental_cli"
)


@pytest.fixture()
def cli(monkeypatch):
    """A ``CarRentalCLI`` with every service manager replaced by a mock.

    ``init_carrental_db`` (run in ``__init__``) is stubbed so construction never
    touches a real database.
    """
    import importlib
    from unittest.mock import MagicMock

    mod = importlib.import_module(CLI_MODULE)

    monkeypatch.setattr(mod, "init_carrental_db", MagicMock(return_value=True))

    vehicle = MagicMock(name="VehicleManager")
    rental = MagicMock(name="RentalManager")
    txn = MagicMock(name="TransactionManager")
    report = MagicMock(name="ReportManager")

    monkeypatch.setattr(mod, "VehicleManager", vehicle)
    monkeypatch.setattr(mod, "RentalManager", rental)
    monkeypatch.setattr(mod, "TransactionManager", txn)
    monkeypatch.setattr(mod, "ReportManager", report)

    instance = mod.CarRentalCLI()
    instance._mod = mod
    instance._vehicle = vehicle
    instance._rental = rental
    instance._txn = txn
    instance._report = report
    return instance


@pytest.fixture()
def capture(monkeypatch):
    """Feed a scripted list of inputs and capture everything printed."""

    def _install(inputs):
        buf = []
        it = iter(inputs)

        def _fake_input(prompt=""):
            buf.append(str(prompt))
            try:
                return next(it)
            except StopIteration:  # pragma: no cover - guards a mis-scripted test
                raise AssertionError("CLI consumed more input than the test supplied")

        def _fake_print(*args, **kwargs):
            buf.append(" ".join(str(a) for a in args))

        monkeypatch.setattr(builtins, "input", _fake_input)
        monkeypatch.setattr(builtins, "print", _fake_print)
        return buf

    return _install


def _text(buf):
    return "\n".join(buf)


# ---------------------------------------------------------------------------
# Construction & main loop
# ---------------------------------------------------------------------------


class TestConstructionAndMainMenu:
    def test_init_initialises_db(self, cli):
        cli._mod.init_carrental_db.assert_called_once()

    def test_run_dispatches_to_vehicles_then_exits(self, cli, capture, monkeypatch):
        # '1' -> vehicles menu (which we stub), then '0' -> exit run loop.
        called = {"v": 0}
        monkeypatch.setattr(cli, "_vehicles_menu", lambda: called.__setitem__("v", called["v"] + 1))
        capture(["1", "0"])
        cli.run()
        assert called["v"] == 1

    def test_run_invalid_option_then_exit(self, cli, capture):
        buf = capture(["9", "", "0"])  # bad choice, press-enter, then exit
        cli.run()
        assert "Invalid option" in _text(buf)

    def test_run_exit_immediately(self, cli, capture):
        buf = capture(["0"])
        cli.run()
        assert "Returning to main menu" in _text(buf)


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


class TestVehicles:
    def test_add_vehicle_success(self, cli, capture):
        cli._vehicle.add_vehicle.return_value = 7
        buf = capture([
            "AB12 CDE", "Toyota", "Corolla", "2022", "economy", "40",
            "red", "5", "manual", "electric", "1000", "GPS",
        ])
        cli._add_vehicle()
        cli._vehicle.add_vehicle.assert_called_once()
        kwargs = cli._vehicle.add_vehicle.call_args.kwargs
        assert kwargs["registration_number"] == "AB12 CDE"
        assert kwargs["year"] == 2022
        assert kwargs["daily_rate"] == 40.0
        assert kwargs["transmission"] == "manual"
        assert "Vehicle added (ID: 7)" in _text(buf)

    def test_add_vehicle_defaults_for_blank_optionals(self, cli, capture):
        cli._vehicle.add_vehicle.return_value = 1
        # Blank color/seats/transmission/fuel/mileage/features -> defaults.
        capture([
            "ZZ99 ZZZ", "Ford", "Focus", "2020", "compact", "35",
            "", "", "", "", "", "",
        ])
        cli._add_vehicle()
        kwargs = cli._vehicle.add_vehicle.call_args.kwargs
        assert kwargs["color"] is None
        assert kwargs["seats"] == 5
        assert kwargs["transmission"] == "automatic"
        assert kwargs["fuel_type"] == "petrol"
        assert kwargs["mileage"] == 0
        assert kwargs["features"] is None

    def test_add_vehicle_failure_message(self, cli, capture):
        cli._vehicle.add_vehicle.return_value = None
        buf = capture([
            "AB12 CDE", "Toyota", "Corolla", "2022", "economy", "40",
            "", "", "", "", "", "",
        ])
        cli._add_vehicle()
        assert "Failed to add vehicle" in _text(buf)

    def test_list_vehicles_empty(self, cli, capture):
        cli._vehicle.get_all_vehicles.return_value = []
        buf = capture([])
        cli._list_vehicles()
        assert "No vehicles found" in _text(buf)

    def test_list_vehicles_rows(self, cli, capture):
        cli._vehicle.get_all_vehicles.return_value = [{
            "vehicle_id": 3, "registration_number": "AB12 CDE", "make": "Toyota",
            "model": "Corolla", "year": 2022, "category": "economy",
            "daily_rate": 40.0, "status": "available",
        }]
        buf = capture([])
        cli._list_vehicles()
        text = _text(buf)
        assert "AB12 CDE" in text and "Toyota" in text

    def test_available_vehicles_filter_passed(self, cli, capture):
        cli._vehicle.get_available_vehicles.return_value = []
        capture(["luxury"])
        cli._available_vehicles()
        cli._vehicle.get_available_vehicles.assert_called_once_with(category="luxury")

    def test_available_vehicles_blank_filter_is_none(self, cli, capture):
        cli._vehicle.get_available_vehicles.return_value = []
        capture([""])
        cli._available_vehicles()
        cli._vehicle.get_available_vehicles.assert_called_once_with(category=None)

    def test_view_vehicle_found(self, cli, capture):
        cli._vehicle.get_vehicle.return_value = {
            "vehicle_id": 3, "registration_number": "AB12 CDE", "make": "Toyota",
            "model": "Corolla", "year": 2022, "category": "economy", "color": "red",
            "seats": 5, "transmission": "automatic", "fuel_type": "petrol",
            "mileage": 1000, "daily_rate": 40.0, "status": "available",
            "features": "GPS", "last_service_date": "2026-01-01",
        }
        buf = capture(["3"])
        cli._view_vehicle()
        text = _text(buf)
        assert "Registration: AB12 CDE" in text
        assert "Features: GPS" in text

    def test_view_vehicle_not_found(self, cli, capture):
        cli._vehicle.get_vehicle.return_value = None
        buf = capture(["99"])
        cli._view_vehicle()
        assert "Vehicle not found" in _text(buf)

    def test_update_vehicle_collects_only_provided_fields(self, cli, capture):
        cli._vehicle.update_vehicle.return_value = True
        # daily_rate given, color blank, mileage given, features blank.
        buf = capture(["3", "55", "", "12345", ""])
        cli._update_vehicle()
        cli._vehicle.update_vehicle.assert_called_once_with(3, daily_rate=55.0, mileage=12345)
        assert "Vehicle updated" in _text(buf)

    def test_update_vehicle_no_changes(self, cli, capture):
        buf = capture(["3", "", "", "", ""])
        cli._update_vehicle()
        cli._vehicle.update_vehicle.assert_not_called()
        assert "No changes specified" in _text(buf)

    def test_update_vehicle_failure(self, cli, capture):
        cli._vehicle.update_vehicle.return_value = False
        buf = capture(["3", "55", "", "", ""])
        cli._update_vehicle()
        assert "Failed to update vehicle" in _text(buf)

    def test_update_vehicle_status(self, cli, capture):
        cli._vehicle.update_vehicle_status.return_value = True
        buf = capture(["3", "maintenance"])
        cli._update_vehicle_status()
        cli._vehicle.update_vehicle_status.assert_called_once_with(3, "maintenance")
        assert "Status updated" in _text(buf)

    def test_vehicles_menu_error_is_caught(self, cli, capture):
        # Choosing '4' (view) with a non-numeric ID raises ValueError inside the
        # handler; the menu's try/except should print it, not crash.
        buf = capture(["4", "not-a-number", "", "0"])
        cli._vehicles_menu()
        assert "Error:" in _text(buf)


# ---------------------------------------------------------------------------
# Rentals
# ---------------------------------------------------------------------------


class TestRentals:
    def test_create_rental_success(self, cli, capture):
        cli._vehicle.get_vehicle.return_value = {"daily_rate": 40.0}
        cli._rental.create_rental.return_value = 11
        buf = capture([
            "3", "CUST1", "Alice", "LIC-1", "a@b.com", "555",
            "2026-06-01", "10:00", "2026-06-04", "10:00",
            "Depot A", "Depot B", "30", "100",
        ])
        cli._create_rental()
        kwargs = cli._rental.create_rental.call_args.kwargs
        assert kwargs["vehicle_id"] == 3
        assert kwargs["daily_rate"] == 40.0
        assert kwargs["insurance_fee"] == 30.0
        assert kwargs["deposit_amount"] == 100.0
        assert "Rental created (ID: 11)" in _text(buf)

    def test_create_rental_vehicle_not_found(self, cli, capture):
        cli._vehicle.get_vehicle.return_value = None
        buf = capture(["3", "CUST1", "Alice", "LIC-1", "", "",
                       "2026-06-01", "10:00", "2026-06-04", "10:00", "", ""])
        cli._create_rental()
        assert "Vehicle not found" in _text(buf)
        cli._rental.create_rental.assert_not_called()

    def test_create_rental_failure(self, cli, capture):
        cli._vehicle.get_vehicle.return_value = {"daily_rate": 40.0}
        cli._rental.create_rental.return_value = None
        buf = capture(["3", "CUST1", "Alice", "LIC-1", "", "",
                       "2026-06-01", "10:00", "2026-06-04", "10:00", "", "", "", ""])
        cli._create_rental()
        assert "Failed to create rental" in _text(buf)

    def test_view_rental_found(self, cli, capture):
        cli._rental.get_rental.return_value = {
            "rental_number": "RNT-1", "make": "Toyota", "model": "Corolla",
            "registration_number": "AB12 CDE", "customer_name": "Alice",
            "license_number": "LIC-1", "pickup_date": "2026-06-01",
            "pickup_time": "10:00", "return_date": "2026-06-04",
            "return_time": "10:00", "total_days": 3, "daily_rate": 40.0,
            "subtotal": 120.0, "total_amount": 120.0, "payment_status": "pending",
            "status": "reserved",
        }
        buf = capture(["11"])
        cli._view_rental()
        assert "Rental #RNT-1" in _text(buf)

    def test_view_rental_not_found(self, cli, capture):
        cli._rental.get_rental.return_value = None
        buf = capture(["11"])
        cli._view_rental()
        assert "Rental not found" in _text(buf)

    def test_list_rentals_status_filter(self, cli, capture):
        cli._rental.get_rentals_by_status.return_value = []
        buf = capture(["active"])
        cli._list_rentals()
        cli._rental.get_rentals_by_status.assert_called_once_with("active")
        assert "No rentals found" in _text(buf)

    def test_list_rentals_blank_status_all(self, cli, capture):
        cli._rental.get_rentals_by_status.return_value = [{
            "rental_id": 1, "rental_number": "RNT-1", "make": "Toyota",
            "model": "Corolla", "customer_name": "Alice", "pickup_date": "2026-06-01",
            "total_amount": 120.0, "status": "reserved",
        }]
        buf = capture([""])
        cli._list_rentals()
        cli._rental.get_rentals_by_status.assert_called_once_with(None)
        assert "RNT-1" in _text(buf)

    def test_start_rental(self, cli, capture):
        cli._rental.start_rental.return_value = True
        buf = capture(["11", "10000", "full", "no damage"])
        cli._start_rental()
        kwargs = cli._rental.start_rental.call_args.kwargs
        assert kwargs["rental_id"] == 11
        assert kwargs["pickup_mileage"] == 10000
        assert kwargs["condition_notes"] == "no damage"
        assert "Rental started" in _text(buf)

    def test_start_rental_blank_notes_none(self, cli, capture):
        cli._rental.start_rental.return_value = False
        capture(["11", "10000", "full", ""])
        cli._start_rental()
        assert cli._rental.start_rental.call_args.kwargs["condition_notes"] is None

    def test_complete_rental(self, cli, capture):
        cli._rental.complete_rental.return_value = True
        buf = capture(["11", "10500", "half", "20", "15", "5"])
        cli._complete_rental()
        kwargs = cli._rental.complete_rental.call_args.kwargs
        assert kwargs["return_mileage"] == 10500
        assert kwargs["late_fee"] == 20.0
        assert kwargs["damage_fee"] == 15.0
        assert kwargs["fuel_fee"] == 5.0
        assert "Rental completed" in _text(buf)

    def test_complete_rental_blank_fees_zero(self, cli, capture):
        cli._rental.complete_rental.return_value = True
        capture(["11", "10500", "half", "", "", ""])
        cli._complete_rental()
        kwargs = cli._rental.complete_rental.call_args.kwargs
        assert kwargs["late_fee"] == 0 and kwargs["damage_fee"] == 0 and kwargs["fuel_fee"] == 0

    def test_cancel_rental(self, cli, capture):
        cli._rental.cancel_rental.return_value = True
        buf = capture(["11", "customer request"])
        cli._cancel_rental()
        cli._rental.cancel_rental.assert_called_once_with(11, "customer request")
        assert "Rental cancelled" in _text(buf)

    def test_cancel_rental_blank_reason_none(self, cli, capture):
        cli._rental.cancel_rental.return_value = False
        capture(["11", ""])
        cli._cancel_rental()
        cli._rental.cancel_rental.assert_called_once_with(11, None)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class TestPayments:
    def test_record_payment_success(self, cli, capture):
        cli._txn.record_payment.return_value = 500
        buf = capture(["11", "CUST1", "120", "card"])
        cli._record_payment()
        kwargs = cli._txn.record_payment.call_args.kwargs
        assert kwargs["rental_id"] == 11
        assert kwargs["amount"] == 120.0
        assert kwargs["payment_method"] == "card"
        assert "Payment recorded (Transaction ID: 500)" in _text(buf)

    def test_record_payment_failure(self, cli, capture):
        cli._txn.record_payment.return_value = None
        buf = capture(["11", "CUST1", "120", "card"])
        cli._record_payment()
        assert "Failed to record payment" in _text(buf)

    def test_record_refund_success(self, cli, capture):
        cli._txn.record_refund.return_value = 600
        buf = capture(["11", "CUST1", "40", "overcharge"])
        cli._record_refund()
        kwargs = cli._txn.record_refund.call_args.kwargs
        assert kwargs["amount"] == 40.0
        assert kwargs["reason"] == "overcharge"
        assert "Refund recorded (Transaction ID: 600)" in _text(buf)

    def test_view_transactions_filtered(self, cli, capture):
        cli._txn.get_transactions.return_value = [{
            "transaction_id": 1, "transaction_type": "payment", "amount": 120.0,
            "payment_method": "card", "status": "completed", "created_at": "2026-06-01",
        }]
        buf = capture(["11"])
        cli._view_transactions()
        cli._txn.get_transactions.assert_called_once_with(11)
        assert "payment" in _text(buf)

    def test_view_transactions_all_when_blank(self, cli, capture):
        cli._txn.get_transactions.return_value = []
        buf = capture([""])
        cli._view_transactions()
        cli._txn.get_transactions.assert_called_once_with(None)
        assert "No transactions found" in _text(buf)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class TestReports:
    def test_fleet_summary(self, cli, capture):
        cli._report.get_fleet_summary.return_value = {
            "total_vehicles": 5, "available": 3, "rented": 1, "maintenance": 1,
        }
        buf = capture([])
        cli._fleet_summary()
        text = _text(buf)
        assert "Total Vehicles: 5" in text and "Available: 3" in text

    def test_fleet_summary_empty(self, cli, capture):
        cli._report.get_fleet_summary.return_value = {}
        buf = capture([])
        cli._fleet_summary()
        assert "No fleet data available" in _text(buf)

    def test_revenue_report_with_dates(self, cli, capture):
        cli._report.get_revenue_report.return_value = {
            "total_rentals": 2, "completed_rentals": 1,
            "total_revenue": 240.0, "avg_rental_value": 120.0,
        }
        buf = capture(["2026-01-01", "2026-12-31"])
        cli._revenue_report()
        cli._report.get_revenue_report.assert_called_once_with("2026-01-01", "2026-12-31")
        assert "Total Revenue: £240.00" in _text(buf)

    def test_revenue_report_handles_none_values(self, cli, capture):
        cli._report.get_revenue_report.return_value = {
            "total_rentals": 0, "completed_rentals": 0,
            "total_revenue": None, "avg_rental_value": None,
        }
        buf = capture(["", ""])
        cli._revenue_report()
        cli._report.get_revenue_report.assert_called_once_with(None, None)
        assert "Total Revenue: £0.00" in _text(buf)

    def test_popular_vehicles_custom_limit(self, cli, capture):
        cli._report.get_popular_vehicles.return_value = [{
            "make": "Toyota", "model": "Corolla", "category": "economy",
            "rental_count": 3, "total_revenue": 360.0,
        }]
        buf = capture(["5"])
        cli._popular_vehicles()
        cli._report.get_popular_vehicles.assert_called_once_with(5)
        assert "Toyota" in _text(buf)

    def test_popular_vehicles_default_limit(self, cli, capture):
        cli._report.get_popular_vehicles.return_value = []
        buf = capture([""])
        cli._popular_vehicles()
        cli._report.get_popular_vehicles.assert_called_once_with(10)
        assert "No data available" in _text(buf)

    def test_admin_report(self, cli, capture):
        cli._report.generate_admin_report.return_value = "REPORT BODY"
        buf = capture([])
        cli._admin_report()
        assert "REPORT BODY" in _text(buf)


# ---------------------------------------------------------------------------
# Email + CSV export
# ---------------------------------------------------------------------------


class TestEmailAndExport:
    def test_email_admin_report_sends(self, cli, capture, monkeypatch):
        from contextlib import contextmanager

        cli._report.generate_admin_report.return_value = "REPORT"

        class _Cursor:
            def fetchone(self):
                return ["admin@uni.edu"]

        class _Conn:
            def execute(self, *a, **k):
                return _Cursor()

        @contextmanager
        def _fake_conn():
            yield _Conn()

        sent = {}

        def _fake_send(recipient_email, subject, body):
            sent.update(recipient=recipient_email, subject=subject, body=body)

        monkeypatch.setattr(
            "education_system.post_18.university_system.infrastructure.database.db.get_db_connection",
            _fake_conn,
        )
        monkeypatch.setattr(
            "education_system.post_18.university_system.infrastructure.email.email_service.send_email",
            _fake_send,
        )
        buf = capture([])
        cli._email_admin_report()
        assert sent["recipient"] == "admin@uni.edu"
        assert "REPORT" in sent["body"]
        assert "emailed to admin@uni.edu" in _text(buf)

    def test_email_admin_report_no_admin(self, cli, capture, monkeypatch):
        from contextlib import contextmanager

        cli._report.generate_admin_report.return_value = "REPORT"

        class _Cursor:
            def fetchone(self):
                return None

        class _Conn:
            def execute(self, *a, **k):
                return _Cursor()

        @contextmanager
        def _fake_conn():
            yield _Conn()

        monkeypatch.setattr(
            "education_system.post_18.university_system.infrastructure.database.db.get_db_connection",
            _fake_conn,
        )
        buf = capture([])
        cli._email_admin_report()
        assert "No admin email found" in _text(buf)

    def test_export_transactions_csv(self, cli, capture, monkeypatch, tmp_path):
        from contextlib import contextmanager

        rows = [
            (1, "2026-06-01", "CUST1", 120.0, "payment", "card", "completed", "PAY-1"),
            (2, "2026-06-02", "CUST2", 40.0, "refund", "refund", "completed", "REF-1"),
        ]

        class _Cursor:
            def execute(self, *a, **k):
                return self

            def fetchall(self):
                return rows

        class _Conn:
            def cursor(self):
                return _Cursor()

        @contextmanager
        def _fake_conn():
            yield _Conn()

        monkeypatch.setattr(
            "education_system.post_18.university_system.infrastructure.database.db.get_db_connection",
            _fake_conn,
        )
        out = tmp_path / "export.csv"
        buf = capture([str(out)])
        cli._export_transactions_csv()

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Transaction ID" in content  # header
        assert "PAY-1" in content and "REF-1" in content
        assert "120.00" in content
        assert "Exported 2 transaction(s)" in _text(buf)


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------


def test_main_constructs_and_runs(monkeypatch):
    import importlib
    from unittest.mock import MagicMock

    mod = importlib.import_module(CLI_MODULE)
    monkeypatch.setattr(mod, "init_carrental_db", MagicMock(return_value=True))
    run_mock = MagicMock()
    monkeypatch.setattr(mod.CarRentalCLI, "run", run_mock)
    mod.main()
    run_mock.assert_called_once()
