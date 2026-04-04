"""Tests for the AssetService in the Primary School system."""

import pytest


class TestCreateAsset:
    """Tests for creating assets."""

    def test_create_asset_returns_dict_with_id(self, asset_service):
        """Creating an asset returns a dict with a valid ID."""
        result = asset_service.create_asset(
            asset_name="Interactive Whiteboard",
            asset_type="IT",
            location="Room 3",
            purchase_date="2025-09-01",
            purchase_cost=1200.00,
            condition="Good",
            serial_number="IWB-0042",
            notes="Installed by vendor",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["asset_name"] == "Interactive Whiteboard"
        assert result["asset_type"] == "IT"

    def test_create_asset_persists(self, asset_service):
        """An asset created via create_asset is retrievable via get_asset."""
        result = asset_service.create_asset(
            asset_name="Teacher Desk",
            asset_type="furniture",
            location="Room 5",
        )
        fetched = asset_service.get_asset(result["id"])
        assert fetched is not None
        assert fetched["asset_name"] == "Teacher Desk"
        assert fetched["asset_type"] == "furniture"
        assert fetched["location"] == "Room 5"
        assert fetched["status"] == "In Use"

    def test_create_asset_minimal_fields(self, asset_service):
        """An asset can be created with only the required name field."""
        result = asset_service.create_asset(asset_name="Football Set")
        assert result["id"] > 0
        fetched = asset_service.get_asset(result["id"])
        assert fetched["asset_name"] == "Football Set"
        assert fetched["condition"] == "Good"


class TestGetAsset:
    """Tests for retrieving a single asset."""

    def test_get_nonexistent_asset_returns_none(self, asset_service):
        """Requesting a non-existent asset ID returns None."""
        assert asset_service.get_asset(99999) is None

    def test_get_asset_returns_all_fields(self, asset_service):
        """get_asset returns a dict containing all stored columns."""
        asset_service.create_asset(
            asset_name="Projector",
            asset_type="IT",
            serial_number="PRJ-100",
            location="Hall",
            purchase_date="2025-01-15",
            purchase_cost=850.00,
            condition="Good",
            notes="Ceiling mounted",
        )
        assets = asset_service.list_assets(asset_type="IT")
        fetched = asset_service.get_asset(assets[0]["id"])
        assert fetched["serial_number"] == "PRJ-100"
        assert fetched["purchase_cost"] == 850.00
        assert fetched["notes"] == "Ceiling mounted"


class TestListAssets:
    """Tests for listing and filtering assets."""

    def test_list_assets_empty_db(self, asset_service):
        """Listing assets on an empty database returns an empty list."""
        assert asset_service.list_assets() == []

    def test_list_assets_filter_by_type(self, asset_service):
        """Filtering by asset_type returns only matching assets."""
        asset_service.create_asset(asset_name="Laptop", asset_type="IT")
        asset_service.create_asset(asset_name="Bookcase", asset_type="furniture")
        it_assets = asset_service.list_assets(asset_type="IT")
        assert len(it_assets) == 1
        assert it_assets[0]["asset_name"] == "Laptop"

    def test_list_assets_filter_by_location(self, asset_service):
        """Filtering by location returns only assets at that location."""
        asset_service.create_asset(
            asset_name="Chair Set", asset_type="furniture", location="Room 1",
        )
        asset_service.create_asset(
            asset_name="Table", asset_type="furniture", location="Room 2",
        )
        room1 = asset_service.list_assets(location="Room 1")
        assert len(room1) == 1
        assert room1[0]["asset_name"] == "Chair Set"


class TestUpdateAsset:
    """Tests for updating assets."""

    def test_update_asset_changes_fields(self, asset_service):
        """Updating an asset persists the new values."""
        result = asset_service.create_asset(
            asset_name="Old Printer", asset_type="IT", condition="Good",
        )
        updated = asset_service.update_asset(
            result["id"], asset_name="New Printer", condition="Fair",
        )
        assert updated["asset_name"] == "New Printer"
        assert updated["condition"] == "Fair"

    def test_update_asset_no_valid_fields_returns_none(self, asset_service):
        """Passing only unrecognised fields returns None."""
        result = asset_service.create_asset(asset_name="Marker Pens")
        assert asset_service.update_asset(result["id"], fake_field="x") is None


class TestDeleteAsset:
    """Tests for deleting assets."""

    def test_delete_existing_asset(self, asset_service):
        """Deleting an existing asset returns True and removes it."""
        result = asset_service.create_asset(asset_name="Broken Monitor")
        assert asset_service.delete_asset(result["id"]) is True
        assert asset_service.get_asset(result["id"]) is None

    def test_delete_nonexistent_asset(self, asset_service):
        """Deleting a non-existent asset returns False."""
        assert asset_service.delete_asset(99999) is False

    def test_delete_does_not_affect_others(self, asset_service):
        """Deleting one asset leaves other assets intact."""
        a1 = asset_service.create_asset(asset_name="Keep Me")
        a2 = asset_service.create_asset(asset_name="Remove Me")
        asset_service.delete_asset(a2["id"])
        assert asset_service.get_asset(a1["id"]) is not None
        assert len(asset_service.list_assets()) == 1
