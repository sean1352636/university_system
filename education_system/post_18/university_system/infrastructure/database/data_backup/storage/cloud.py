"""AWS S3 cloud storage operations."""

import boto3
from botocore.exceptions import NoCredentialsError

from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.infrastructure.database.data_backup.config import config

logger = configure_logging(name=__name__)


def upload_to_aws_s3(file_path: str, bucket: str, key: str) -> bool:
    """Upload file to AWS S3"""
    from botocore.exceptions import ClientError, ParamValidationError
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=config["aws_access_key"],
            aws_secret_access_key=config["aws_secret_key"],
            region_name=config["aws_region"]
        )

        s3_client.upload_file(file_path, bucket, key)
        logger.info(f"Uploaded {file_path} to S3: s3://{bucket}/{key}")
        return True
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        return False
    except ClientError as e:
        logger.error(f"AWS S3 client error: {e}")
        return False
    except ParamValidationError as e:
        logger.error(f"Invalid AWS S3 parameters: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for S3 upload: {e}")
        return False


def download_from_aws_s3(bucket: str, key: str, download_path: str) -> bool:
    """Download file from AWS S3"""
    from botocore.exceptions import ClientError, ParamValidationError
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=config["aws_access_key"],
            aws_secret_access_key=config["aws_secret_key"],
            region_name=config["aws_region"]
        )

        s3_client.download_file(bucket, key, download_path)
        logger.info(f"Downloaded s3://{bucket}/{key} to {download_path}")
        return True
    except NoCredentialsError:
        logger.error("AWS credentials not found for download")
        return False
    except ClientError as e:
        logger.error(f"AWS S3 client error during download: {e}")
        return False
    except ParamValidationError as e:
        logger.error(f"Invalid AWS S3 parameters: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error writing downloaded file: {e}")
        return False
