from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class MenuItem:
    product_id: int
    name: str
    category: str
    price: float
    stock_quantity: int = 0

@dataclass(frozen=True)
class Order:
    order_id: int
    total_amount: float
    status: str = "pending"

@dataclass(frozen=True)
class Reservation:
    reservation_id: int
    customer_name: str
    reservation_time: datetime
    party_size: int

@dataclass(frozen=True)
class Supplier:
    supplier_id: int
    name: str
    email: str = ""

@dataclass(frozen=True)
class LoyaltyAccount:
    account_id: int
    customer_id: str
    points: int = 0
