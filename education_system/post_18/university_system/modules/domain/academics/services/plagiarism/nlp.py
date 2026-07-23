from education_system.post_18.university_system.core.paths import NLTK_DATA_DIR
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging

logger = configure_logging(name=__name__)

# Optional imports with fallback
try:
    import nltk
    # Use centralized NLTK data path
    custom_nltk_path = str(NLTK_DATA_DIR)
    if custom_nltk_path not in nltk.data.path:
        nltk.data.path.insert(0, custom_nltk_path)

    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.util import ngrams
    NLTK_AVAILABLE = True
except ImportError:
    logger.warning("NLTK not available. Using fallback tokenization.")
    NLTK_AVAILABLE = False
    word_tokenize = None
    stopwords = None
    ngrams = None

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    logger.warning("textract not available. Only .txt files will be supported.")
    TEXTRACT_AVAILABLE = False
    textract = None


def download_nltk_data():
    """Download required NLTK data with error handling"""
    if not NLTK_AVAILABLE:
        return

    required_data = [
        ('tokenizers/punkt', 'punkt'),
        ('tokenizers/punkt_tab', 'punkt_tab'),
        ('corpora/stopwords', 'stopwords')
    ]

    for data_path, download_name in required_data:
        try:
            nltk.data.find(data_path)
        except LookupError:
            try:
                logger.info(f"Downloading NLTK {download_name}...")
                nltk.download(download_name, quiet=True)
                logger.info(f"Successfully downloaded NLTK {download_name}")
            except Exception as e:
                logger.error(f"Failed to download NLTK {download_name}: {e}")


# Initialize NLTK data on import
download_nltk_data()
