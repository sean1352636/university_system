"""Fixed-asset register (systems.primary.domain.operations.assets.assets)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.assets import assets as A
from education_system.systems.primary.domain.staff import staff as ST

TODAY = dt.date.today()
_n = 0


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _asset(**extra):
    global _n
    _n += 1
    data = {"asset_tag": f"PA-{_n:04d}", "name": f"Laptop {_n}", "location": "Main Office"}
    data.update(extra)
    return A.create_asset(data)


def _staff(first="Sam", last="Keeper"):
    return ST.create_staff({"first_name": first, "last_name": last})


# ── create / get ──

def test_create_stores_fields_and_defaults():
    keeper = _staff()
    a = A.create_asset({
        "asset_tag": "IT/LAP-01", "name": "  Teacher laptop ", "category": "Laptop",
        "manufacturer": " Dell ", "model": "", "serial_number": "SN1", "location": " Y3 ",
        "room": "R3", "custodian_id": keeper.staff_id.lower(), "purchase_date": "2024-09-01",
        "purchase_cost": "650.5", "residual_value": 50, "useful_life_years": "4",
        "warranty_expiry": "2027-09-01", "supplier": "CDW"})
    got = A.get_asset(a.asset_id)
    assert got == a
    assert (got.asset_tag, got.name, got.category, got.location) == \
        ("IT/LAP-01", "Teacher laptop", "Laptop", "Y3")
    assert (got.manufacturer, got.model, got.serial_number) == ("Dell", None, "SN1")
    assert got.custodian_id == keeper.staff_id
    assert (got.purchase_cost, got.residual_value, got.useful_life_years) == (650.5, 50.0, 4)
    assert (got.depreciation_method, got.condition, got.status) == \
        ("Straight Line", "Good", "In Use")
    assert got.disposal_date is None and got.is_active and not got.is_disposed


def test_defaults_category_other_and_zero_residual():
    a = _asset()
    assert a.category == "Other" and a.residual_value == 0.0 and a.purchase_cost is None


def test_get_by_tag_and_missing():
    a = _asset(asset_tag="TAG-9")
    assert A.get_by_tag(" TAG-9 ").asset_id == a.asset_id
    assert A.get_by_tag("nope") is None
    assert A.get_asset(999) is None


# ── validation ──

def test_tag_required_format_and_unique():
    with pytest.raises(A.ValidationError, match="Asset tag is required"):
        _asset(asset_tag="")
    with pytest.raises(A.ValidationError, match="Asset tag must be 1..32"):
        _asset(asset_tag="-bad")
    with pytest.raises(A.ValidationError, match="Asset tag must be 1..32"):
        _asset(asset_tag="A" * 33)
    _asset(asset_tag="DUP")
    with pytest.raises(A.ValidationError, match="Asset tag 'DUP' is already in use"):
        _asset(asset_tag="DUP")


def test_name_and_location_required():
    with pytest.raises(A.ValidationError, match="Name is required"):
        _asset(name=" ")
    with pytest.raises(A.ValidationError, match="Location is required"):
        _asset(location="")


@pytest.mark.parametrize("field,value,message", [
    ("category", "Spaceship", "Category must be one of"),
    ("condition", "Mint", "Condition must be one of"),
    ("status", "Missing", "Status must be one of"),
    ("depreciation_method", "Sum of digits", "Depreciation method must be one of"),
])
def test_allowed_values(field, value, message):
    with pytest.raises(A.ValidationError, match=message):
        _asset(**{field: value})


def test_unknown_custodian():
    with pytest.raises(A.ValidationError, match="No staff with id T9999999"):
        _asset(custodian_id="t9999999")


def test_dates_must_be_real():
    with pytest.raises(A.ValidationError, match="Purchase date must be YYYY-MM-DD"):
        _asset(purchase_date="1/9/2024")
    with pytest.raises(A.ValidationError, match="Warranty expiry must be a valid date"):
        _asset(warranty_expiry="2024-02-30")


def test_amount_rules():
    with pytest.raises(A.ValidationError, match="Purchase cost must be a number"):
        _asset(purchase_cost="lots", purchase_date="2024-01-01")
    with pytest.raises(A.ValidationError, match="at most 2 decimal places"):
        _asset(purchase_cost="10.001", purchase_date="2024-01-01")
    with pytest.raises(A.ValidationError, match="Purchase cost cannot be negative"):
        _asset(purchase_cost=-1, purchase_date="2024-01-01")


def test_cost_residual_and_date_consistency():
    with pytest.raises(A.ValidationError, match="Residual value requires a purchase cost"):
        _asset(residual_value=10)
    with pytest.raises(A.ValidationError, match="Residual value cannot exceed purchase cost"):
        _asset(purchase_cost=100, residual_value=101, purchase_date="2024-01-01")
    with pytest.raises(A.ValidationError, match="Purchase date is required when"):
        _asset(purchase_cost=100)


def test_useful_life_range():
    with pytest.raises(A.ValidationError, match="Useful life must be a whole number"):
        _asset(useful_life_years="four")
    with pytest.raises(A.ValidationError, match="between 1 and 50"):
        _asset(useful_life_years=0)
    with pytest.raises(A.ValidationError, match="between 1 and 50"):
        _asset(useful_life_years=51)
    assert _asset(useful_life_years=50).useful_life_years == 50


def test_disposal_fields_only_for_disposed_statuses():
    with pytest.raises(A.ValidationError, match="Disposal fields are only valid"):
        _asset(disposal_method="Sold")
    with pytest.raises(A.ValidationError, match="Disposal method must be one of"):
        _asset(status="Disposed", disposal_method="Burnt")
    a = _asset(status="Disposed", disposal_method="Sold", disposal_date="2025-01-01",
               disposal_proceeds="20")
    assert (a.disposal_method, a.disposal_date, a.disposal_proceeds) == \
        ("Sold", "2025-01-01", 20.0)
    assert a.is_disposed and not a.is_active


# ── list / update / status / delete ──

def test_list_filters_and_order():
    keeper = _staff()
    p = _asset(asset_tag="B-2", category="Projector", location="Hall", condition="Fair")
    l1 = _asset(asset_tag="L-2", category="Laptop", custodian_id=keeper.staff_id,
                manufacturer="Lenovo")
    l0 = _asset(asset_tag="L-1", category="Laptop", status="In Repair", serial_number="XYZ")

    def tags(**kw):
        return [a.asset_tag for a in A.list_assets(**kw)]

    assert tags() == ["L-1", "L-2", "B-2"]
    assert tags(category="Laptop") == ["L-1", "L-2"]
    assert tags(status="In Repair") == ["L-1"]
    assert tags(condition="Fair") == ["B-2"]
    assert tags(location="hal") == ["B-2"]
    assert tags(custodian_id=keeper.staff_id.lower()) == ["L-2"]
    assert tags(search="lenovo") == ["L-2"]
    assert tags(search="xyz") == ["L-1"]
    assert {p.asset_id, l1.asset_id, l0.asset_id} == {a.asset_id for a in A.list_assets()}


def test_list_rejects_unknown_filter_values():
    with pytest.raises(A.ValidationError, match="Category must be one of"):
        A.list_assets(category="x")
    with pytest.raises(A.ValidationError, match="Status must be one of"):
        A.list_assets(status="x")
    with pytest.raises(A.ValidationError, match="Condition must be one of"):
        A.list_assets(condition="x")


def test_update_merges_and_keeps_own_tag():
    a = _asset(asset_tag="KEEP", manufacturer="HP")
    out = A.update_asset(a.asset_id, {"name": "Renamed", "condition": "Poor"})
    assert (out.asset_tag, out.name, out.condition, out.manufacturer) == \
        ("KEEP", "Renamed", "Poor", "HP")


def test_update_refuses_taken_tag_and_unknown_asset():
    _asset(asset_tag="TAKEN")
    b = _asset()
    with pytest.raises(A.ValidationError, match="already in use"):
        A.update_asset(b.asset_id, {"asset_tag": "TAKEN"})
    with pytest.raises(A.ValidationError, match="No asset #404"):
        A.update_asset(404, {"name": "x"})


def test_set_status_clears_disposal_when_reinstated():
    a = _asset(status="Lost/Stolen", disposal_method="Stolen", disposal_date="2025-03-01")
    back = A.set_status(a.asset_id, "In Storage")
    assert back.status == "In Storage"
    assert (back.disposal_date, back.disposal_method, back.disposal_proceeds) == (None, None, None)
    with pytest.raises(A.ValidationError, match="Status must be one of"):
        A.set_status(a.asset_id, "Gone")
    with pytest.raises(A.ValidationError, match="No asset #77"):
        A.set_status(77, "Retired")


def test_delete_cascades_maintenance():
    a = _asset()
    m = A.add_maintenance(a.asset_id, {"service_date": "2025-01-01"})
    assert A.delete_asset(a.asset_id) is True
    assert A.get_maintenance(m.maintenance_id) is None
    assert A.delete_asset(a.asset_id) is False


def test_deleting_custodian_sets_null():
    keeper = _staff()
    a = _asset(custodian_id=keeper.staff_id)
    assert ST.delete_staff(keeper.staff_id)
    assert A.get_asset(a.asset_id).custodian_id is None


# ── maintenance ──

def test_add_maintenance_defaults_and_values():
    tech = _staff("Tech", "Person")
    a = _asset()
    m = A.add_maintenance(a.asset_id, {"service_type": "PAT Test", "staff_id": tech.staff_id,
                                       "performed_by": " Sparky Ltd ", "cost": "12.50",
                                       "next_service_due": "2026-01-01", "notes": " ok "})
    got = A.get_maintenance(m.maintenance_id)
    assert got == m
    assert (got.service_date, got.service_type, got.outcome) == \
        (TODAY.isoformat(), "PAT Test", "Completed")
    assert (got.performed_by, got.staff_id, got.cost, got.notes) == \
        ("Sparky Ltd", tech.staff_id, 12.5, "ok")


def test_maintenance_validation():
    a = _asset()
    with pytest.raises(A.ValidationError, match="No asset #55"):
        A.add_maintenance(55, {})
    with pytest.raises(A.ValidationError, match="Service type must be one of"):
        A.add_maintenance(a.asset_id, {"service_type": "Polish"})
    with pytest.raises(A.ValidationError, match="Outcome must be one of"):
        A.add_maintenance(a.asset_id, {"outcome": "Meh"})
    with pytest.raises(A.ValidationError, match="Cost cannot be negative"):
        A.add_maintenance(a.asset_id, {"cost": -5})
    with pytest.raises(A.ValidationError, match="Service date must be a valid date"):
        A.add_maintenance(a.asset_id, {"service_date": "2025-13-01"})
    with pytest.raises(A.ValidationError, match="No staff with id"):
        A.add_maintenance(a.asset_id, {"staff_id": "T1"})


def test_list_maintenance_filters_and_order():
    a, b = _asset(), _asset()
    m1 = A.add_maintenance(a.asset_id, {"service_date": "2025-01-10", "service_type": "Repair",
                                        "outcome": "Failed"})
    m2 = A.add_maintenance(a.asset_id, {"service_date": "2025-03-01"})
    m3 = A.add_maintenance(b.asset_id, {"service_date": "2025-03-01"})

    def ids(**kw):
        return [m.maintenance_id for m in A.list_maintenance(**kw)]

    assert ids() == [m3.maintenance_id, m2.maintenance_id, m1.maintenance_id]
    assert ids(asset_id=a.asset_id) == [m2.maintenance_id, m1.maintenance_id]
    assert ids(service_type="Repair") == ids(outcome="Failed") == [m1.maintenance_id]
    assert ids(date_from="2025-02-01") == [m3.maintenance_id, m2.maintenance_id]
    assert ids(date_to="2025-02-01") == [m1.maintenance_id]
    with pytest.raises(A.ValidationError, match="Service type must be one of"):
        A.list_maintenance(service_type="x")
    with pytest.raises(A.ValidationError, match="Outcome must be one of"):
        A.list_maintenance(outcome="x")
    with pytest.raises(A.ValidationError, match="date_from must be YYYY-MM-DD"):
        A.list_maintenance(date_from="Jan")


def test_update_and_delete_maintenance():
    a = _asset()
    m = A.add_maintenance(a.asset_id, {"service_date": "2025-01-10", "cost": 5})
    out = A.update_maintenance(m.maintenance_id, {"outcome": "Partial"})
    assert (out.outcome, out.cost, out.service_date) == ("Partial", 5.0, "2025-01-10")
    with pytest.raises(A.ValidationError, match="No maintenance entry #99"):
        A.update_maintenance(99, {})
    assert A.delete_maintenance(m.maintenance_id) is True
    assert A.delete_maintenance(m.maintenance_id) is False


# ── book value ──

def test_book_value_straight_line():
    a = _asset(purchase_cost=1000, residual_value=100, useful_life_years=8,
               purchase_date="2020-01-01")
    # 2020-01-01 → 2024-01-01 is 1461 days = exactly 4 years: half the life gone.
    assert A.book_value(a, as_of=dt.date(2024, 1, 1)) == 550.0
    assert A.book_value(a, as_of=dt.date(2019, 6, 1)) == 1000.0
    assert A.book_value(a, as_of=dt.date(2040, 1, 1)) == 100.0


def test_book_value_reducing_balance():
    a = _asset(purchase_cost=1600, residual_value=100, useful_life_years=4,
               purchase_date="2020-01-01", depreciation_method="Reducing Balance")
    # rate r = 1 - (100/1600) ** (1/4) = 0.5
    assert A.book_value(a, as_of=dt.date(2022, 1, 1)) == \
        round(1600 * 0.5 ** (731 / 365.25), 2)
    assert A.book_value(a, as_of=dt.date(2030, 1, 1)) == 100.0


def test_book_value_reducing_balance_without_residual_uses_25_percent():
    a = _asset(purchase_cost=1000, useful_life_years=10, purchase_date="2020-01-01",
               depreciation_method="Reducing Balance")
    assert A.book_value(a, as_of=dt.date(2024, 1, 1)) == 316.41


def test_book_value_without_depreciation_inputs():
    assert A.book_value(_asset()) == 0.0
    none = _asset(purchase_cost=300, purchase_date="2020-01-01", useful_life_years=3,
                  depreciation_method="None")
    assert A.book_value(none, as_of=dt.date(2030, 1, 1)) == 300.0
    no_life = _asset(purchase_cost=300, purchase_date="2020-01-01")
    assert A.book_value(no_life, as_of=dt.date(2030, 1, 1)) == 300.0


# ── views ──

def test_view_asset():
    keeper = _staff("Kim", "Custodian")
    a = _asset(custodian_id=keeper.staff_id, purchase_date=_iso(-100), purchase_cost=500,
               depreciation_method="None", useful_life_years=5)
    A.add_maintenance(a.asset_id, {"service_date": "2025-01-01"})
    A.add_maintenance(a.asset_id, {"service_date": "2025-06-01"})
    v = A.view_asset(a.asset_id)
    assert (v.maintenance_count, v.last_service_date) == (2, "2025-06-01")
    assert v.custodian_name == keeper.full_name
    assert (v.current_book_value, v.age_days) == (500.0, 100)
    assert A.view_asset(12345) is None


def test_list_views_passes_filters():
    _asset(category="Laptop")
    _asset(category="Tablet")
    views = A.list_views(category="Tablet")
    assert [v.asset.category for v in views] == ["Tablet"]
    assert views[0].maintenance_count == 0 and views[0].custodian_name is None
    assert A.list_views(category="Monitor") == []


# ── summary ──

def test_summary_figures():
    _asset(category="Laptop", location="Office", purchase_cost=200, depreciation_method="None",
           purchase_date=_iso(-400), useful_life_years=3)            # no service, >1y old
    serviced = _asset(category="Laptop", location="Office", purchase_cost=100,
                      purchase_date=_iso(-400), useful_life_years=3, depreciation_method="None",
                      warranty_expiry=_iso(-1), next_audit_due=_iso(-1))
    A.add_maintenance(serviced.asset_id, {"service_date": _iso(-10)})
    _asset(category="Tablet", location="Hall", condition="Poor", status="Retired",
           warranty_expiry=_iso(-5), next_audit_due=_iso(-5), purchase_date=_iso(-800))
    _asset(category="Tablet", location="Y6", purchase_date=_iso(-30), warranty_expiry=_iso(30))
    s = A.summary()
    assert s.total_assets == 4
    assert (s.by_category["Laptop"], s.by_category["Tablet"], s.by_category["Other"]) == (2, 2, 0)
    assert (s.by_status["In Use"], s.by_status["Retired"], s.by_status["Disposed"]) == (3, 1, 0)
    assert (s.by_condition["Good"], s.by_condition["Poor"]) == (3, 1)
    assert s.by_location[0] == ("Office", 2)
    assert sorted(s.by_location[1:]) == [("Hall", 1), ("Y6", 1)]
    assert (s.total_purchase_cost, s.total_book_value) == (300.0, 300.0)
    assert s.count_overdue_service == 1
    assert s.count_warranty_expired == 1
    assert s.count_due_for_audit == 1


def test_summary_empty():
    s = A.summary()
    assert s.total_assets == 0 and s.by_location == []
    assert s.total_purchase_cost == 0.0 and s.total_book_value == 0.0
    assert set(s.by_category) == set(A.CATEGORIES)
