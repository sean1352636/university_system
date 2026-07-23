"""Behavioral tests for the Charity Shop CLI inventory surface + shared plumbing.

The charity shop CLI (``modules.services.cli.charity_shop_cli``) is the largest CLI
package in the university system. Its testable surface is almost entirely
direct-argument, DB-backed functions (CRUD, summaries, bulk import/export) plus a
handful of pure helpers, so we drive the functions directly rather than the menu
loop.

Isolation mirrors the gym-cli template: repoint the shared ``DEFAULT_DB_PATH`` at a
temp file (``get_connection`` reads it at call time), build the schema via the
package's own ``init_charity_shop_db()``, and neutralise the activity-logger seam so
nothing escapes the test.
"""

import csv

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli.charity_shop_cli import (
    db as csdb,
    inventory,
    _imports as _imp,
)

_DB_PATH_ATTR = (
    "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH"
)


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def shop_db(tmp_path, monkeypatch):
    """Temp DB + full charity-shop schema, activity logger disabled."""
    db_path = str(tmp_path / "charity.db")
    monkeypatch.setattr(_DB_PATH_ATTR, db_path)
    # Silence the audit fan-out in every submodule that references it.
    for mod in (inventory,):
        monkeypatch.setattr(mod, "ACTIVITY_LOGGER_AVAILABLE", False, raising=False)
    assert csdb.init_charity_shop_db() is True
    return db_path


# ---------------------------------------------------------------------------
# Schema / init
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_creates_expected_tables(self, shop_db):
        tables = {
            r["name"]
            for r in _rows(shop_db, "SELECT name FROM sqlite_master WHERE type='table'")
        }
        for expected in (
            _imp.TABLE_NAME,
            _imp.CUSTOMERS_TABLE,
            _imp.DONATIONS_TABLE,
            _imp.DONORS_TABLE,
            _imp.STAFF_TABLE,
            _imp.SALES_TABLE,
        ):
            assert expected in tables

    def test_init_is_idempotent(self, shop_db):
        # Re-running against an existing schema must still succeed.
        assert csdb.init_charity_shop_db() is True


# ---------------------------------------------------------------------------
# auth / permission plumbing (set_auth seam)
# ---------------------------------------------------------------------------

class TestAuthPlumbing:
    def test_set_auth_stores_global(self, monkeypatch):
        sentinel = object()
        # Avoid touching the real shared-context / auth-instance setters.
        monkeypatch.setattr(_imp, "HAS_AUTH", False, raising=False)
        _imp.set_auth(sentinel)
        assert _imp.auth is sentinel
        _imp.set_auth(None)  # reset for other tests

    def test_setup_permissions_grants_roles(self, monkeypatch):
        granted = []

        class FakeAuth:
            def add_permission_to_role(self, role, perm):
                granted.append((role, perm))

        csdb.setup_charity_shop_permissions(FakeAuth())
        # Admin should receive the full delete-capable permission set.
        assert ("admin", "delete_charity_shop_item") in granted
        # Staff must NOT get delete permissions.
        assert ("staff", "delete_charity_shop_item") not in granted
        assert ("staff", "add_charity_shop_item") in granted
        # Students only get view.
        assert ("student", "view_charity_shop_stock") in granted

    def test_setup_permissions_no_auth_is_noop(self, monkeypatch):
        # No auth instance and no global auth -> returns quietly.
        monkeypatch.setattr(_imp, "auth", None, raising=False)
        monkeypatch.setattr(csdb, "get_auth", lambda: None, raising=False)
        assert csdb.setup_charity_shop_permissions(None) is None


# ---------------------------------------------------------------------------
# add / read
# ---------------------------------------------------------------------------

