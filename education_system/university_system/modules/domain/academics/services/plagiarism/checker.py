from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import ensure_parent_dir
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.logging.log_config import configure_logging

import os
import re
import hashlib
from datetime import datetime
from difflib import SequenceMatcher

from education_system.university_system.modules.domain.academics.services.plagiarism.exceptions import PlagiarismCheckerError, DatabaseError, FileProcessingError
from education_system.university_system.modules.domain.academics.services.plagiarism.nlp import (
    NLTK_AVAILABLE, TEXTRACT_AVAILABLE,
    word_tokenize, stopwords, ngrams, textract,
)
from education_system.university_system.modules.domain.academics.services.plagiarism.db import get_safe_db_connection

logger = configure_logging(name=__name__)


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

                # Per-course toggle: skip the check if the course owning
                # this module has plagiarism detection disabled. Use the
                # course-level threshold when no explicit one is passed.
                try:
                    from education_system.university_system.modules.domain.academics.services.course_management.integrity_settings import (
                        get_course_integrity_settings,
                    )
                    settings = get_course_integrity_settings(doc_module or "")
                    if not settings["plagiarism_enabled"]:
                        return {
                            "document_id": doc_id,
                            "skipped": True,
                            "reason": (
                                f"Plagiarism check disabled for "
                                f"course {doc_module}"
                            ),
                            "check_date": datetime.now().strftime(
                                '%Y-%m-%d %H:%M:%S'),
                        }
                    # Caller's explicit threshold wins; otherwise use the
                    # course's configured threshold.
                    if threshold == 0.3 and settings["similarity_threshold"] != 0.3:
                        threshold = settings["similarity_threshold"]
                except Exception as _exc:
                    logger.debug(
                        "Integrity-settings lookup failed for "
                        "module %s: %s — proceeding with default policy",
                        doc_module, _exc,
                    )

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
                    search_pattern = f"%{escape_like(search_term.strip())}%"
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
