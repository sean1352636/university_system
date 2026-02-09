from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection, ensure_parent_dir
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, NLTK_DATA_DIR
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
import os
import re
import hashlib
import time
import logging
import sys
from datetime import datetime
from difflib import SequenceMatcher
from collections import Counter
from contextlib import contextmanager
from university_system.utils.logging.log_config import configure_logging

# Set up logging
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

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    logger.warning("textract not available. Only .txt files will be supported.")
    TEXTRACT_AVAILABLE = False

# =============================================================================
# Exception Classes
# =============================================================================

class PlagiarismCheckerError(Exception):
    """Base exception for plagiarism checker errors"""
    pass


class DatabaseError(PlagiarismCheckerError):
    """Database-related errors"""
    pass


class FileProcessingError(PlagiarismCheckerError):
    """File processing related errors"""
    pass


class IntegrationError(PlagiarismCheckerError):
    """Integration-related errors"""
    pass


# =============================================================================
# NLTK Initialization
# =============================================================================

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


# =============================================================================
# Database Utilities
# =============================================================================

@contextmanager
def get_safe_db_connection(db_path=str(DEFAULT_DB_PATH)):
    """Safe database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database operation failed: {e}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected database error: {e}")
        raise DatabaseError(f"Unexpected database error: {e}")
    finally:
        if conn:
            conn.close()


# =============================================================================
# Main Plagiarism Checker Class
# =============================================================================

class PlagiarismChecker:
    """Main plagiarism detection and document management system"""
    
    def __init__(self, db_path=str(DEFAULT_DB_PATH)):
        self.db_path = db_path
        ensure_parent_dir(self.db_path)
        self.init_db()    
    def get_db_connection(self):
        """Get database connection context manager"""
        return get_safe_db_connection(self.db_path)
        
    def init_db(self):
        """Initialize database tables for plagiarism checking"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Create table for document repository
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_repository (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK(length(title) > 0),
                    content TEXT NOT NULL CHECK(length(content) > 0),
                    content_hash TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    module_code TEXT,
                    submission_date TEXT NOT NULL,
                    file_type TEXT,
                    word_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code) ON DELETE SET NULL
                )
                ''')
                
                # Create table for plagiarism check results
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plagiarism_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    matched_document_id INTEGER,
                    similarity_score REAL NOT NULL CHECK(similarity_score >= 0 AND similarity_score <= 1),
                    check_date TEXT NOT NULL,
                    checked_by INTEGER,
                    status TEXT NOT NULL,
                    report TEXT,
                    threshold_used REAL DEFAULT 0.3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES document_repository (id) ON DELETE CASCADE,
                    FOREIGN KEY (matched_document_id) REFERENCES document_repository (id) ON DELETE SET NULL,
                    FOREIGN KEY (checked_by) REFERENCES users (id) ON DELETE SET NULL
                )
                ''')
                
                # Create indexes for better query performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_hash ON document_repository (content_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_author ON document_repository (author_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_module ON document_repository (module_code)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plagiarism_doc ON plagiarism_results (document_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plagiarism_status ON plagiarism_results (status)')
                
                # Create trigger to update updated_at timestamp
                cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS update_document_timestamp 
                AFTER UPDATE ON document_repository
                BEGIN
                    UPDATE document_repository SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
                ''')
                
                conn.commit()
                logger.info("Plagiarism checker database initialized successfully!")
                return True
                
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during database initialization: {e}")
            raise PlagiarismCheckerError(f"Database initialization failed: {e}")
            
    def extract_text_from_file(self, file_path):
        """Extract text content from various file formats"""
        if not file_path:
            raise ValueError("File path cannot be empty")
        
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Check file size (limit to 50MB)
            file_size = os.path.getsize(file_path)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                raise FileProcessingError(f"File too large: {file_size / (1024*1024):.1f}MB (max: 50MB)")
            
            if file_size == 0:
                raise FileProcessingError("File is empty")
                
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.txt':
                return self._extract_text_file(file_path), 'txt'
            elif TEXTRACT_AVAILABLE:
                return self._extract_with_textract(file_path, file_extension)
            else:
                raise FileProcessingError(f"Unsupported file type: {file_extension}. Only .txt files are supported.")
                
        except (FileNotFoundError, FileProcessingError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error extracting text from {file_path}: {e}")
            raise FileProcessingError(f"Failed to extract text: {e}")
    
    def _extract_text_file(self, file_path):
        """Extract text from .txt files with encoding detection"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    content = file.read()
                    if content.strip():  # Check if content is not just whitespace
                        return content
                    else:
                        raise FileProcessingError("File contains only whitespace")
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise FileProcessingError(f"Error reading text file: {e}")
        
        raise FileProcessingError("Could not decode file with any supported encoding")
    
    def _extract_with_textract(self, file_path, file_extension):
        """Extract text using textract"""
        try:
            text = textract.process(file_path).decode('utf-8')
            if not text.strip():
                raise FileProcessingError("Extracted text is empty")
            return text, file_extension[1:] if file_extension.startswith('.') else file_extension
        except Exception as e:
            logger.error(f"Error extracting text with textract: {e}")
            raise FileProcessingError(f"Could not extract text from {file_extension} file: {e}")
    
    def preprocess_text(self, text):
        """Preprocess text for plagiarism detection"""
        if not text or not isinstance(text, str):
            return []
        
        try:
            # Convert to lowercase and normalize whitespace
            text = re.sub(r'\s+', ' ', text.lower().strip())
            
            # Remove special characters and numbers but keep basic punctuation for sentence structure
            text = re.sub(r'[^\w\s\.\!\?]', '', text)
            text = re.sub(r'\d+', '', text)
            
            # Tokenize
            if NLTK_AVAILABLE:
                try:
                    tokens = word_tokenize(text)
                except Exception as e:
                    logger.warning(f"NLTK tokenization failed, using fallback: {e}")
                    tokens = self._fallback_tokenize(text)
            else:
                tokens = self._fallback_tokenize(text)
            
            # Remove stopwords and short words
            if NLTK_AVAILABLE:
                try:
                    stop_words = set(stopwords.words('english'))
                except Exception as e:
                    logger.warning(f"NLTK stopwords failed, using fallback: {e}")
                    stop_words = self._get_fallback_stopwords()
            else:
                stop_words = self._get_fallback_stopwords()
            
            filtered_tokens = [
                word for word in tokens 
                if word not in stop_words and len(word) > 2 and word.isalpha()
            ]
            
            return filtered_tokens
            
        except Exception as e:
            logger.error(f"Error preprocessing text: {e}")
            return []
    
    def _fallback_tokenize(self, text):
        """Fallback tokenization when NLTK is not available"""
        words = re.findall(r'\b[a-zA-Z]+\b', text)
        return words
    
    def _get_fallback_stopwords(self):
        """Fallback stopwords when NLTK is not available"""
        return {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'have', 'had', 'this', 'but', 'or',
            'not', 'you', 'all', 'can', 'her', 'him', 'his', 'she', 'they',
            'we', 'would', 'there', 'been'
        }
    
    def compute_ngrams(self, tokens, n=3):
        """Compute n-grams from tokens"""
        if not tokens or not isinstance(tokens, list):
            return []
        
        if len(tokens) < n:
            return [tuple(tokens)] if tokens else []
        
        try:
            if NLTK_AVAILABLE:
                return list(ngrams(tokens, n))
            else:
                # Fallback n-gram generation
                return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]
        except Exception as e:
            logger.error(f"Error computing n-grams: {e}")
            return []
    
    def compute_similarity(self, ngrams1, ngrams2):
        """Compute Jaccard similarity between two sets of n-grams"""
        try:
            if not ngrams1 or not ngrams2:
                return 0.0
                
            set1 = set(ngrams1)
            set2 = set(ngrams2)
            
            if not set1 or not set2:
                return 0.0
                
            intersection = set1.intersection(set2)
            union = set1.union(set2)
            
            if len(union) == 0:
                return 0.0
                
            jaccard_similarity = len(intersection) / len(union)
            
            # Also compute sequence similarity as a backup
            try:
                text1 = ' '.join([' '.join(ngram) for ngram in ngrams1[:1000]])  # Limit for performance
                text2 = ' '.join([' '.join(ngram) for ngram in ngrams2[:1000]])
                sequence_similarity = SequenceMatcher(None, text1, text2).ratio()
                
                # Use the higher of the two similarities
                return max(jaccard_similarity, sequence_similarity)
            except Exception:
                return jaccard_similarity
                
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def get_content_hash(self, content):
        """Create a hash of the document content"""
        try:
            if not content or not isinstance(content, str):
                raise ValueError("Content must be a non-empty string")
            
            # Normalize content before hashing to catch minor formatting differences
            normalized_content = re.sub(r'\s+', ' ', content.strip().lower())
            return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"Error creating content hash: {e}")
            # Fallback to simple hash
            try:
                return str(abs(hash(content)))
            except Exception:
                return str(abs(hash(str(content))))
    
    def add_document_to_repository(self, title, content, author_id, module_code, file_type):
        """Add a document to the repository for future plagiarism checks"""
        # Input validation
        if not title or not isinstance(title, str) or len(title.strip()) == 0:
            raise ValueError("Title must be a non-empty string")
        
        if not content or not isinstance(content, str) or len(content.strip()) == 0:
            raise ValueError("Content must be a non-empty string")
        
        if not isinstance(author_id, int) or author_id <= 0:
            raise ValueError("Author ID must be a positive integer")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Validate author exists
                cursor.execute('SELECT id FROM users WHERE id = ?', (author_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Author with ID {author_id} does not exist")
                
                # Validate module exists if provided
                if module_code:
                    cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
                    if not cursor.fetchone():
                        logger.warning(f"Module {module_code} does not exist, proceeding anyway")
                
                content_hash = self.get_content_hash(content)
                word_count = len(content.split())
                submission_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Check for exact duplicate
                cursor.execute('''
                SELECT id, title FROM document_repository 
                WHERE content_hash = ? AND author_id = ?
                ''', (content_hash, author_id))
                
                existing = cursor.fetchone()
                if existing:
                    logger.warning(f"Document with identical content already exists: {existing[1]} (ID: {existing[0]})")
                    return existing[0]  # Return existing document ID
                
                cursor.execute('''
                INSERT INTO document_repository 
                (title, content, content_hash, author_id, module_code, submission_date, file_type, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title.strip(), content, content_hash, author_id, module_code, 
                      submission_date, file_type or 'unknown', word_count))
                
                document_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Document '{title}' added to repository with ID: {document_id}")
                return document_id
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error while adding document: {e}")
            raise PlagiarismCheckerError(f"Failed to add document: {e}")
    
    def check_exact_match(self, content_hash):
        """Check if there's an exact match for the document in the repository"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT id, title, author_id, submission_date 
                FROM document_repository 
                WHERE content_hash = ?
                ORDER BY submission_date ASC
                ''', (content_hash,))
                
                matches = cursor.fetchall()
                return matches
                
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during exact match check: {e}")
            return []
    
    def check_plagiarism(self, document_id, checker_id=None, threshold=0.3):
        """
        Check a document for plagiarism against the repository
        
        Args:
            document_id: ID of the document to check
            checker_id: ID of the user performing the check
            threshold: Similarity threshold (0-1) for flagging as potential plagiarism
            
        Returns:
            Dictionary with plagiarism check results
        """
        # Input validation
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValueError("Document ID must be a positive integer")
        
        if threshold is not None and (not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1):
            raise ValueError("Threshold must be a number between 0 and 1")
        
        if threshold is None:
            threshold = 0.3
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get the document to check
                cursor.execute('''
                SELECT id, title, content, content_hash, author_id, module_code
                FROM document_repository 
                WHERE id = ?
                ''', (document_id,))
                
                doc_data = cursor.fetchone()
                if not doc_data:
                    raise ValueError(f"Document with ID {document_id} not found")
                    
                doc_id, doc_title, doc_content, doc_hash, doc_author, doc_module = doc_data
                
                # First check for exact matches (excluding the document itself)
                cursor.execute('''
                SELECT id, title, content, author_id, submission_date
                FROM document_repository 
                WHERE content_hash = ? AND id != ?
                ORDER BY submission_date ASC
                ''', (doc_hash, doc_id))
                
                exact_matches = cursor.fetchall()
                
                check_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if exact_matches:
                    # We have exact matches - this is 100% plagiarism
                    match_id = exact_matches[0][0]
                    match_title = exact_matches[0][1]
                    
                    report = f"Exact match found with document '{match_title}' (ID: {match_id})"
                    if len(exact_matches) > 1:
                        report += f"\nTotal exact matches found: {len(exact_matches)}"
                    
                    # Record the result
                    cursor.execute('''
                    INSERT INTO plagiarism_results
                    (document_id, matched_document_id, similarity_score, check_date, checked_by, status, report, threshold_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        doc_id, match_id, 1.0, check_date, checker_id, 
                        "EXACT_MATCH", report, threshold
                    ))
                    
                    result_id = cursor.lastrowid
                    conn.commit()
                    
                    return {
                        "result_id": result_id,
                        "document_id": doc_id,
                        "match_type": "exact",
                        "matches": [(match[0], match[1], 1.0) for match in exact_matches],
                        "highest_similarity": 1.0,
                        "status": "EXACT_MATCH",
                        "threshold_used": threshold
                    }
                
                # No exact matches, so compare content for similarity
                logger.info(f"Checking document {doc_id} for similarity matches...")
                
                # Preprocess the document content
                doc_tokens = self.preprocess_text(doc_content)
                if not doc_tokens:
                    logger.warning(f"No tokens extracted from document {doc_id}")
                    
                doc_ngrams = self.compute_ngrams(doc_tokens)
                
                # Get all other documents to compare with (same module for better performance)
                cursor.execute('''
                SELECT id, title, content, author_id
                FROM document_repository 
                WHERE id != ? AND (module_code = ? OR module_code IS NULL)
                ''', (doc_id, doc_module))
                
                all_docs = cursor.fetchall()
                
                # Calculate similarity with each document
                similarities = []
                processed_docs = 0
                
                for other_doc in all_docs:
                    other_id, other_title, other_content, other_author = other_doc
                    processed_docs += 1
                    
                    if processed_docs % 10 == 0:
                        logger.info(f"Processed {processed_docs}/{len(all_docs)} documents for comparison")
                    
                    try:
                        # Calculate similarity
                        other_tokens = self.preprocess_text(other_content)
                        if not other_tokens:
                            continue
                            
                        other_ngrams = self.compute_ngrams(other_tokens)
                        
                        similarity = self.compute_similarity(doc_ngrams, other_ngrams)
                        
                        if similarity >= threshold:
                            similarities.append((other_id, other_title, similarity))
                            
                    except Exception as e:
                        logger.error(f"Error comparing with document {other_id}: {e}")
                        continue
                
                # Sort by similarity score (descending)
                similarities.sort(key=lambda x: x[2], reverse=True)
                
                # Record the results
                if similarities:
                    highest_match_id, highest_match_title, highest_similarity = similarities[0]
                    
                    if highest_similarity >= 0.7:
                        status = "HIGH_SIMILARITY"
                    elif highest_similarity >= 0.5:
                        status = "MODERATE_SIMILARITY"
                    else:
                        status = "LOW_SIMILARITY"
                    
                    report = f"Highest similarity ({highest_similarity:.2%}) found with document '{highest_match_title}' (ID: {highest_match_id})"
                    if len(similarities) > 1:
                        report += f"\nTotal documents with similarity above threshold: {len(similarities)}"
                    
                    cursor.execute('''
                    INSERT INTO plagiarism_results
                    (document_id, matched_document_id, similarity_score, check_date, checked_by, status, report, threshold_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        doc_id, highest_match_id, highest_similarity, check_date, checker_id, 
                        status, report, threshold
                    ))
                else:
                    # No significant similarities found
                    status = "NO_MATCH"
                    report = f"No significant similarities found above threshold ({threshold:.1%})"
                    
                    cursor.execute('''
                    INSERT INTO plagiarism_results
                    (document_id, matched_document_id, similarity_score, check_date, checked_by, status, report, threshold_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        doc_id, None, 0.0, check_date, checker_id, 
                        status, report, threshold
                    ))
                
                result_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Plagiarism check completed for document {doc_id}")
                
                return {
                    "result_id": result_id,
                    "document_id": doc_id,
                    "match_type": "similarity",
                    "matches": similarities,
                    "highest_similarity": similarities[0][2] if similarities else 0.0,
                    "status": status,
                    "threshold_used": threshold
                }
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Error during plagiarism check: {e}")
            raise PlagiarismCheckerError(f"Plagiarism check failed: {e}")
    
    def get_plagiarism_result(self, result_id):
        """Get a specific plagiarism check result"""
        if not isinstance(result_id, int) or result_id <= 0:
            raise ValueError("Result ID must be a positive integer")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT pr.id, pr.document_id, pr.matched_document_id, pr.similarity_score, 
                       pr.check_date, pr.status, pr.report, pr.threshold_used,
                       d1.title as doc_title, d2.title as match_title,
                       u1.first_name || ' ' || u1.last_name as author_name,
                       u2.first_name || ' ' || u2.last_name as checker_name
                FROM plagiarism_results pr
                JOIN document_repository d1 ON pr.document_id = d1.id
                LEFT JOIN document_repository d2 ON pr.matched_document_id = d2.id
                LEFT JOIN users u1 ON d1.author_id = u1.id
                LEFT JOIN users u2 ON pr.checked_by = u2.id
                WHERE pr.id = ?
                ''', (result_id,))
                
                result = cursor.fetchone()
                
                if not result:
                    raise ValueError(f"Plagiarism result with ID {result_id} not found")
                    
                return {
                    "result_id": result[0],
                    "document_id": result[1],
                    "document_title": result[8],
                    "matched_document_id": result[2],
                    "matched_document_title": result[9],
                    "similarity_score": result[3],
                    "check_date": result[4],
                    "status": result[5],
                    "report": result[6],
                    "threshold_used": result[7],
                    "author_name": result[10],
                    "checker_name": result[11]
                }
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error while retrieving result: {e}")
            raise PlagiarismCheckerError(f"Failed to retrieve result: {e}")
    
    def get_document_check_history(self, document_id):
        """Get all plagiarism check results for a document"""
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValueError("Document ID must be a positive integer")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Verify document exists
                cursor.execute('SELECT id FROM document_repository WHERE id = ?', (document_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Document with ID {document_id} not found")
                
                cursor.execute('''
                SELECT id, matched_document_id, similarity_score, check_date, status, threshold_used
                FROM plagiarism_results
                WHERE document_id = ?
                ORDER BY check_date DESC
                ''', (document_id,))
                
                results = cursor.fetchall()
                
                return [
                    {
                        "result_id": r[0],
                        "matched_document_id": r[1],
                        "similarity_score": r[2],
                        "check_date": r[3],
                        "status": r[4],
                        "threshold_used": r[5]
                    }
                    for r in results
                ]
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error while retrieving history: {e}")
            raise PlagiarismCheckerError(f"Failed to retrieve check history: {e}")
            
    def search_repository(self, search_term=None, author_id=None, module_code=None):
        """Search for documents in the repository"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                SELECT id, title, author_id, module_code, submission_date, file_type, word_count
                FROM document_repository
                WHERE 1=1
                '''
                params = []
                
                if search_term:
                    if not isinstance(search_term, str):
                        raise ValueError("Search term must be a string")
                    query += " AND (title LIKE ? OR content LIKE ?)"
                    search_pattern = f"%{search_term.strip()}%"
                    params.extend([search_pattern, search_pattern])
                
                if author_id:
                    if not isinstance(author_id, int) or author_id <= 0:
                        raise ValueError("Author ID must be a positive integer")
                    query += " AND author_id = ?"
                    params.append(author_id)
                    
                if module_code:
                    if not isinstance(module_code, str):
                        raise ValueError("Module code must be a string")
                    query += " AND module_code = ?"
                    params.append(module_code.strip())
                
                query += " ORDER BY submission_date DESC"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                return [
                    {
                        "id": r[0],
                        "title": r[1],
                        "author_id": r[2],
                        "module_code": r[3],
                        "submission_date": r[4],
                        "file_type": r[5],
                        "word_count": r[6]
                    }
                    for r in results
                ]
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise PlagiarismCheckerError(f"Search failed: {e}")
    
    def get_document_details(self, document_id):
        """Get details of a specific document"""
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValueError("Document ID must be a positive integer")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT dr.id, dr.title, dr.author_id, dr.module_code, dr.submission_date, 
                       dr.file_type, dr.word_count, dr.created_at, dr.updated_at,
                       u.first_name || ' ' || u.last_name as author_name
                FROM document_repository dr
                LEFT JOIN users u ON dr.author_id = u.id
                WHERE dr.id = ?
                ''', (document_id,))
                
                result = cursor.fetchone()
                
                if not result:
                    raise ValueError(f"Document with ID {document_id} not found")
                    
                # Get the most recent plagiarism check result
                cursor.execute('''
                SELECT id, similarity_score, status, check_date, threshold_used
                FROM plagiarism_results
                WHERE document_id = ?
                ORDER BY check_date DESC
                LIMIT 1
                ''', (document_id,))
                
                check_result = cursor.fetchone()
                
                return {
                    "id": result[0],
                    "title": result[1],
                    "author_id": result[2],
                    "author_name": result[9] or "Unknown",
                    "module_code": result[3],
                    "submission_date": result[4],
                    "file_type": result[5],
                    "word_count": result[6],
                    "created_at": result[7],
                    "updated_at": result[8],
                    "latest_check": {
                        "result_id": check_result[0],
                        "similarity_score": check_result[1],
                        "status": check_result[2],
                        "check_date": check_result[3],
                        "threshold_used": check_result[4]
                    } if check_result else None
                }
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error while retrieving document: {e}")
            raise PlagiarismCheckerError(f"Failed to retrieve document details: {e}")

    def delete_document(self, document_id):
        """Delete a document and its plagiarism check results"""
        if not isinstance(document_id, int) or document_id <= 0:
            raise ValueError("Document ID must be a positive integer")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if document exists
                cursor.execute('SELECT title FROM document_repository WHERE id = ?', (document_id,))
                doc = cursor.fetchone()
                if not doc:
                    raise ValueError(f"Document with ID {document_id} not found")
                
                # First delete associated plagiarism results
                cursor.execute('''
                DELETE FROM plagiarism_results
                WHERE document_id = ? OR matched_document_id = ?
                ''', (document_id, document_id))
                
                results_deleted = cursor.rowcount
                
                # Then delete the document
                cursor.execute('''
                DELETE FROM document_repository
                WHERE id = ?
                ''', (document_id,))
                
                doc_deleted = cursor.rowcount > 0
                conn.commit()
                
                logger.info(f"Deleted document '{doc[0]}' and {results_deleted} associated check results")
                return doc_deleted
                
        except (ValueError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error while deleting document: {e}")
            raise PlagiarismCheckerError(f"Failed to delete document: {e}")

    def get_statistics(self):
        """Get statistics about the plagiarism checking system"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Total documents
                cursor.execute('SELECT COUNT(*) FROM document_repository')
                total_docs = cursor.fetchone()[0]
                
                # Total checks
                cursor.execute('SELECT COUNT(*) FROM plagiarism_results')
                total_checks = cursor.fetchone()[0]
                
                # Checks by status
                cursor.execute('''
                SELECT status, COUNT(*) 
                FROM plagiarism_results 
                GROUP BY status
                ORDER BY COUNT(*) DESC
                ''')
                status_counts = dict(cursor.fetchall())
                
                # Recent checks
                cursor.execute('''
                SELECT pr.id, d.title, pr.similarity_score, pr.status, pr.check_date
                FROM plagiarism_results pr
                JOIN document_repository d ON pr.document_id = d.id
                ORDER BY pr.check_date DESC
                LIMIT 10
                ''')
                recent_checks = [
                    {
                        "result_id": r[0],
                        "document_title": r[1],
                        "similarity_score": r[2],
                        "status": r[3],
                        "check_date": r[4]
                    }
                    for r in cursor.fetchall()
                ]
                
                # Documents by module
                cursor.execute('''
                SELECT module_code, COUNT(*) 
                FROM document_repository 
                WHERE module_code IS NOT NULL
                GROUP BY module_code
                ORDER BY COUNT(*) DESC
                LIMIT 10
                ''')
                module_stats = dict(cursor.fetchall())
                
                return {
                    "total_documents": total_docs,
                    "total_checks": total_checks,
                    "status_counts": status_counts,
                    "recent_checks": recent_checks,
                    "documents_by_module": module_stats
                }
                
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error while retrieving statistics: {e}")
            raise PlagiarismCheckerError(f"Failed to retrieve statistics: {e}")


# =============================================================================
# User Interface Functions
# =============================================================================

def safe_input(prompt, default=None, validator=None):
    """Safe input function with validation"""
    while True:
        try:
            value = input(prompt).strip()
            if not value and default is not None:
                return default
            if validator:
                if validator(value):
                    return value
                else:
                    print("Invalid input. Please try again.")
                    continue
            return value
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"Input error: {e}")
            continue


def display_plagiarism_checker_menu(auth):
    """Display the plagiarism checker menu and handle user choices"""
    if not auth or not auth.current_user:
        print("You must be logged in to access the Plagiarism Checker.")
        return

    # Check for appropriate permissions
    has_check_permission = auth.check_permission('check_plagiarism')
    has_manage_permission = auth.check_permission('manage_plagiarism_system')
    has_submit_permission = auth.check_permission('submit_document')
    
    if not (has_check_permission or has_manage_permission or has_submit_permission):
        print("You don't have permission to access the Plagiarism Checker.")
        return

    # Initialize the plagiarism checker
    try:
        checker = PlagiarismChecker()
    except Exception as e:
        print(f"Error initializing plagiarism checker: {e}")
        print("Please ensure the database is properly set up.")
        return
    
    while True:
        try:
            print("\nPlagiarism Checker Menu:")
            print("=========================")
            
            # Options based on permissions
            options = []
            option_num = 1
            
            if has_submit_permission:
                print(f"{option_num}. Submit Document")
                options.append("submit_document")
                option_num += 1
                
                print(f"{option_num}. View My Documents")
                options.append("view_my_documents")
                option_num += 1
            
            if has_check_permission:
                print(f"{option_num}. Check Document for Plagiarism")
                options.append("check_document")
                option_num += 1
                
                print(f"{option_num}. View Plagiarism Check Results")
                options.append("view_results")
                option_num += 1
                
                print(f"{option_num}. Search Document Repository")
                options.append("search_repository")
                option_num += 1
            
            if has_manage_permission:
                print(f"{option_num}. System Statistics")
                options.append("view_statistics")
                option_num += 1
                
                print(f"{option_num}. Manage Document Repository")
                options.append("manage_repository")
                option_num += 1
            
            print(f"{option_num}. Return to Main Menu")
            
            choice = safe_input("\nEnter your choice: ")
            if choice is None:  # User cancelled
                return
            
            try:
                choice_num = int(choice)
                
                if choice_num > 0 and choice_num <= len(options):
                    action = options[choice_num - 1]
                    
                    if action == "submit_document":
                        submit_document(checker, auth)
                    elif action == "view_my_documents":
                        view_my_documents(checker, auth)
                    elif action == "check_document":
                        check_document(checker, auth)
                    elif action == "view_results":
                        view_results(checker, auth)
                    elif action == "search_repository":
                        search_repository(checker, auth)
                    elif action == "view_statistics":
                        view_statistics(checker, auth)
                    elif action == "manage_repository":
                        manage_repository(checker, auth)
                elif choice_num == option_num:
                    return
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled. Returning to main menu.")
            return
        except Exception as e:
            print(f"Unexpected error in menu: {e}")


def submit_document(checker, auth):
    """Submit a document to the repository"""
    try:
        print("\nSubmit Document")
        print("===============")
        
        # Get document information
        title = safe_input("Document Title: ")
        if not title:
            print("Operation cancelled or invalid title.")
            return
        
        # Get list of modules/courses
        try:
            with checker.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT module_code, module_name FROM modules
                ORDER BY module_code
                ''')
                
                modules = cursor.fetchall()
                
                if not modules:
                    print("No modules found in the system.")
                    module_code = safe_input("Enter module code manually (optional): ")
                else:
                    print("\nSelect Module/Course:")
                    for i, module in enumerate(modules, 1):
                        print(f"{i}. {module[0]} - {module[1]}")
                    
                    print(f"{len(modules) + 1}. Enter manually")
                    
                    module_choice = safe_input(f"\nModule number (1-{len(modules) + 1}): ")
                    if not module_choice:
                        return
                    
                    try:
                        module_idx = int(module_choice) - 1
                        if 0 <= module_idx < len(modules):
                            module_code = modules[module_idx][0]
                        elif module_idx == len(modules):
                            module_code = safe_input("Enter module code: ")
                        else:
                            print("Invalid module selection.")
                            return
                    except ValueError:
                        print("Please enter a valid number.")
                        return
                        
        except Exception as e:
            print(f"Error retrieving modules: {e}")
            module_code = safe_input("Enter module code manually: ")
        
        # Get file path
        while True:
            file_path = safe_input("\nEnter the full path to the document file (or 'cancel' to abort): ")
            if not file_path or file_path.lower() == 'cancel':
                print("Document submission cancelled.")
                return
                
            if not os.path.exists(file_path):
                print("File not found. Please enter a valid path.")
                continue
                
            # Check file size
            try:
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
                if file_size > 50:  # Limit to 50MB
                    print(f"File is too large ({file_size:.1f}MB). Maximum size is 50MB.")
                    continue
            except Exception as e:
                print(f"Error checking file size: {e}")
                continue
                
            break
        
        # Extract text from the file
        print("\nExtracting text from file, please wait...")
        try:
            content, file_type = checker.extract_text_from_file(file_path)
        except FileProcessingError as e:
            print(f"Error extracting text from file: {e}")
            return
        except Exception as e:
            print(f"Unexpected error extracting text: {e}")
            return
            
        # Add document to repository
        print("Adding document to repository...")
        try:
            document_id = checker.add_document_to_repository(
                title, content, auth.current_user['id'], module_code, file_type
            )
            
            print(f"\nDocument '{title}' successfully added to the repository with ID: {document_id}")
            
            # Ask if user wants to check for plagiarism now
            if auth.check_permission('check_plagiarism'):
                check_now = safe_input("\nDo you want to check this document for plagiarism now? (y/n): ").lower()
                if check_now == 'y':
                    print("\nChecking for plagiarism, please wait...")
                    try:
                        result = checker.check_plagiarism(document_id, auth.current_user['id'])
                        display_check_result(result)
                    except Exception as e:
                        print(f"Error during plagiarism check: {e}")
        except PlagiarismCheckerError as e:
            print(f"Error adding document: {e}")
        except Exception as e:
            print(f"Unexpected error adding document: {e}")
            
    except Exception as e:
        print(f"Error during document submission: {e}")


def view_my_documents(checker, auth):
    """View documents submitted by the current user"""
    try:
        print("\nFetching your documents, please wait...")
        try:
            documents = checker.search_repository("", author_id=auth.current_user['id'])
        except PlagiarismCheckerError as e:
            print(f"Error retrieving documents: {e}")
            return
            
        if not documents:
            print("You haven't submitted any documents yet.")
            return
            
        print("\nYour Documents:")
        print("===============")
        
        for i, doc in enumerate(documents, 1):
            try:
                status_info = ""
                doc_details = checker.get_document_details(doc['id'])
                
                if doc_details['latest_check']:
                    check = doc_details['latest_check']
                    similarity = check['similarity_score'] * 100  # Convert to percentage
                    status_info = f"{check['status']} (Similarity: {similarity:.1f}%)"
                else:
                    status_info = "Not checked yet"
                    
                print(f"{i}. {doc['title']} ({doc['file_type']}) - {status_info}")
                print(f"   Submitted: {doc['submission_date']}, Words: {doc['word_count']}")
            except Exception as e:
                print(f"{i}. {doc['title']} - Error retrieving details: {e}")
            
        # Ask if user wants to view details for a specific document
        view_choice = safe_input(f"\nEnter document number to view details (1-{len(documents)}, or press Enter to return): ")
        if view_choice:
            try:
                view_num = int(view_choice)
                if 1 <= view_num <= len(documents):
                    doc_id = documents[view_num-1]['id']
                    display_document_details(checker, doc_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a valid number.")
                
    except Exception as e:
        print(f"Error retrieving your documents: {e}")


def check_document(checker, auth):
    """Check a document for plagiarism"""
    if not auth.check_permission('check_plagiarism'):
        print("You don't have permission to check documents for plagiarism.")
        return
        
    try:
        # Let user search for a document first
        search_term = safe_input("\nEnter document title to search (or leave blank to see all): ")
        if search_term is None:
            return
        
        # Get module filter if they have permission to check across all modules
        module_code = None
        if auth.check_permission('check_plagiarism_any_course'):
            use_filter = safe_input("Filter by module? (y/n): ").lower()
            if use_filter == 'y':
                module_code = get_module_selection(checker)
                if module_code is None:
                    return
        else:
            # Get instructor's assigned modules
            module_code = get_module_selection(checker)
            if module_code is None:
                return
        
        # Search for documents
        print("\nSearching for documents, please wait...")
        try:
            documents = checker.search_repository(search_term, module_code=module_code)
        except PlagiarismCheckerError as e:
            print(f"Error searching documents: {e}")
            return
            
        if not documents:
            print("No documents found matching your criteria.")
            return
            
        print("\nDocuments:")
        print("==========")
        
        for i, doc in enumerate(documents, 1):
            try:
                doc_details = checker.get_document_details(doc['id'])
                
                if doc_details['latest_check']:
                    check = doc_details['latest_check']
                    status_info = f"{check['status']} (Last checked: {check['check_date']})"
                else:
                    status_info = "Not checked yet"
                    
                print(f"{i}. {doc['title']} - {status_info}")
                print(f"   Author: {doc_details.get('author_name', 'Unknown')}, Module: {doc['module_code']}")
            except Exception as e:
                print(f"{i}. {doc['title']} - Error retrieving details: {e}")
            
        # Select document to check
        check_choice = safe_input(f"\nEnter document number to check for plagiarism (1-{len(documents)}): ")
        if not check_choice:
            return
        
        try:
            check_num = int(check_choice)
            if 1 <= check_num <= len(documents):
                doc_id = documents[check_num-1]['id']
                
                # Get similarity threshold
                threshold = 0.3  # Default
                custom_threshold = safe_input("\nEnter similarity threshold (0.1-0.9, default is 0.3): ")
                if custom_threshold:
                    try:
                        threshold = float(custom_threshold)
                        threshold = max(0.1, min(0.9, threshold))  # Clamp between 0.1 and 0.9
                    except ValueError:
                        print("Invalid threshold. Using default 0.3.")
                
                print(f"\nChecking document '{documents[check_num-1]['title']}' for plagiarism...")
                print("This may take a moment, please wait...")
                
                try:
                    result = checker.check_plagiarism(doc_id, auth.current_user['id'], threshold)
                    display_check_result(result)
                except PlagiarismCheckerError as e:
                    print(f"Error during plagiarism check: {e}")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")
            
    except Exception as e:
        print(f"Error during plagiarism check: {e}")


def get_module_selection(checker):
    """Helper function to get module selection"""
    try:
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT module_code, module_name FROM modules
            ORDER BY module_code
            ''')
            
            modules = cursor.fetchall()
            
            if not modules:
                print("No modules found in the system.")
                return safe_input("Enter module code manually (optional): ")
                
            print("\nSelect Module/Course:")
            for i, module in enumerate(modules, 1):
                print(f"{i}. {module[0]} - {module[1]}")
            print(f"{len(modules) + 1}. All modules")
                
            module_choice = safe_input(f"\nModule number (1-{len(modules) + 1}): ")
            if not module_choice:
                return None
            
            try:
                module_idx = int(module_choice) - 1
                if 0 <= module_idx < len(modules):
                    return modules[module_idx][0]
                elif module_idx == len(modules):
                    return None  # All modules
                else:
                    print("Invalid module selection.")
                    return None
            except ValueError:
                print("Please enter a valid number.")
                return None
                
    except Exception as e:
        print(f"Error selecting module: {e}")
        return None


def view_results(checker, auth):
    """View plagiarism check results"""
    if not auth.check_permission('check_plagiarism'):
        print("You don't have permission to view plagiarism check results.")
        return
        
    try:
        # Let user search for a document first
        search_term = safe_input("\nEnter document title to search (or leave blank to see all): ")
        if search_term is None:
            return
        
        # Get module filter if they have permission to check across all modules
        module_code = None
        if auth.check_permission('check_plagiarism_any_course'):
            use_filter = safe_input("Filter by module? (y/n): ").lower()
            if use_filter == 'y':
                module_code = get_module_selection(checker)
        
        # Search for documents
        print("\nSearching for documents, please wait...")
        try:
            documents = checker.search_repository(search_term, module_code=module_code)
        except PlagiarismCheckerError as e:
            print(f"Error searching documents: {e}")
            return
            
        if not documents:
            print("No documents found matching your criteria.")
            return
            
        print("\nDocuments with Check Results:")
        print("=============================")
        
        # Filter to only show documents that have been checked
        checked_docs = []
        for doc in documents:
            try:
                doc_details = checker.get_document_details(doc['id'])
                if doc_details['latest_check']:
                    checked_docs.append((doc, doc_details['latest_check']))
            except Exception as e:
                print(f"Error retrieving details for document {doc['title']}: {e}")
                
        if not checked_docs:
            print("No documents with plagiarism check results found.")
            return
            
        for i, (doc, check) in enumerate(checked_docs, 1):
            status_color = ""
            if check['status'] == "EXACT_MATCH" or check['status'] == "HIGH_SIMILARITY":
                status_color = "HIGH RISK"
            elif check['status'] == "MODERATE_SIMILARITY":
                status_color = "MEDIUM RISK"
            else:
                status_color = "LOW RISK"
                
            similarity = check['similarity_score'] * 100  # Convert to percentage
            print(f"{i}. {doc['title']} - [{status_color}] {check['status']}")
            print(f"   Similarity: {similarity:.1f}%, Checked: {check['check_date']}")
            
        # Select document to view details
        view_choice = safe_input(f"\nEnter document number to view detailed results (1-{len(checked_docs)}): ")
        if view_choice:
            try:
                view_num = int(view_choice)
                if 1 <= view_num <= len(checked_docs):
                    result_id = checked_docs[view_num-1][1]['result_id']
                    display_result_details(checker, result_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a valid number.")
            
    except Exception as e:
        print(f"Error viewing results: {e}")


def search_repository(checker, auth):
    """Search the document repository"""
    if not auth.check_permission('check_plagiarism'):
        print("You don't have permission to search the document repository.")
        return
        
    try:
        search_term = safe_input("\nEnter search term for document title: ")
        if search_term is None:
            return
        
        author_filter = None
        module_filter = None
        
        use_filters = safe_input("Apply additional filters? (y/n): ").lower()
        if use_filters == 'y':
            # Author filter
            author_name = safe_input("Filter by author name (leave blank for all): ")
            if author_name:
                author_filter = get_author_selection(checker, author_name)
            
            # Module filter
            if auth.check_permission('check_plagiarism_any_course'):
                module_name = safe_input("Filter by module (leave blank for all): ")
                if module_name:
                    module_filter = get_module_selection_by_name(checker, module_name)
        
        # Search for documents
        print("\nSearching repository, please wait...")
        try:
            documents = checker.search_repository(search_term, author_id=author_filter, module_code=module_filter)
        except PlagiarismCheckerError as e:
            print(f"Error searching repository: {e}")
            return
            
        if not documents:
            print("No documents found matching your criteria.")
            return
            
        print("\nSearch Results:")
        print("===============")
        
        for i, doc in enumerate(documents, 1):
            try:
                doc_details = checker.get_document_details(doc['id'])
                
                author_name = doc_details.get('author_name', 'Unknown')
                status_info = ""
                
                if doc_details['latest_check']:
                    check = doc_details['latest_check']
                    similarity = check['similarity_score'] * 100  # Convert to percentage
                    status_info = f"{check['status']} ({similarity:.1f}%)"
                else:
                    status_info = "Not checked"
                    
                print(f"{i}. {doc['title']} - {status_info}")
                print(f"   Author: {author_name}, Module: {doc['module_code']}")
                print(f"   Submitted: {doc['submission_date']}, Type: {doc['file_type']}")
            except Exception as e:
                print(f"{i}. {doc['title']} - Error retrieving details: {e}")
                
        # Select document to view details
        view_choice = safe_input(f"\nEnter document number to view details (1-{len(documents)}, or press Enter to return): ")
        if view_choice:
            try:
                view_num = int(view_choice)
                if 1 <= view_num <= len(documents):
                    doc_id = documents[view_num-1]['id']
                    display_document_details(checker, doc_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a valid number.")
                
    except Exception as e:
        print(f"Error searching repository: {e}")


def get_author_selection(checker, author_name):
    """Helper function to get author selection"""
    try:
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, first_name, last_name
            FROM users
            WHERE first_name LIKE ? OR last_name LIKE ?
            ORDER BY last_name, first_name
            ''', (f"%{author_name}%", f"%{author_name}%"))
            
            authors = cursor.fetchall()
            
            if not authors:
                print("No authors found matching that name.")
                return None
                
            print("\nSelect Author:")
            for i, author in enumerate(authors, 1):
                print(f"{i}. {author[1]} {author[2]}")
                
            author_choice = safe_input(f"\nAuthor number (1-{len(authors)}): ")
            if not author_choice:
                return None
            
            try:
                author_idx = int(author_choice) - 1
                if 0 <= author_idx < len(authors):
                    return authors[author_idx][0]
                else:
                    print("Invalid author selection.")
                    return None
            except ValueError:
                print("Invalid choice.")
                return None
                
    except Exception as e:
        print(f"Error filtering by author: {e}")
        return None


def get_module_selection_by_name(checker, module_name):
    """Helper function to get module selection by name"""
    try:
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT module_code, module_name
            FROM modules
            WHERE module_code LIKE ? OR module_name LIKE ?
            ORDER BY module_code
            ''', (f"%{module_name}%", f"%{module_name}%"))
            
            modules = cursor.fetchall()
            
            if not modules:
                print("No modules found matching that name.")
                return None
                
            print("\nSelect Module:")
            for i, module in enumerate(modules, 1):
                print(f"{i}. {module[0]} - {module[1]}")
                
            module_choice = safe_input(f"\nModule number (1-{len(modules)}): ")
            if not module_choice:
                return None
            
            try:
                module_idx = int(module_choice) - 1
                if 0 <= module_idx < len(modules):
                    return modules[module_idx][0]
                else:
                    print("Invalid module selection.")
                    return None
            except ValueError:
                print("Invalid choice.")
                return None
                
    except Exception as e:
        print(f"Error filtering by module: {e}")
        return None


def view_statistics(checker, auth):
    """View system statistics"""
    if not auth.check_permission('manage_plagiarism_system'):
        print("You don't have permission to view system statistics.")
        return
        
    try:
        print("\nGathering statistics, please wait...")
        try:
            stats = checker.get_statistics()
        except PlagiarismCheckerError as e:
            print(f"Error retrieving statistics: {e}")
            return
            
        print("\nPlagiarism Checker Statistics")
        print("=============================")
        print(f"Total Documents in Repository: {stats['total_documents']}")
        print(f"Total Plagiarism Checks Performed: {stats['total_checks']}")
        
        if stats.get('status_counts'):
            print("\nCheck Results by Status:")
            for status, count in stats['status_counts'].items():
                print(f"  {status}: {count}")
        
        if stats.get('documents_by_module'):
            print("\nDocuments by Module:")
            for module, count in stats['documents_by_module'].items():
                print(f"  {module}: {count}")
            
        if stats.get('recent_checks'):
            print("\nRecent Plagiarism Checks:")
            for i, check in enumerate(stats['recent_checks'][:10], 1):
                similarity = check['similarity_score'] * 100  # Convert to percentage
                print(f"{i}. {check['document_title']} - {check['status']} ({similarity:.1f}%)")
                print(f"   Checked: {check['check_date']}")
            
        safe_input("\nPress Enter to return to menu...")
            
    except Exception as e:
        print(f"Error retrieving statistics: {e}")


def manage_repository(checker, auth):
    """Manage the document repository"""
    if not auth.check_permission('manage_plagiarism_system'):
        print("You don't have permission to manage the document repository.")
        return
        
    while True:
        try:
            print("\nManage Document Repository")
            print("==========================")
            print("1. Delete Document")
            print("2. Check Repository Integrity")
            print("3. Back")
            
            choice = safe_input("\nEnter your choice (1-3): ")
            if not choice:
                return
            
            if choice == '1':
                delete_document_interactive(checker)
            elif choice == '2':
                check_repository_integrity(checker)
            elif choice == '3':
                return
            else:
                print("Invalid choice. Please try again.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return
        except Exception as e:
            print(f"Error in repository management: {e}")


def delete_document_interactive(checker):
    """Interactive document deletion"""
    try:
        search_term = safe_input("\nEnter document title to search: ")
        if not search_term:
            return
        
        print("\nSearching for documents, please wait...")
        try:
            documents = checker.search_repository(search_term)
        except PlagiarismCheckerError as e:
            print(f"Error searching documents: {e}")
            return
            
        if not documents:
            print("No documents found matching your criteria.")
            return
            
        print("\nDocuments:")
        for i, doc in enumerate(documents, 1):
            print(f"{i}. {doc['title']} (ID: {doc['id']})")
            
        delete_choice = safe_input(f"\nEnter document number to delete (1-{len(documents)}, or 0 to cancel): ")
        if not delete_choice:
            return
        
        try:
            delete_num = int(delete_choice)
            if delete_num == 0:
                print("Deletion cancelled.")
                return
                
            if 1 <= delete_num <= len(documents):
                doc_id = documents[delete_num-1]['id']
                doc_title = documents[delete_num-1]['title']
                
                confirm = safe_input(f"Are you sure you want to delete '{doc_title}'? (y/n): ").lower()
                if confirm == 'y':
                    second_confirm = safe_input("This action cannot be undone. Type 'DELETE' to confirm: ")
                    if second_confirm == 'DELETE':
                        print("\nDeleting document, please wait...")
                        try:
                            if checker.delete_document(doc_id):
                                print(f"Document '{doc_title}' has been deleted.")
                            else:
                                print("Error deleting document.")
                        except PlagiarismCheckerError as e:
                            print(f"Error deleting document: {e}")
                    else:
                        print("Deletion cancelled.")
                else:
                    print("Deletion cancelled.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")
    except Exception as e:
        print(f"Error during document deletion: {e}")


def check_repository_integrity(checker):
    """Check repository integrity"""
    try:
        print("\nChecking repository integrity...")
        
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check for orphaned records in plagiarism_results
            cursor.execute('''
            SELECT COUNT(*) FROM plagiarism_results pr
            LEFT JOIN document_repository dr ON pr.document_id = dr.id
            WHERE dr.id IS NULL
            ''')
            
            orphaned_results = cursor.fetchone()[0]
            
            # Check for documents without content
            cursor.execute('''
            SELECT COUNT(*) FROM document_repository
            WHERE content IS NULL OR content = ''
            ''')
            
            empty_docs = cursor.fetchone()[0]
            
            # Check for documents with invalid authors
            cursor.execute('''
            SELECT COUNT(*) FROM document_repository dr
            LEFT JOIN users u ON dr.author_id = u.id
            WHERE u.id IS NULL
            ''')
            
            invalid_authors = cursor.fetchone()[0]
            
            print("\nRepository Integrity Check Results:")
            print(f"  Orphaned plagiarism results: {orphaned_results}")
            print(f"  Documents without content: {empty_docs}")
            print(f"  Documents with invalid authors: {invalid_authors}")
            
            total_issues = orphaned_results + empty_docs + invalid_authors
            
            if total_issues > 0:
                fix = safe_input(f"\nFound {total_issues} issues. Would you like to fix them? (y/n): ").lower()
                if fix == 'y':
                    try:
                        if orphaned_results > 0:
                            cursor.execute('''
                            DELETE FROM plagiarism_results
                            WHERE document_id NOT IN (SELECT id FROM document_repository)
                            ''')
                            print(f"Deleted {cursor.rowcount} orphaned plagiarism results.")
                            
                        if empty_docs > 0:
                            cursor.execute('''
                            DELETE FROM document_repository
                            WHERE content IS NULL OR content = ''
                            ''')
                            print(f"Deleted {cursor.rowcount} empty documents.")
                        
                        if invalid_authors > 0:
                            cursor.execute('''
                            DELETE FROM document_repository
                            WHERE author_id NOT IN (SELECT id FROM users)
                            ''')
                            print(f"Deleted {cursor.rowcount} documents with invalid authors.")
                            
                        conn.commit()
                        print("\nIntegrity issues fixed successfully.")
                    except Exception as e:
                        print(f"Error fixing integrity issues: {e}")
                        conn.rollback()
            else:
                print("\nNo integrity issues found. Repository is healthy!")
            
    except Exception as e:
        print(f"Error during integrity check: {e}")


def display_document_details(checker, doc_id):
    """Display detailed information about a document"""
    try:
        print("\nRetrieving document details, please wait...")
        try:
            doc_details = checker.get_document_details(doc_id)
        except PlagiarismCheckerError as e:
            print(f"Error retrieving document details: {e}")
            return
            
        print("\nDocument Details")
        print("================")
        print(f"ID: {doc_details['id']}")
        print(f"Title: {doc_details['title']}")
        print(f"Author: {doc_details['author_name']}")
        print(f"Module: {doc_details['module_code'] or 'N/A'}")
        print(f"Submission Date: {doc_details['submission_date']}")
        print(f"File Type: {doc_details['file_type']}")
        print(f"Word Count: {doc_details['word_count']}")
        
        if doc_details['latest_check']:
            similarity = doc_details['latest_check']['similarity_score'] * 100  # Convert to percentage
            print("\nLatest Plagiarism Check:")
            print(f"  Status: {doc_details['latest_check']['status']}")
            print(f"  Similarity Score: {similarity:.1f}%")
            print(f"  Check Date: {doc_details['latest_check']['check_date']}")
            print(f"  Threshold Used: {doc_details['latest_check']['threshold_used']:.1%}")
            
            # Option to view full check details
            view_check = safe_input("\nView complete check results? (y/n): ").lower()
            if view_check == 'y':
                display_result_details(checker, doc_details['latest_check']['result_id'])
        else:
            print("\nThis document has not been checked for plagiarism.")
        
        # Show check history
        try:
            check_history = checker.get_document_check_history(doc_id)
            if len(check_history) > 1:
                print("\nPlagiarism Check History:")
                for i, check in enumerate(check_history, 1):
                    similarity = check['similarity_score'] * 100  # Convert to percentage
                    print(f"{i}. {check['check_date']} - {check['status']} ({similarity:.1f}%)")
                    
                # Option to view a specific check result
                view_hist = safe_input(f"\nEnter number to view detailed results (1-{len(check_history)}, or press Enter to return): ")
                if view_hist:
                    try:
                        hist_num = int(view_hist)
                        if 1 <= hist_num <= len(check_history):
                            display_result_details(checker, check_history[hist_num-1]['result_id'])
                        else:
                            print("Invalid selection.")
                    except ValueError:
                        print("Please enter a valid number.")
        except Exception as e:
            print(f"Error retrieving check history: {e}")
                
    except Exception as e:
        print(f"Error displaying document details: {e}")


def display_result_details(checker, result_id):
    """Display detailed information about a plagiarism check result"""
    try:
        print("\nRetrieving plagiarism check results, please wait...")
        try:
            result = checker.get_plagiarism_result(result_id)
        except PlagiarismCheckerError as e:
            print(f"Error retrieving result details: {e}")
            return
            
        similarity = result['similarity_score'] * 100  # Convert to percentage
        print("\nPlagiarism Check Result")
        print("======================")
        print(f"Document: {result['document_title']}")
        print(f"Author: {result['author_name'] or 'Unknown'}")
        print(f"Check Date: {result['check_date']}")
        print(f"Checked By: {result['checker_name'] or 'Unknown'}")
        print(f"Status: {result['status']}")
        print(f"Similarity Score: {similarity:.1f}%")
        print(f"Threshold Used: {result['threshold_used']:.1%}")
        
        if result['matched_document_id']:
            print(f"\nMatched with: {result['matched_document_title']} (ID: {result['matched_document_id']})")
            
            # Option to view matched document
            view_match = safe_input("\nView matched document details? (y/n): ").lower()
            if view_match == 'y':
                display_document_details(checker, result['matched_document_id'])
        
        print("\nDetailed Report:")
        print(result['report'])
        
        safe_input("\nPress Enter to continue...")
        
    except Exception as e:
        print(f"Error displaying result details: {e}")


def display_check_result(result):
    """Display the results of a plagiarism check"""
    try:
        print("\nPlagiarism Check Complete")
        print("========================")
        
        if result['match_type'] == 'exact':
            print("⚠️ ALERT: EXACT MATCH FOUND! ⚠️")
            print(f"This document exactly matches {len(result['matches'])} document(s) in the repository.")
            
            print("\nMatched Documents:")
            for i, match in enumerate(result['matches'], 1):
                match_id, match_title, similarity = match
                print(f"{i}. {match_title} (ID: {match_id}) - 100% match")
                
        else:
            if result['status'] == "NO_MATCH":
                print("✓ No significant similarities found.")
                print("This document appears to be original.")
            else:
                print(f"Status: {result['status']}")
                similarity = result['highest_similarity'] * 100  # Convert to percentage
                print(f"Highest Similarity: {similarity:.1f}%")
                print(f"Threshold Used: {result['threshold_used']:.1%}")
                
                if result['matches']:
                    print("\nSimilar Documents:")
                    for i, match in enumerate(result['matches'][:5], 1):  # Show top 5
                        match_id, match_title, match_similarity = match
                        similarity = match_similarity * 100  # Convert to percentage
                        print(f"{i}. {match_title} (ID: {match_id}) - {similarity:.1f}% similarity")
                    
                    if len(result['matches']) > 5:
                        print(f"... and {len(result['matches']) - 5} more matches")
        
        print(f"\nCheck ID: {result['result_id']}")
        print("To view complete results, use the 'View Plagiarism Check Results' option.")
        
        safe_input("\nPress Enter to continue...")
        
    except Exception as e:
        print(f"Error displaying check result: {e}")


# =============================================================================
# Setup and Testing Functions
# =============================================================================

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


def create_sample_documents(checker):
    """Create sample documents for testing the plagiarism system"""
    try:
        # Only create if directory is empty
        text_files_dir = 'text_files'
        if os.path.exists(text_files_dir) and not os.listdir(text_files_dir):
            print("\nCreating sample documents for testing...")
            
            # Get system users and modules
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Get users
                    cursor.execute('''
                    SELECT id, username FROM users
                    WHERE id IN (SELECT user_id FROM user_roles WHERE role_id IN 
                        (SELECT id FROM roles WHERE role_name IN ('student', 'instructor', 'staff')))
                    LIMIT 3
                    ''')
                    
                    users = cursor.fetchall()
                    
                    # Get modules
                    cursor.execute('SELECT module_code FROM modules LIMIT 2')
                    modules = [row[0] for row in cursor.fetchall()]
                    
                    if not users:
                        print("Warning: No suitable users found for creating sample documents.")
                        return
                    
                    if not modules:
                        modules = ['TEST_MODULE']  # Fallback module
                        
            except sqlite3.Error as e:
                print(f"Database error getting users/modules: {e}")
                return
            
            # Create sample documents with realistic content
            sample_docs = [
                {
                    'title': 'AI in Education: Opportunities and Challenges',
                    'content': create_ai_education_content(),
                    'filename': 'original_paper.txt'
                },
                {
                    'title': 'Artificial Intelligence Applications in Modern Education',
                    'content': create_similar_ai_content(),
                    'filename': 'similar_paper.txt'
                },
                {
                    'title': 'Environmental Impact of Urban Renewable Energy Transitions',
                    'content': create_different_content(),
                    'filename': 'different_paper.txt'
                }
            ]
            
            # Write files and add to repository
            for i, doc in enumerate(sample_docs):
                try:
                    # Write to file
                    file_path = os.path.join(text_files_dir, doc['filename'])
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(doc['content'])
                    
                    # Add to repository
                    user_id = users[min(i, len(users)-1)][0]
                    module_code = modules[min(i, len(modules)-1)]
                    
                    checker.add_document_to_repository(
                        doc['title'],
                        doc['content'],
                        user_id,
                        module_code,
                        'txt'
                    )
                    
                    logger.info(f"Created sample document: {doc['title']}")
                    
                except Exception as e:
                    logger.error(f"Error creating sample document {doc['title']}: {e}")
            
            print("Sample documents created and added to repository.")
            print("Test files are available in the 'text_files' directory.")
            
    except Exception as e:
        logger.error(f"Error creating sample documents: {e}")


def create_ai_education_content():
    """Create original AI education content"""
    return """
    Abstract
    This paper explores the growing importance of artificial intelligence in modern education.
    The integration of AI technologies in educational settings presents both opportunities and challenges.
    We analyze current trends and propose frameworks for ethical implementation.
    
    Introduction
    Artificial intelligence has transformed many sectors of society, and education is increasingly
    affected by these technological advances. From personalized learning to administrative efficiency,
    AI offers numerous benefits to educational institutions. However, concerns regarding privacy,
    algorithmic bias, and the changing role of educators require careful consideration.
    
    Literature Review
    Previous research has identified several key areas where AI impacts education.
    Smith (2020) explored how machine learning algorithms can predict student performance.
    Jones and Williams (2021) examined the ethical implications of automated assessment systems.
    Chen et al. (2022) investigated the role of natural language processing in providing
    feedback on student writing.
    
    Methodology
    Our study employed a mixed-methods approach, combining quantitative analysis of
    implementation outcomes across 42 educational institutions with qualitative
    interviews of 15 administrators, 30 teachers, and 50 students.
    
    Results
    The findings indicate that institutions implementing AI-assisted learning tools
    saw a 23% improvement in student engagement metrics and a 17% increase in
    completion rates for online courses. However, 68% of educators expressed
    concerns about reduced human interaction in the learning process.
    
    Discussion
    While the quantitative benefits of AI in education are clear, the qualitative
    concerns raised by stakeholders suggest that a balanced approach is necessary.
    The technology should augment rather than replace human teaching elements.
    
    Conclusion
    As AI continues to evolve, educational institutions must develop thoughtful
    integration strategies that maximize benefits while mitigating potential drawbacks.
    Future research should focus on longitudinal studies examining the long-term
    impacts of AI-assisted education on student outcomes and wellbeing.
    """


def create_similar_ai_content():
    """Create similar AI education content (for plagiarism testing)"""
    return """
    Abstract
    This paper examines the increasing significance of artificial intelligence in modern education.
    The adoption of AI technologies in educational contexts offers both opportunities and challenges.
    We examine current patterns and suggest frameworks for ethical implementation.
    
    Introduction
    Artificial intelligence has revolutionized many sectors of society, and education is increasingly
    influenced by these technological advances. From personalized learning to administrative efficiency,
    AI provides numerous advantages to educational institutions. However, issues regarding privacy,
    algorithmic bias, and the changing role of teachers require careful consideration.
    
    Literature Review
    Prior studies have identified several key areas where AI impacts education.
    Smith (2020) explored how machine learning algorithms can predict student performance.
    Jones and Williams (2021) examined the ethical implications of automated assessment systems.
    Chen et al. (2022) investigated the role of natural language processing in providing
    feedback on student writing.
    
    Methodology
    Our investigation used a mixed-methods approach, combining quantitative analysis of
    implementation outcomes across 42 schools with qualitative
    interviews of 15 administrators, 30 teachers, and 50 students.
    
    Results
    The data indicates that institutions implementing AI-assisted learning tools
    saw a 23% improvement in student engagement metrics and a 17% increase in
    completion rates for online courses. However, 68% of educators expressed
    concerns about reduced human interaction in the learning process.
    
    Discussion
    While the quantitative benefits of AI in education are evident, the qualitative
    concerns raised by participants suggest that a balanced approach is necessary.
    The technology should augment rather than replace human teaching elements.
    
    Conclusion
    As AI continues to develop, educational institutions must create thoughtful
    integration strategies that maximize benefits while minimizing potential drawbacks.
    Future research should focus on longitudinal studies examining the long-term
    effects of AI-assisted education on student outcomes and wellbeing.
    """


def create_different_content():
    """Create different content (for negative testing)"""
    return """
    Abstract
    This study investigates the environmental impact of renewable energy transitions in urban settings.
    With increasing concerns about climate change, cities worldwide are implementing sustainable
    energy solutions. We evaluate the effectiveness of these initiatives across different regions.
    
    Introduction
    Climate change presents an urgent challenge that requires significant transformations
    in how we produce and consume energy. Urban areas, responsible for over 70% of global
    carbon emissions, are critical sites for implementing renewable energy solutions.
    This paper examines various approaches cities have taken to reduce their carbon footprint.
    
    Literature Review
    Research on urban energy transitions has grown substantially in recent years.
    Wang (2021) analyzed solar panel adoption rates in metropolitan areas.
    Rodriguez and Lee (2022) compared the effectiveness of municipal incentive programs.
    The Urban Climate Initiative (2023) published comprehensive guidelines for city planners.
    
    Methodology
    We conducted case studies of five major cities across three continents,
    collecting data on energy consumption patterns, renewable infrastructure development,
    and policy frameworks. Interviews with 25 city officials and 10 energy experts
    provided additional insights into implementation challenges.
    
    Results
    Cities that integrated renewable energy planning with broader urban development
    goals achieved 34% greater emissions reductions than those implementing isolated
    initiatives. Public-private partnerships increased project completion rates by 28%.
    Community engagement programs correlated with 45% higher resident satisfaction.
    
    Discussion
    While technological solutions are important, our findings highlight the critical
    role of policy coherence and stakeholder engagement. Small-scale, community-based
    projects often serve as effective catalysts for larger transitions.
    
    Conclusion
    Successful urban energy transitions require integrated approaches that address
    technical, economic, and social dimensions simultaneously. Future research should
    explore how digital technologies might further optimize renewable energy systems
    in increasingly complex urban environments.
    """


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


# =============================================================================
# Testing Functions
# =============================================================================



def test_document_repository(checker, auth):
    """Test basic document repository operations"""
    try:
        # Test searching repository
        results = checker.search_repository()
        if not isinstance(results, list):
            print("Error: Could not search repository")
            return False
            
        print(f"Found {len(results)} documents in repository")
        
        # Check if we can get document details for existing documents
        if results:
            doc_id = results[0]['id']
            try:
                details = checker.get_document_details(doc_id)
                
                if not isinstance(details, dict) or not details.get('title'):
                    print(f"Error getting document details: invalid response")
                    return False
                    
                print(f"Successfully retrieved details for document: {details['title']}")
            except Exception as e:
                print(f"Error getting document details: {e}")
                return False
        
        # Test invalid document ID
        try:
            checker.get_document_details(99999)
            print("Error: Should have failed for invalid document ID")
            return False
        except ValueError:
            print("Correctly handled invalid document ID")
        except Exception as e:
            print(f"Unexpected error for invalid document ID: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"Error in document repository test: {e}")
        return False


def test_document_submission(checker, auth):
    """Test document submission functionality"""
    try:
        # Get a module code
        try:
            with get_safe_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT module_code FROM modules LIMIT 1')
                module_result = cursor.fetchone()
                
                module_code = module_result[0] if module_result else 'TEST_MODULE'
                        
        except Exception as e:
            print(f"Error getting module: {e}")
            module_code = 'TEST_MODULE'
        
        # Test valid document submission
        test_content = f"""
        This is a test document created by the automated testing system.
        It contains some unique content to avoid false positives.
        The current timestamp is: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        This document is being submitted under the user: {auth.current_user['username']}
        
        The purpose of this document is to test the submission functionality
        of the plagiarism detection system. If this test passes, it means that
        the system can properly accept new documents and add them to the repository.
        Random identifier: TEST_{datetime.now().strftime('%Y%m%d%H%M%S%f')}
        """
        
        title = f"Test Document - {datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            doc_id = checker.add_document_to_repository(
                title,
                test_content,
                auth.current_user['id'],
                module_code,
                'txt'
            )
            
            if not doc_id:
                print("Error: Failed to add document to repository")
                return False
                
            print(f"Successfully added document to repository with ID: {doc_id}")
        except Exception as e:
            print(f"Error adding document: {e}")
            return False
        
        # Verify document exists in repository
        try:
            details = checker.get_document_details(doc_id)
            
            if details['title'] != title:
                print(f"Error: Document title mismatch: {details['title']} != {title}")
                return False
                
            print("Document submission verification passed")
        except Exception as e:
            print(f"Error verifying document: {e}")
            return False
        
        # Test invalid submissions
        invalid_tests = [
            ("", test_content, auth.current_user['id'], module_code, 'txt'),  # Empty title
            (title, "", auth.current_user['id'], module_code, 'txt'),  # Empty content
            (title, test_content, -1, module_code, 'txt'),  # Invalid user ID
        ]
        
        for i, (t, c, u, m, f) in enumerate(invalid_tests):
            try:
                checker.add_document_to_repository(t, c, u, m, f)
                print(f"Error: Invalid submission test {i+1} should have failed")
                return False
            except (ValueError, PlagiarismCheckerError):
                print(f"Correctly rejected invalid submission {i+1}")
            except Exception as e:
                print(f"Unexpected error in invalid submission test {i+1}: {e}")
                return False
        
        return True
    except Exception as e:
        print(f"Error in document submission test: {e}")
        return False


def test_plagiarism_check(checker, auth):
    """Test plagiarism checking functionality"""
    try:
        # Get a module code
        try:
            with get_safe_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT module_code FROM modules LIMIT 1')
                module_result = cursor.fetchone()
                module_code = module_result[0] if module_result else 'TEST_MODULE'
        except Exception:
            module_code = 'TEST_MODULE'
        
        # Create two similar documents
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        
        original_content = f"""
        Artificial intelligence (AI) is revolutionizing education by providing personalized
        learning experiences for students. Machine learning algorithms can analyze student
        performance data to identify areas where additional support is needed. Natural language
        processing allows for automated assessment of written assignments, providing timely
        feedback to students. Virtual tutors can provide 24/7 assistance, helping students
        when human teachers are not available.
        Test identifier: ORIGINAL_{timestamp}
        """
        
        similar_content = f"""
        AI is transforming education through personalized learning experiences. Machine learning
        algorithms analyze student performance to find areas needing more support. NLP enables
        automated assessment of writing assignments, giving prompt feedback. Virtual tutoring
        systems provide round-the-clock help when human teachers aren't available.
        Test identifier: SIMILAR_{timestamp}
        """
        
        # Submit original document
        try:
            original_title = f"Original Test - {timestamp}"
            original_id = checker.add_document_to_repository(
                original_title,
                original_content,
                auth.current_user['id'],
                module_code,
                'txt'
            )
            
            if not original_id:
                print("Error: Failed to add original document")
                return False
                
            print(f"Added original document with ID: {original_id}")
        except Exception as e:
            print(f"Error adding original document: {e}")
            return False
        
        # Submit similar document
        try:
            similar_title = f"Similar Test - {timestamp}"
            similar_id = checker.add_document_to_repository(
                similar_title,
                similar_content,
                auth.current_user['id'],
                module_code,
                'txt'
            )
            
            if not similar_id:
                print("Error: Failed to add similar document")
                return False
                
            print(f"Added similar document with ID: {similar_id}")
        except Exception as e:
            print(f"Error adding similar document: {e}")
            return False
        
        # Check similar document for plagiarism
        try:
            result = checker.check_plagiarism(similar_id, auth.current_user['id'], threshold=0.1)
            
            if not isinstance(result, dict):
                print("Error: Invalid plagiarism check result format")
                return False
            
            if 'matches' not in result:
                print("Error: No matches field in result")
                return False
            
            # The similar document should have some similarity
            similarity = result.get('highest_similarity', 0) * 100
            print(f"Similarity between documents: {similarity:.1f}%")
            
            if similarity < 5:  # Very low threshold for basic functionality
                print("Warning: Similarity score is lower than expected")
            
            print("Plagiarism check completed successfully")
        except Exception as e:
            print(f"Error in plagiarism check: {e}")
            return False
        
        # Test invalid plagiarism check
        try:
            checker.check_plagiarism(-1, auth.current_user['id'])
            print("Error: Should have failed for invalid document ID")
            return False
        except ValueError:
            print("Correctly handled invalid document ID in plagiarism check")
        except Exception as e:
            print(f"Unexpected error for invalid plagiarism check: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"Error in plagiarism check test: {e}")
        return False


def test_error_handling(checker, auth):
    """Test error handling"""
    try:
        print("Testing error handling...")
        
        # Test invalid inputs
        error_tests = [
            lambda: checker.get_document_details("invalid"),  # Non-integer ID
            lambda: checker.get_document_details(0),  # Zero ID
            lambda: checker.get_plagiarism_result("invalid"),  # Non-integer result ID
            lambda: checker.check_plagiarism("invalid"),  # Non-integer document ID
            lambda: checker.add_document_to_repository(None, "content", 1, "MOD", "txt"),  # None title
        ]
        
        for i, test_func in enumerate(error_tests):
            try:
                test_func()
                print(f"Error: Error test {i+1} should have raised an exception")
                return False
            except (ValueError, TypeError, PlagiarismCheckerError):
                print(f"Error test {i+1}: Correctly handled invalid input")
            except Exception as e:
                print(f"Error test {i+1}: Unexpected exception type: {e}")
                return False
        
        # Test database connection resilience
        try:
            # This should work with proper error handling
            stats = checker.get_statistics()
            if not isinstance(stats, dict):
                print("Error: Statistics should return a dictionary")
                return False
            print("Statistics retrieval: Passed")
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"Error in error handling test: {e}")
        return False


def test_edge_cases(checker, auth):
    """Test edge cases"""
    try:
        print("Testing edge cases...")
        
        # Test empty search
        try:
            results = checker.search_repository("")
            print(f"Empty search returned {len(results)} results")
        except Exception as e:
            print(f"Error in empty search: {e}")
            return False
        
        # Test search with no results
        try:
            results = checker.search_repository("NONEXISTENT_DOCUMENT_TITLE_12345")
            if len(results) != 0:
                print(f"Warning: Search for non-existent title returned {len(results)} results")
            else:
                print("Search for non-existent document correctly returned 0 results")
        except Exception as e:
            print(f"Error in no-results search: {e}")
            return False
        
        # Test very short content
        try:
            short_content = "AI."
            title = f"Short Test - {datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            doc_id = checker.add_document_to_repository(
                title, short_content, auth.current_user['id'], 'TEST_MODULE', 'txt'
            )
            
            if doc_id:
                print("Successfully handled very short content")
                
                # Try to check it for plagiarism
                result = checker.check_plagiarism(doc_id, auth.current_user['id'])
                print("Successfully checked short document for plagiarism")
            else:
                print("Failed to add short document")
                return False
                
        except Exception as e:
            print(f"Error with short content: {e}")
            return False
        
        # Test text preprocessing edge cases
        try:
            edge_texts = [
                "",  # Empty
                "   ",  # Whitespace only
                "123 456 789",  # Numbers only
                "!@#$%^&*()",  # Symbols only
                "a b c",  # Very short words
            ]
            
            for text in edge_texts:
                tokens = checker.preprocess_text(text)
                print(f"Preprocessed '{text}' -> {len(tokens)} tokens")
                
        except Exception as e:
            print(f"Error in text preprocessing: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"Error in edge cases test: {e}")
        return False


def test_plagiarism_checker():
    """Test the plagiarism checker functionality"""
    print("Plagiarism Checker Test Script")
    print("=============================")
    
    # Check if database exists
    if not os.path.exists(str(DEFAULT_DB_PATH)):
        print("Error: Database file str(DEFAULT_DB_PATH) not found.")
        print("Please initialize the main system first.")
        return False
    
    # Check database connection
    try:
        with get_safe_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if user tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                print("Error: User authentication tables not found in database.")
                return False
            
            # Check for any login credentials
            cursor.execute('SELECT username FROM users LIMIT 1')
            if not cursor.fetchone():
                print("Error: No user accounts found. Please initialize the system first.")
                return False
                
    except Exception as e:
        print(f"Database error: {e}")
        return False
    
    print("Database checks passed.")
    
    # Create a UserAuth object for testing
    try:
        # Try to get centralized auth first
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
        # Get first user for testing
        with get_safe_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM users LIMIT 1')
            user_data = cursor.fetchone()
            if user_data:
                # Note: In real usage, would use proper login with password
                # For testing, we create a basic session
                auth.current_user = {'username': user_data[0]}
                print(f"Test authentication context created with user: {user_data[0]}")
            else:
                print("No users found for testing.")
                return False
    except Exception as e:
        print(f"Error creating test auth: {e}")
        return False
    
    # Initialize the plagiarism checker
    try:
        checker = PlagiarismChecker()
        print("Plagiarism checker initialized successfully.")
    except Exception as e:
        print(f"Error initializing plagiarism checker: {e}")
        return False
    
    # Run basic tests
    test_cases = [
        test_document_repository,
        test_document_submission,
        test_plagiarism_check,
        test_error_handling,
        test_edge_cases
    ]
    
    test_results = []
    for test_case in test_cases:
        try:
            name = test_case.__name__.replace('_', ' ').title()
            print(f"\nRunning test: {name}")
            result = test_case(checker, auth)
            test_results.append((name, result))
            if result:
                print(f"{name}: PASSED")
            else:
                print(f"{name}: FAILED")
        except Exception as e:
            print(f"Error in test {test_case.__name__}: {e}")
            test_results.append((test_case.__name__.replace('_', ' ').title(), False))
    
    # Summarize results
    print("\nTest Results Summary:")
    print("====================")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for name, result in test_results:
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")
    
    print(f"\nPassed {passed} out of {total} tests ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\nAll tests passed! The plagiarism checker is working correctly.")
        return True
    else:
        print("\nSome tests failed. Please check the error messages above.")
        return False

def main():
    """Main function to demonstrate the plagiarism system"""
    print("Unified Plagiarism Detection System")
    print("==================================")
    print("1. Setup System")
    print("2. Test System")
    print("3. Run Interactive Demo")
    print("4. Exit")
    
    while True:
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            try:
                if setup_plagiarism_system():
                    print("\nSetup completed successfully!")
                else:
                    print("\nSetup failed. Please check the errors above.")
            except KeyboardInterrupt:
                print("\nSetup cancelled by user.")
            except Exception as e:
                print(f"\nSetup failed with error: {e}")
                
        elif choice == '2':
            try:
                if test_plagiarism_checker():
                    print("\n✓ All tests completed successfully!")
                else:
                    print("\n✗ Some tests failed.")
            except KeyboardInterrupt:
                print("\nTesting cancelled by user.")
            except Exception as e:
                print(f"\nTesting failed with error: {e}")
                
        elif choice == '3':
            try:
                # Create UserAuth for demo
                auth = get_auth()
                if auth is None:
                    auth = UserAuth()
                with get_safe_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT username FROM users LIMIT 1')
                    user_data = cursor.fetchone()
                    if user_data:
                        auth.current_user = {'username': user_data[0]}
                        display_plagiarism_checker_menu(auth)
                    else:
                        print("Cannot run demo: No user accounts found in database.")
                        print("Please set up the main system first.")
            except KeyboardInterrupt:
                print("\nDemo cancelled by user.")
            except Exception as e:
                print(f"\nDemo failed with error: {e}")
                
        elif choice == '4':
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    except Exception as e:
        print(f"\nProgram failed with error: {e}")
    finally:
        input("\nPress Enter to exit...")
