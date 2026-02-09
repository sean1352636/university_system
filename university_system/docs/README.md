# University Management System - Documentation

Complete documentation for the University Management System.

## Documentation Structure

```
docs/
├── README.md                 # This file - documentation index
├── QUICK_START.md            # Get running in 5 minutes
├── TROUBLESHOOTING.md        # Common issues and solutions
│
├── security/                 # Security & Authentication
│   ├── SECURITY.md          # Security features and best practices
│   ├── AUTHENTICATION.md    # Authentication implementation guide
│   ├── AUTH_QUICK_REFERENCE.md  # Quick authentication reference
│   ├── MFA_SYSTEM_DOCUMENTATION.md  # Complete MFA guide
│   └── MFA_QUICK_START.md   # MFA setup quick start
│
├── infrastructure/           # Infrastructure guides
│   ├── DATABASE.md          # Database schema and usage
│   ├── TRANSACTIONS.md      # Transaction safety guide
│   └── EMAIL_SCHEDULER.md   # Automated email system
│
├── development/              # Developer documentation
│   ├── README.md            # Development overview
│   ├── EXCEPTION_HANDLING.md    # Error handling patterns
│   └── TESTING_GUIDE.md     # Writing and running tests
│
└── modules/                  # Module documentation
    └── README.md            # Module overview and guides
```

## Quick Start

New to the system? Start here:

1. **[Quick Start Guide](QUICK_START.md)** - Get running in 5 minutes
2. **[Security Setup](security/SECURITY.md)** - Configure security settings
3. **[MFA Setup](security/MFA_QUICK_START.md)** - Enable multi-factor authentication

## By Topic

### Security & Authentication

| Document | Description |
|----------|-------------|
| [SECURITY.md](security/SECURITY.md) | Comprehensive security features and best practices |
| [AUTHENTICATION.md](security/AUTHENTICATION.md) | Authentication system implementation |
| [AUTH_QUICK_REFERENCE.md](security/AUTH_QUICK_REFERENCE.md) | Quick reference for auth operations |
| [MFA_SYSTEM_DOCUMENTATION.md](security/MFA_SYSTEM_DOCUMENTATION.md) | Complete MFA implementation guide |
| [MFA_QUICK_START.md](security/MFA_QUICK_START.md) | Quick MFA setup guide |

### Infrastructure

| Document | Description |
|----------|-------------|
| [DATABASE.md](infrastructure/DATABASE.md) | Database schema, tables, and queries |
| [TRANSACTIONS.md](infrastructure/TRANSACTIONS.md) | Transaction handling and ACID compliance |
| [EMAIL_SCHEDULER.md](infrastructure/EMAIL_SCHEDULER.md) | Automated email scheduling system |

### Development

| Document | Description |
|----------|-------------|
| [Development README](development/README.md) | Development environment setup |
| [EXCEPTION_HANDLING.md](development/EXCEPTION_HANDLING.md) | Error handling patterns and guidelines |
| [TESTING_GUIDE.md](development/TESTING_GUIDE.md) | Testing framework and best practices |

### Modules

| Document | Description |
|----------|-------------|
| [Modules README](modules/README.md) | Overview of all system modules |

## Troubleshooting

Having issues? Check:

1. **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions
2. **[Auth Quick Reference](security/AUTH_QUICK_REFERENCE.md)** - Authentication problems
3. **[Database Guide](infrastructure/DATABASE.md)** - Database issues

## For Developers

### Getting Started

```bash
# Run tests
make test

# Format code
make format

# Run quality checks
make check
```

### Key Resources

- **[CLAUDE.md](../CLAUDE.md)** - AI assistant instructions and project overview
- **[Testing Guide](development/TESTING_GUIDE.md)** - Write and run tests
- **[Exception Handling](development/EXCEPTION_HANDLING.md)** - Error handling patterns

## Documentation Standards

All documentation follows these standards:

- Written in GitHub-flavored Markdown
- Code examples are tested and working
- Clear, concise language
- Organized by topic

---

**Last Updated**: December 2025
**Version**: 5.0.0
