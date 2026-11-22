from collections import namedtuple

from education_system.systems.university.infrastructure.utils.document_manager._common import os, sqlite3, get_connection, _t


# Honest, structured result for a single OCR attempt.
#   success:    True only when the engine ran and produced text.
#   text:       extracted text (empty string on failure).
#   error:      human-readable reason when success is False, else None.
#   confidence: mean word confidence (0-100) reported by tesseract for an
#               image; None when the engine gives none (PDF text layer,
#               plain text, failure) — never invented.
#   pages:      pages read (PDF page count, 1 for an image), else None.
OCRResult = namedtuple("OCRResult", ["success", "text", "error", "confidence", "pages"],
                       defaults=(None, None))


def _tesseract_confidence(pytesseract, img):
    """Mean of tesseract's per-word confidences, or None if it gives none."""
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001 - confidence is optional; the text is the result
        return None
    scores = []
    for raw, word in zip(data.get("conf", []), data.get("text", [])):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value >= 0 and str(word or "").strip():
            scores.append(value)
    return round(sum(scores) / len(scores), 1) if scores else None


def run_ocr(file_path):
    """Run real OCR on a single image file.

    Returns an OCRResult. This NEVER fakes success: if pytesseract or the
    underlying tesseract binary is not available, it returns success=False
    with a clear message rather than a silent empty result.
    """
    if not file_path or not os.path.exists(file_path):
        return OCRResult(False, "", f"File not found: {file_path}")

    suffix = os.path.splitext(file_path)[1].lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        try:
            with open(file_path, "r", encoding="utf-8") as source:
                return OCRResult(True, source.read(), None)
        except (OSError, UnicodeError) as exc:
            return OCRResult(False, "", f"Text extraction failed: {exc}")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            pages = PdfReader(file_path).pages
            text = "\n\n".join(page.extract_text() or "" for page in pages)
            return OCRResult(True, text, None, None, len(pages))
        except ImportError as exc:
            return OCRResult(False, "", f"PDF text extraction is unavailable: {exc}")
        except Exception as exc:
            return OCRResult(False, "", f"PDF text extraction failed: {exc}")

    # pytesseract and PIL are imported lazily so this module still imports
    # cleanly in environments where the OCR engine is absent.
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        return OCRResult(
            False, "", f"OCR engine (tesseract) is not installed: {exc}"
        )

    try:
        with Image.open(file_path) as img:
            text = pytesseract.image_to_string(img)
            confidence = _tesseract_confidence(pytesseract, img)
    except pytesseract.TesseractNotFoundError:
        return OCRResult(
            False, "", "OCR engine (tesseract) is not installed"
        )
    except Exception as exc:  # noqa: BLE001 - report any real processing failure honestly
        return OCRResult(False, "", f"OCR processing failed: {exc}")

    return OCRResult(True, text, None, confidence, 1)


# ── OCR job log ─────────────────────────────────────────────────────────
#
# Every OCR attempt the Document Manager makes (single document, picked
# file, batch) is recorded here, success or failure, so the OCR Results
# History window shows what really ran. ``ocr_results`` keeps the text a
# user chose to save against a document; this table is the run history.

_OCR_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_ocr_jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(document_id) ON DELETE SET NULL,
    file_name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'file',
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    error TEXT,
    characters INTEGER NOT NULL DEFAULT 0,
    pages INTEGER,
    confidence REAL,
    language TEXT,
    duration_ms INTEGER,
    processed_by TEXT,
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def ensure_ocr_results(conn):
    """Create ``ocr_results`` (saved OCR text per document) if missing, and
    heal older deployments where it was created with ``REFERENCES
    student_documents`` — a table that never existed, so every INSERT under
    FK enforcement raised "no such table: main.student_documents". A wrong
    FK target is rebuilt onto ``documents``, carrying existing rows over.
    May commit (the rebuild needs foreign keys off outside a transaction)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ocr_results (
            ocr_id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            extracted_text TEXT,
            confidence_score REAL,
            processing_date TEXT,
            FOREIGN KEY (document_id) REFERENCES documents (document_id)
        )""")
    fks = list(conn.execute("PRAGMA foreign_key_list(ocr_results)"))
    # row layout: (id, seq, table, from, to, on_update, on_delete, match)
    if not any(r[2] != 'documents' for r in fks):
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        conn.execute("ALTER TABLE ocr_results RENAME TO _ocr_results_old")
        conn.execute("""
            CREATE TABLE ocr_results (
                ocr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                extracted_text TEXT,
                confidence_score REAL,
                processing_date TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (document_id)
            )""")
        conn.execute("""
            INSERT INTO ocr_results (ocr_id, document_id, extracted_text,
                                     confidence_score, processing_date)
            SELECT ocr_id, document_id, extracted_text, confidence_score, processing_date
            FROM _ocr_results_old""")
        conn.execute("DROP TABLE _ocr_results_old")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def ensure_ocr_jobs(conn):
    conn.execute(_OCR_JOBS_SCHEMA)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_document_ocr_jobs_at "
                 "ON document_ocr_jobs(processed_at)")


