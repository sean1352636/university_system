# Deployment

> Back to [README](../README.md)

## Deployment

### Production Deployment

#### Using Docker (Recommended)

```bash
# Build image
docker build -t education-system:latest -f docker/Dockerfile .

# Run with docker-compose (recommended)
docker compose -f docker/docker-compose.yml up -d

# Or run standalone container
docker run -d -p 5000:5000 \
  -v $(pwd)/var:/app/var \
  --env-file .env.production \
  --name education-system \
  education-system:latest \
  python -m education_system --api
```

`docker/docker-compose.yml` runs the API under Gunicorn behind nginx and keeps all runtime state in the `app-var` volume, mounted at `/app/var`. Pass `API_SECRET_KEY`, `JWT_SECRET_KEY` and `CREDENTIAL_SIGNING_KEY` from the host or a `.env` file; they're required when `APP_ENV=production`. To use the CLI against that volume, run `docker compose -f docker/docker-compose.yml run --rm app python -m education_system --cli`. The image's own default command is the CLI. For orchestrated deployments, use `deploy/docker-stack.yml` or `deploy/kubernetes/`.

#### Manual Deployment

```bash
# 1. Set production environment
export APP_ENV=production
export DEBUG=False

# 2. Install production dependencies
make install
pip install -e . --no-deps

# 3. Configure production secrets in .env (JWT_SECRET_KEY, API_SECRET_KEY, API_CORS_ORIGINS)
# Databases are SQLite files under var/data/

# 4. Run the application
python -m education_system --gui  # For GUI
python -m education_system --cli  # For CLI
python -m education_system --api  # For REST API server
```

### Backup & Recovery

#### Pre-configured Backup Templates

The system includes **6 professionally configured backup templates** for different use cases:

1. **Daily Basic** - Standard daily backups with compression
2. **Secure Encrypted** - High-security backups with encryption and retention
3. **Incremental Fast** - Quick incremental backups for high-activity environments
4. **Cloud AWS** - AWS S3 cloud storage integration
5. **Selective Tables** - Backup only critical database tables
6. **Remote SFTP** - Secure off-site backups via SFTP

**Documentation**: See [Backup Templates README](../../src/education_system/systems/university/assets/templates/seeds/backup/README.md) for detailed template descriptions, configuration options, and usage examples.

**Using Templates via GUI**:
1. Open Data Backup GUI from the main interface
2. Click "Load Template" button
3. Select a template (descriptions shown)
4. Configure required settings (passwords, credentials)
5. Save and run backup

#### Automatic Backups
- **Location**: `var/backups/` directory (centralized via `paths.py`)
- **Schedule**: Daily at 2 AM (configurable per template)
- **Retention**: 7-30 days (configurable via retention policies)
- **Includes**: Database, configuration files, uploads
- **Features**: Compression, encryption, cloud sync, deduplication

#### Manual Backup

```bash
# Create backup programmatically
python -c "from education_system.systems.university.infrastructure.database.data_backup import create_enhanced_backup; create_enhanced_backup(manual=True)"
```

Or use the Data Backup screen in the University GUI (`systems/university/shell/gui/database/backup_gui.py`).

#### Restore from Backup

```bash
# Restore programmatically
python -c "from education_system.systems.university.infrastructure.database.data_backup import restore_from_backup; restore_from_backup('var/backups/university/database/<backup file>')"
```

The Data Backup screen in the University GUI is recommended for selective restore.

#### Backup Features
- **Multiple backup types**: Full, incremental, differential, selective
- **Compression**: GZIP or ZIP with configurable compression levels
- **Encryption**: AES encryption with password protection
- **Cloud storage**: AWS S3, Google Cloud, Azure Blob
- **Remote storage**: SFTP, FTP support
- **Email notifications**: Success/failure alerts
- **Integrity verification**: Hash-based backup validation
- **Deduplication**: Reduce storage usage
- **Activity logging**: Complete audit trail in the backup log under `var/logs/`

### Database Migration

```bash
# 1. Backup current database
python -c "from education_system.systems.university.infrastructure.database.data_backup import create_enhanced_backup; create_enhanced_backup(manual=True)"

# 2. Run migrations (the launcher also applies them at startup)
alembic -c src/education_system/alembic.ini upgrade head

# 3. Verify migration
alembic -c src/education_system/alembic.ini current
```

---