class TestAddAndRead:
    def test_add_item_persists_row(self, shop_db):
        assert inventory.add_item("Novel", "Books", 2.50, 4, "Good") is True
        rows = _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME}")
        assert len(rows) == 1
        assert rows[0]["name"] == "Novel"
        assert rows[0]["category"] == "Books"
        assert rows[0]["price"] == 2.50
        assert rows[0]["quantity"] == 4
        assert rows[0]["sold"] == 0

    def test_get_all_stock_ordered_by_name(self, shop_db):
        inventory.add_item("Zebra", "Toys", 1.0, 1, "Good")
        inventory.add_item("Apple", "Toys", 1.0, 1, "Good")
        names = [r[1] for r in inventory.get_all_stock()]
        assert names == ["Apple", "Zebra"]

    def test_search_stock_filters_by_name_and_category(self, shop_db):
        inventory.add_item("Red Mug", "Homeware", 1.0, 1, "Good")
        inventory.add_item("Blue Mug", "Homeware", 1.0, 1, "Good")
        inventory.add_item("Red Shirt", "Clothing", 1.0, 1, "Good")
        both = inventory.search_stock("Mug")
        assert {r[1] for r in both} == {"Red Mug", "Blue Mug"}
        clothing = inventory.search_stock("Red", category="Clothing")
        assert {r[1] for r in clothing} == {"Red Shirt"}

    def test_search_available_vs_sold_filter(self, shop_db):
        inventory.add_item("Widget", "Other", 5.0, 2, "Good")
        item_id = _rows(shop_db, f"SELECT id FROM {_imp.TABLE_NAME}")[0]["id"]
        inventory.mark_as_sold(item_id)  # sells all -> sold flag set
        assert inventory.search_stock("Widget", show_sold="available") == []
        assert len(inventory.search_stock("Widget", show_sold="sold")) == 1


# ---------------------------------------------------------------------------
# update / sell / delete
# ---------------------------------------------------------------------------

class TestMutations:
    def _one_item(self, shop_db, qty=5):
        inventory.add_item("Lamp", "Homeware", 10.0, qty, "Good")
        return _rows(shop_db, f"SELECT id FROM {_imp.TABLE_NAME}")[0]["id"]

    def test_update_item_changes_fields(self, shop_db):
        iid = self._one_item(shop_db)
        assert inventory.update_item(iid, "Lamp XL", "Homeware", 12.0, 3, "Excellent", False) is True
        row = _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME} WHERE id = ?", (iid,))[0]
        assert row["name"] == "Lamp XL"
        assert row["price"] == 12.0
        assert row["condition"] == "Excellent"

    def test_mark_as_sold_partial_keeps_available(self, shop_db):
        iid = self._one_item(shop_db, qty=5)
        assert inventory.mark_as_sold(iid, quantity_sold=2) is True
        row = _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME} WHERE id = ?", (iid,))[0]
        assert row["quantity"] == 3
        assert row["sold_quantity"] == 2
        assert row["sold"] == 0  # still stock left

    def test_mark_as_sold_full_sets_flag(self, shop_db):
        iid = self._one_item(shop_db, qty=2)
        assert inventory.mark_as_sold(iid) is True  # default sells all
        row = _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME} WHERE id = ?", (iid,))[0]
        assert row["quantity"] == 0
        assert row["sold"] == 1
        assert row["sold_date"] is not None

    def test_mark_as_sold_missing_item_returns_false(self, shop_db):
        assert inventory.mark_as_sold(99999) is False

    def test_mark_as_available_clears_sold(self, shop_db):
        iid = self._one_item(shop_db, qty=1)
        inventory.mark_as_sold(iid)
        assert inventory.mark_as_available(iid) is True
        row = _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME} WHERE id = ?", (iid,))[0]
        assert row["sold"] == 0
        assert row["sold_date"] is None

    def test_delete_item_removes_row(self, shop_db):
        iid = self._one_item(shop_db)
        assert inventory.delete_item(iid) is True
        assert _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME} WHERE id = ?", (iid,)) == []

    def test_adjust_stock_quantity_floors_at_zero(self, shop_db):
        iid = self._one_item(shop_db, qty=3)
        assert inventory.adjust_stock_quantity(iid, -10) is True
        row = _rows(shop_db, f"SELECT quantity FROM {_imp.TABLE_NAME} WHERE id = ?", (iid,))[0]
        assert row["quantity"] == 0

    def test_adjust_stock_missing_item_false(self, shop_db):
        assert inventory.adjust_stock_quantity(4242, 5) is False

    def test_merge_duplicate_items_combines_and_deletes(self, shop_db):
        inventory.add_item("Chair", "Furniture", 8.0, 2, "Good")
        inventory.add_item("Chair", "Furniture", 8.0, 3, "Good")
        ids = [r["id"] for r in _rows(shop_db, f"SELECT id FROM {_imp.TABLE_NAME} ORDER BY id")]
        keep, merge = ids[0], ids[1]
        assert inventory.merge_duplicate_items(keep, merge) is True
        remaining = _rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME}")
        assert len(remaining) == 1
        assert remaining[0]["id"] == keep
        assert remaining[0]["quantity"] == 5

    def test_merge_missing_item_false(self, shop_db):
        iid = self._one_item(shop_db)
        assert inventory.merge_duplicate_items(iid, 999999) is False


