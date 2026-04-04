"""Tests for AssetService."""
import pytest


class TestAsset:
    def test_add_asset(self, asset_service):
        asset = asset_service.add_asset(
            asset_tag="IT-001", name="Dell Laptop",
            category="IT", location="Room 101",
            purchase_cost=450.0,
        )
        assert asset["name"] == "Dell Laptop"
        assert asset["category"] == "IT"

    def test_list_assets(self, asset_service):
        asset_service.add_asset("IT-001", "Laptop A", category="IT")
        asset_service.add_asset("FUR-001", "Desk B", category="furniture")
        assets = asset_service.list_assets()
        assert len(assets) >= 2

    def test_list_assets_filters_by_category(self, asset_service):
        asset_service.add_asset("IT-001", "Laptop", category="IT")
        asset_service.add_asset("FUR-001", "Chair", category="furniture")
        assets = asset_service.list_assets(category="IT")
        assert all(a["category"] == "IT" for a in assets)

    def test_update_asset(self, asset_service):
        asset = asset_service.add_asset("IT-002", "Old Name", category="IT")
        asset_service.update_asset(asset["id"], name="New Name", location="Room 202")
        assets = asset_service.list_assets()
        updated = [a for a in assets if a["id"] == asset["id"]][0]
        assert updated["name"] == "New Name"
        assert updated["location"] == "Room 202"

    def test_delete_asset(self, asset_service):
        asset = asset_service.add_asset("IT-003", "Delete Me", category="IT")
        asset_service.delete_asset(asset["id"])
        assets = asset_service.list_assets()
        assert all(a["id"] != asset["id"] for a in assets)

    def test_asset_summary(self, asset_service):
        asset_service.add_asset("IT-010", "Laptop 1", category="IT", purchase_cost=500.0)
        asset_service.add_asset("IT-011", "Laptop 2", category="IT", purchase_cost=600.0)
        asset_service.add_asset("FUR-010", "Chair", category="furniture", purchase_cost=100.0)
        summary = asset_service.asset_summary()
        assert isinstance(summary, list)
        assert len(summary) >= 2
        it_row = [s for s in summary if s["category"] == "IT"][0]
        assert it_row["cnt"] >= 2
