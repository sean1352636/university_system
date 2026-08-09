"""Admissions: prospects, applicants and entry decisions.

Owns the CRM, application lifecycle, admissions policy, selection, clearing and
adjustment, recognition of prior learning, UCAS and sixth-form intake.

Enrolment conversion is a boundary: this slice publishes an accepted-applicant
outcome; Learners creates the student record and Finance creates any fee
liability. Neither is reached into from here.
"""
