# Backup Templates

This directory contains pre-configured backup templates for the University Management System's data backup functionality.

## Available Templates

### 1. Daily Basic (`daily_basic.json`)
**Description**: Standard daily backup with compression, no encryption

**Use case**: General-purpose daily backups for non-sensitive data
- Full backup type
- Daily frequency at 2:00 AM
- Keeps 7 daily backups
- GZIP compression (level 6)
- No encryption
- Local storage only

### 2. Secure Encrypted (`secure_encrypted.json`)
**Description**: High-security backup with encryption and secure deletion

**Use case**: Backing up sensitive student records and financial data
- Full backup type
- Daily frequency at 3:00 AM
- Keeps 14 daily, 8 weekly, 24 monthly, 10 yearly backups
- GZIP compression (level 9 - maximum)
- Encryption enabled (password required)
- Secure deletion of old backups
- Email notifications enabled
- Deduplication enabled

### 3. Incremental Fast (`incremental_fast.json`)
**Description**: Quick incremental backups for frequent changes

**Use case**: Frequent backups in high-activity environments
- Incremental backup type
- Hourly frequency at 12:00 PM
- Keeps 24 hourly backups
- GZIP compression (level 3 - fast)
- Change detection enabled
- Parallel backup with 4 threads
- Deduplication enabled

### 4. Cloud AWS (`cloud_aws.json`)
**Description**: Backup with AWS S3 cloud storage integration

**Use case**: Off-site backups to Amazon S3
- Full backup type
- Daily frequency at 1:00 AM
- Keeps 15 backups
- GZIP compression (level 9)
- Encryption enabled
- AWS S3 cloud storage integration
- Bandwidth limit: 50 Mbps
- Email notifications
- 50GB storage quota

**Required configuration**:
- `aws_bucket`: Your S3 bucket name
- `aws_access_key`: Your AWS access key
- `aws_secret_key`: Your AWS secret key
- `aws_region`: AWS region (default: us-east-1)

### 5. Selective Tables (`selective_tables.json`)
**Description**: Backup only specific critical tables

**Use case**: Quick backups of essential data only
- Full backup type
- Daily frequency at 4:00 AM
- Keeps 10 daily backups
- GZIP compression (level 6)
- Selective table backup enabled
- Default tables: students, courses, enrollments, grades, users

**Customization**: Modify the `selective_tables` array to include your desired tables.

### 6. Remote SFTP (`remote_sftp.json`)
**Description**: Backup to remote server via SFTP

**Use case**: Secure off-site backups to your own server
- Full backup type
- Daily frequency at 11:00 PM
- Keeps 7 daily backups
- GZIP compression (level 7)
- Encryption enabled
- SFTP remote storage
- Email notifications
- Bandwidth limit: 20 Mbps

**Required configuration**:
- `remote_host`: Your SFTP server hostname/IP
- `remote_username`: SFTP username
- `remote_password`: SFTP password
- `remote_path`: Remote directory path (default: /backups)

## Using Templates

### From GUI
1. Open the Data Backup GUI
2. Click "Load Template" button
3. Select a template from the list
4. Click "Load"
5. Configure any required settings (passwords, credentials, etc.)
6. Save your configuration

### Programmatically
```python
from university_system.infrastructure.database.gui.data_backup_gui import load_backup_template

# Load a template
load_backup_template("Daily Basic Backup")
```

### Import/Export Templates
- **Export**: Use the "Export Template" button to save a template to a JSON file
- **Import**: Use the "Import Template" button to load a template from a JSON file

## Creating Custom Templates

You can create your own templates by:

1. **Method 1**: Configure settings in the GUI and use "Save Template"
2. **Method 2**: Create a JSON file manually in this directory

### Template JSON Structure
```json
{
  "name": "My Custom Template",
  "description": "Description of what this template does",
  "backup_type": "full",
  "scheduled_backup_time": "02:00",
  "backup_frequency": "daily",
  "max_backups": 10,
  "auto_backup_enabled": true,
  "compression_enabled": true,
  "compression_format": "gzip",
  "compression_level": 6,
  "encryption_enabled": false,
  "encryption_password": "",
  "retention_policy": {
    "daily_keep": 7,
    "weekly_keep": 4,
    "monthly_keep": 12,
    "yearly_keep": 5
  }
}
```

## Configuration Fields

### Backup Types
- `full`: Complete database backup
- `incremental`: Only changes since last backup
- `differential`: Changes since last full backup

### Backup Frequency
- `hourly`, `daily`, `weekly`, `monthly`

### Compression Formats
- `gzip`: Good compression, widely compatible
- `zip`: Universal compatibility

### Compression Levels (for gzip)
- `1-3`: Fast compression, larger files
- `4-6`: Balanced (recommended)
- `7-9`: Maximum compression, slower

## Best Practices

1. **Use encryption** for backups containing sensitive student data
2. **Enable email notifications** for critical backup jobs
3. **Test restore** from your backups regularly
4. **Use incremental backups** for large databases to save time and space
5. **Configure retention policies** to balance storage usage and recovery options
6. **Enable cloud/remote storage** for disaster recovery
7. **Set bandwidth limits** to avoid impacting network performance
8. **Use selective backups** during business hours to minimize disruption

## Security Notes

- **Never commit passwords** in template files to version control
- **Encrypt backups** containing personal information (FERPA compliance)
- **Use secure deletion** when removing old backups with sensitive data
- **Verify backup integrity** regularly
- **Store encryption passwords** securely (use a password manager)

## Template Locations

Templates are loaded from:
1. **Primary**: `university_system/templates/backup_templates/` (this directory)
2. **Fallback**: Application config file (for backward compatibility)

## Troubleshooting

### Template Not Loading
- Check JSON syntax is valid
- Ensure file is in the correct directory
- Check file permissions (should be readable)

### Backup Failing
- Verify database path in settings
- Check backup directory exists and is writable
- Ensure sufficient disk space
- Review logs in the GUI's "View Logs" section

### Cloud/Remote Storage Issues
- Verify credentials are correct
- Check network connectivity
- Ensure remote path exists
- Review bandwidth limits

## Support

For issues or questions, check:
- Application logs: `logs/backup_gui.log`
- System documentation: `docs/`
- GitHub issues: Report problems at the repository
