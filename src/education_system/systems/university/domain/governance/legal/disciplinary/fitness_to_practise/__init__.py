"""Fitness to Practise (FtP) module.

Specialist disciplinary surface for students on regulated programmes
(NMC, HCPC, GMC, GPhC, GTC, etc.). The general disciplinary portal
covers conduct issues for the general student body; FtP cases are a
parallel track because the regulator-facing process has its own stages,
evidence rules, panel composition, and outcomes vocabulary.

Cases are linked back to the central ``disciplinary_records`` table via
``source_record_id`` so an FtP referral originating from a normal
disciplinary record cross-references both ways.
"""
