"""File compression and decompression utilities."""

import gzip
import os
import shutil
import zipfile

from education_system.university_system.utils.logging.log_config import configure_logging

logger = configure_logging(name=__name__)


def compress_file(file_path: str, compression_format: str = "gzip", level: int = 6) -> str:
    """Compress a file using specified format"""
    try:
        if compression_format == "gzip":
            compressed_path = file_path + ".gz"
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb', compresslevel=level) as f_out:
                    shutil.copyfileobj(f_in, f_out)

        elif compression_format == "zip":
            compressed_path = file_path + ".zip"
            with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level) as zipf:
                zipf.write(file_path, os.path.basename(file_path))

        else:
            from education_system.university_system.infrastructure.exceptions import InvalidInputError
            raise InvalidInputError(
                f"Unsupported compression format: {compression_format}",
                code="INVALID_COMPRESSION_FORMAT",
                details={'format': compression_format, 'supported': ['gzip', 'bz2', 'lzma', 'zip']}
            )

        # Remove original file
        os.remove(file_path)

        return compressed_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during compression: {e}")
        return None
    except (zipfile.BadZipFile, gzip.BadGzipFile) as e:
        logger.error(f"Compression format error: {e}")
        return None


def decompress_file(compressed_path: str, output_path: str = None) -> str:
    """Decompress a file"""
    try:
        if compressed_path.endswith('.gz'):
            if output_path is None:
                output_path = compressed_path[:-3]  # Remove .gz extension

            with gzip.open(compressed_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        elif compressed_path.endswith('.zip'):
            if output_path is None:
                output_path = os.path.splitext(compressed_path)[0]

            with zipfile.ZipFile(compressed_path, 'r') as zipf:
                zipf.extractall(os.path.dirname(output_path))
                # Assume single file in zip
                extracted_files = zipf.namelist()
                if extracted_files:
                    extracted_path = os.path.join(os.path.dirname(output_path), extracted_files[0])
                    if extracted_path != output_path:
                        shutil.move(extracted_path, output_path)

        return output_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during decompression: {e}")
        return None
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        return None
    except gzip.BadGzipFile as e:
        logger.error(f"Invalid GZIP file: {e}")
        return None
