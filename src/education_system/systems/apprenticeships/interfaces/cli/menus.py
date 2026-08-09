"""The CLI menu tree, one per role.

Deliberately the same shape as the GUI's ``NAV_BY_ROLE``: an apprentice
who is talked through a task over the phone should find the same
options in the same groups whichever interface they are in. Each entry
names a module under ``interfaces/cli/commands`` and the function in it
to run.
"""

from __future__ import annotations

from education_system.systems.apprenticeships import config

# role -> [(category, [(label, "module:function")])]
MENUS: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    config.ADMIN: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
            ("Reports", "reports:menu"),
        ]),
        ("People", [
            ("Admissions", "admissions:menu"),
            ("Apprentices", "apprentices:menu"),
            ("Employers", "employers:menu"),
            ("Staff & Caseloads", "admin:staff_menu"),
        ]),
        ("Delivery", [
            ("Programmes & KSBs", "programmes:menu"),
            ("Training Sessions", "training:menu"),
        ]),
        ("Assurance", [
            ("Off-the-Job Hours", "off_the_job_hours:menu"),
            ("Portfolios", "portfolios:menu"),
            ("Progress Reviews", "reviews:menu"),
            ("Gateway", "gateway:menu"),
            ("End-Point Assessment", "end_point_assessment:menu"),
            ("Funding", "admin:funding_menu"),
            ("Compliance", "admin:compliance_menu"),
        ]),
        ("Communication", [
            ("Correspondence", "email:menu"),
        ]),
    ],
    config.STAFF: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
            ("My Caseload", "apprentices:caseload"),
            # Read-only for staff: a tutor plans around who is coming
            # without being able to admit them. The screen hides the
            # decision options for anyone without admission.decide.
            ("Admissions Queue", "admissions:menu"),
        ]),
        ("Delivery", [
            ("Training Sessions", "training:menu"),
            ("Off-the-Job Approvals", "off_the_job_hours:approval_menu"),
        ]),
        ("Assessment", [
            ("Portfolios", "portfolios:menu"),
            ("Progress Reviews", "reviews:menu"),
            ("Gateway Checks", "gateway:menu"),
        ]),
        ("Communication", [
            ("Correspondence", "email:menu"),
        ]),
    ],
    config.APPRENTICE: [
        ("My Apprenticeship", [
            ("Dashboard", "reports:dashboard"),
            ("My Details", "apprentices:my_details"),
            ("Training Plan", "training:my_plan"),
        ]),
        ("My Evidence", [
            ("Off-the-Job Hours", "off_the_job_hours:my_menu"),
            ("Portfolio", "portfolios:my_menu"),
            ("Progress Reviews", "reviews:my_menu"),
        ]),
        ("Finishing", [
            ("Gateway", "gateway:my_gateway"),
            ("End-Point Assessment", "end_point_assessment:my_menu"),
        ]),
        ("Communication", [
            ("Messages", "email:menu"),
        ]),
    ],
    config.EMPLOYER: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
            ("My Apprentices", "apprentices:menu"),
        ]),
        ("Approvals", [
            ("Off-the-Job Hours", "off_the_job_hours:approval_menu"),
            ("Evidence", "portfolios:menu"),
            ("Progress Reviews", "reviews:menu"),
        ]),
        ("Feedback", [
            ("Give Feedback", "reviews:feedback_menu"),
        ]),
        ("Communication", [
            ("Messages", "email:menu"),
        ]),
    ],
    config.END_POINT_ASSESSOR: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
        ]),
        ("Assessment", [
            ("Gateway Requests", "gateway:epao_menu"),
            ("Bookings", "end_point_assessment:booking_menu"),
            ("Results", "end_point_assessment:results_menu"),
            ("Resits", "end_point_assessment:resit_menu"),
        ]),
    ],
}


# Appended to every role's tree, mirroring the GUI's System group.
# Defined once so a screen added here cannot be forgotten for one role.
SYSTEM_CATEGORY: list[tuple[str, str]] = [
    ("Change Password", "system:change_password"),
    ("Multi-Factor Authentication", "system:mfa"),
    ("Settings", "system:settings"),
    ("About", "system:about"),
]

SYSTEM_CATEGORY_ADMIN: list[tuple[str, str]] = [
    ("User Accounts", "system:user_accounts"),
]


def menu_for(role: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """The menu tree for *role*, plus the shared System group.

    An unrecognised role still gets System, so they can at least read
    who they are signed in as and why the rest is missing.
    """
    tree = list(MENUS.get(role, []))
    system = list(SYSTEM_CATEGORY)
    if role == config.ADMIN:
        system += SYSTEM_CATEGORY_ADMIN
    return [*tree, ("System", system)]
