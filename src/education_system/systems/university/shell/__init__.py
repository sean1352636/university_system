"""System-wide delivery shell for the university.

The shell is the chrome that no single business domain owns: the launcher and
menu router, session and theme handling, the main GUI window, and the API
application together with the cross-cutting routes (auth, users, documents,
notifications) that are not attached to one domain.

It sits beside ``domains/`` rather than inside it::

    shell/cli/    menu router, auth manager, area entrypoints
    shell/gui/    main window, navigation, shared widgets and dialogs
    shell/api/    app creation and the cross-cutting route blueprints

Anything that belongs to a business domain belongs in that domain's own
``domains/<domain>/interfaces/`` layer instead. The dependency runs one way:
the shell composes the domains, and a domain must never import the shell.
"""
