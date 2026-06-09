"""Preview endpoint handler for Nightwatch.

Provides a GET /api/nightwatch/preview endpoint that runs the digest
pipeline and returns the text without sending to Telegram.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.nightwatch import digest_orchestrator

logger = logging.getLogger(__name__)

preview_router = APIRouter(prefix="/api/nightwatch", tags=["nightwatch"])


@preview_router.get("/preview")
async def get_nightwatch_preview(db: Session = Depends(get_db)):
    """Run a preview of the Nightwatch digest without sending to Telegram.
    
    Useful for testing the digest text and LLM response before enabling delivery.
    
    Returns:
        Dict with preview text, findings count, actions count, and any error.
    """
    try:
        result = await digest_orchestrator.run_digest(db, preview=True)
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
