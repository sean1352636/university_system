"""Finance screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "dinner_money": Page(
        "Dinner Money",
        "dinner_money_views",
        "draw_dinner_money",
        state="_dinner_money_state",
        links=("open_pupil",),
    ),
    "expense_claims": Page(
        "Expense Claims",
        "expense_claims_views",
        "draw_expense_claims",
        state="_expense_claims_state",
    ),
    "budgets": Page(
        "Budgets",
        "budgets_views",
        "draw_budgets",
        state="_budgets_state",
    ),
    # Every member of staff: their own claims, and the cost centres they hold.
    "my_expense_claims": Page(
        "My Expense Claims",
        "expense_claims_views",
        "draw_my_expense_claims",
        state="_my_expense_claims_state",
    ),
    "my_budgets": Page(
        "My Budgets",
        "budgets_views",
        "draw_my_budgets",
        state="_my_budgets_state",
    ),
    "pupil_premium": Page(
        "Pupil Premium",
        "pupil_premium_views",
        "draw_pupil_premium",
        state="_pupil_premium_state",
        links=("open_pupil",),
    ),
}
