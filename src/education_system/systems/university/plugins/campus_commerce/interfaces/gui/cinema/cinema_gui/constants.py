"""
Cinema Booking System - Constants and Configuration
"""

# Try importing QR code library
try:
    import qrcode
    from PIL import Image, ImageTk
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Try importing webbrowser for trailers
import webbrowser

# Ticket type pricing multipliers
TICKET_TYPES = {
    "Adult": 1.0,
    "Child": 0.6,
    "Senior": 0.7,
    "Student": 0.8,
}

# Snacks menu
SNACKS_MENU = {
    "Popcorn (Small)": 4.99,
    "Popcorn (Medium)": 6.99,
    "Popcorn (Large)": 8.99,
    "Soda (Small)": 2.99,
    "Soda (Medium)": 3.99,
    "Soda (Large)": 4.99,
    "Candy": 3.49,
    "Nachos": 5.99,
    "Hot Dog": 4.99,
    "Combo (Popcorn + Soda)": 9.99,
}

# Membership tiers
MEMBERSHIP_TIERS = {
    "Bronze": {"min_points": 0, "discount": 0, "points_multiplier": 1.0},
    "Silver": {"min_points": 500, "discount": 5, "points_multiplier": 1.25},
    "Gold": {"min_points": 1500, "discount": 10, "points_multiplier": 1.5},
    "Platinum": {"min_points": 3000, "discount": 15, "points_multiplier": 2.0},
}

# Dynamic pricing multipliers
DYNAMIC_PRICING = {
    "weekday_matinee": 0.75,      # Before 5pm on weekdays
    "weekday_evening": 1.0,       # After 5pm on weekdays
    "weekend_matinee": 0.90,      # Before 5pm on weekends
    "weekend_evening": 1.20,      # After 5pm on weekends
    "holiday": 1.30,              # Holiday pricing
}

# Group booking thresholds
GROUP_DISCOUNTS = {
    10: 0.10,   # 10+ seats: 10% off
    20: 0.15,   # 20+ seats: 15% off
    30: 0.20,   # 30+ seats: 20% off
}

# Early bird discount (days in advance -> discount)
EARLY_BIRD_DISCOUNTS = {
    14: 0.15,   # 14+ days: 15% off
    7: 0.10,    # 7+ days: 10% off
    3: 0.05,    # 3+ days: 5% off
}

# Season pass types
SEASON_PASSES = {
    "monthly": {"price": 29.99, "movies": "unlimited", "duration_days": 30},
    "quarterly": {"price": 79.99, "movies": "unlimited", "duration_days": 90},
    "annual": {"price": 249.99, "movies": "unlimited", "duration_days": 365},
}

# Seat types with pricing
SEAT_TYPES = {
    "standard": {"multiplier": 1.0, "icon": "S", "description": "Standard seating", "price_modifier": 0.00},
    "vip": {"multiplier": 1.5, "icon": "V", "description": "VIP premium seating with extra legroom", "price_modifier": 5.00},
    "couple": {"multiplier": 2.5, "icon": "C", "description": "Couple loveseat for two", "price_modifier": 10.00},
    "wheelchair": {"multiplier": 1.0, "icon": "W", "description": "Wheelchair accessible space", "price_modifier": 0.00},
    "companion": {"multiplier": 1.0, "icon": "A", "description": "Companion seat next to wheelchair space", "price_modifier": 0.00},
}

# Snack dietary categories
SNACK_DIETARY = {
    "Popcorn (Small)": ["vegan", "gluten-free"],
    "Popcorn (Medium)": ["vegan", "gluten-free"],
    "Popcorn (Large)": ["vegan", "gluten-free"],
    "Soda (Small)": ["vegan", "gluten-free"],
    "Soda (Medium)": ["vegan", "gluten-free"],
    "Soda (Large)": ["vegan", "gluten-free"],
    "Candy": [],
    "Nachos": ["vegetarian"],
    "Hot Dog": [],
    "Combo (Popcorn + Soda)": ["vegan", "gluten-free"],
}

# Snack combos
SNACK_COMBOS = {
    "Date Night": {"items": ["Popcorn (Large)", "Soda (Large)", "Soda (Large)"], "price": 14.99, "savings": 4.98},
    "Family Pack": {"items": ["Popcorn (Large)", "Popcorn (Medium)", "Soda (Large)", "Soda (Medium)", "Soda (Medium)"], "price": 22.99, "savings": 7.95},
    "Solo Snacker": {"items": ["Popcorn (Small)", "Soda (Small)", "Candy"], "price": 9.99, "savings": 1.47},
}

# Movie age ratings requiring verification
AGE_RESTRICTED_RATINGS = ["R", "NC-17", "18+", "X"]

# Staff roles and permissions
STAFF_ROLES = {
    "admin": {"permissions": ["all"], "description": "Full system access"},
    "manager": {"permissions": ["bookings", "reports", "screenings", "staff", "inventory"], "description": "Theater management"},
    "cashier": {"permissions": ["bookings", "snacks", "gift_cards"], "description": "Front desk operations"},
    "concessions": {"permissions": ["snacks", "inventory"], "description": "Concessions stand"},
    "usher": {"permissions": ["tickets_verify"], "description": "Ticket verification only"},
}

# Referral program settings
REFERRAL_REWARD = 5.00  # £5 credit for both parties

# Birthday reward
BIRTHDAY_REWARD_TICKET = True  # Free ticket on birthday

# Seat holding timeout (seconds)
SEAT_HOLD_TIMEOUT = 600  # 10 minutes

# Themed night types
THEMED_NIGHTS = {
    "throwback_thursday": {"day": 3, "discount": 0.20, "name": "Throwback Thursday"},
    "horror_friday": {"day": 4, "discount": 0, "genre": "Horror", "name": "Horror Fridays"},
    "family_sunday": {"day": 6, "discount": 0.15, "genre": "Family", "name": "Family Sundays"},
}
