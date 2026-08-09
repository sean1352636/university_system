# University Integration

Where apprenticeships meets the other five systems — and, specifically,
where a higher apprentice meets a degree.

Two distinct things share this page because they are easy to confuse:

| | Status |
|---|---|
| **Cross-system transitions** — a learner *moving* between systems | Built |
| **Degree apprenticeships** — a learner on a degree *and* an apprenticeship at once | Not built |

---

## Cross-system transitions — built

Secondary, sixth form, FE college and university all feed
apprenticeships, and a completed higher apprentice can go on to a
degree. `integrations/cross_system_adapter.py` is this system's side of
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

## Degree apprenticeships — not built

A degree apprenticeship is a Level 6 or 7 apprenticeship where the
apprentice is simultaneously a registered university student: the degree
is embedded in the standard, and the two records have to agree about
credits, assessment and completion.

The scaffolding is there and empty:

```
pathways/
├── intermediate/rules.py                          (Level 2)
├── advanced/rules.py                              (Level 3)
├── higher/rules.py, higher_education_qualifications.py   (Levels 4–5)
└── degree/rules.py, academic_requirements.py,
        credit_tracking.py, degree_outcomes.py     (Levels 6–7)

integrations/
├── university_gateway.py     empty
├── employer_gateway.py       empty
├── epao_gateway.py           empty
└── funding_gateway.py        empty
```

Every one of those is a single docstring. Nothing imports them.

`config.pathway_for_level(level)` already routes a level to a pathway
name — `intermediate`, `advanced`, `higher`, `degree` — so the contract
exists and the packages that would answer it do not.

### What is missing, concretely

**Level-band rules.** Minimum duration, functional-skill level, whether
a qualification is embedded, and what the EPA plan must contain differ
by band. Today `config.MINIMUM_PRACTICAL_PERIOD_DAYS` (365) is applied
flat to every level, and gateway checks it directly.

**Credit tracking.** A degree apprentice accrues HE credits alongside
KSB coverage. The portfolio roll-up knows nothing about credits, and the
university's record of them is in a different database.

**Degree outcomes.** The apprenticeship's overall grade is the lowest of
the per-method EPA grades (`domain/end_point_assessment/results.overall_grade`).
A degree classification is a different calculation over different
inputs. Which one a degree apprentice finishes with — and how the two
reconcile — is a policy decision nobody has made here.

**The university gateway itself.** Whether it reads the university
system in-process, over the unified API, or through the cross-system
bus is undecided. Note that apprenticeships is not currently on the
unified API at all (see
[`../reference/college_and_apprenticeships/api.md`](../reference/college_and_apprenticeships/api.md)),
so the second option needs that first.

### What already works for a Level 6 apprentice

Nothing above blocks running one today. `config.PROGRAMME_LEVELS`
includes 6 and 7, `LEVEL_LABELS` names them as degree apprenticeships,
funding bands go to £27,000, and the whole gateway and EPA machinery is
level-agnostic. What is missing is the *university side* of the record —
the credits, the classification, and the link between the two systems'
views of one person.

## See also

- [The apprenticeship system](apprenticeship_system.md)
- [`docs/reference/college_and_apprenticeships/architecture.md`](../reference/college_and_apprenticeships/architecture.md)
- ADR 0010 and the `platform/cross_system/` package for the transition contract
