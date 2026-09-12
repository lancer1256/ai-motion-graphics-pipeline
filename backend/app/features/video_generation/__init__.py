"""Video Generation Feature Slice
Handles video generation, storage, and serving.
"""

from .router import router
from .service import video_service

__all__ = ["router", "video_service"] 