"""Safeguarding: intake, cases, risk and protected records.

Owns safeguarding intake, drafts, cases, risk assessment, protected media,
on-call workflow, training compliance, retention, notifications, submissions
and safeguarding webhooks.

Unlike the other slices this one was *re-layered*, not just relocated: the flat
``domain/safeguarding`` package mixed business rules with API, authentication,
configuration, cryptography and database code. It now separates into

    domain/          risk analysis and authorisation policy
    application/     the flat public facade (api.py) and the service layer
    infrastructure/  current-user, config, crypto, database and i18n adapters
    interfaces/      cli and gui

``safeguarding_system.py`` stays at the slice root: it is a back-compat facade
that deliberately spans layers, re-exporting the historic single-module API.

Shared authentication and crypto are reused through this slice's infrastructure
adapters; safeguarding-specific authorisation policy stays in ``domain``.
"""
