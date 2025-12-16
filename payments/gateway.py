"""
Payment Gateway Integration - Connects to external payment processors.

BUG INVENTORY:
- BUG-008: API key stored in plaintext
- BUG-009: No retry with exponential backoff
- BUG-010: Timeout too short for international transactions
- BUG-011: Exception swallowing hides payment failures
"""

import time
import json
import hashlib
from typing import Optional, Dict
from datetime import datetime


# BUG-008: Hardcoded API credentials in source code
PAYMENT_API_KEY = "sk_test_REDACTED_FOR_AI_TRAINING_001"
PAYMENT_API_SECRET = "whsec_REDACTED_FOR_AI_TRAINING_002"
GATEWAY_URL = "https://api.paymentgateway.com/v2"

# BUG-010: 3-second timeout is too short for cross-border transactions
DEFAULT_TIMEOUT = 3  # Should be 30+ seconds


class PaymentResult:
    def __init__(self, success: bool, transaction_id: str = "",
                 error_code: str = "", error_message: str = ""):
        self.success = success
        self.transaction_id = transaction_id
        self.error_code = error_code
        self.error_message = error_message
        self.timestamp = datetime.utcnow()


class PaymentGateway:
    """Handles payment processing through external gateways."""

    def __init__(self, api_key: str = None, environment: str = "production"):
        # BUG-008: Falls back to hardcoded key if none provided
        self.api_key = api_key or PAYMENT_API_KEY
        self.environment = environment
        self.timeout = DEFAULT_TIMEOUT
        self._request_count = 0
        self._error_log = []

    def charge(self, amount: float, currency: str, card_token: str,
               metadata: Dict = None) -> PaymentResult:
        """
        Process a payment charge.

        BUG-009: No retry mechanism - transient network failures
        cause permanent transaction failures.

        BUG-011: Broad exception catch hides real errors.
        """
        self._request_count += 1

        try:
            # Validate inputs
            if amount <= 0:
                return PaymentResult(False, error_code="INVALID_AMOUNT",
                                     error_message="Amount must be positive")

            if not card_token:
                return PaymentResult(False, error_code="INVALID_TOKEN",
                                     error_message="Card token is required")

            # Build payment request
            payload = {
                "amount": int(amount * 100),  # Convert to cents
                "currency": currency.lower(),
                "source": card_token,
                "metadata": metadata or {},
                "idempotency_key": self._generate_idempotency_key(
                    amount, card_token
                ),
            }

            # Simulate API call (in real code, this would be requests.post)
            response = self._simulate_api_call(payload)

            if response.get("status") == "succeeded":
                return PaymentResult(
                    True,
                    transaction_id=response.get("id", ""),
                )
            else:
                return PaymentResult(
                    False,
                    error_code=response.get("error", {}).get("code", "UNKNOWN"),
                    error_message=response.get("error", {}).get("message", ""),
                )

        except Exception:
            # BUG-011: Swallowing ALL exceptions - hides critical failures
            # like network errors, auth failures, data corruption
            return PaymentResult(False, error_code="INTERNAL_ERROR",
                                 error_message="Payment processing failed")

    def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Process a refund for a previous charge."""
        try:
            payload = {
                "charge": transaction_id,
                "amount": int(amount * 100) if amount else None,
            }

            response = self._simulate_api_call(payload)

            return PaymentResult(
                response.get("status") == "succeeded",
                transaction_id=response.get("id", ""),
            )
        except Exception as e:
            # BUG-011: Logs error but returns success=False with no details
            self._error_log.append(str(e))
            return PaymentResult(False)

    def _simulate_api_call(self, payload: dict) -> dict:
        """Simulate external API call with realistic failure modes."""
        # Simulate network latency
        time.sleep(0.05)

        # Simulate occasional failures (10% rate)
        if self._request_count % 10 == 7:
            raise ConnectionError("Gateway timeout")

        if self._request_count % 15 == 0:
            return {
                "status": "failed",
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests"
                }
            }

        return {
            "id": f"ch_{hashlib.md5(json.dumps(payload).encode()).hexdigest()[:16]}",
            "status": "succeeded",
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
        }

    def _generate_idempotency_key(self, amount: float, token: str) -> str:
        """Generate idempotency key for deduplication."""
        data = f"{amount}:{token}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def get_health_status(self) -> dict:
        """Check gateway health."""
        return {
            "status": "healthy" if len(self._error_log) < 5 else "degraded",
            "total_requests": self._request_count,
            "error_count": len(self._error_log),
            "uptime_percentage": max(0, 100 - (len(self._error_log) / max(self._request_count, 1) * 100)),
        }
