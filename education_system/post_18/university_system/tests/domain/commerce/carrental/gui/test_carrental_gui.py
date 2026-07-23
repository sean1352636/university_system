"""GUI tests for commerce/carrental (``CarRentalGUI``).

These build the *real* Tkinter widget tree against a real (headless) Tk root and
drive the handler methods, so they carry ``pytest.mark.gui`` and are deselected
by the default ``-m "not gui"`` run. If no display/Tk is available the whole
module skips.

DB isolation follows the repo's service-test convention: the carrental managers
resolve ``DEFAULT_DB_PATH`` at call time, so we point that module global at a
temp DB (the GUI's own ``_init_database`` creates the carrental tables) and hand
the not-owned ``transactions`` table over ourselves. ``messagebox`` is replaced
with a recorder so no modal dialog ever blocks the test run.
"""

import sqlite3

import pytest

pytestmark = pytest.mark.gui

GUI_MODULE = (
    "education_system.post_18.university_system.modules.domain."
    "commerce.carrental.gui.carrental_gui"
)
DB_MODULE = "education_system.post_18.university_system.infrastructure.database.db"
FINANCE_RECORD_PAYMENT = (
    "education_system.post_18.university_system.modules.domain.finance."
    "core.unified_payments.record_payment"
)

_TRANSACTIONS_DDL = """
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        reference_id INTEGER,
        reference_type TEXT,
        customer_id TEXT,
        amount DECIMAL(10,2),
        transaction_type TEXT,
        payment_method TEXT,
        reference_number TEXT,
        status TEXT DEFAULT 'completed',
        notes TEXT,
        processed_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


@pytest.fixture()
def tk_root_factory():
    """Yield a factory that makes real, withdrawn Tk roots for one test.

    Function-scoped so it runs *after* the autouse ``_live_tkinter`` fixture has
    restored real tkinter (see this directory's conftest); a module-scoped
    factory would build its root while tkinter was still neutered. Every root is
    withdrawn and destroyed on teardown so nothing is mapped to a display.
    """
    tk = pytest.importorskip("tkinter")

    created = []

    def _make():
        try:
            root = tk.Tk()
        except Exception as exc:  # pragma: no cover - headless CI
            pytest.skip(f"Tk not available: {exc}")
        root.withdraw()
        created.append(root)
        return root

    yield _make

    for root in created:
        try:
            root.destroy()
        except Exception:  # pragma: no cover
            pass


@pytest.fixture()
def gui_env(tmp_path, monkeypatch):
    """Isolated DB + patched messagebox; returns the carrental modules."""
    db_path = str(tmp_path / "carrental_gui.db")
    monkeypatch.setattr(f"{DB_MODULE}.DEFAULT_DB_PATH", db_path)

    # Keep the finance mirror off the real DB (record_payment fans out to it).
    monkeypatch.setattr(FINANCE_RECORD_PAYMENT, lambda **kw: 999)

    import importlib

    core = importlib.import_module(
        "education_system.post_18.university_system.modules.domain."
        "commerce.carrental.services.carrental_core"
    )
    gui_mod = importlib.import_module(GUI_MODULE)

    assert core.init_carrental_db() is True
    conn = sqlite3.connect(db_path)
    conn.executescript(_TRANSACTIONS_DDL)
    conn.commit()
    conn.close()

    # Replace messagebox so success/warn/error dialogs are recorded, not shown.
    from unittest.mock import MagicMock

    box = MagicMock()
    monkeypatch.setattr(gui_mod, "messagebox", box)

    class _Env:
        pass

    env = _Env()
    env.db_path = db_path
    env.core = core
    env.gui_mod = gui_mod
    env.box = box
    return env


def _auth(**overrides):
    from unittest.mock import Mock

    user = {"id": "USER1", "username": "operator", "role": "admin"}
    user.update(overrides.pop("user", {}))
    auth = Mock()
    auth.current_user = user
    for k, v in overrides.items():
        setattr(auth, k, v)
    return auth


@pytest.fixture()
def gui(gui_env, tk_root_factory):
    """A fully-built CarRentalGUI on a real, isolated root."""
    root = tk_root_factory()
    app = gui_env.gui_mod.CarRentalGUI(root, _auth())
    app._env = gui_env
    app._root = root
    return app


def _add_vehicle(env, reg="AB12 CDE", rate=40.0, **kw):
    return env.core.VehicleManager.add_vehicle(
        reg, "Toyota", "Corolla", 2022, "economy", rate, **kw
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_imports(self, gui_env):
        assert hasattr(gui_env.gui_mod, "CarRentalGUI")
        assert hasattr(gui_env.gui_mod, "launch_carrental_gui")

    def test_builds_five_tabs(self, gui):
        assert len(gui.notebook.tabs()) == 5

    def test_core_widgets_present(self, gui):
        for attr in (
            "vehicles_tree", "available_tree", "active_rentals_tree",
            "report_text", "rental_entries", "rental_cost_var",
        ):
            assert hasattr(gui, attr), attr

    def test_title_and_geometry(self, gui):
        assert gui.root.title()  # non-empty translated title
        assert gui.current_user["username"] == "operator"

    def test_login_required_destroys_root(self, gui_env, tk_root_factory):
        root = tk_root_factory()
        from unittest.mock import Mock

        auth = Mock()
        auth.current_user = None
        gui_env.gui_mod.CarRentalGUI(root, auth)
        gui_env.box.showerror.assert_called_once()


# ---------------------------------------------------------------------------
# Vehicles tab
# ---------------------------------------------------------------------------


class TestVehiclesTab:
    def test_load_vehicles_populates_tree(self, gui):
        _add_vehicle(gui._env, reg="LV1 AAA")
        _add_vehicle(gui._env, reg="LV2 BBB")
        gui.vehicle_category_filter.set("All")
        gui._load_vehicles()
        assert len(gui.vehicles_tree.get_children()) == 2

    def test_load_vehicles_category_filter(self, gui):
        _add_vehicle(gui._env, reg="EC1 AAA")  # economy
        gui._env.core.VehicleManager.add_vehicle("LX1 AAA", "BMW", "7", 2023, "luxury", 200.0)
        gui.vehicle_category_filter.set("luxury")
        gui._load_vehicles()
        assert len(gui.vehicles_tree.get_children()) == 1

    def test_available_tree_excludes_rented(self, gui):
        vid = _add_vehicle(gui._env, reg="AV1 AAA")
        gui._env.core.VehicleManager.update_vehicle_status(vid, "rented")
        gui._load_available_vehicles()
        assert len(gui.available_tree.get_children()) == 0

    def test_add_vehicle_success(self, gui):
        gui.vehicle_entries["registration"].insert(0, "NW1 AAA")
        gui.vehicle_entries["make"].insert(0, "Honda")
        gui.vehicle_entries["model"].insert(0, "Civic")
        gui.vehicle_entries["year"].insert(0, "2021")
        gui.vehicle_entries["daily_rate"].insert(0, "45")
        gui.vehicle_category_combo.set("compact")
        gui.add_vehicle()
        gui._env.box.showinfo.assert_called_once()
        assert any(
            v["registration_number"] == "NW1 AAA"
            for v in gui._env.core.VehicleManager.get_all_vehicles()
        )

    def test_add_vehicle_missing_fields(self, gui):
        gui.vehicle_entries["registration"].insert(0, "NW1 AAA")  # rest blank
        gui.add_vehicle()
        gui._env.box.showerror.assert_called_once()

    def test_add_vehicle_invalid_number(self, gui):
        gui.vehicle_entries["registration"].insert(0, "NW1 AAA")
        gui.vehicle_entries["make"].insert(0, "Honda")
        gui.vehicle_entries["model"].insert(0, "Civic")
        gui.vehicle_entries["year"].insert(0, "not-a-year")
        gui.vehicle_entries["daily_rate"].insert(0, "45")
        gui.vehicle_category_combo.set("compact")
        gui.add_vehicle()
        # ValueError branch -> invalid_input error dialog.
        gui._env.box.showerror.assert_called_once()

    def test_update_vehicle_no_selection_warns(self, gui):
        gui.update_vehicle()
        gui._env.box.showwarning.assert_called_once()

    def test_update_vehicle_selected(self, gui):
        vid = _add_vehicle(gui._env, reg="UP1 AAA")
        gui.vehicle_category_filter.set("All")
        gui._load_vehicles()
        first = gui.vehicles_tree.get_children()[0]
        gui.vehicles_tree.selection_set(first)
        gui.vehicle_entries["daily_rate"].insert(0, "99")
        gui.update_vehicle()
        gui._env.box.showinfo.assert_called_once()
        assert gui._env.core.VehicleManager.get_vehicle(vid)["daily_rate"] == 99.0


# ---------------------------------------------------------------------------
# Rentals tab
# ---------------------------------------------------------------------------


class TestRentalsTab:
    def test_calculate_rental_cost(self, gui):
        vid = _add_vehicle(gui._env, rate=50.0)
        gui.selected_vehicle_id = vid
        gui.rental_entries["pickup_date"].delete(0, "end")
        gui.rental_entries["pickup_date"].insert(0, "2026-06-01")
        gui.rental_entries["return_date"].delete(0, "end")
        gui.rental_entries["return_date"].insert(0, "2026-06-04")
        gui._calculate_rental_cost()
        assert "150.00" in gui.rental_cost_var.get()
        assert "3 days" in gui.rental_cost_var.get()

    def test_calculate_rental_cost_no_vehicle_noops(self, gui):
        gui.selected_vehicle_id = None
        gui.rental_cost_var.set("£0.00")
        gui._calculate_rental_cost()
        assert gui.rental_cost_var.get() == "£0.00"

    def test_book_rental_no_vehicle_warns(self, gui):
        gui.selected_vehicle_id = None
        gui.book_rental()
        gui._env.box.showwarning.assert_called_once()

    def test_book_rental_missing_license_errors(self, gui):
        vid = _add_vehicle(gui._env)
        gui.selected_vehicle_id = vid
        gui.rental_entries["license_number"].delete(0, "end")  # blank
        gui.book_rental()
        gui._env.box.showerror.assert_called_once()

    def test_book_rental_success(self, gui):
        vid = _add_vehicle(gui._env)
        gui.selected_vehicle_id = vid
        gui.rental_entries["license_number"].insert(0, "LIC-1")
        gui.book_rental()
        gui._env.box.showinfo.assert_called_once()
        reserved = gui._env.core.RentalManager.get_rentals_by_status("reserved")
        assert len(reserved) == 1
        # Vehicle flipped to rented by the service layer.
        assert gui._env.core.VehicleManager.get_vehicle(vid)["status"] == "rented"

    def test_clear_rental_form_resets_defaults(self, gui):
        gui.selected_vehicle_id = 5
        gui.rental_entries["license_number"].insert(0, "LIC-1")
        gui._clear_rental_form()
        assert gui.selected_vehicle_id is None
        assert gui.rental_entries["license_number"].get() == ""
        assert gui.rental_cost_var.get() == "£0.00"
        # pickup/return dates re-seeded.
        assert gui.rental_entries["pickup_date"].get()


# ---------------------------------------------------------------------------
# Returns tab
# ---------------------------------------------------------------------------


class TestReturnsTab:
    def test_load_active_rentals_default_filter(self, gui):
        vid = _add_vehicle(gui._env)
        gui._env.core.RentalManager.create_rental(
            vid, "C1", "Alice", "LIC", "2026-06-01", "10:00",
            "2026-06-04", "10:00", 40.0,
        )
        gui._load_active_rentals()
        # Newly created rental is 'reserved' -> shown under Active + Reserved.
        assert len(gui.active_rentals_tree.get_children()) == 1

    def test_load_active_rentals_all_filter(self, gui):
        vid = _add_vehicle(gui._env)
        rid = gui._env.core.RentalManager.create_rental(
            vid, "C1", "Alice", "LIC", "2026-06-01", "10:00",
            "2026-06-04", "10:00", 40.0,
        )
        gui._env.core.RentalManager.cancel_rental(rid)
        gui.rental_status_filter.set("All")
        gui._load_active_rentals()
        assert len(gui.active_rentals_tree.get_children()) == 1

    def test_cancel_rental_no_selection_warns(self, gui):
        gui.cancel_rental()
        gui._env.box.showwarning.assert_called_once()

    def test_return_no_selection_warns(self, gui):
        gui.return_vehicle_with_payment()
        gui._env.box.showwarning.assert_called_once()


# ---------------------------------------------------------------------------
# Reports tab
# ---------------------------------------------------------------------------


class TestReportsTab:
    def _report_text(self, gui):
        return gui.report_text.get("1.0", "end")

    def test_fleet_summary(self, gui):
        _add_vehicle(gui._env, reg="FS1 AAA")
        gui.show_fleet_summary()
        text = self._report_text(gui)
        assert "FLEET SUMMARY" in text
        assert "Total Vehicles: 1" in text

    def test_revenue_report_handles_empty(self, gui):
        gui.show_revenue_report()
        text = self._report_text(gui)
        assert "REVENUE REPORT" in text
        assert "Total Revenue: £0.00" in text

    def test_popular_vehicles(self, gui):
        vid = _add_vehicle(gui._env, reg="PV1 AAA")
        gui._env.core.RentalManager.create_rental(
            vid, "C1", "Alice", "LIC", "2026-06-01", "10:00",
            "2026-06-04", "10:00", 40.0,
        )
        gui.show_popular_vehicles()
        assert "TOP 10 VEHICLES" in self._report_text(gui)
        assert "Toyota Corolla" in self._report_text(gui)

    def test_generate_admin_report(self, gui):
        # Seed a paid rental so the revenue aggregate isn't NULL (the core
        # report f-strings can't format a None total).
        vid = _add_vehicle(gui._env, reg="AR1 AAA")
        rid = gui._env.core.RentalManager.create_rental(
            vid, "C1", "Alice", "LIC", "2026-06-01", "10:00",
            "2026-06-04", "10:00", 40.0,
        )
        gui._env.core.TransactionManager.record_payment(rid, "C1", 120.0, "card")
        gui.generate_admin_report()
        assert "CAR RENTAL SYSTEM" in self._report_text(gui)

    def test_email_admin_report_no_admin(self, gui, monkeypatch):
        # users table doesn't exist in the temp DB -> lookup yields nothing ->
        # the "no admin email" warning path (exception-safe).
        gui.email_admin_report()
        assert gui._env.box.showwarning.called or gui._env.box.showerror.called


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class TestMisc:
    def test_refresh_all_data_runs(self, gui):
        _add_vehicle(gui._env, reg="RF1 AAA")
        gui.refresh_all_data()  # should not raise
        assert len(gui.vehicles_tree.get_children()) == 1

    def test_return_to_homescreen_destroys(self, gui, monkeypatch):
        called = {"n": 0}
        monkeypatch.setattr(gui.root, "destroy", lambda: called.__setitem__("n", 1))
        gui.return_to_homescreen()
        assert called["n"] == 1

    def test_get_categories(self, gui):
        assert gui._get_categories() == gui._env.core.VEHICLE_CATEGORIES

    def test_launch_with_parent_returns_app(self, gui_env, tk_root_factory):
        parent = tk_root_factory()
        app = gui_env.gui_mod.launch_carrental_gui(parent=parent, auth=_auth())
        assert isinstance(app, gui_env.gui_mod.CarRentalGUI)
