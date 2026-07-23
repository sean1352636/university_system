"""Behavioral tests for the Charity Shop CLI donations/donor surface.

Covers the pure value estimator, donor CRUD, donation recording (and its effect on
donor totals), the tax-receipt generator (including the known hardcoded
``tax_id`` placeholder), donation-drive aggregation, and the thank-you letter
generator. Isolation matches the inventory suite: temp DB via ``DEFAULT_DB_PATH``,
schema from ``init_charity_shop_db()``, activity logger disabled.
"""

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli.charity_shop_cli import (
    db as csdb,
    donations,
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
    db_path = str(tmp_path / "charity.db")
    monkeypatch.setattr(_DB_PATH_ATTR, db_path)
    monkeypatch.setattr(donations, "ACTIVITY_LOGGER_AVAILABLE", False, raising=False)
    assert csdb.init_charity_shop_db() is True
    return db_path


# ---------------------------------------------------------------------------
# Pure helper: value estimator
# ---------------------------------------------------------------------------

class TestValueEstimator:
    def test_known_category_and_condition(self):
        # Electronics base 25.00 * New multiplier 1.5 = 37.50
        assert donations.donation_value_estimator("Electronics", "New") == 37.50

    def test_good_condition_is_base_value(self):
        assert donations.donation_value_estimator("Books", "Good") == 3.00

    def test_unknown_category_falls_back_to_default(self):
        # Unknown category -> 5.00 base, Fair multiplier 0.6 -> 3.00
        assert donations.donation_value_estimator("Spaceship", "Fair") == 3.00

    def test_unknown_condition_multiplier_is_one(self):
        assert donations.donation_value_estimator("Clothing", "Mint") == 8.00

    def test_result_is_rounded(self):
        val = donations.donation_value_estimator("Toys", "Excellent")  # 5 * 1.2
        assert val == 6.00


# ---------------------------------------------------------------------------
# Donor database CRUD
# ---------------------------------------------------------------------------

class TestDonorDatabase:
    def test_add_returns_id_and_persists(self, shop_db):
        donor_id = donations.donor_database("add", name="Jane Doe", email="jane@x.com")
        assert isinstance(donor_id, int)
        rows = _rows(shop_db, f"SELECT * FROM {_imp.DONORS_TABLE} WHERE id = ?", (donor_id,))
        assert rows[0]["name"] == "Jane Doe"
        assert rows[0]["email"] == "jane@x.com"

    def test_get_returns_full_dict(self, shop_db):
        donor_id = donations.donor_database("add", name="Bob", phone="555")
        donor = donations.donor_database("get", donor_id=donor_id)
        assert donor["name"] == "Bob"
        assert donor["phone"] == "555"
        assert donor["total_donations"] == 0

    def test_get_missing_returns_none(self, shop_db):
        assert donations.donor_database("get", donor_id=987654) is None

    def test_search_matches_name(self, shop_db):
        donations.donor_database("add", name="Alice Smith", email="alice@x.com")
        donations.donor_database("add", name="Charlie", email="charlie@y.com")
        found = donations.donor_database("search", term="Alice")
        assert len(found) == 1
        assert found[0]["name"] == "Alice Smith"

    def test_list_returns_all(self, shop_db):
        donations.donor_database("add", name="D1")
        donations.donor_database("add", name="D2")
        assert len(donations.donor_database("list")) == 2

    def test_unknown_action_returns_none(self, shop_db):
        assert donations.donor_database("frobnicate") is None


# ---------------------------------------------------------------------------
# record_donation
# ---------------------------------------------------------------------------

class TestRecordDonation:
    def test_record_persists_and_updates_donor_totals(self, shop_db):
        donor_id = donations.donor_database("add", name="Giver")
        d_id = donations.record_donation(
            donor_id, "Box of books", category="Books", quantity=5, estimated_value=15.0
        )
        assert isinstance(d_id, int)
        drow = _rows(shop_db, f"SELECT * FROM {_imp.DONATIONS_TABLE} WHERE id = ?", (d_id,))[0]
        assert drow["item_description"] == "Box of books"
        assert drow["receipt_number"].startswith("DON-")
        # Donor rollups updated.
        donor = _rows(shop_db, f"SELECT * FROM {_imp.DONORS_TABLE} WHERE id = ?", (donor_id,))[0]
        assert donor["total_donations"] == 1
        assert donor["total_value"] == 15.0

    def test_multiple_donations_accumulate(self, shop_db):
        donor_id = donations.donor_database("add", name="Repeat")
        donations.record_donation(donor_id, "A", estimated_value=10.0)
        donations.record_donation(donor_id, "B", estimated_value=5.0)
        donor = _rows(shop_db, f"SELECT * FROM {_imp.DONORS_TABLE} WHERE id = ?", (donor_id,))[0]
        assert donor["total_donations"] == 2
        assert donor["total_value"] == 15.0


# ---------------------------------------------------------------------------
# generate_donation_receipt  (tax_id / organization sourced from env config)
# ---------------------------------------------------------------------------

class TestDonationReceipt:
    def test_receipt_tax_id_empty_when_unconfigured(self, shop_db, monkeypatch):
        monkeypatch.delenv("CHARITY_TAX_ID", raising=False)
        monkeypatch.delenv("CHARITY_ORG_NAME", raising=False)
        donor_id = donations.donor_database("add", name="Taxpayer", email="t@x.com",
                                            address="1 Road")
        d_id = donations.record_donation(donor_id, "Chair", category="Furniture",
                                         quantity=1, estimated_value=20.0)
        receipt = donations.generate_donation_receipt(d_id)
        # No fake ID when unconfigured; falls back to empty string + default name.
        assert receipt["tax_id"] == ""
        assert receipt["organization"] == "University Charity Shop"
        assert receipt["donor_name"] == "Taxpayer"
        assert receipt["item_description"] == "Chair"

    def test_receipt_tax_id_from_env(self, shop_db, monkeypatch):
        monkeypatch.setenv("CHARITY_TAX_ID", "12-3456789")
        monkeypatch.setenv("CHARITY_ORG_NAME", "Acme Charity")
        donor_id = donations.donor_database("add", name="Taxpayer", email="t@x.com",
                                            address="1 Road")
        d_id = donations.record_donation(donor_id, "Chair", category="Furniture",
                                         quantity=1, estimated_value=20.0)
        receipt = donations.generate_donation_receipt(d_id)
        assert receipt["tax_id"] == "12-3456789"
        assert receipt["organization"] == "Acme Charity"

    def test_receipt_missing_donation_returns_none(self, shop_db):
        assert donations.generate_donation_receipt(555555) is None


# ---------------------------------------------------------------------------
# donation_drive_tracker
# ---------------------------------------------------------------------------

class TestDonationDrives:
    def test_summary_aggregates_drive(self, shop_db):
        donor_id = donations.donor_database("add", name="Driver")
        donations.record_donation(donor_id, "X", quantity=2, estimated_value=10.0,
                                  donation_drive_id="SPRING")
        donations.record_donation(donor_id, "Y", quantity=3, estimated_value=5.0,
                                  donation_drive_id="SPRING")
        summary = donations.donation_drive_tracker("summary", drive_id="SPRING")
        assert summary["total_donations"] == 2
        assert summary["total_items"] == 5
        assert summary["total_value"] == 15.0

    def test_list_drives_only_includes_named_drives(self, shop_db):
        donor_id = donations.donor_database("add", name="Driver2")
        donations.record_donation(donor_id, "Z", estimated_value=1.0, donation_drive_id="XMAS")
        donations.record_donation(donor_id, "NoDrive", estimated_value=1.0)  # no drive id
        drives = donations.donation_drive_tracker("list_drives")
        ids = {d["drive_id"] for d in drives}
        assert ids == {"XMAS"}


# ---------------------------------------------------------------------------
# thank_you_letter_generator
# ---------------------------------------------------------------------------

class TestThankYouLetter:
    def test_letter_summarises_year_donations(self, shop_db):
        donor_id = donations.donor_database("add", name="Grace", email="g@x.com")
        donations.record_donation(donor_id, "Item", quantity=2, estimated_value=12.0)
        year = int(_imp.datetime.now().year)
        letter = donations.thank_you_letter_generator(donor_id, year=year)
        assert letter["donor_name"] == "Grace"
        assert letter["donation_count"] == 1
        assert letter["items_donated"] == 2
        assert "Grace" in letter["letter_text"]

    def test_missing_donor_returns_empty(self, shop_db):
        assert donations.thank_you_letter_generator(424242) == {}
