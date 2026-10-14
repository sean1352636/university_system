"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchPersistenceDonationsMixin:
    def _db_save_donation(self, donation):
        """Save a donation to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_donations (donor_name, donor_email, amount, donation_type,
                    payment_method, transaction_ref, date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (donation.get('donor_name'), donation.get('donor_email'), donation.get('amount'),
                      donation.get('donation_type'), donation.get('payment_method'),
                      donation.get('transaction_ref'), donation.get('date'), donation.get('notes')))
                donation['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save donation: {e}")
            return False
