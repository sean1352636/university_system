"""Tkinter views for Sixth Form Parking Permits."""

from __future__ import annotations

import logging
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domains.operations.domain.parking import (
    parking as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    option_key,
    option_label,
    staff_options,
    student_options,
)

logger = logging.getLogger(__name__)

_PERMIT_TAGS = {
    data.REVOKED: ("#ffd1d1", "#8c0d0d"),
    data.EXPIRED: ("#eeeeee", "#444444"),
    "expiring":   ("#fff7e6", "#7a5800"),
}
_SPACE_TAGS = {
    "free":     ("#e6f7e6", "#0d6b2a"),
    "taken":    ("#e6f0ff", "#1a3f8c"),
    "inactive": ("#eeeeee", "#444444"),
}


def open_parking_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Parking Permits")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    def free_space_options(holder_type: str | None = None,
                           permit_type: str | None = None,
                           keep: int | None = None) -> list[str]:
        out = ["(none)"]
        for s in data.list_spaces(active_only=True):
            if s.space_type == "Visitor":
                continue
            if holder_type and s.space_type in ("Staff", "Student") \
                    and s.space_type != holder_type:
                continue
            if s.space_type == "Disabled" and permit_type \
                    and permit_type != "Blue Badge":
                continue
            if s.is_free or s.space_id == keep:
                out.append(option_label(s.space_id,
                                        f"{s.label} ({s.space_type})"))
        return out

    def _space_id(label: str | None) -> int | None:
        key = option_key(label)
        return int(key) if key and key.isdigit() else None

    # ── Permits ──
    def permit_row(p):
        days = p.days_to_expiry()
        tag = (p.status if p.status != data.ACTIVE
               else "expiring" if days <= 30 else "")
        return (p.permit_id,
                (p.permit_id, p.permit_number, p.holder_type, p.holder_id,
                 p.holder_name, p.vehicle_reg,
                 " ".join(x for x in (p.vehicle_colour, p.vehicle_make)
                          if x),
                 p.permit_type, p.issued_on, p.expires_on,
                 p.space_label, p.status,
                 p.revoked_reason or ""),
                (tag,) if tag else ())

    def permits_loader(f):
        rows = data.list_permits(holder_type=f.get("holder"),
                                 status=f.get("status"),
                                 permit_type=f.get("ptype"))
        reg = f.get("reg")
        if reg:
            norm = reg.replace(" ", "").upper()
            rows = [p for p in rows if norm in p.vehicle_reg]
        return [permit_row(p) for p in rows]

    def _permit(tab):
        pid = tab.selected()
        return data.get_permit(int(pid)) if pid else None

    def issue(tab):
        holder = form_dialog(win, "Permit holder", [
            Field("holder_type", "Holder type", "combo", data.HOLDER_TYPES,
                  required=True),
            Field("permit_type", "Permit type", "combo", data.PERMIT_TYPES,
                  required=True),
        ])
        if not holder:
            return
        htype, ptype = holder["holder_type"], holder["permit_type"]
        people = staff_options() if htype == "Staff" else student_options()
        v = form_dialog(win, f"Issue {ptype} permit ({htype})", [
            Field("holder", htype, "combo", people, required=True,
                  width=44),
            Field("vehicle_reg", "Vehicle registration", required=True),
            Field("vehicle_make", "Make / model"),
            Field("vehicle_colour", "Colour"),
            Field("issued_on", "Issued on (blank = today)"),
            Field("expires_on", "Expires on (blank = default for type)"),
            Field("space", "Space", "combo",
                  free_space_options(htype, ptype)),
            Field("issued_by", "Issued by"),
            Field("notes", "Notes", "text"),
        ])
        if v:
            data.issue_permit({
                "holder_type": htype, "permit_type": ptype,
                "holder_id": option_key(v["holder"]),
                "vehicle_reg": v["vehicle_reg"],
                "vehicle_make": v["vehicle_make"],
                "vehicle_colour": v["vehicle_colour"],
                "issued_on": v["issued_on"], "expires_on": v["expires_on"],
                "space_id": _space_id(v["space"]),
                "issued_by": v["issued_by"], "notes": v["notes"]})
            refresh_all()

    def edit(tab):
        p = _permit(tab)
        if not p:
            return
        v = form_dialog(win, f"Edit permit {p.permit_number}", [
            Field("vehicle_reg", "Vehicle registration", required=True),
            Field("vehicle_make", "Make / model"),
            Field("vehicle_colour", "Colour"),
            Field("permit_type", "Permit type", "combo", data.PERMIT_TYPES,
                  required=True),
            Field("issued_on", "Issued on", required=True),
            Field("expires_on", "Expires on", required=True),
            Field("notes", "Notes", "text"),
        ], vars(p))
        if v:
            data.update_permit(p.permit_id, v)
            refresh_all()

    def assign(tab):
        p = _permit(tab)
        if not p:
            return
        v = form_dialog(win, f"Space for {p.permit_number}", [
            Field("space", "Space", "combo",
                  free_space_options(p.holder_type, p.permit_type,
                                     keep=p.space_id), required=True),
        ])
        if v:
            data.assign_space(p.permit_id, _space_id(v["space"]))
            refresh_all()

    def revoke(tab):
        p = _permit(tab)
        if not p:
            return
        reason = simpledialog.askstring(
            "Revoke", f"Reason for revoking {p.permit_number}:", parent=win)
        if reason:
            data.revoke_permit(p.permit_id, reason=reason)
            refresh_all()

    def renew(tab):
        p = _permit(tab)
        if not p:
            return
        new = simpledialog.askstring(
            "Renew", "New expiry (YYYY-MM-DD, blank = next period):",
            parent=win)
        if new is None:
            return
        out = data.renew_permit(p.permit_id, expires_on=new or None)
        messagebox.showinfo("Renewed",
                            f"{out.permit_number} now expires "
                            f"{out.expires_on}.", parent=win)
        refresh_all()

    def delete(tab):
        p = _permit(tab)
        if p and messagebox.askyesno(
                "Delete", f"Delete permit {p.permit_number}? (Use Revoke "
                "for a real permit.)", parent=win):
            data.delete_permit(p.permit_id)
            refresh_all()

    permit_cols = [
        ("id", "ID", 45), ("num", "Permit", 110), ("htype", "Holder", 65),
        ("hid", "ID", 80), ("name", "Name", 150), ("reg", "Reg", 90),
        ("veh", "Vehicle", 140), ("ptype", "Type", 90),
        ("iss", "Issued", 90), ("exp", "Expires", 90),
        ("space", "Space", 100), ("status", "Status", 70),
        ("why", "Revoked because", 150)]
    permit_actions = [("Issue permit", issue), ("Edit", edit),
                      ("Assign space", assign), ("Renew", renew),
                      ("Revoke", revoke), ("Delete", delete)]
    tabs.append(TableTab(
        nb, "Permits", permit_cols, permits_loader,
        filters=[Field("holder", "Holder", "combo", data.HOLDER_TYPES,
                       width=8),
                 Field("status", "Status", "combo", data.STATUSES, width=9),
                 Field("ptype", "Type", "combo", data.PERMIT_TYPES,
                       width=11),
                 Field("reg", "Reg", width=10)],
        actions=permit_actions, on_double=edit, tag_colours=_PERMIT_TAGS))

    def expiring_loader(f):
        try:
            days = int(f.get("days") or 30)
        except ValueError:
            days = 30
        return [permit_row(p) for p in data.expiring_soon(days)]

    tabs.append(TableTab(
        nb, "Expiring Soon", permit_cols, expiring_loader,
        filters=[Field("days", "Within days (30)", width=5)],
        actions=[("Renew", renew), ("Revoke", revoke)],
        tag_colours=_PERMIT_TAGS))

    # ── Spaces ──
    space_fields = [
        Field("car_park", "Car park", required=True),
        Field("space_number", "Space number", required=True),
        Field("space_type", "Space type", "combo", data.SPACE_TYPES,
              required=True),
        Field("active", "In use", "check"),
        Field("notes", "Notes", "text"),
    ]

    def spaces_loader(f):
        rows = []
        for s in data.list_spaces(car_park=f.get("car_park"),
                                  space_type=f.get("stype"),
                                  free_only=bool(f.get("free"))):
            tag = ("inactive" if not s.active
                   else "free" if s.is_free else "taken")
            rows.append((s.space_id,
                         (s.space_id, s.car_park, s.space_number,
                          s.space_type, "Yes" if s.active else "No",
                          s.permit_number or "", s.notes), (tag,)))
        return rows

    def new_space(tab):
        v = form_dialog(win, "New parking space", space_fields,
                        {"active": True})
        if v:
            data.create_space(v)
            refresh_all()

    def add_run(tab):
        v = form_dialog(win, "Add numbered spaces", [
            Field("car_park", "Car park", required=True),
            Field("prefix", "Number prefix"),
            Field("first", "First number", required=True),
            Field("count", "How many", required=True),
            Field("space_type", "Space type", "combo", data.SPACE_TYPES,
                  required=True),
        ], {"first": 1, "count": 10})
        if v:
            made = data.add_spaces(v["car_park"], int(v["first"]),
                                   int(v["count"]),
                                   space_type=v["space_type"],
                                   prefix=v["prefix"])
            messagebox.showinfo("Spaces", f"Added {len(made)} space(s).",
                                parent=win)
            refresh_all()

    def edit_space(tab):
        sid = tab.selected()
        if not sid:
            return
        s = data.get_space(int(sid))
        v = form_dialog(win, f"Edit space {s.label}", space_fields, vars(s))
        if v:
            data.update_space(s.space_id, v)
            refresh_all()

    def delete_space(tab):
        sid = tab.selected()
        if sid and messagebox.askyesno("Delete", "Delete this space?",
                                       parent=win):
            data.delete_space(int(sid))
            refresh_all()

    tabs.append(TableTab(
        nb, "Spaces",
        [("id", "ID", 50), ("park", "Car park", 180),
         ("num", "Space", 80), ("type", "Type", 90),
         ("active", "In use", 70), ("permit", "Held by permit", 130),
         ("notes", "Notes", 260)],
        spaces_loader,
        filters=[Field("car_park", "Car park", width=14),
                 Field("stype", "Type", "combo", data.SPACE_TYPES, width=9),
                 Field("free", "Free only", "check")],
        actions=[("New space", new_space), ("Add numbered spaces", add_run),
                 ("Edit", edit_space), ("Delete", delete_space)],
        on_double=edit_space, tag_colours=_SPACE_TAGS))

    def render():
        s = data.summary()
        lines = ["Parking summary", "",
                 f"  Spaces in use:     {s.spaces}",
                 f"  Free spaces:       {s.free_spaces}"]
        lines += [f"    {t:<10} {s.by_space_type[t]:>4} total, "
                  f"{s.free_by_type[t]:>4} free" for t in data.SPACE_TYPES]
        lines += ["",
                  f"  Permits on file:   {s.permits}",
                  f"  Active permits:    {s.active_permits} "
                  f"(staff {s.staff_permits}, students {s.student_permits})",
                  f"  Expiring in 30d:   {s.expiring_soon}", "",
                  "  By status:"]
        lines += [f"    {k:<10} {v}" for k, v in s.by_status.items()]
        lines += ["", "  Active by permit type:"]
        lines += [f"    {k:<12} {v}" for k, v in s.by_permit_type.items()]
        return lines

    tabs.append(SummaryTab(nb, render))
