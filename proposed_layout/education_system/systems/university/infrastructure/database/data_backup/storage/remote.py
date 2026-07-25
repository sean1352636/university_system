"""FTP and SFTP remote storage operations."""

import ftplib
import os

import paramiko

from education_system.systems.university.infrastructure.logging.log_config import configure_logging

logger = configure_logging(name=__name__)


def upload_to_ftp(file_path: str, host: str, username: str, password: str, remote_path: str) -> bool:
    """Upload file to FTP server"""
    try:
        with ftplib.FTP(host) as ftp:
            ftp.login(username, password)
            ftp.cwd(remote_path)

            with open(file_path, 'rb') as file:
                ftp.storbinary(f'STOR {os.path.basename(file_path)}', file)

        logger.info(f"Uploaded {file_path} to FTP: {host}{remote_path}")
        return True
    except ftplib.all_errors as e:
        logger.error(f"FTP error during upload: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for FTP upload: {e}")
        return False


def upload_to_sftp(file_path: str, host: str, username: str, password: str, remote_path: str) -> bool:
    """Upload file to SFTP server"""
    try:
        with paramiko.SSHClient() as ssh:
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
            ssh.connect(host, username=username, password=password)

            with ssh.open_sftp() as sftp:
                remote_file_path = f"{remote_path}/{os.path.basename(file_path)}"
                sftp.put(file_path, remote_file_path)

        logger.info(f"Uploaded {file_path} to SFTP: {host}{remote_path}")
        return True
    except paramiko.AuthenticationException:
        logger.error("SFTP authentication failed")
        return False
    except paramiko.SSHException as e:
        logger.error(f"SSH/SFTP connection error: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for SFTP upload: {e}")
        return False
