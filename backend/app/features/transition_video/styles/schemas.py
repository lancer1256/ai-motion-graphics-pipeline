"""Pydantic schemas for Transition Styles API"""

from __future__ import annotations
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field


class GlowConfig(BaseModel):
    strengths: Optional[List[float]] = Field(default_factory=list, description="Array of blur radius for each glow layer in pixels. Length determines number of layers.")


class LayoutConfig(BaseModel):
    mode: str = Field("centered", description="Layout mode name")
    avgStepPct: Optional[float] = 6
    jitterPct: Optional[float] = 3
    safeLeftPct: Optional[float] = 10
    safeRightPct: Optional[float] = 90
    accent: Optional[str] = "longestWord"
    accentColor: Optional[str] = "#6AB0A1"
    accentScale: Optional[float] = 1.05
    startTopPct: Optional[float] = 30
    lineHeight: Optional[float] = 1.4
    relativeOffsets: Optional[List[float]] = None
    centerAtPct: Optional[float] = None


class TransitionStyleBase(BaseModel):
    name: str = Field(..., max_length=100)
    fontFamily: str = Field(..., description="CSS font-family string")
    fontSize: float = Field(..., gt=0)
    fontColor: str = Field(..., pattern=r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
    backgroundColor: str = Field(..., pattern=r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    glow: Optional[GlowConfig] = Field(default_factory=GlowConfig)


class TransitionStyleCreate(TransitionStyleBase):
    id: Optional[str] = None  # Allow user to specify custom ID


class TransitionStyleUpdate(TransitionStyleBase):
    id: str


class TransitionStyle(TransitionStyleBase):
    id: str
    created: Optional[str]
    updated: Optional[str]
    is_default: Optional[bool] = False

    class Config:
        from_attributes = True


class ValidationErrorResponse(BaseModel):
    success: bool = False
    error: str
    errors: List[str] = [] 