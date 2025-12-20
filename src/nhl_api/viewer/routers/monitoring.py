"""Monitoring endpoints for data pipeline status.

Future implementation will provide:
- Pipeline run status
- Job statistics
- Error rates and alerts
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/status")
async def get_status() -> dict[str, str]:
    """Get pipeline monitoring status (not yet implemented)."""
    return {"message": "Monitoring endpoints coming soon"}
