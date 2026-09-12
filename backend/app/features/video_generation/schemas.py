"""Pydantic schemas for video generation operations"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class VideoGenerationResult(BaseModel):
    success: bool
    video_path: Optional[str] = None
    prompt_used: Optional[str] = None
    timestamp: Optional[datetime] = None
    cost: Optional[float] = None
    error: Optional[str] = None

class VideoThumbnailResponse(BaseModel):
    success: bool
    thumbnail_data: Optional[str] = None
    error: Optional[str] = None

class VideoConcatResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None 