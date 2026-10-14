"""Fallback nail bar catalogue.

Used when ``nailbar_core`` is unavailable; ``schema`` decides which definition
of ``NAIL_TREATMENTS`` wins.
"""

NAIL_TREATMENTS = {
    'manicure': {'name': 'Classic Manicure', 'price': 20.00, 'duration': 45, 'category': 'manicure'},
    'gel_manicure': {'name': 'Gel Manicure', 'price': 30.00, 'duration': 60, 'category': 'manicure'},
    'acrylic_manicure': {'name': 'Acrylic Manicure', 'price': 40.00, 'duration': 75, 'category': 'manicure'},
    'deluxe_manicure': {'name': 'Deluxe Manicure', 'price': 50.00, 'duration': 90, 'category': 'manicure'},
    'pedicure': {'name': 'Classic Pedicure', 'price': 25.00, 'duration': 60, 'category': 'pedicure'},
    'spa_pedicure': {'name': 'Spa Pedicure', 'price': 40.00, 'duration': 75, 'category': 'pedicure'},
    'gel_pedicure': {'name': 'Gel Pedicure', 'price': 35.00, 'duration': 70, 'category': 'pedicure'},
    'nail_art': {'name': 'Nail Art', 'price': 15.00, 'duration': 30, 'category': 'art'},
    'nail_extensions': {'name': 'Nail Extensions', 'price': 45.00, 'duration': 90, 'category': 'extensions'},
    'paraffin_treatment': {'name': 'Paraffin Hand Treatment', 'price': 20.00, 'duration': 30, 'category': 'treatment'},
    'foot_massage': {'name': 'Foot Massage', 'price': 25.00, 'duration': 30, 'category': 'treatment'},
}

DEFAULT_TECHNICIANS = [
    ('Sarah Johnson', 'Manicure, Gel Nails', 'Mon-Fri: 9:00-17:00', 8),
    ('Emily Chen', 'Pedicure, Spa Treatments', 'Mon-Sat: 10:00-18:00', 10),
    ('Maria Garcia', 'Nail Art, Extensions', 'Tue-Sat: 11:00-19:00', 6),
    ('Sophie Williams', 'All Treatments', 'Mon-Fri: 8:00-16:00', 8),
]

__all__ = ['NAIL_TREATMENTS', 'DEFAULT_TECHNICIANS']
