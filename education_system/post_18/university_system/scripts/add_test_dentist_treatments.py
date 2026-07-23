#!/usr/bin/env python3
"""
Add test treatment data to dentist system.

This script creates sample treatment records for testing the dentist GUI.
"""

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from datetime import datetime, timedelta
import random

def add_test_treatments():
    """Add sample treatment data."""

    try:
        with get_connection() as conn:
            # Get the first patient
            cursor = conn.execute("SELECT patient_id, user_id FROM dentist_patients LIMIT 1")
            patient = cursor.fetchone()

            if not patient:
                print("❌ No patients found. Please register as a patient first.")
                return False

            patient_id = patient[0]
            user_id = patient[1]

            print(f"Adding test treatments for patient ID: {patient_id} (User: {user_id})")

        # Sample treatments
        test_treatments = [
            {
                'type': 'checkup',
                'date': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                'dentist': 'Dr. Sarah Mitchell',
                'dentist_id': 'DEN001',
                'tooth': None,
                'description': 'Routine 6-month checkup',
                'notes': 'All teeth healthy, minor plaque buildup',
                'payment': 'paid',
                'follow_up': False
            },
            {
                'type': 'cleaning',
                'date': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                'dentist': 'Dr. Sarah Mitchell',
                'dentist_id': 'DEN001',
                'tooth': None,
                'description': 'Professional teeth cleaning',
                'notes': 'Cleaned and polished all surfaces',
                'payment': 'paid',
                'follow_up': False
            },
            {
                'type': 'filling',
                'date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                'dentist': 'Dr. Emily Chen',
                'dentist_id': 'DEN003',
                'tooth': '14',
                'description': 'Composite filling for cavity',
                'notes': 'Small cavity on molar, filled with composite resin',
                'payment': 'paid',
                'follow_up': True,
                'follow_up_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            },
            {
                'type': 'xray',
                'date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                'dentist': 'Dr. Emily Chen',
                'dentist_id': 'DEN003',
                'tooth': None,
                'description': 'Dental X-Ray imaging',
                'notes': 'Bitewing X-rays to check for cavities',
                'payment': 'paid',
                'follow_up': False
            },
            {
                'type': 'consultation',
                'date': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                'dentist': 'Dr. James Wilson',
                'dentist_id': 'DEN002',
                'tooth': None,
                'description': 'Orthodontic consultation',
                'notes': 'Discussed braces options, patient considering treatment',
                'payment': 'pending',
                'follow_up': True,
                'follow_up_date': (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
            }
        ]

        # Treatment fees
        from education_system.post_18.university_system.modules.domain.health.dentist.services.dentist_core import TREATMENT_TYPES

        treatments_added = 0
        with transaction() as conn:
            for treatment in test_treatments:
                treatment_info = TREATMENT_TYPES.get(treatment['type'], TREATMENT_TYPES['consultation'])
                fee = treatment_info['fee']

                conn.execute('''
                    INSERT INTO dentist_treatments
                    (patient_id, dentist_id, dentist_name, treatment_type, treatment_date,
                     tooth_number, description, fee, payment_status, notes,
                     follow_up_required, follow_up_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    patient_id,
                    treatment['dentist_id'],
                    treatment['dentist'],
                    treatment['type'],
                    treatment['date'],
                    treatment.get('tooth'),
                    treatment['description'],
                    fee,
                    treatment['payment'],
                    treatment['notes'],
                    1 if treatment.get('follow_up', False) else 0,
                    treatment.get('follow_up_date')
                ))

                treatments_added += 1
                print(f"  ✓ Added {treatment_info['name']} - {treatment['date']} (GBP {fee:.2f})")

        print(f"\n✅ Successfully added {treatments_added} test treatments!")
        print("\nYou can now view them in the Treatments tab of the Dentist GUI.")
        print("\nFiltering features:")
        print("  - Filter by treatment type (e.g., 'Routine Check-up', 'Dental Filling')")
        print("  - Filter by payment status (paid/pending)")
        print("  - View full details by double-clicking or using 'View Full Details' button")
        print("  - Export to CSV for records")
        print("  - Pay pending treatments")
        print("  - Schedule follow-up appointments")

        return True

    except Exception as e:
        print(f"❌ Error adding test treatments: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("ADDING TEST DENTIST TREATMENT DATA")
    print("=" * 70)
    print()

    success = add_test_treatments()

    if success:
        print("\n" + "=" * 70)
        print("✅ TEST DATA ADDED SUCCESSFULLY")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ FAILED TO ADD TEST DATA")
        print("=" * 70)
