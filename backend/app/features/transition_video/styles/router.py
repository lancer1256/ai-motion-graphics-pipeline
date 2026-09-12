"""FastAPI router for Transition Styles CRUD operations"""

from fastapi import APIRouter, HTTPException, status
from typing import Any, Dict, List

from .schemas import (
    TransitionStyle,
    TransitionStyleCreate,
    TransitionStyleUpdate,
    ValidationErrorResponse,
)
from .service import transition_style_service

router = APIRouter()


@router.get("/", response_model=List[TransitionStyle])
async def list_transition_styles():
    """Return list of all transition styles (default first)."""
    return await transition_style_service.list_styles()


@router.get("/{style_id}", response_model=TransitionStyle)
async def get_transition_style(style_id: str):
    style = await transition_style_service.get_style(style_id)
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style not found")
    return style


@router.post("/", response_model=TransitionStyle, responses={400: {"model": ValidationErrorResponse}})
async def create_or_update_transition_style(style: TransitionStyleCreate):
    data: Dict[str, Any] = style.model_dump(exclude_unset=True)
    try:
        saved = await transition_style_service.save_style(data)
        return saved
    except ValueError as e:
        # e.args may contain message and error list
        msg = str(e.args[0]) if e.args else "Validation failed"
        errors = e.args[1] if len(e.args) > 1 else []
        raise HTTPException(status_code=400, detail={"error": msg, "errors": errors})


@router.delete("/{style_id}", response_model=dict)
async def delete_transition_style(style_id: str):
    try:
        success = await transition_style_service.delete_style(style_id)
        if not success:
            raise HTTPException(status_code=404, detail="Style not found or cannot delete")
        return {"success": True, "message": f"Style {style_id} deleted"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) 