"""
Reconciliation Engine - Matches internal records with external bank statements.

BUG INVENTORY:
- BUG-005: Off-by-one in date range filtering
- BUG-006: Silent data corruption when merging partial matches
- BUG-007: N+1 query pattern in batch reconciliation
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional


class ReconciliationRecord:
    def __init__(self, ref_id: str, amount: float, date: datetime,
                 source: str, description: str = ""):
        self.ref_id = ref_id
        self.amount = amount
        self.date = date
        self.source = source
        self.description = description
        self.matched = False
        self.match_confidence = 0.0


class ReconciliationEngine:
    """Matches internal ledger records with external bank statements."""

    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance
        self.internal_records: List[ReconciliationRecord] = []
        self.external_records: List[ReconciliationRecord] = []
        self.matches: List[Tuple[str, str, float]] = []
        self.unmatched_internal: List[ReconciliationRecord] = []
        self.unmatched_external: List[ReconciliationRecord] = []

    def load_internal_records(self, records: List[dict]) -> int:
        """Load internal ledger records for reconciliation."""
        count = 0
        for r in records:
            rec = ReconciliationRecord(
                ref_id=r["id"],
                amount=r["amount"],
                date=datetime.fromisoformat(r["date"]),
                source="internal",
                description=r.get("description", "")
            )
            self.internal_records.append(rec)
            count += 1
        return count

    def load_external_records(self, records: List[dict]) -> int:
        """Load external bank statement records."""
        count = 0
        for r in records:
            rec = ReconciliationRecord(
                ref_id=r["id"],
                amount=r["amount"],
                date=datetime.fromisoformat(r["date"]),
                source="external",
                description=r.get("description", "")
            )
            self.external_records.append(rec)
            count += 1
        return count

    def reconcile(self, date_from: str, date_to: str) -> Dict[str, int]:
        """
        Run reconciliation for a date range.

        BUG-005: Off-by-one error - transactions on date_to are excluded
        because we use < instead of <= for the end date comparison.
        """
        start = datetime.fromisoformat(date_from)
        end = datetime.fromisoformat(date_to)

        # BUG-005: Should be <= end, not < end
        filtered_internal = [
            r for r in self.internal_records
            if start <= r.date < end  # BUG: excludes end date
        ]
        filtered_external = [
            r for r in self.external_records
            if start <= r.date < end  # BUG: excludes end date
        ]

        matched_count = 0
        for int_rec in filtered_internal:
            # BUG-007: N+1 pattern - iterates all external for each internal
            for ext_rec in filtered_external:
                if ext_rec.matched:
                    continue

                if self._is_match(int_rec, ext_rec):
                    confidence = self._calculate_confidence(int_rec, ext_rec)
                    self.matches.append((int_rec.ref_id, ext_rec.ref_id, confidence))
                    int_rec.matched = True
                    ext_rec.matched = True
                    matched_count += 1
                    break

        # Collect unmatched
        self.unmatched_internal = [r for r in filtered_internal if not r.matched]
        self.unmatched_external = [r for r in filtered_external if not r.matched]

        return {
            "matched": matched_count,
            "unmatched_internal": len(self.unmatched_internal),
            "unmatched_external": len(self.unmatched_external),
            "total_processed": len(filtered_internal) + len(filtered_external),
        }

    def _is_match(self, internal: ReconciliationRecord,
                  external: ReconciliationRecord) -> bool:
        """Check if two records match within tolerance."""
        amount_diff = abs(internal.amount - external.amount)
        date_diff = abs((internal.date - external.date).days)

        # BUG-006: Tolerance check doesn't account for currency precision
        return amount_diff <= self.tolerance and date_diff <= 1

    def _calculate_confidence(self, internal: ReconciliationRecord,
                              external: ReconciliationRecord) -> float:
        """Calculate match confidence score (0.0 to 1.0)."""
        score = 1.0

        amount_diff = abs(internal.amount - external.amount)
        if amount_diff > 0:
            score -= amount_diff / max(internal.amount, 0.01) * 0.5

        date_diff = abs((internal.date - external.date).days)
        if date_diff > 0:
            score -= 0.2

        # BUG-006: Score can go negative, should be clamped
        return score  # Should be max(0.0, score)

    def generate_report(self) -> dict:
        """Generate reconciliation summary report."""
        total_matched_amount = sum(
            r.amount for r in self.internal_records if r.matched
        )
        total_unmatched_amount = sum(
            r.amount for r in self.internal_records if not r.matched
        )

        return {
            "total_matches": len(self.matches),
            "total_matched_amount": total_matched_amount,
            "total_unmatched_amount": total_unmatched_amount,
            "average_confidence": (
                sum(m[2] for m in self.matches) / len(self.matches)
                if self.matches else 0.0
            ),
            "unmatched_internal_count": len(self.unmatched_internal),
            "unmatched_external_count": len(self.unmatched_external),
        }
