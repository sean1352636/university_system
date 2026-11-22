# Permissions

Apprenticeships only. FE College's access rules are in `systems/fe_college/services/session.py`.

Everything here is defined in
`education_system/systems/apprenticeships/config/__init__.py` and enforced in
`application/security/access.py`. No interface module grants or checks a capability
of its own.

## Roles

| Key | Label | Inside the provider? |
|---|---|---|
| `admin` | Provider Admin | yes |
| `staff` | Tutor / Assessor | yes |
| `apprentice` | Apprentice | no |
| `employer` | Employer | no |
| `end_point_assessor` | End-Point Assessor | no |

`config.PROVIDER_ROLES` is `{admin, staff}`. It governs read-visibility
of formative material — the employer and the EPAO do not see the
provider's own in-progress judgements.

## The two capabilities the provider must not hold

```python
EPAO_EXCLUSIVE = frozenset({"gateway.approve", "epa.grade"})

ROLE_PERMISSIONS[ADMIN] = (
    frozenset(PERMISSIONS) - EPAO_EXCLUSIVE - frozenset({"apprentice.view_own"})
)
```

End-Point Assessment is independent by design: the organisation that
delivered the training neither decides that its own apprentice has
passed gateway nor grades the assessment it is paid for them
completing. Granting either to an administrator would make the
independence cosmetic. **This is load-bearing.** The System → About
screen says so out loud to anyone whose role lacks `epa.grade`, because
"why can't I do that?" is otherwise only answerable by reading the
source.

## The grid

`·` withheld, `✓` held.

| Capability | admin | staff | apprentice | employer | assessor |
|---|:--:|:--:|:--:|:--:|:--:|
| `admission.view` | ✓ | ✓ | · | · | · |
| `admission.decide` | ✓ | · | · | · | · |
| `apprentice.view` | ✓ | ✓ | · | ✓ | ✓ |
| `apprentice.view_own` | · | · | ✓ | · | · |
| `apprentice.manage` | ✓ | · | · | · | · |
| `employer.view` | ✓ | ✓ | · | ✓ | · |
| `employer.manage` | ✓ | · | · | · | · |
| `staff.view` | ✓ | ✓ | · | · | · |
| `staff.manage` | ✓ | · | · | · | · |
| `programme.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `programme.manage` | ✓ | · | · | · | · |
| `training.view` | ✓ | ✓ | ✓ | ✓ | · |
| `training.manage` | ✓ | ✓ | · | · | · |
| `otj.view` | ✓ | ✓ | ✓ | ✓ | · |
| `otj.log` | ✓ | · | ✓ | · | · |
| `otj.approve` | ✓ | ✓ | · | ✓ | · |
| `portfolio.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `portfolio.upload` | ✓ | · | ✓ | · | · |
| `portfolio.assess` | ✓ | ✓ | · | · | · |
| `portfolio.verify` | ✓ | ✓ | · | · | · |
| `review.view` | ✓ | ✓ | ✓ | ✓ | · |
| `review.conduct` | ✓ | ✓ | · | · | · |
| `review.sign` | ✓ | ✓ | ✓ | ✓ | · |
| `review.feedback` | ✓ | · | · | ✓ | · |
| `gateway.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `gateway.request` | ✓ | ✓ | · | · | · |
| **`gateway.approve`** | **·** | · | · | · | **✓** |
| `epa.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `epa.book` | ✓ | · | · | · | ✓ |
| **`epa.grade`** | **·** | · | · | · | **✓** |
| `epa.resit` | ✓ | · | · | · | ✓ |
| `email.view` | ✓ | ✓ | ✓ | ✓ | · |
| `email.send` | ✓ | ✓ | · | · | · |
| `funding.view` | ✓ | · | · | ✓ | · |
| `funding.manage` | ✓ | · | · | · | · |
| `compliance.view` | ✓ | ✓ | · | · | · |
| `compliance.manage` | ✓ | · | · | · | · |
| `report.view` | ✓ | ✓ | · | · | · |

Granularity is deliberately coarse — roughly one permission per screen's
worth of capability. Rules that depend on *which* record are enforced by
scoping the query, not by adding another permission.

## Scope

Permission is only half the check. `application/security/access.Actor` carries the
records the login resolves to:

```python
Actor(username, role, display_name, apprentice_id, employer_id, staff_id)
```

`access.apprentice_filters(actor)` turns those into repository filters:

| Role | Filter |
|---|---|
| `admin`, `end_point_assessor` | none — they legitimately see the whole cohort |
| `staff` | `tutor_id = actor.staff_id` |
| `employer` | `employer_id = actor.employer_id` |
| `apprentice` | `apprentice_id = actor.apprentice_id` |
| anything else | `apprentice_id = -1` |

An unresolved scope yields `-1`, which matches nothing. A
half-provisioned employer login sees zero rows, not everybody's — the
safe direction, and there is a test that pins it.

## Rules the permission grid cannot express

Some rules depend on *who you are* rather than *what you hold*, and live
in the services:

- **Signing a review.** Each actor may only sign the line belonging to
  the party they actually are (`review_service._SIGNATORY_FOR_ROLE`).
  Refused for every role including administrators, whose remedy is
  `unsign_review`.
- **Recording a KSB as Competent.** An apprentice may map evidence at
  *Not started* or *Developing* and no higher, because Competent is the
  judgement the gateway check reads.
- **Submitting hours or evidence.** Only the apprentice whose they are,
  or an administrator.
- **The audit trail and the retention report.** Administrators only. A
  log that records everyone's actions must not be readable by the people
  it records, so it is not scoped-and-shared.
- **The funding evidence pack.** Provider staff only.
- **Managing EPAOs.** Provider admin. There is no separate permission —
  the directory is configuration, not day-to-day work.

## Granting access

An account reaches this system only once it holds a `user_systems` row
for `apprenticeships` in the shared `auth.db`. Grant it from **System →
User Accounts**, or with
`tools/college_and_apprenticeships/create_admin.py`.

A role is not enough on its own: an apprentice, employer or staff login
also has to be **linked** to its record, because every scope check reads
that link. `application/security/account_service.LINK_TARGETS` names what each role
needs, and the accounts screen flags the ones that are missing.
