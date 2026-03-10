# Quick Start Guide

Get the University Management System running in 5 minutes.

## Prerequisites

- Python 3.8+ installed
- 500MB free disk space
- Internet connection (for dependencies)

## Installation

### 1. Install Dependencies

```bash
# Navigate to project directory
cd university_system

# Install required packages
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings (optional for first run)
nano .env
```

### 3. Run the Application

```bash
# Using Make (recommended)
make run-gui

# Or using Python directly
python run.py --gui
```

## First Login

Use the default administrator credentials:

- **Username**: `admin`
- **Password**: `admin123`

⚠️ **IMPORTANT**: Change the default password immediately after first login!

## Quick Tour

### Main Dashboard
After login, you'll see the main dashboard with access to all modules:

1. **Student Management** - Enrollment, records, grading
2. **Course Management** - Course catalog, scheduling
3. **Financial Management** - Billing, payments, scholarships
4. **Student Union** - Clubs, events, facilities
5. **Health Services** - Medical records, appointments
6. **Library System** - Book checkout, fines
7. **Reports & Analytics** - Custom reports, dashboards

### Common Tasks

#### Add a New Student
1. Navigate to **Student Management**
2. Click **New Student**
3. Fill in student information
4. Click **Save**

#### Create a Course
1. Navigate to **Course Management**
2. Click **New Course**
3. Enter course details
4. Assign instructor
5. Click **Create**

#### Process a Payment
1. Navigate to **Financial Management**
2. Select student
3. View outstanding balances
4. Click **Process Payment**
5. Enter payment details
6. Confirm transaction

## Next Steps

- [Complete Installation Guide](INSTALLATION.md) - Detailed setup instructions
- [Configuration Guide](CONFIGURATION.md) - Advanced configuration options
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions

## Getting Help

- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Development Commands](development/README.md#make-commands) - Make commands reference

## Development Quick Start

For developers wanting to contribute:

```bash
# Complete setup with development tools
make setup

# Run tests
make test

# Format code
make format

# Run all quality checks
make check
```

See [Development Setup](development/README.md) for complete development environment setup.

---

**Estimated Time**: 5 minutes
**Difficulty**: Beginner
**Next**: [Documentation Index](README.md)
