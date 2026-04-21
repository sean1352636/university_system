import os
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.logging.log_config import configure_logging

from education_system.university_system.modules.domain.academics.services.plagiarism.checker import PlagiarismChecker
from education_system.university_system.modules.domain.academics.services.plagiarism.nlp import download_nltk_data
from education_system.university_system.modules.domain.academics.services.plagiarism.sample_data import create_sample_documents

logger = configure_logging(name=__name__)


def check_requirements():
    """Check if required dependencies are installed"""
    missing_packages = []

    try:
        import nltk
        logger.info("NLTK available")
    except ImportError:
        missing_packages.append("nltk")
        logger.warning("NLTK not available")

    try:
        import textract
        logger.info("textract available")
    except ImportError:
        missing_packages.append("textract")
        logger.warning("textract not available - only .txt files will be supported")

    if missing_packages:
        print("Missing optional packages:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print("\nYou can install them with: pip install " + " ".join(missing_packages))
        print("The system will work with limited functionality without these packages.")

    return True  # Don't fail setup for optional packages


def check_database():
    """Check if database exists and has required tables"""
    if not os.path.exists(str(DEFAULT_DB_PATH)):
        print("Error: Database file str(DEFAULT_DB_PATH) not found.")
        print("Please initialize the main system first.")
        return False

    # Check if required tables exist
    required_tables = ['users', 'roles', 'permissions']

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]

            missing_tables = [table for table in required_tables if table not in existing_tables]

            if missing_tables:
                print("Error: Required tables not found in database:")
                for table in missing_tables:
                    print(f"  - {table}")
                print("\nPlease initialize the main system properly.")
                return False

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

    return True


def create_directories():
    """Create necessary directories"""
    directories = ['text_files', 'logs']

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created/verified directory: {directory}")
        except OSError as e:
            print(f"Warning: Could not create directory '{directory}': {e}")


def setup_plagiarism_system():
    """Set up the plagiarism detection system"""
    print("Setting up plagiarism detection system...")

    # Check requirements (non-blocking)
    check_requirements()

    # Check database (blocking)
    if not check_database():
        return False

    # Create directories
    create_directories()

    # Download NLTK data if available
    download_nltk_data()

    # Initialize the plagiarism checker
    try:
        checker = PlagiarismChecker()
        print("Plagiarism checker initialized successfully.")
    except Exception as e:
        print(f"Error initializing plagiarism checker: {e}")
        return False

    # Integrate with main system
    try:
        if integrate_plagiarism_checker_with_main():
            print("Plagiarism checker integrated successfully with main system.")
        else:
            print("Warning: Integration with main system may not be complete.")
    except Exception as e:
        print(f"Error during integration: {e}")
        print("Manual integration may be required.")

    # Create sample documents for testing
    create_sample_documents(checker)

    print("\nSetup completed successfully!")
    print("You can now use the plagiarism detection system.")
    print("Access it from the main menu of the student record management system.")

    return True
