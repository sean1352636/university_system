# University Core Scope and Infrastructure Ownership

## Supported core

The university core is the authoritative system for:

1. Identity and delegated access
2. Admissions and applicant conversion
3. Student records and registration
4. Programmes, curriculum and module enrolment
5. Assessment, boards, progression and awards
6. Attendance and engagement
7. Charges, payments, sponsorship and financial holds
8. Student support, health privacy and safeguarding
9. Reporting, statutory returns, retention and audit

The core must remain usable when every optional capability is disabled.

## Capability classification

| Classification | Examples | Support policy |
|---|---|---|
| Core | admissions, records, assessment, finance | Required, migration-safe, full security and availability gates |
| Integration | UCAS, HESA, SLC, UKVI, VLE, library, IdP | Versioned connector with reconciliation and retry |
| Optional campus service | accommodation, dining, parking, facilities | Installable capability; canonical data is read through core APIs |
| Optional specialist | analytics, AI, document/OCR, realtime | Lazy dependency and explicit unavailable response |
| Demo/plugin candidate | betting, butcher, bakery, nail bar, church, car rental | Disabled by default; no direct canonical-data writes |
| Retire | duplicate or unowned implementations | Read-only deprecation, migration, then removal |

No optional module may create a student, alter a registration, ratify an award,
or mutate a payment ledger directly.

## Infrastructure ownership

| Capability | Owner | University access |
|---|---|---|
| Identity, MFA, sessions, authorization | `platform.identity` | Authentication/authorization port |
| Database revision and unit of work | `platform` migration/runtime layer | Repository and unit-of-work ports |
| Durable cross-system events | `platform.integrations.external` | Outbox publisher and idempotent consumer |
| Correlation and structured logging | `platform.kernel.core` | Request/worker context |
| Immutable security audit | `platform.governance` | Audit writer/query ports |
| Email, SMS and notifications | `platform` communications service | Message command and delivery receipt |
| Secrets and key references | deployment/platform secret provider | Named secret reference; never a package path |
| Files and evidence | platform document service | Classified object reference |
| Retention and legal hold | `platform.services.data_retention` | Policy assignment and disposition events |
| Domain rules and decisions | university domain/application services | Stable API used by web, CLI and desktop |

University-local implementations become compatibility adapters during
migration. They must not receive new features after a platform owner exists.

## Installation profiles

The target packaging split is:

- `education-system-core`: web/API, records, migrations and security baseline.
- `education-system[desktop]`: Tkinter interfaces.
- `education-system[analytics]`: NumPy, pandas, SciPy, scikit-learn and charts.
- `education-system[documents]`: PDF, Office, OCR and barcode features.
- `education-system[ai]`: model and advanced NLP dependencies.
- `education-system[integrations]`: external provider SDKs.
- `education-system[campus-services]`: supported optional campus services.
- Individual plugins for demo/plugin-candidate facilities.

Dependencies may move out of the default install only after import tests prove
the core starts without them. Until then, moving a dependency is a migration
task rather than a manifest-only edit.

## Plugin rules

A plugin manifest must declare:

- Identifier, semantic version and compatible platform range
- Capability names and routes
- Required permissions and data classifications
- Optional dependencies and configuration schema
- Migrations in a plugin-owned namespace
- Health checks, retention policy and support level
- Uninstall/data-export behaviour

Plugins consume canonical core APIs and events. Direct imports of core database
modules, runtime DDL and writes to canonical tables are prohibited.

