from decimal import Decimal

def ticket_income(*, price: Decimal, sold: int) -> Decimal:
    return price * sold

def event_balance(*, income: Decimal, costs: Decimal) -> Decimal:
    return income - costs
