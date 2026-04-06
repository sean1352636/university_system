# Education System - Documentation

Central documentation hub for all four management systems in the Education System platform.

---

## Systems

| System | Description | Docs |
|--------|-------------|------|
| **University** | Higher education platform — 51 domain modules, CLI/GUI/API/Web Portal | [University Docs](university_system/README.md) |
| **Sixth Form College** | Further education (16-19) — 110 domain modules, CLI/GUI/API | [College Docs](college_system/README.md) |
| **Secondary School** | Years 7-11, KS3/KS4, GCSE 9-1 — 51 domain modules, CLI/GUI | [Secondary School Docs](secondary_school/README.md) |
| **Primary School** | Reception-Year 6, EYFS/KS1/KS2 — 46 domain modules, CLI/GUI | [Primary School Docs](primary_school/README.md) |

## Quick Start

Each system has its own quick start guide:

- [University Quick Start](university_system/QUICK_START.md)
- [College Quick Start](college_system/QUICK_START.md)
- [Secondary School Quick Start](secondary_school/QUICK_START.md)
- [Primary School Quick Start](primary_school/QUICK_START.md)

## Shared Infrastructure

All four systems share a unified authentication module. Full documentation:

- [Shared Authentication](shared/AUTHENTICATION.md) — architecture, database, roles, default accounts
- [MFA Guide](shared/MFA_GUIDE.md) — TOTP setup, login flow, recovery codes
- [Universal Login](shared/UNIVERSAL_LOGIN.md) — cross-system login window and launcher

The unified launcher (`run.py`) provides system and mode selection for both CLI and GUI, with runtime system switching.

## Documentation Structure

```
docs/
├── README.md                        # This file
├── appendices.md                    # Appendices A-K
├── shared/                          # Shared infrastructure docs
│   ├── AUTHENTICATION.md           # Unified auth system
│   ├── MFA_GUIDE.md                # Multi-factor authentication
│   └── UNIVERSAL_LOGIN.md          # Cross-system login
├── university_system/               # University system docs
│   ├── README.md                    # Documentation index
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── technical_reference.md       # Module APIs and patterns
│   ├── security/                    # Auth, MFA, security guides
│   ├── infrastructure/              # Database, email, monitoring
│   ├── development/                 # Dev setup, testing, API
│   ├── guides/                      # 20+ user guides
│   └── modules/                     # Module documentation
├── college_system/                   # College system docs
│   ├── README.md                    # Documentation index
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                    # Auth, MFA, security
│   ├── infrastructure/              # Database, API, config
│   ├── development/                 # Dev setup, testing, modules
│   └── guides/                      # Domain guides
├── secondary_school/                 # Secondary school docs
│   ├── README.md                    # Documentation index
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                    # Auth, MFA, security
│   ├── infrastructure/              # Database, auth, config
│   ├── development/                 # Dev setup, testing, modules
│   └── guides/                      # Domain guides
├── primary_school/                   # Primary school docs
│   ├── README.md                    # Documentation index
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                    # Auth, MFA, security
│   ├── infrastructure/              # Database, auth, config
│   ├── development/                 # Dev setup, testing, modules
│   └── guides/                      # Domain guides
└── changelogs/                       # Archived changelogs
    ├── CHANGELOG-v5.md              # Versions 0.x through 5.x
    ├── CHANGELOG-modules.md         # Module-specific changelogs
    └── CHANGELOG-legacy-notes.md    # Legacy feature docs
```

## Troubleshooting

- [University Troubleshooting](university_system/TROUBLESHOOTING.md)
- [College Troubleshooting](college_system/TROUBLESHOOTING.md)
- [Secondary School Troubleshooting](secondary_school/TROUBLESHOOTING.md)
- [Primary School Troubleshooting](primary_school/TROUBLESHOOTING.md)

## Reference

| Document | Description |
|----------|-------------|
| [appendices.md](appendices.md) | Appendices A-K: bug reports, conventions, references |
| [technical_reference.md](university_system/technical_reference.md) | University module APIs, function signatures, integration patterns |

## Changelog Archives

The main [CHANGELOG.md](../../CHANGELOG.md) covers v6.0+. Older history is archived here:

| Archive | Description |
|---------|-------------|
| [CHANGELOG-v5.md](changelogs/CHANGELOG-v5.md) | Versions 0.x through 5.x (298 releases) |
| [CHANGELOG-modules.md](changelogs/CHANGELOG-modules.md) | Module-specific changelogs (29 entries) |
| [CHANGELOG-legacy-notes.md](changelogs/CHANGELOG-legacy-notes.md) | Legacy feature documentation and migration notes |

---

**Last Updated**: March 2026