def _document_exists(conn, document_id):
    if document_id in (None, ""):
        return None
    try:
        doc = int(document_id)
    except (TypeError, ValueError):
        return None
    row = conn.execute("SELECT 1 FROM documents WHERE document_id = ?", (doc,)).fetchone()
    return doc if row else None


def record_ocr_job(result, file_path, *, document_id=None, source="file",
                   language=None, duration_ms=None, processed_by=None, conn=None):
    """Write one OCR attempt to ``document_ocr_jobs``; returns its id.

    Best effort: a failure to record is logged, never raised, so OCR itself
    is not lost because the history could not be written."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_ocr_jobs(conn)
        job_id = conn.execute(
            "INSERT INTO document_ocr_jobs (document_id, file_name, source, status, error, "
            "characters, pages, confidence, language, duration_ms, processed_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_document_exists(conn, document_id), os.path.basename(str(file_path or "")) or "(unknown)",
             source, "success" if result.success else "failed",
             None if result.success else result.error,
             len((result.text or "").strip()), result.pages, result.confidence,
             language, duration_ms, processed_by)).lastrowid
        if own:
            conn.commit()
        return job_id
    except sqlite3.Error:
        import logging
        logging.getLogger(__name__).exception("Could not record OCR job for %s", file_path)
        return None
    finally:
        if own and conn is not None:
            conn.close()


def run_and_record_ocr(file_path, *, document_id=None, source="file", language=None,
                       processed_by=None):
    """Run OCR and record the attempt (timed) in the job log."""
    import time
    started = time.monotonic()
    result = run_ocr(file_path)
    record_ocr_job(result, file_path, document_id=document_id, source=source,
                   language=language, processed_by=processed_by,
                   duration_ms=int((time.monotonic() - started) * 1000))
    return result


def ocr_job_stats(conn):
    """Real totals from the job log: total, successful, failed, average
    confidence (None when no run reported one)."""
    ensure_ocr_jobs(conn)
    total, ok, failed, avg = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(status = 'success'), 0), "
        "COALESCE(SUM(status = 'failed'), 0), AVG(confidence) FROM document_ocr_jobs").fetchone()
    return {"total": total, "success": ok, "failed": failed,
            "avg_confidence": None if avg is None else round(avg, 1)}


def ocr_jobs(conn, limit=500):
    """Most recent OCR attempts, newest first, as dicts."""
    ensure_ocr_jobs(conn)
    cur = conn.execute(
        "SELECT job_id, document_id, file_name, source, status, error, characters, pages, "
        "confidence, language, duration_ms, processed_by, processed_at "
        "FROM document_ocr_jobs ORDER BY processed_at DESC, job_id DESC LIMIT ?", (int(limit),))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def clear_ocr_jobs(conn):
    """Delete the OCR run history (not saved ``ocr_results`` text). Caller commits."""
    ensure_ocr_jobs(conn)
    return conn.execute("DELETE FROM document_ocr_jobs").rowcount


def run_batch_ocr(file_paths):
    """Run real OCR over many files, aggregating real results and errors.

    Returns a dict: {file_path: OCRResult}.
    """
    return {path: run_ocr(path) for path in file_paths}


class OCRMixin:
    def ocr_integration_menu(self):
        """OCR integration menu"""
        print("\n👁️ OCR INTEGRATION")
        print("1. Extract Text from Document")
        print("2. Batch OCR Processing")
        print("3. View OCR Results")
        print("4. OCR Settings")
        print("5. Return to Main Menu")

        choice = input("\nChoose option (1-5): ").strip()

        if choice == '1':
            self.extract_text_from_document()
        elif choice == '2':
            self.batch_ocr_processing()
        elif choice == '3':
            self.view_ocr_results()
        elif choice == '4':
            self.ocr_settings()

    def extract_text_from_document(self):
        """Extract text from a document using OCR"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check if OCR is enabled
            cursor.execute('''
            SELECT setting_value FROM system_settings WHERE setting_name = 'ocr_enabled'
            ''')

            result = cursor.fetchone()
            if not result or result[0] != 'true':
                print("❌ OCR is not enabled. Please enable it in OCR settings first.")
                conn.close()
                return

            doc_id = input("Enter document ID to process: ").strip()

            cursor.execute('''
            SELECT file_path, original_filename
            FROM documents
            WHERE document_id = ? AND is_current_version = 1
            ''', (doc_id,))

            doc = cursor.fetchone()

            if not doc:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return

            file_path, filename = doc
            conn.close()

            print(f"\nProcessing: {filename}")
            result = run_and_record_ocr(file_path, document_id=doc_id, source='document',
                                        processed_by=getattr(self, 'current_user', None))
            if result.success:
                print("✅ OCR complete. Extracted text:\n")
                print(result.text.strip() or "(no text detected in image)")
            else:
                # Be honest: do not pretend OCR succeeded.
                print(f"❌ OCR failed: {result.error}")
            return result

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def batch_ocr_processing(self):
        """Process multiple documents with OCR"""
        print("\n👁️  BATCH OCR PROCESSING")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check if OCR is enabled
            cursor.execute('''
            SELECT setting_value FROM system_settings WHERE setting_name = 'ocr_enabled'
            ''')

            result = cursor.fetchone()
            if not result or result[0] != 'true':
                print("❌ OCR is not enabled. Please enable it in OCR settings first.")
                conn.close()
                return

            print("\nSelect documents to process:")
            print("1. All pending documents")
            print("2. Documents by type")
            print("3. Specific student's documents")

            choice = input("\nChoose option (1-3): ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM documents
                WHERE is_current_version = 1
                ''')
            elif choice == '2':
                type_info = self.select_document_type(cursor)
                if not type_info:
                    conn.close()
                    return
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM documents
                WHERE type_id = ? AND is_current_version = 1
                ''', (type_info[0],))
            elif choice == '3':
                student_id = self.select_student(cursor)
                if not student_id:
                    conn.close()
                    return
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM documents
                WHERE owner_id = ? AND source_type = 'student' AND is_current_version = 1
                ''', (student_id,))
            else:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents to process.")

            confirm = input("Start OCR processing? (y/n): ").strip().lower()

            conn.close()

            if confirm == 'y':
                print("\nProcessing documents...")

                success_count = 0
                error_count = 0
                for doc_id, file_path, filename in documents:
                    print(f"  Processing: {filename}")
                    result = run_and_record_ocr(file_path, document_id=doc_id, source='batch',
                                                processed_by=getattr(self, 'current_user', None))
                    if result.success:
                        success_count += 1
                        chars = len(result.text.strip())
                        print(f"    ✅ Extracted {chars} characters")
                    else:
                        error_count += 1
                        print(f"    ❌ {result.error}")

                print(f"\nBatch processing finished for {len(documents)} documents.")
                print(f"   Succeeded: {success_count}")
                print(f"   Failed:    {error_count}")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_ocr_results(self):
        """View OCR extraction results"""
        print("\n👁️  OCR RESULTS")

        doc_id = input("Enter document ID (blank for overall history): ").strip()

        try:
            conn = get_connection()
            try:
                stats = ocr_job_stats(conn)
                print(f"\nOCR runs recorded: {stats['total']}  "
                      f"(successful {stats['success']}, failed {stats['failed']})")
                avg = stats["avg_confidence"]
                print(f"Average confidence: {'%.1f%%' % avg if avg is not None else 'not reported'}")

                jobs = ocr_jobs(conn, limit=50)
                if doc_id:
                    jobs = [j for j in jobs if str(j["document_id"]) == doc_id]
                    saved = []
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                    "AND name = 'ocr_results'").fetchone():
                        saved = conn.execute(
                            "SELECT processing_date, confidence_score, extracted_text FROM ocr_results "
                            "WHERE document_id = ? ORDER BY processing_date DESC", (doc_id,)).fetchall()
                    print(f"\nSaved OCR text for document {doc_id}: {len(saved)}")
                    for when, conf, text in saved:
                        preview = (text or "").strip().replace("\n", " ")[:120]
                        print(f"  {when}  confidence {conf if conf is not None else 'n/a'}  {preview}")
                print(f"\nRecent OCR runs{' for document ' + doc_id if doc_id else ''}: {len(jobs)}")
                for j in jobs:
                    detail = f"{j['characters']} chars" if j["status"] == "success" else (j["error"] or "")
                    print(f"  {j['processed_at']}  {j['file_name']}  {j['status']}  {detail}")
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
