"""
Transaction Engine - Core ledger transaction processing.
Handles creation, validation, and execution of financial transactions.

BUG INVENTORY (for PEIS detection):
- BUG-001: Float arithmetic for currency (should use Decimal)
- BUG-002: Race condition in balance updates (no locking)
- BUG-003: Memory leak in transaction history cache
- BUG-004: No idempotency check on duplicate transactions
"""

import time
import threading
from datetime import datetime
from typing import List, Dict, Optional

# BUG-003: Global cache that never gets cleared - MEMORY LEAK
_transaction_cache = []
_cache_lock = threading.Lock()


class TransactionStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class Transaction:
    def __init__(self, sender_id: str, receiver_id: str, amount: float,
                 currency: str = "USD", description: str = ""):
        self.id = f"TXN-{int(time.time() * 1000)}"
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        # BUG-001: Using float for currency amounts - causes rounding errors
        self.amount = amount
        self.currency = currency
        self.description = description
        self.status = TransactionStatus.PENDING
        self.created_at = datetime.utcnow()
        self.completed_at = None
        self.fee = self._calculate_fee()

    def _calculate_fee(self) -> float:
        """Calculate transaction fee based on amount and currency."""
        fee_rates = {
            "USD": 0.029,
            "EUR": 0.025,
            "GBP": 0.031,
            "JPY": 0.015,
            "INR": 0.022,
        }
        rate = fee_rates.get(self.currency, 0.035)
        # BUG-001: Float multiplication causes precision loss
        # Example: 19.99 * 0.029 = 0.57971 but stored as 0.5797099999...
        fee = self.amount * rate
        return round(fee, 2)  # round helps but doesn't fully fix IEEE 754 issues

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender_id,
            "receiver": self.receiver_id,
            "amount": self.amount,
            "currency": self.currency,
            "fee": self.fee,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class LedgerEngine:
    """Core ledger engine for processing financial transactions."""

    def __init__(self):
        self.accounts: Dict[str, float] = {}
        self.transactions: List[Transaction] = []
        # BUG-002: No mutex/lock for concurrent balance modifications
        self._balance_lock = None  # Should be threading.Lock()

    def create_account(self, account_id: str, initial_balance: float = 0.0) -> bool:
        """Create a new account with optional initial balance."""
        if account_id in self.accounts:
            return False
        # BUG-001: Float for balance
        self.accounts[account_id] = initial_balance
        return True

    def get_balance(self, account_id: str) -> Optional[float]:
        """Get current balance for an account."""
        return self.accounts.get(account_id)

    def process_transaction(self, txn: Transaction) -> bool:
        """
        Process a financial transaction between two accounts.

        BUG-002: No locking mechanism - concurrent transactions can cause
        inconsistent balances. Two simultaneous withdrawals could both
        succeed even if combined amount exceeds balance.

        BUG-004: No idempotency check - same transaction could be processed
        multiple times if retried.
        """
        # Validate accounts exist
        if txn.sender_id not in self.accounts:
            txn.status = TransactionStatus.FAILED
            return False

        if txn.receiver_id not in self.accounts:
            txn.status = TransactionStatus.FAILED
            return False

        total_debit = txn.amount + txn.fee

        # BUG-002: TOCTOU race condition - balance check and update are not atomic
        if self.accounts[txn.sender_id] < total_debit:
            txn.status = TransactionStatus.FAILED
            return False

        # Simulate processing delay (makes race condition more likely)
        time.sleep(0.001)

        # BUG-002: Non-atomic balance modification
        self.accounts[txn.sender_id] -= total_debit
        self.accounts[txn.receiver_id] += txn.amount

        txn.status = TransactionStatus.COMPLETED
        txn.completed_at = datetime.utcnow()

        # BUG-003: Append to global cache that never gets pruned
        with _cache_lock:
            _transaction_cache.append(txn.to_dict())

        self.transactions.append(txn)
        return True

    def reverse_transaction(self, txn_id: str) -> bool:
        """Reverse a completed transaction."""
        target_txn = None
        for txn in self.transactions:
            if txn.id == txn_id:
                target_txn = txn
                break

        if not target_txn or target_txn.status != TransactionStatus.COMPLETED:
            return False

        # BUG: Fee is not refunded on reversal - money disappears
        self.accounts[target_txn.receiver_id] -= target_txn.amount
        self.accounts[target_txn.sender_id] += target_txn.amount
        # Missing: self.accounts[target_txn.sender_id] += target_txn.fee

        target_txn.status = TransactionStatus.REVERSED
        return True

    def batch_process(self, transactions: List[Transaction]) -> Dict[str, int]:
        """
        Process a batch of transactions sequentially.

        BUG-003: Each transaction adds to the global cache, causing
        memory growth proportional to total transaction volume with
        no upper bound.
        """
        results = {"success": 0, "failed": 0}
        for txn in transactions:
            if self.process_transaction(txn):
                results["success"] += 1
            else:
                results["failed"] += 1
        return results

    def get_transaction_history(self, account_id: str) -> List[dict]:
        """Get all transactions for an account."""
        history = []
        for txn in self.transactions:
            if txn.sender_id == account_id or txn.receiver_id == account_id:
                history.append(txn.to_dict())
        return history

    def calculate_daily_volume(self, date_str: str) -> float:
        """Calculate total transaction volume for a given date."""
        total = 0.0
        for txn in self.transactions:
            if txn.created_at.strftime("%Y-%m-%d") == date_str:
                # BUG-001: Accumulating floats compounds rounding errors
                total += txn.amount
        return total
