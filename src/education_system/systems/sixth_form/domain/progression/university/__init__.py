"""The whole of a sixth-form learner's route to university, in one place.

This package was six: ``ucas``, ``ucas_workflow``, ``personal_statements``,
``references``, ``offers`` and ``university_progression``. They were never
six domains. Five of them sat directly on top of the two UCAS tables —
``offers`` described itself as "a focused view over the existing
``ucas_choices`` data", and ``ucas_workflow`` existed only to stitch the
other five back together for one learner at a time. The split ran across
the workflow instead of along it, so a member of staff working one
application visited six screens, and the same fact got typed into more
than one of them: a final decision, a personal statement and a set of
offer terms each had two homes that could disagree.

What lives here, and what owns what:

===================  ==========================================
:mod:`.ucas`         ``ucas_applications`` + ``ucas_choices`` —
                     the root everything else hangs off
:mod:`.statements`   ``personal_statements`` (the draft history)
:mod:`.references`   ``academic_references``
:mod:`.offers`       ``offer_details``, keyed 1:1 to a choice
:mod:`.workflow`     ``ucas_workflow_stages`` — the tracked
                     pipeline across all of the above
:mod:`.board`        no table; the progression board, assembled
                     from UCAS plus the handover checks
===================  ==========================================

Plus the two outbound notices, kept beside the data rather than inside
it so a UCAS write never depends on the communications package:
:mod:`.submission_notice` and :mod:`.feedback_notice`.

``cli/`` and ``views/`` hold the adapters, one module per area, and they
are the only things in here that know about a terminal or a Tk widget.

Nothing is re-exported from this ``__init__``. Importing it would pull
in all six data modules — and their databases — for a caller that wanted
one, which is the cost the sixth form already pays elsewhere and does
not need to pay again here. Import the submodule you mean.
"""
