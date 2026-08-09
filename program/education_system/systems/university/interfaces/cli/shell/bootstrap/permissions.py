from .integrations import (
    add_finance_permissions, setup_alumni_permissions,
    setup_cafe_permissions, setup_charity_shop_permissions,
    setup_grocery_permissions, setup_internship_permissions,
    setup_office_hours_permissions, setup_shop_permissions,
    setup_staff_hr_permissions, setup_student_union_permissions,
    setup_ta_permissions, setup_takeaway_permissions, setup_trip_permissions,
)

PERMISSION_INITIALIZERS = (
    setup_alumni_permissions, setup_internship_permissions,
    setup_student_union_permissions, add_finance_permissions,
    setup_shop_permissions, setup_trip_permissions,
    setup_charity_shop_permissions, setup_cafe_permissions,
    setup_takeaway_permissions, setup_grocery_permissions,
    setup_staff_hr_permissions, setup_office_hours_permissions,
    setup_ta_permissions,
)

def initialize_permissions() -> None:
    for setup in PERMISSION_INITIALIZERS:
        setup()
