# Standard library imports
import datetime
import time
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ImportResult:
    """Data class to track import operation results"""
    total_records: int = 0
    successful_imports: int = 0
    failed_imports: int = 0
    duplicates_found: int = 0
    duplicates_skipped: int = 0
    duplicates_updated: int = 0
    errors: List[Dict] = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ProgressTracker:
    """Track and display progress for batch operations"""
    def __init__(self, total_items: int, operation_name: str = "Processing"):
        self.total_items = total_items
        self.current_item = 0
        self.operation_name = operation_name
        self.start_time = time.time()
        self.last_update = 0

    def update(self, increment: int = 1):
        self.current_item += increment
        current_time = time.time()

        # Update progress every 0.5 seconds or at completion
        if current_time - self.last_update > 0.5 or self.current_item >= self.total_items:
            self.display_progress()
            self.last_update = current_time

    def display_progress(self):
        if self.total_items == 0:
            return

        percentage = (self.current_item / self.total_items) * 100
        elapsed_time = time.time() - self.start_time

        if self.current_item > 0:
            estimated_total_time = elapsed_time * (self.total_items / self.current_item)
            eta = estimated_total_time - elapsed_time
            eta_str = f"ETA: {int(eta//60)}:{int(eta%60):02d}"
        else:
            eta_str = "ETA: --:--"

        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * percentage / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        print(f"\r{self.operation_name}: [{bar}] {percentage:.1f}% ({self.current_item}/{self.total_items}) {eta_str}", end='', flush=True)

        if self.current_item >= self.total_items:
            print()  # New line when complete
