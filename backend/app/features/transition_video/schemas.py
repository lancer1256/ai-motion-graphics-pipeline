"""Schemas for transition video generation"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class LayoutConfig(BaseModel):
    """Layout configuration for transition videos"""
    mode: str = Field("centered", description="Layout mode: centered, diagonalDrift, relativeOffsets, relativeToCenterOffsets")
    avgStepPct: float = Field(6.0, ge=0, le=20, description="Average step percentage for drift")
    jitterPct: float = Field(3.0, ge=0, le=20, description="Jitter percentage for randomness")
    safeLeftPct: float = Field(10.0, ge=0, le=100, description="Safe left margin percentage")
    safeRightPct: float = Field(90.0, ge=0, le=100, description="Safe right margin percentage")
    accent: str = Field("longestWord", description="Accent mode: none, longestWord, manual")
    accentColor: str = Field("#6AB0A1", pattern=r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
    accentScale: float = Field(1.05, ge=0.5, le=3.0, description="Scale factor for accent words")
    accentBold: bool = Field(True, description="Whether accent words should be bold")
    startTopPct: float = Field(30.0, ge=0, le=100, description="Starting top position percentage")
    lineHeight: float = Field(1.4, ge=0.5, le=3.0, description="Line height multiplier")
    relativeOffsets: Optional[List[float]] = Field(None, description="Array of relative position offsets")


class TransitionStyle(BaseModel):
    """Transition style configuration"""
    fontFamily: str = Field("Times New Roman, serif", description="CSS font family")
    fontSize: int = Field(48, ge=1, le=200, description="Font size in pixels")
    fontColor: str = Field("#000000", pattern=r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
    backgroundColor: str = Field("#ffffff", pattern=r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
    fontWeight: str = Field("normal", pattern=r"^(normal|bold)$")
    layout: LayoutConfig = Field(default_factory=LayoutConfig)


class WordTiming(BaseModel):
    """Word timing information"""
    punctuated_word: Optional[str] = None
    word: Optional[str] = None
    start: float = Field(..., description="Start time in seconds")
    end: Optional[float] = Field(None, description="End time in seconds")


class TransitionVideoRequest(BaseModel):
    """Request to generate a transition video"""
    line: str = Field(..., description="Text line to render")
    rebased_timings: List[WordTiming] = Field(..., description="Word timing data")
    duration: float = Field(..., gt=0, description="Video duration in seconds")
    style_id: Optional[str] = Field(None, description="Transition style ID to use")
    layout_seed: Optional[int] = Field(None, description="Random seed for layout")


class VideoGenerationResult(BaseModel):
    """Result of video generation"""
    enabled: bool = True
    video_path: Optional[str] = Field(None, description="Relative path to generated video")
    prompt_used: str = Field(..., description="Text prompt that was rendered")
    timestamp: str = Field(..., description="Generation timestamp")
    api_info: Dict[str, Any] = Field(default_factory=dict, description="API metadata")
    cost: float = Field(0.0, ge=0, description="Generation cost")
    error: Optional[str] = Field(None, description="Error message if generation failed")


class TransitionVideoResponse(BaseModel):
    """Response from transition video generation"""
    success: bool
    result: Optional[VideoGenerationResult] = None
    error: Optional[str] = None