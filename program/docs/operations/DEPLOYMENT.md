# Deployment

> Back to [README](../../README.md)

## Deployment

### Production Deployment

#### Using Docker (Recommended)

```bash
# Build image
docker build -t education-system:latest -f docker/Dockerfile .

# Run with docker-compose (recommended)
docker compose -f docker/docker-compose.yml up -d

# Or run standalone container
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --env-file .env.production \
  --name education-system \
  education-system:latest
```

#### Manual Deployment

```bash
# 1. Set production environment
export APP_ENV=production
export DEBUG=False

# 2. Install production dependencies
pip install -r requirements.txt

# 3. Configure production database (PostgreSQL/MySQL recommended)
# Edit .env with production database credentials

# 4. Run the application
python run.py --gui  # For GUI
python run.py --cli  # For CLI
python run.py --api  # For REST API server
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

**Documentation**: See [Backup Templates README](../education_system/university_system/templates/backup_templates/README.md) for detailed template descriptions, configuration options, and usage examples.

**Using Templates via GUI**:
1. Open Data Backup GUI from the main interface
2. Click "Load Template" button
3. Select a template (descriptions shown)
4. Configure required settings (passwords, credentials)
5. Save and run backup

#### Automatic Backups
- **Location**: `backups/` directory (centralized via `paths.py`)
- **Schedule**: Daily at 2 AM (configurable per template)
- **Retention**: 7-30 days (configurable via retention policies)
- **Includes**: Database, configuration files, uploads
- **Features**: Compression, encryption, cloud sync, deduplication

#### Manual Backup

```bash
# Create full backup using Make
make db-backup

# Create backup programmatically
python -m university_system.infrastructure.database.database_utils --backup

# Using Data Backup GUI
python -m university_system.infrastructure.database.gui.data_backup_gui
```

#### Restore from Backup

```bash
# Restore using Make
make db-restore BACKUP_FILE=backups/backup_20250101.db

# Restore programmatically
python -m university_system.infrastructure.database.database_utils --restore backups/backup_20250101.db

# Using Data Backup GUI (recommended for selective restore)
python -m university_system.infrastructure.database.gui.data_backup_gui
```

#### Backup Features
- **Multiple backup types**: Full, incremental, differential, selective
- **Compression**: GZIP or ZIP with configurable compression levels
- **Encryption**: AES encryption with password protection
- **Cloud storage**: AWS S3, Google Cloud, Azure Blob
- **Remote storage**: SFTP, FTP support
- **Email notifications**: Success/failure alerts
- **Integrity verification**: Hash-based backup validation
- **Deduplication**: Reduce storage usage
- **Activity logging**: Complete audit trail in `logs/backup.log`

### Database Migration

```bash
# 1. Backup current database
make db-backup

# 2. Run migrations
python -m university_system.infrastructure.database.migrate

# 3. Verify migration
python -m university_system.infrastructure.database.verify
```

---

