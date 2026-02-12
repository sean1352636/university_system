"""
Cinema Booking System - Helper Functions
"""

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from .database import DB_FILE
from .constants import (
    DYNAMIC_PRICING, GROUP_DISCOUNTS, EARLY_BIRD_DISCOUNTS,
    MEMBERSHIP_TIERS, AGE_RESTRICTED_RATINGS
)

def calculate_dynamic_price(self, base_price, show_datetime_str):
    try:
        show_dt = datetime.strptime(show_datetime_str, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return base_price
    is_weekend = show_dt.weekday() >= 5
    is_matinee = show_dt.hour < 17
    if is_weekend:
        mult = DYNAMIC_PRICING['weekend_matinee'] if is_matinee else DYNAMIC_PRICING['weekend_evening']
    else:
        mult = DYNAMIC_PRICING['weekday_matinee'] if is_matinee else DYNAMIC_PRICING['weekday_evening']
    return base_price * mult

def calculate_group_discount(self, num_seats):
    discount = 0
    for threshold, disc in sorted(GROUP_DISCOUNTS.items(), reverse=True):
        if num_seats >= threshold:
            discount = disc
            break
    return discount

def calculate_early_bird_discount(self, show_date_str):
    try:
        show_date = datetime.strptime(show_date_str, "%Y-%m-%d")
        days_ahead = (show_date - datetime.now()).days
        for days, discount in sorted(EARLY_BIRD_DISCOUNTS.items(), reverse=True):
            if days_ahead >= days:
                return discount
    except (ValueError, TypeError):
        pass
    return 0

def get_member_discount(self, email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tier FROM members WHERE email = ? AND status = 'active'", (email,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return MEMBERSHIP_TIERS.get(result[0], {}).get('discount', 0)
    return 0

def verify_age(self, rating):
    return rating in AGE_RESTRICTED_RATINGS
