"""CLI flows for Secondary School Assets."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.secondary.domain.governance.assets import assets as data
from education_system.systems.secondary.domain.governance.assets.assets import (
    Asset,
    CATEGORIES,
    CONDITIONS,
    CURRENCY_SYMBOL,
    DEFAULT_CATEGORY,
    DEFAULT_CONDITION,
    DEFAULT_DEPRECIATION_METHOD,
    DEFAULT_MAINTENANCE_OUTCOME,
    DEFAULT_SERVICE_TYPE,
    DEFAULT_STATUS,
    DEPRECIATION_METHODS,
    DISPOSAL_METHODS,
    DISPOSED_STATUSES,
    MAINTENANCE_OUTCOMES,
    MaintenanceEntry,
    SERVICE_TYPES,
    STATUSES,
    ValidationError,
)
from education_system.systems.secondary.domain.staff import staff as _staff

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default,
                            allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_optional(label: str, options: list[str],
                       default: str | None = None) -> str | None:
    raw = _input(f"{label} (blank for none)",
                  default=default or "")
    if not raw.strip():
        return None
    if raw not in options:
        print(f"    Must be one of: {', '.join(options)}")
        return _pick_optional(label, options, default)
    return raw


def _pick_staff_optional(default: str | None = None) -> str | None:
    rows = _staff.list_staff() if hasattr(_staff,
                                              "list_staff") else []
    if not rows:
        return _input("Staff id (blank for none)",
                        default=default or "") or None
    print("\n  Staff:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.staff_id:<10}  {s.full_name}")
    raw = _input(
        f"Pick #1..{len(rows)} or id (blank for none)",
        default=default or "")
    if not raw.strip():
        return None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(rows):
            return rows[n - 1].staff_id
    m = next((s for s in rows
                if s.staff_id.upper() == raw.upper()), None)
    if m:
        return m.staff_id
    print("    No matching staff — leaving blank.")
    return None


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


# ── Print helpers ──────────────────────────────────────────────────

def _print_views(rows: list[data.AssetView]) -> None:
    if not rows:
        print("\n  (no assets)")
        return
    print()
    print(f"  {'#':>4}  {'Tag':<12}  {'Name':<24}  "
          f"{'Category':<18}  {'Location':<18}  "
          f"{'Custodian':<18}  {'Cond':<10}  {'Status':<15}  "
          f"{'Book':>10}")
    print("  " + "-" * 150)
    for v in rows:
        a = v.asset
        print(f"  {a.asset_id:>4}  {a.asset_tag[:12]:<12}  "
              f"{a.name[:24]:<24}  {a.category[:18]:<18}  "
              f"{a.location[:18]:<18}  "
              f"{(v.custodian_name or '—')[:18]:<18}  "
              f"{a.condition:<10}  {a.status:<15}  "
              f"{_money(v.current_book_value):>10}")
    print(f"\n  {len(rows)} asset(s).")


def _print_maintenance(rows: list[MaintenanceEntry]) -> None:
    if not rows:
        print("\n  (no maintenance entries)")
        return
    print()
    print(f"  {'#':>4}  {'Asset':>5}  {'Date':<10}  "
          f"{'Type':<18}  {'Performed by':<22}  "
          f"{'Cost':>9}  {'Outcome':<10}  Next due")
    print("  " + "-" * 110)
    for m in rows:
        print(f"  {m.maintenance_id:>4}  {m.asset_id:>5}  "
              f"{m.service_date:<10}  "
              f"{m.service_type[:18]:<18}  "
              f"{(m.performed_by or '—')[:22]:<22}  "
              f"{_money(m.cost):>9}  {m.outcome:<10}  "
              f"{m.next_service_due or '—'}")
    print(f"\n  {len(rows)} entry(ies).")


def _print_full(v: data.AssetView) -> None:
    a = v.asset
    print()
    print(f"    #{a.asset_id}  Tag {a.asset_tag}")
    print(f"    Name              : {a.name}")
    print(f"    Category          : {a.category}")
    print(f"    Manufacturer/Model: "
          f"{a.manufacturer or '—'} / {a.model or '—'}")
    print(f"    Serial number     : {a.serial_number or '—'}")
    print(f"    Location          : {a.location}")
    print(f"    Room              : {a.room or '—'}")
    print(f"    Custodian         : "
          f"{a.custodian_id or '—'}"
          + (f"  ({v.custodian_name})" if v.custodian_name else ""))
    print(f"    Purchase          : "
          f"{a.purchase_date or '—'}  {_money(a.purchase_cost)}")
    print(f"    Supplier          : {a.supplier or '—'}")
    print(f"    Warranty expiry   : {a.warranty_expiry or '—'}"
          + ("  (EXPIRED)" if a.warranty_expired else ""))
    print(f"    Useful life       : "
          f"{a.useful_life_years or '—'} year(s)")
    print(f"    Depreciation      : {a.depreciation_method}")
    print(f"    Residual value    : {_money(a.residual_value)}")
    print(f"    Current book value: "
          f"{_money(v.current_book_value)}")
    print(f"    Age               : {v.age_days} day(s)")
    print(f"    Condition         : {a.condition}")
    print(f"    Status            : {a.status}")
    if a.is_disposed:
        print(f"    Disposal          : "
              f"{a.disposal_date or '—'}  "
              f"{a.disposal_method or '—'}  "
              f"{_money(a.disposal_proceeds)}")
    print(f"    Last audit        : {a.last_audit_date or '—'}")
    print(f"    Next audit due    : {a.next_audit_due or '—'}"
          + ("  (OVERDUE)" if a.audit_overdue else ""))
    print(f"    Maintenance count : {v.maintenance_count}  "
          f"(last: {v.last_service_date or '—'})")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


def _pick_asset() -> Asset:
    rows = data.list_assets()
    if not rows:
        print("    No assets yet.")
        raise _UserAbort
    print("\n  Assets:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.asset_id:<4} {a.asset_tag:<12}  "
              f"{a.name[:30]:<30}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id/tag)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            m = next((r for r in rows if r.asset_id == n), None)
            if m:
                return m
        m = next((r for r in rows
                    if r.asset_tag.lower() == raw.lower()), None)
        if m:
            return m
        print("    No matching asset.")


# ── Asset flows ────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Assets ═══")
    _print_views(data.list_views())
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Assets ═══")
    try:
        cat = _pick_optional("Category", list(CATEGORIES))
        status = _pick_optional("Status", list(STATUSES))
        cond = _pick_optional("Condition", list(CONDITIONS))
        loc = _input("Location contains") or None
        search = _input("Search (tag/name/manufacturer/serial)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_views(
            category=cat, status=status, condition=cond,
            location=loc, search=search)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_views(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Asset ═══")
    try:
        a = _pick_asset()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    v = data.view_asset(a.asset_id)
    if v is None:
        print("  Asset not found.")
        _pause()
        return
    _print_full(v)
    print()
    _print_maintenance(
        data.list_maintenance(asset_id=a.asset_id))
    _pause()


def _collect_asset_form(existing: Asset | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["asset_tag"] = _input(
        "Asset tag",
        default=(existing.asset_tag if is_edit else ""),
        allow_empty=False)
    p["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    p["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    p["manufacturer"] = _input(
        "Manufacturer",
        default=(existing.manufacturer or "") if is_edit else "")
    p["model"] = _input(
        "Model",
        default=(existing.model or "") if is_edit else "")
    p["serial_number"] = _input(
        "Serial number",
        default=(existing.serial_number or "") if is_edit else "")
    p["location"] = _input(
        "Location",
        default=(existing.location if is_edit else ""),
        allow_empty=False)
    p["room"] = _input(
        "Room",
        default=(existing.room or "") if is_edit else "")
    p["custodian_id"] = _pick_staff_optional(
        default=(existing.custodian_id if is_edit else None))
    p["purchase_date"] = _input(
        "Purchase date (YYYY-MM-DD, blank=none)",
        default=(existing.purchase_date or "") if is_edit else "")
    p["purchase_cost"] = _input(
        "Purchase cost (blank=none)",
        default=(str(existing.purchase_cost)
                  if is_edit and existing.purchase_cost
                  is not None else ""))
    p["supplier"] = _input(
        "Supplier",
        default=(existing.supplier or "") if is_edit else "")
    p["warranty_expiry"] = _input(
        "Warranty expiry (YYYY-MM-DD, blank=none)",
        default=(existing.warranty_expiry or "")
        if is_edit else "")
    p["useful_life_years"] = _input(
        "Useful life (years, blank=none)",
        default=(str(existing.useful_life_years)
                  if is_edit and existing.useful_life_years
                  is not None else ""))
    p["depreciation_method"] = _pick_from(
        "Depreciation method", list(DEPRECIATION_METHODS),
        default=(existing.depreciation_method if is_edit
                  else DEFAULT_DEPRECIATION_METHOD))
    p["residual_value"] = _input(
        "Residual value (default 0)",
        default=(str(existing.residual_value)
                  if is_edit else "0"))
    p["condition"] = _pick_from(
        "Condition", list(CONDITIONS),
        default=(existing.condition if is_edit
                  else DEFAULT_CONDITION))
    p["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    if p["status"] in DISPOSED_STATUSES:
        p["disposal_date"] = _input(
            "Disposal date (YYYY-MM-DD)",
            default=(existing.disposal_date
                      if is_edit and existing.disposal_date
                      else _date.today().isoformat()))
        p["disposal_method"] = _pick_from(
            "Disposal method", list(DISPOSAL_METHODS),
            default=(existing.disposal_method
                      if is_edit and existing.disposal_method
                      else DISPOSAL_METHODS[0]))
        p["disposal_proceeds"] = _input(
            "Disposal proceeds (blank=none)",
            default=(str(existing.disposal_proceeds)
                      if is_edit and existing.disposal_proceeds
                      is not None else ""))
    else:
        p["disposal_date"] = None
        p["disposal_method"] = None
        p["disposal_proceeds"] = None
    p["last_audit_date"] = _input(
        "Last audit date (YYYY-MM-DD, blank=none)",
        default=(existing.last_audit_date or "")
        if is_edit else "")
    p["next_audit_due"] = _input(
        "Next audit due (YYYY-MM-DD, blank=none)",
        default=(existing.next_audit_due or "") if is_edit else "")
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_asset() -> None:
    print("\n═══ New Asset ═══")
    try:
        payload = _collect_asset_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_asset(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created asset #{a.asset_id} ({a.asset_tag})")
    _pause()


def edit_asset() -> None:
    print("\n═══ Edit Asset ═══")
    try:
        a = _pick_asset()
        payload = _collect_asset_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_asset(a.asset_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.asset_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_asset()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.asset_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.asset_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete Asset ═══")
    try:
        a = _pick_asset()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{a.asset_id} ({a.asset_tag})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_asset(a.asset_id):
        print(f"\n  ✓ Deleted #{a.asset_id}")
    _pause()


# ── Maintenance flows ─────────────────────────────────────────────

def _pick_maintenance(asset_id: int) -> MaintenanceEntry:
    rows = data.list_maintenance(asset_id=asset_id)
    if not rows:
        print("    No maintenance entries.")
        raise _UserAbort
    print("\n  Maintenance entries:")
    for i, m in enumerate(rows, 1):
        print(f"    {i:>3}) #{m.maintenance_id:<4} "
              f"{m.service_date}  {m.service_type[:18]:<18}  "
              f"[{m.outcome}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            m = next((r for r in rows
                        if r.maintenance_id == n), None)
            if m:
                return m
        print("    No match.")


def _collect_maint_form(
        existing: MaintenanceEntry | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["service_date"] = _input(
        "Service date (YYYY-MM-DD)",
        default=(existing.service_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    p["service_type"] = _pick_from(
        "Service type", list(SERVICE_TYPES),
        default=(existing.service_type if is_edit
                  else DEFAULT_SERVICE_TYPE))
    p["performed_by"] = _input(
        "Performed by",
        default=(existing.performed_by or "")
        if is_edit else "")
    p["staff_id"] = _pick_staff_optional(
        default=(existing.staff_id if is_edit else None))
    p["cost"] = _input(
        "Cost (blank=none)",
        default=(str(existing.cost)
                  if is_edit and existing.cost is not None
                  else ""))
    p["outcome"] = _pick_from(
        "Outcome", list(MAINTENANCE_OUTCOMES),
        default=(existing.outcome if is_edit
                  else DEFAULT_MAINTENANCE_OUTCOME))
    p["next_service_due"] = _input(
        "Next service due (YYYY-MM-DD, blank=none)",
        default=(existing.next_service_due or "")
        if is_edit else "")
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def add_maintenance_flow() -> None:
    print("\n═══ Add Maintenance ═══")
    try:
        a = _pick_asset()
        payload = _collect_maint_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.add_maintenance(a.asset_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Added maintenance #{m.maintenance_id} "
          f"to asset #{a.asset_id}")
    _pause()


def edit_maintenance_flow() -> None:
    print("\n═══ Edit Maintenance ═══")
    try:
        a = _pick_asset()
        m = _pick_maintenance(a.asset_id)
        payload = _collect_maint_form(m)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_maintenance(m.maintenance_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated maintenance #{m.maintenance_id}")
    _pause()


def delete_maintenance_flow() -> None:
    print("\n═══ Delete Maintenance ═══")
    try:
        a = _pick_asset()
        m = _pick_maintenance(a.asset_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete maintenance #{m.maintenance_id}? "
              "Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_maintenance(m.maintenance_id):
        print(f"\n  ✓ Deleted #{m.maintenance_id}")
    _pause()


def list_maintenance_flow() -> None:
    print("\n═══ Maintenance Log ═══")
    try:
        a = _pick_asset()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_maintenance(
        data.list_maintenance(asset_id=a.asset_id))
    _pause()


# ── Summary ──────────────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Assets Summary ═══")
    s = data.summary()
    print(f"\n  Total assets        : {s.total_assets}")
    print(f"  Total purchase cost : "
          f"{_money(s.total_purchase_cost)}")
    print(f"  Total book value    : "
          f"{_money(s.total_book_value)}")
    print(f"  Overdue service     : {s.count_overdue_service}")
    print(f"  Warranty expired    : {s.count_warranty_expired}")
    print(f"  Due for audit       : {s.count_due_for_audit}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By condition:")
    for k in CONDITIONS:
        n = s.by_condition.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  Top locations:")
    for loc, n in s.by_location:
        print(f"    {loc[:30]:<30}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("Filter",              filter_flow),
    ("View detail",         view_flow),
    ("─" * 6,               lambda: None),
    ("New asset",           new_asset),
    ("Edit asset",          edit_asset),
    ("Change status",       set_status_flow),
    ("Delete asset",        delete_flow),
    ("─" * 6,               lambda: None),
    ("Maintenance log",     list_maintenance_flow),
    ("Add maintenance",     add_maintenance_flow),
    ("Edit maintenance",    edit_maintenance_flow),
    ("Delete maintenance",  delete_maintenance_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Assets ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Assets CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Assets":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Assets CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True


__all__ = ["run", "dispatch"]
