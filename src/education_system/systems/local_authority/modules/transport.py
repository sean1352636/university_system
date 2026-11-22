"""Home-to-school transport (Travel to school for children of compulsory
school age, 2024) and the routes that provide it.

Eligibility, worked out when the decision is left blank:

* **distance** - the nearest suitable school is beyond statutory walking
  distance: 2 miles under age 8, 3 miles from 8;
* **SEN, disability or mobility** - the child can't reasonably be expected
  to walk, whatever the distance;
* **unsafe route** - no walking route is available;
* **low income** (free school meals or maximum Working Tax Credit), extended
  rights: age 8-10, more than 2 miles to the nearest suitable school; age
  11-16, 2-6 miles to one of the three nearest suitable schools.

Otherwise it's not eligible, unless the authority agrees it as
discretionary. Agreed transport names a route with a free seat; ending it
frees the seat.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.local_authority.core import dates
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.local_authority.infrastructure import database as db
from education_system.systems.local_authority.modules import children, schools

GROUNDS = ("Distance", "SEN, disability or mobility", "Unsafe walking route", "Low income",
           "Discretionary")
DECISIONS = ("Pending", "Eligible", "Not eligible", "Discretionary - agreed")
STATUSES = ("Applied", "Agreed", "Refused", "Ended")
VEHICLES = ("Coach", "Minibus", "Taxi", "Bus pass", "Rail pass",
            "Personal travel budget / mileage")


def walking_distance(age: int) -> float:
    return 2.0 if age < 8 else 3.0


def assess(age: int, grounds: str, miles: float | None, nearest: bool) -> str:
    """The eligibility decision the rules give."""
    if grounds in ("SEN, disability or mobility", "Unsafe walking route"):
        return "Eligible"
    if miles is None:
        return "Pending"
    if grounds == "Distance":
        return "Eligible" if nearest and miles > walking_distance(age) else "Not eligible"
    if grounds == "Low income":
        if 8 <= age < 11:
            return "Eligible" if nearest and miles > 2 else "Not eligible"
        if 11 <= age < 16:
            return "Eligible" if 2 <= miles <= 6 else "Not eligible"
        return "Eligible" if nearest and miles > walking_distance(age) else "Not eligible"
    return "Pending"


def seats_used(route_id: int, excluding: int | None = None) -> int:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM transport WHERE route_id = ? AND status = "
                            "'Agreed' AND id IS NOT ?", (route_id, excluding)).fetchone()[0]


def _check_transport(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    child = r.get(children.CHILDREN, int(merged["learner_id"]))
    dob = r.to_date(child["dob"])
    applied = r.to_date(merged.get("applied_on")) or date.today()
    age = dates.age_on(dob, applied)
    if age < 4 or age > 25:
        raise ValidationError("Home-to-school transport is for ages 4-25.")
    miles = merged.get("distance_miles")
    if miles is not None and float(miles) < 0:
        raise ValidationError("The distance can't be negative.")
    grounds = merged.get("grounds")
    if grounds == "Low income" and not child.get("free_school_meals") and \
            not merged.get("income_evidence"):
        raise ValidationError("Low income: the child isn't recorded as on free school meals - "
                              "record the evidence (e.g. maximum Working Tax Credit).")
    decision = merged.get("decision")
    if decision in (None, "", "Pending"):
        values["decision"] = decision = assess(age, grounds,
                                               None if miles is None else float(miles),
                                               bool(merged.get("nearest_suitable")))
        if grounds == "Discretionary":
            values["decision"] = decision = "Pending"
    status = merged.get("status")
    if status == "Agreed":
        if decision not in ("Eligible", "Discretionary - agreed"):
            raise ValidationError("Transport is agreed only when eligible (or agreed as "
                                  "discretionary).")
        if not merged.get("route_id"):
            raise ValidationError("Choose the route.")
        route = r.get(ROUTES, int(merged["route_id"]))
        if route["status"] != "Active":
            raise ValidationError(f"Route {route['code']} isn't running.")
        if (old is None or old.get("status") != "Agreed" or old.get("route_id") !=
                int(merged["route_id"])) and route.get("seats") is not None and \
                seats_used(route["id"], (old or {}).get("id")) >= int(route["seats"]):
            raise ValidationError(f"Route {route['code']} is full ({route['seats']} seats).")
        if not merged.get("start_date"):
            values["start_date"] = date.today().isoformat()
    if status == "Refused" and decision not in ("Not eligible",):
        raise ValidationError("Refuse only a child found not eligible.")
    if status == "Ended":
        if not merged.get("end_date"):
            values["end_date"] = date.today().isoformat()
    start, end = r.to_date(values.get("start_date", merged.get("start_date"))), \
        r.to_date(values.get("end_date", merged.get("end_date")))
    if start and end and end < start:
        raise ValidationError("Transport can't end before it starts.")


TRANSPORT = RecordType(
    key="transport", title="Transport Applications", singular="transport application",
    order_by="applied_on DESC, id DESC", check=_check_transport,
    filters=("grounds", "decision", "status"),
    describe=lambda row: f"Transport: {children.child_name(row.get('learner_id'))}",
    computed=(("School", lambda row: schools.school_name(row.get("school_id"))),
              ("Route", lambda row: (r.get(ROUTES, row["route_id"]) or {}).get("code", "")
               if row.get("route_id") else "")),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("school_id", "School", "ref", ref="schools", required=True, listed=False),
        Field("applied_on", "Applied", "date", required=True),
        Field("grounds", "Grounds", "choice", GROUNDS, required=True, default="Distance"),
        Field("distance_miles", "Walking distance (miles)", "number"),
        Field("nearest_suitable", "Nearest suitable school", "bool", default=1, listed=False),
        Field("income_evidence", "Low-income evidence", listed=False),
        Field("decision", "Decision", "choice", DECISIONS, default="Pending",
              help="Blank / Pending: worked out from the rules"),
        Field("route_id", "Route", "ref", ref="routes", on_delete="SET NULL", listed=False),
        Field("pass_no", "Pass number", listed=False),
        Field("start_date", "From", "date", listed=False),
        Field("end_date", "To", "date", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Applied"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _check_route(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if values.get("code"):
        values["code"] = values["code"].upper().replace(" ", "")
    seats = merged.get("seats")
    if seats is not None:
        if int(seats) < 0:
            raise ValidationError("Seats can't be negative.")
        if old is not None and int(seats) < seats_used(old["id"]):
            raise ValidationError(f"{seats_used(old['id'])} children use this route, so it "
                                  f"needs at least that many seats.")
    if float(merged.get("daily_cost") or 0) < 0:
        raise ValidationError("The cost can't be negative.")
    if merged.get("status") == "Ended" and old is not None and seats_used(old["id"]):
        raise ValidationError("Children still use this route: move or end their transport "
                              "first.")


ROUTES = RecordType(
    key="routes", title="Transport Routes", singular="route", order_by="code",
    check=_check_route, filters=("vehicle", "status"),
    describe=lambda row: f"{row.get('code')} {row.get('operator') or ''}".strip(),
    computed=(("Used", lambda row: f"{seats_used(row['id'])}/{row.get('seats') or '-'}"
               if row.get("id") else ""),),
    fields=(
        Field("code", "Route", required=True),
        Field("operator", "Operator", required=True),
        Field("vehicle", "Vehicle", "choice", VEHICLES, required=True, default="Minibus"),
        Field("seats", "Seats", "int"),
        Field("escort", "Passenger assistant", "bool", default=0),
        Field("daily_cost", "Cost per day", "money"),
        Field("schools_served", "Schools served", listed=False),
        Field("contract_ends", "Contract ends", "date", listed=False),
        Field("status", "Status", "choice", ("Active", "Suspended", "Ended"), required=True,
              default="Active"),
    ),
)

#: School days a year (for annual cost estimates).
SCHOOL_DAYS = 190


def route_costs() -> list[dict]:
    out = []
    for route in r.list_records(ROUTES, equals={"status": "Active"}):
        n = seats_used(route["id"])
        daily = float(route.get("daily_cost") or 0)
        out.append({"route": route["code"], "operator": route["operator"],
                    "vehicle": route["vehicle"], "children": n, "daily": daily,
                    "annual": daily * SCHOOL_DAYS,
                    "per_child": daily * SCHOOL_DAYS / n if n else None})
    return sorted(out, key=lambda x: -x["annual"])
