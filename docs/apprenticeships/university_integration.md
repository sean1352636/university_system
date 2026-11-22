# University Integration

Where apprenticeships meets the other six systems — and, specifically,
where a higher apprentice meets a degree.

Two distinct things share this page because they are easy to confuse:

| | Status |
|---|---|
| **Cross-system transitions** — a learner *moving* between systems | Built |
| **Degree apprenticeship identity and enrolment link** | Built |
| **Degree-pathway gateway and outcome rules** | Not built |

---

## Cross-system transitions — built

Secondary, sixth form, FE college and university all feed
apprenticeships, and a completed higher apprentice can go on to a
degree. `src/education_system/systems/apprenticeships/infrastructure/integrations/cross_system_adapter.py` is this system's side of
the platform's four-method transition contract
(`platform.cross_system.adapters.base.PhaseAdapter`).

The dependency points inwards: nothing in `platform/` imports this
module. It registers itself with the platform registry when `register()`
is called at launch, and the platform then addresses it by the system
key `"apprenticeships"`.

### Two rules specific to work-based learning

**An arriving learner is an Applicant, never an apprentice.** A school
can hand over in June, but nobody is on programme until an employer has
signed and eligibility has passed. `create_applicant` creates the record
at status `Applicant`; `create_enrolment` is what moves it to
`On Programme`. Between those two the record deliberately has no
employer — that is the normal state, not an incomplete one.

**Leaving is Withdrawn or Transferred, never a delete.** The funding and
audit trail has to survive a departure: an apprentice who left has a
claim history the ESFA can still ask about.

### Idempotency

Handover delivery is at-least-once, so `create_applicant` is idempotent
on `journey_id` — a redelivered bus event finds the row stamped by the
first delivery and returns it unchanged. Failing that, it matches on
ULN and adopts the existing row rather than creating a second record for
one person. The `journey_id` column and its partial index are added by
`schema._migrate()`, not by `SCHEMA`, because the script runs against
existing databases too.

---

## Degree apprenticeships — linked foundations built

A degree apprenticeship is a Level 6 or 7 apprenticeship where the
apprentice is simultaneously a registered university student: the degree
is embedded in the standard, and the two records have to agree about
credits, assessment and completion.

The shared-record foundation is implemented. One canonical ``journey_id``
links the apprenticeship learner and university student, while two concurrent
``learner_enrolment`` rows record that both registrations are active. Neither
system changes ownership of its domain data:

| Owner | Authoritative data |
|---|---|
| Apprenticeships | employer, KSBs, portfolio, off-the-job hours, reviews, funding, gateway and EPA |
| University | registration, modules, credits, academic results, classification and degree completion |
| Platform | person identity and enrolment history |

``services/degree_apprenticeship_service.py`` maps Level 6/7 standards to a
university degree and links a learner. The operation is idempotent. Because the
three records live in separate SQLite databases, a local link is written as
``Pending`` first and becomes ``Active`` after both shared enrolments exist; a
failed attempt is visible and can safely be retried.

Normal operation is event-driven. University publishes registration, credit and
award snapshots over the durable cross-system bus; apprenticeships consumes
them into ``degree_academic_progress_projection`` for its dashboard. The
projection is replaceable and never becomes the source used to award a degree.
``src/education_system/systems/apprenticeships/infrastructure/integrations/university_gateway.py`` remains an explicit read-only verifier for
imports, diagnostics and tests, not the normal runtime connection.

The apprenticeship database owns two association tables:

* ``degree_apprenticeship_programmes`` maps a local apprenticeship programme to
  a logical ``university_degree_program_id`` and records its credit requirement,
  integration type and active state.
* ``degree_apprenticeship_links`` joins the local apprentice, canonical
  ``journey_id`` and logical university student/programme identifiers, with
  link status, linked/synchronised timestamps and reconciliation state.

Only the apprenticeship-side identifiers have local foreign keys. University
student and degree programme identifiers are deliberately logical references:
SQLite cannot enforce a foreign key into the separately owned university
database.

The link itself is modelled in `domain/degree_apprenticeships/links.py`.

There are no level-band rules yet. `config.pathway_for_level(level)`
names a level's band — `intermediate`, `advanced`, `higher`, `degree` —
but nothing answers it: the empty `pathways/` packages that once stood
in for those rules were removed in September 2026. When band rules are
written (academic requirements, credit tracking, degree outcomes for
Levels 6–7) they belong in `domain/programmes/`, and they are not yet
part of gateway or completion decisions.

### What is missing, concretely

**Level-band rules.** Minimum duration, functional-skill level, whether
a qualification is embedded, and what the EPA plan must contain differ
by band. Today `config.MINIMUM_PRACTICAL_PERIOD_DAYS` (365) is applied
flat to every level, and gateway checks it directly.

**Credit rules.** Current university credit progress can now be read through
the gateway. Programme-specific rules that decide whether an academic credit
position blocks gateway or completion are not yet defined.

**Degree outcomes.** The apprenticeship's overall grade is the lowest of
the per-method EPA grades (`domain/end_point_assessment/results.overall_grade`).
A degree classification is a different calculation over different
inputs. Which one a degree apprentice finishes with — and how the two
reconcile — is a policy decision nobody has made here.

**Event-driven synchronisation.** The durable bus carries
``degree_apprenticeship.linked``, university registration/credit/award changes,
apprenticeship gateway/completion changes and reconciliation warnings. Delivery
is idempotent by event/handler identity. The university consumer creates or
matches its student when the link event arrives, then publishes the initial
academic snapshot.

The shared platform account is granted ``apprentice`` access in apprenticeships
and ``student`` access in university during linking. Integrated programmes also
require an explicit ``university_gateway_confirmed`` academic snapshot before
the apprenticeship gateway can be requested.

Degree award and apprenticeship completion are independent. When only one is
complete the link is flagged ``Degree Complete; Apprenticeship Incomplete`` or
``Apprenticeship Complete; Degree Incomplete`` and a reconciliation event is
published for staff; neither outcome overwrites the other.

### What already works for a Level 6 apprentice

Nothing above blocks running one today. `config.PROGRAMME_LEVELS`
includes 6 and 7, `LEVEL_LABELS` names them as degree apprenticeships,
funding bands go to £27,000, and the whole gateway and EPA machinery is
level-agnostic. The university registration and link can now be resolved, but
classification, award reconciliation and Level 6/7 gateway policy remain to
be built.

## See also

- [The apprenticeship system](apprenticeship_system.md)
- [`docs/reference/college_and_apprenticeships/architecture.md`](../reference/college_and_apprenticeships/architecture.md)
- ADR 0010 and the `platform/cross_system/` package for the transition contract
