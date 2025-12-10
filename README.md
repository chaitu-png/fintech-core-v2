# Fintech Core v2

A financial transaction ledger system with multi-currency support, reconciliation engine, and audit trail.

## Architecture
- `ledger/` - Core transaction engine
- `payments/` - Payment processing and gateway integration
- `compliance/` - AML/KYC compliance checks
- `reports/` - Financial reporting and analytics

## Setup
```bash
pip install -r requirements.txt
python -m pytest tests/
```

## Known Issues
- Currency rounding occasionally produces off-by-one cent errors
- High-volume batch processing may cause memory issues
- Reconciliation engine has edge cases with reversed transactions


<!-- Simulated update -->