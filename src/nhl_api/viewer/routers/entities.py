"""Entity exploration endpoints.

Future implementation will provide:
- Player lookups
- Team information
- Game data exploration
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/")
async def list_entity_types() -> dict[str, str]:
    """List available entity types (not yet implemented)."""
    return {"message": "Entity endpoints coming soon"}
