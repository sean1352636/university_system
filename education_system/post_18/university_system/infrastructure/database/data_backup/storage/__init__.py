"""Cloud and remote storage providers for backups."""

from education_system.post_18.university_system.infrastructure.database.data_backup.storage.cloud import (
    upload_to_aws_s3,
    download_from_aws_s3,
)
from education_system.post_18.university_system.infrastructure.database.data_backup.storage.remote import (
    upload_to_ftp,
    upload_to_sftp,
)

__all__ = [
    "upload_to_aws_s3",
    "download_from_aws_s3",
    "upload_to_ftp",
    "upload_to_sftp",
]
