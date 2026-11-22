"""Finance menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "dinner_money": "dinner_money_cli",
    "expense_claims": "expense_claims_cli",
    "budgets": "budgets_cli",
    "my_expense_claims": "expense_claims_cli:menu_mine",
    "my_budgets": "budgets_cli:menu_mine",
    "pupil_premium": "pupil_premium_cli",
}
