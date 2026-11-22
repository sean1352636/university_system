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
            ("My Tasks", "tasks:menu"),
            ("Calendar", "calendar:menu"),
            ("Search", "search:menu"),
            ("Awaiting Signature", "signatures:menu"),
            ("Reports", "reports:menu"),
        ]),
        ("People", [
            ("Admissions", "admissions:menu"),
            ("Apprentices", "apprentices:menu"),
            ("Employers", "employers:menu"),
            ("Employer Contacts", "employer_contacts:menu"),
            ("Staff & Caseloads", "admin:staff_menu"),
            ("Workload", "workload:menu"),
        ]),
        ("Cross-System", [
            ("University Progression", "cross_system:university_progression"),
            ("FE College Referrals", "cross_system:fe_referrals"),
            ("Training Provider Requests", "cross_system:training_requests"),
            ("Learner Journey (360)", "cross_system:learner_journey"),
        ]),
        ("Delivery", [
            ("Programmes & KSBs", "programmes:menu"),
            ("Learning Plans", "learning_plan:menu"),
            ("Degree Apprenticeships", "degree_apprenticeships:menu"),
            ("Training Sessions", "training:menu"),
        ]),
        ("Progress", [
            ("Action Plans", "actions:menu"),
            ("Assignments", "assignments:menu"),
            ("Skills Matrix", "skills_matrix:menu"),
            ("Functional Skills", "functional_skills:menu"),
            ("Qualifications", "qualifications:menu"),
        ]),
        ("Support", [
            ("Support & Adjustments", "support:menu"),
            ("Welfare & Risk", "welfare:menu"),
        ]),
        ("Assurance", [
            ("Off-the-Job Hours", "off_the_job_hours:menu"),
            ("Portfolios", "portfolios:menu"),
            ("Progress Reviews", "reviews:menu"),
            ("Gateway", "gateway:menu"),
            ("End-Point Assessment", "end_point_assessment:menu"),
            ("Funding", "admin:funding_menu"),
            ("Compliance", "admin:compliance_menu"),
            ("Documents", "documents:menu"),
            ("Audit Log", "audit:menu"),
            ("Employer Risk", "employer_risk:menu"),
        ]),
        ("Quality", [
            ("Complaints", "complaints:menu"),
            ("Appeals", "appeals:menu"),
            ("Surveys", "surveys:menu"),
        ]),
        ("Communication", [
            ("Correspondence", "email:menu"),
        ]),
    ],
    config.STAFF: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
            ("My Tasks", "tasks:menu"),
            ("Calendar", "calendar:menu"),
            ("Search", "search:menu"),
            ("Awaiting Signature", "signatures:menu"),
            ("My Caseload", "apprentices:caseload"),
            ("Workload", "workload:menu"),
            # Read-only for staff: a tutor plans around who is coming
            # without being able to admit them. The screen hides the
            # decision options for anyone without admission.decide.
            ("Admissions Queue", "admissions:menu"),
        ]),
        # Read-only dashboard for staff; submitting needs admission.decide.
        ("Cross-System", [
            ("University Progression", "cross_system:university_progression"),
            ("FE College Referrals", "cross_system:fe_referrals"),
            ("Training Provider Requests", "cross_system:training_requests"),
            ("Learner Journey (360)", "cross_system:learner_journey"),
        ]),
        ("Delivery", [
            ("Learning Plans", "learning_plan:menu"),
            ("Degree Apprenticeships", "degree_apprenticeships:menu"),
            ("Training Sessions", "training:menu"),
            ("Off-the-Job Approvals", "off_the_job_hours:approval_menu"),
        ]),
        ("Assessment", [
            ("Portfolios", "portfolios:menu"),
            ("Progress Reviews", "reviews:menu"),
            ("Gateway Checks", "gateway:menu"),
        ]),
        ("Progress", [
            ("Action Plans", "actions:menu"),
            ("Assignments", "assignments:menu"),
            ("Skills Matrix", "skills_matrix:menu"),
            ("Functional Skills", "functional_skills:menu"),
            ("Qualifications", "qualifications:menu"),
        ]),
        ("Support", [
            ("Support & Adjustments", "support:menu"),
            ("Welfare & Risk", "welfare:menu"),
            ("Employer Contacts", "employer_contacts:menu"),
            ("Documents", "documents:menu"),
        ]),
        ("Quality", [
            ("Complaints", "complaints:menu"),
            ("Surveys", "surveys:menu"),
        ]),
        ("Communication", [
            ("Correspondence", "email:menu"),
        ]),
    ],
    config.APPRENTICE: [
        ("My Apprenticeship", [
            ("Dashboard", "reports:dashboard"),
            ("My Tasks", "tasks:menu"),
            ("Calendar", "calendar:menu"),
            ("Search", "search:menu"),
            ("My Details", "apprentices:my_details"),
            ("University Degree", "degree_apprenticeships:menu"),
            ("Learning Plan", "learning_plan:my_plan"),
        ]),
        ("My Evidence", [
            ("Off-the-Job Hours", "off_the_job_hours:my_menu"),
            ("Portfolio", "portfolios:my_menu"),
            ("Progress Reviews", "reviews:my_menu"),
            ("Action Plans", "actions:menu"),
            ("Assignments", "assignments:menu"),
            ("Skills Matrix", "skills_matrix:menu"),
            ("Functional Skills", "functional_skills:menu"),
            ("Qualifications", "qualifications:menu"),
            ("Documents", "documents:menu"),
        ]),
        ("Finishing", [
            ("Gateway", "gateway:my_gateway"),
            ("End-Point Assessment", "end_point_assessment:my_menu"),
        ]),
        ("Support & Feedback", [
            ("Support & Adjustments", "support:menu"),
            ("Awaiting Signature", "signatures:menu"),
            ("Complaints", "complaints:menu"),
            ("Appeals", "appeals:menu"),
            ("Surveys", "surveys:menu"),
        ]),
        ("Communication", [
            ("Messages", "email:menu"),
        ]),
    ],
    config.EMPLOYER: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
            ("My Tasks", "tasks:menu"),
            ("Calendar", "calendar:menu"),
            ("Search", "search:menu"),
            ("My Apprentices", "apprentices:menu"),
            ("Learning Plans", "learning_plan:menu"),
            ("Skills Matrix", "skills_matrix:menu"),
            ("Qualifications", "qualifications:menu"),
            ("Support & Adjustments", "support:menu"),
        ]),
        ("Approvals", [
            ("Off-the-Job Hours", "off_the_job_hours:approval_menu"),
            ("Evidence", "portfolios:menu"),
            ("Progress Reviews", "reviews:menu"),
            ("Action Plans", "actions:menu"),
            ("Awaiting Signature", "signatures:menu"),
            ("Documents", "documents:menu"),
        ]),
        ("Feedback", [
            ("Give Feedback", "reviews:feedback_menu"),
            ("Surveys", "surveys:menu"),
            ("Complaints", "complaints:menu"),
        ]),
        ("Communication", [
            ("Messages", "email:menu"),
        ]),
    ],
    config.END_POINT_ASSESSOR: [
        ("Overview", [
            ("Dashboard", "reports:dashboard"),
            ("My Tasks", "tasks:menu"),
            ("Calendar", "calendar:menu"),
            ("Search", "search:menu"),
        ]),
        ("Assessment", [
            ("Gateway Requests", "gateway:epao_menu"),
            ("Bookings", "end_point_assessment:booking_menu"),
            ("Results", "end_point_assessment:results_menu"),
            ("Resits", "end_point_assessment:resit_menu"),
            ("Appeals", "appeals:menu"),
            ("EPA Documents", "documents:menu"),
            ("Complaints", "complaints:menu"),
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
