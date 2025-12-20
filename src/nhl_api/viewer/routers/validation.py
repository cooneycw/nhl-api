"""Data validation endpoints.

Future implementation will provide:
- Data quality checks
- Validation rule status
- Anomaly detection results
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/status")
async def get_validation_status() -> dict[str, str]:
    """Get data validation status (not yet implemented)."""
    return {"message": "Validation endpoints coming soon"}