# ---------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------

class TestSummaries:
    def test_stock_summary_counts_available_value(self, shop_db):
        inventory.add_item("A", "Books", 2.0, 3, "Good")  # value 6
        inventory.add_item("B", "Books", 5.0, 2, "Good")  # value 10
        total_items, total_qty, total_value = inventory.get_stock_summary()
        assert total_items == 2
        assert total_qty == 5
        assert total_value == 16.0

    def test_revenue_summary_from_sold(self, shop_db):
        inventory.add_item("Sold", "Books", 4.0, 5, "Good")
        iid = _rows(shop_db, f"SELECT id FROM {_imp.TABLE_NAME}")[0]["id"]
        inventory.mark_as_sold(iid, quantity_sold=3)
        sold_items, total_sold, total_revenue = inventory.get_revenue_summary()
        assert sold_items == 1
        assert total_sold == 3
        assert total_revenue == 12.0

    def test_stock_by_category_groups(self, shop_db):
        inventory.add_item("A", "Books", 1.0, 1, "Good")
        inventory.add_item("B", "Books", 1.0, 1, "Good")
        inventory.add_item("C", "Toys", 1.0, 1, "Good")
        by_cat = dict((r[0], r[1]) for r in inventory.get_stock_by_category())
        assert by_cat["Books"] == 2
        assert by_cat["Toys"] == 1


# ---------------------------------------------------------------------------
# low stock
# ---------------------------------------------------------------------------

class TestLowStock:
    def test_view_low_stock_uses_default_threshold(self, shop_db):
        inventory.add_item("Plenty", "Books", 1.0, 50, "Good")
        inventory.add_item("Scarce", "Books", 1.0, 2, "Good")
        low = inventory.view_low_stock_items()  # default threshold 5
        names = {r[1] for r in low}
        assert "Scarce" in names
        assert "Plenty" not in names

    def test_set_low_stock_alert_persists(self, shop_db):
        inventory.add_item("X", "Books", 1.0, 8, "Good")
        iid = _rows(shop_db, f"SELECT id FROM {_imp.TABLE_NAME}")[0]["id"]
        assert inventory.set_low_stock_alert(iid, 10) is True
        # With threshold 10 and qty 8, item now surfaces as low stock.
        low_ids = {r[0] for r in inventory.view_low_stock_items()}
        assert iid in low_ids


# ---------------------------------------------------------------------------
# bulk import / export (CSV round trip)
# ---------------------------------------------------------------------------

class TestBulkCsv:
    def test_bulk_import_counts_success_and_errors(self, shop_db, tmp_path):
        csv_path = tmp_path / "import.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["name", "category", "price", "quantity", "condition"])
            w.writerow(["Good Item", "Books", "3.0", "2", "Good"])
            w.writerow(["Bad Price", "Books", "notanumber", "1", "Good"])
            w.writerow(["", "Books", "1.0", "1", "Good"])  # empty name -> error
        success, errors = inventory.bulk_import_items(str(csv_path))
        assert success == 1
        assert errors == 2
        assert len(_rows(shop_db, f"SELECT * FROM {_imp.TABLE_NAME}")) == 1

    def test_bulk_import_missing_file(self, shop_db, tmp_path):
        assert inventory.bulk_import_items(str(tmp_path / "nope.csv")) == (0, -1)

    def test_bulk_export_writes_rows(self, shop_db, tmp_path):
        inventory.add_item("Exp", "Books", 1.0, 1, "Good")
        out = tmp_path / "export.csv"
        assert inventory.bulk_export_items(str(out)) is True
        with open(out, newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))
        assert reader[0][1] == "name"  # header
        assert any(row and row[1] == "Exp" for row in reader[1:])
