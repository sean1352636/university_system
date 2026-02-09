"""Blockchain-based audit trail for academic integrity."""

import hashlib
import json
from datetime import datetime
from typing import Dict

from university_system.utils.ai.ai_detector.core.constants import logger


class BlockchainAuditTrail:
    """Implements blockchain-based audit trail for academic integrity"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.blockchain = []
        self.pending_transactions = []

    def create_detection_record(self, submission_id: int, detection_result: Dict) -> str:
        """Create immutable detection record"""
        # Create transaction
        transaction = {
            'type': 'ai_detection',
            'submission_id': submission_id,
            'detection_hash': hashlib.sha256(json.dumps(detection_result, sort_keys=True).encode()).hexdigest(),
            'timestamp': datetime.now().isoformat(),
            'analyzer_id': self.detector.current_user.get('id') if self.detector.current_user else None
        }

        # Add to pending transactions
        self.pending_transactions.append(transaction)

        # Mine block if enough transactions
        if len(self.pending_transactions) >= 5:
            self._mine_block()

        return transaction['detection_hash']

    def verify_detection_integrity(self, submission_id: int, claimed_hash: str) -> bool:
        """Verify integrity of detection record"""
        # Search blockchain for record
        for block in self.blockchain:
            for transaction in block.get('transactions', []):
                if (transaction.get('submission_id') == submission_id and
                    transaction.get('detection_hash') == claimed_hash):
                    return True

        return False

    def _mine_block(self):
        """Mine a new block with pending transactions"""
        previous_hash = self.blockchain[-1]['hash'] if self.blockchain else '0' * 64

        block = {
            'index': len(self.blockchain),
            'timestamp': datetime.now().isoformat(),
            'transactions': self.pending_transactions.copy(),
            'previous_hash': previous_hash,
            'nonce': 0
        }

        # Simple proof of work (in production, use proper PoW algorithm)
        while True:
            block_string = json.dumps(block, sort_keys=True)
            block_hash = hashlib.sha256(block_string.encode()).hexdigest()

            if block_hash.startswith('0000'):  # Difficulty = 4 leading zeros
                block['hash'] = block_hash
                break

            block['nonce'] += 1

        self.blockchain.append(block)
        self.pending_transactions = []

        logger.info(f"New block mined: {block['hash']}")
