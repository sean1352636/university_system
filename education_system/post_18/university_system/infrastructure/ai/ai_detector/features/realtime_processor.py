"""Real-time submission processing."""

import time
import uuid
import threading
from datetime import datetime
from typing import Any, Dict

from education_system.post_18.university_system.infrastructure.ai.ai_detector.core.constants import logger


class RealTimeProcessor:
    """Processes submissions in real-time"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.processing_queue = []
        self.workers = []
        self.is_running = False

    def start_real_time_processing(self, num_workers: int = 3):
        """Start real-time processing with worker threads"""
        self.is_running = True

        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_process, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

        logger.info(f"Started real-time processing with {num_workers} workers")

    def stop_real_time_processing(self):
        """Stop real-time processing"""
        self.is_running = False

        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)

        self.workers = []
        logger.info("Stopped real-time processing")

    def queue_submission(self, submission_data: Dict, priority: int = 1) -> str:
        """Queue submission for real-time processing"""
        task_id = str(uuid.uuid4())

        task = {
            'id': task_id,
            'data': submission_data,
            'priority': priority,
            'queued_at': datetime.now(),
            'status': 'queued'
        }

        # Insert in priority order
        inserted = False
        for i, existing_task in enumerate(self.processing_queue):
            if existing_task['priority'] < priority:
                self.processing_queue.insert(i, task)
                inserted = True
                break

        if not inserted:
            self.processing_queue.append(task)

        return task_id

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a queued task"""
        for task in self.processing_queue:
            if task['id'] == task_id:
                return {
                    'status': task['status'],
                    'queued_at': task['queued_at'].isoformat(),
                    'position': self.processing_queue.index(task)
                }

        return {'status': 'not_found'}

    def _worker_process(self, worker_id: int):
        """Worker process for handling queued submissions"""
        logger.info(f"Worker {worker_id} started")

        while self.is_running:
            try:
                if self.processing_queue:
                    task = self.processing_queue.pop(0)
                    task['status'] = 'processing'

                    # Process the submission
                    result = self.detector.analyze_text_enhanced(**task['data'])

                    # Store result or send notification
                    self._handle_processing_result(task, result)

                else:
                    time.sleep(0.1)  # Brief sleep when queue is empty

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                time.sleep(1)

        logger.info(f"Worker {worker_id} stopped")

    def _handle_processing_result(self, task: Dict, result: Dict):
        """Handle the result of processing"""
        # This could send notifications, trigger alerts, etc.
        if result.get('is_ai_generated'):
            logger.warning(f"High-risk submission detected: {task['id']}")
            # Could send alert to instructors here
