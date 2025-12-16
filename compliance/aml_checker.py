"""
AML (Anti-Money Laundering) Compliance Checker.

BUG INVENTORY:
- BUG-012: Threshold check uses wrong comparison operator
- BUG-013: Sanctions list loaded once and never refreshed
- BUG-014: Log injection vulnerability in audit trail
"""

import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# BUG-013: Sanctions list loaded at module import - never refreshed
SANCTIONS_LIST = [
    "ACME_SHELL_CORP", "DARKPOOL_LTD", "OFFSHORE_HOLDINGS_X",
    "SHADOW_FINANCE_GRP", "PHANTOM_TRADES_INC"
]

# AML thresholds (in USD)
SINGLE_TXN_THRESHOLD = 10000
DAILY_AGGREGATE_THRESHOLD = 25000
STRUCTURING_WINDOW_HOURS = 24
STRUCTURING_MIN_COUNT = 3


class AMLAlert:
    def __init__(self, alert_type: str, severity: str, account_id: str,
                 details: str, amount: float = 0):
        self.id = f"AML-{int(datetime.utcnow().timestamp())}"
        self.alert_type = alert_type
        self.severity = severity
        self.account_id = account_id
        self.details = details
        self.amount = amount
        self.created_at = datetime.utcnow()
        self.reviewed = False
        self.reviewer = None


class AMLChecker:
    """Anti-Money Laundering compliance checker."""

    def __init__(self):
        self.alerts: List[AMLAlert] = []
        self.checked_transactions = 0
        self.flagged_accounts = set()

    def check_transaction(self, txn: dict) -> Optional[AMLAlert]:
        """
        Check a single transaction against AML rules.

        BUG-012: Uses > instead of >= for threshold check.
        A transaction of exactly $10,000 (common structuring amount)
        will NOT be flagged.
        """
        self.checked_transactions += 1
        amount = txn.get("amount", 0)
        account = txn.get("sender_id", "")

        # BUG-012: Should be >= not > (exactly $10,000 slips through)
        if amount > SINGLE_TXN_THRESHOLD:
            alert = AMLAlert(
                alert_type="LARGE_TRANSACTION",
                severity="HIGH",
                account_id=account,
                details=f"Transaction of ${amount:.2f} exceeds threshold",
                amount=amount
            )
            self.alerts.append(alert)
            self.flagged_accounts.add(account)

            # BUG-014: Log injection - account/details not sanitized
            logger.warning(f"AML ALERT: Account {account} - {alert.details}")

            return alert

        return None

    def check_sanctions(self, entity_name: str) -> bool:
        """
        Check if entity is on sanctions list.

        BUG-013: Uses stale sanctions list from module load time.
        New sanctions entries won't be detected until restart.
        """
        # BUG: Case-sensitive comparison - "acme_shell_corp" won't match
        return entity_name in SANCTIONS_LIST

    def detect_structuring(self, transactions: List[dict],
                           account_id: str) -> Optional[AMLAlert]:
        """
        Detect potential structuring (smurfing) - breaking large amounts
        into smaller transactions to avoid reporting thresholds.
        """
        # Filter transactions for this account within window
        account_txns = [
            t for t in transactions
            if t.get("sender_id") == account_id
        ]

        if len(account_txns) < STRUCTURING_MIN_COUNT:
            return None

        # Check for pattern: multiple transactions just below threshold
        suspicious = [
            t for t in account_txns
            if 8000 <= t.get("amount", 0) < SINGLE_TXN_THRESHOLD
        ]

        if len(suspicious) >= STRUCTURING_MIN_COUNT:
            total = sum(t.get("amount", 0) for t in suspicious)
            if total > DAILY_AGGREGATE_THRESHOLD:
                alert = AMLAlert(
                    alert_type="STRUCTURING",
                    severity="CRITICAL",
                    account_id=account_id,
                    details=f"Potential structuring detected: {len(suspicious)} "
                            f"transactions totaling ${total:.2f}",
                    amount=total
                )
                self.alerts.append(alert)
                self.flagged_accounts.add(account_id)
                return alert

        return None

    def generate_compliance_report(self) -> dict:
        """Generate AML compliance summary report."""
        severity_counts = {}
        for alert in self.alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        return {
            "total_checked": self.checked_transactions,
            "total_alerts": len(self.alerts),
            "flagged_accounts": len(self.flagged_accounts),
            "alerts_by_severity": severity_counts,
            "reviewed": sum(1 for a in self.alerts if a.reviewed),
            "pending_review": sum(1 for a in self.alerts if not a.reviewed),
            "report_date": datetime.utcnow().isoformat(),
        }
