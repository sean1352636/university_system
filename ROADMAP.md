# Roadmap

> This document was extracted from the main [README.md](./README.md). See the README for the full project documentation.

---

## Known Limitations

The following limitations should be considered when deploying this system:

| Limitation | Details |
|------------|---------|
| **Web Interface** | All 4 systems have REST APIs via the unified server; University has the most comprehensive Web Portal SPA; Secondary and Primary have web dashboard navigation but fewer custom CRUD pages |
| **Multi-tenancy** | Single-tenant design; multi-institution hosting planned for future release |
| **SQLite Concurrency** | May have performance limits with high concurrent writes; use PostgreSQL for high-traffic deployments |
| **i18n Coverage** | Most GUI modules now have i18n support (500+ strings translated in v5.41.x); some modules still have incomplete coverage |
| **Production Readiness** | Not recommended for production without implementing security recommendations (see [Security Documentation](education_system/docs/university_system/security/SECURITY.md)) |
| **Mobile Support** | No native mobile app; web interface responsive but not mobile-optimized |
| **Real-time Features** | WebSocket support planned but not yet implemented |

---

### Multi-System Education Platform (March 2026) - CURRENT
- [x] **Unified Launcher** (`run.py`): Single entry point for University, College, Secondary School, and Primary School systems with CLI & GUI system selection and runtime switching
- [x] **Shared Authentication** (`education_system/shared/auth/`): Unified auth across all 4 systems with bcrypt hashing, MFA, sessions, and central auth.db
- [x] **Cross-System CLI Switching** (v7.5.0): All 4 CLI systems support switching to any other system without re-authenticating
- [x] **Unified REST API** (v7.25.0-v7.31.0): All 4 systems served from `shared/api/unified_server.py` -- university (104 route files), college, secondary (52 route files), primary (48 route files) with web dashboard, superadmin portal, CSRF protection, and CSP compliance
- [x] **Sixth Form College System**: 930+ files, 110 domain modules, 74 tests -- apprenticeships, T-levels, UCAS, functional skills, safeguarding, Prevent duty, GDPR, quality assurance, bursary, funding, and more
- [x] **Secondary School System**: 290+ files, 50 domain modules -- Years 7-11, KS3/KS4, GCSE grades 9-1, pastoral care, behaviour/detentions/exclusions, form groups, seating plans, parents' evening
- [x] **Primary School System**: 280+ files, 46 domain modules -- Reception-Year 6, EYFS/KS1/KS2, phonics, reading records, SATs, safeguarding, SEND, pastoral care

### Version 5.47.0 (February 25, 2026) -- COMPLETED
- [x] **Web Portal** (v5.47.0): Full SPA at `/portal` with JWT auth, dashboard, CRUD for all major entities
- [x] **Staff HR Expansion** (v5.44.0-v5.46.0): 20 new modules -- payroll, faculty scheduling, curriculum design, travel, sabbatical, committees, IP, equipment, cover, workload, directory, mentoring, grants, peer review, communication hub, teaching load; 75+ new database tables
- [x] **Student Services** (v5.43.0): Academic advising, digital student ID, study room booking, printing services, textbook store
- [x] **Codebase Consolidation** (v5.46.1-v5.46.2): Merged fragmented versioned files (HR schemas 7->1, admin tools GUI+locale 4->2), centralised path helpers
- [x] **Continued Refactoring** (v5.42.55-v5.42.64): Additional monolithic file decompositions with backward compatibility

### Version 5.42.54 (February 22, 2026) -- COMPLETED
- [x] **Advanced Authentication** (v5.40.0): WebAuthn/FIDO2, SSO (SAML 2.0 & OIDC), biometric, account linking, delegated access, 25 new permissions
- [x] **Codebase Refactoring** (v5.42.x): 54 monolithic files decomposed into modular packages with full backward compatibility
- [x] **i18n Expansion** (v5.41.x): 500+ hardcoded strings replaced with translation calls across 20+ GUI modules
- [x] **Bug Fixes** (v5.39.6-v5.40.x): 50+ database schema fixes, GUI layout corrections, email integration fixes
- [x] **Security Hardening** (v5.39.7): Removed hardcoded credentials, secure random password generation via `secrets` module

### Version 5.39.5 (February 11, 2026) -- COMPLETED
- [x] **Flask REST API** (v5.22.0): 60 route files, JWT auth, 57+ endpoint groups, pagination, rate limiting
- [x] **Major Security Audit** (v5.28.0): 25+ critical/high/medium fixes across 30+ files
- [x] **Office Hours & TA Management** (v5.29.0): Full CRUD with CLI, GUI, and API
- [x] **Role-Based Dashboards** (v5.29.0-v5.39.0): Admin, instructor, student dashboards with live data
- [x] **Admin Tools** (v5.36.0): Alert config, department management, institution branding
- [x] **Instructor Tools** (v5.37.0): Roster viewer, bulk grade import, course messaging, semester analytics
- [x] **Student Self-Service** (v5.39.0): 13 new features (profile, security, notifications, grades, degree progress, catalog, GPA calculator, messaging, forums, finance, help center, documents)
- [x] **Seed Demo Data** (v5.38.0): 310+ records across 30 tables
- [x] 200+ bug fixes and quality improvements

### Version 5.17.0 (February 7, 2026) -- COMPLETED
- [x] **Document Manager GUI**: 26-file modular package (from 18,953-line monolith)
- [x] **AI Detector**: 49-file modular package (from 10,864-line monolith)
- [x] **Cinema GUI**: 52-file modular package (from 11,086-line monolith)
- [x] **Plagiarism GUI**: 20-file modular package (from 7,132-line monolith)
- [x] **Housing & Shop GUIs**: Converted to modular packages

### Version 5.12.0 (February 2026) -- COMPLETED
- [x] **Observability & Monitoring** - Metrics, health checks, alerts
- [x] **Automated Data Management** - Backup scheduler with retention
- [x] **Performance Optimization** - LRU cache with TTL
- [x] **Remember Me Authentication** - 30-day persistent tokens

### Version 5.5.0 (January 2026) -- COMPLETED
- [x] **Student Success & Engagement Platform** - 18 comprehensive modules
- [x] 40+ new database tables, full CLI and GUI interfaces

### Version 5.4.0 (January 2026) -- COMPLETED
- [x] **Staff HR Management System** - 15 specialized managers
- [x] 23 new database tables, 14 CLI menus + 14 GUI interfaces

### Next Up
- [x] ~~REST API for Secondary School and Primary School systems~~ (completed v7.25.0-v7.31.0)
- [ ] Mobile application (React Native)
- [ ] Integration with external LMS systems (Canvas, Blackboard, Moodle)
- [ ] Complete i18n support for all remaining GUI modules
- [ ] Real-time collaboration features (live sessions, chat via WebSockets)

### Future Considerations
- [ ] Microservices architecture
- [ ] GraphQL API alongside REST
- [ ] Multi-tenancy support for hosting multiple institutions
- [ ] Cloud-native deployment (Kubernetes, Docker Swarm)
- [ ] Localization (l10n) -- expanding translation coverage beyond 10 languages
- [ ] Blockchain for credential verification and academic records
- [ ] Advanced AI features (chatbot improvements, automated grading)
- [ ] Mobile-first responsive web design
