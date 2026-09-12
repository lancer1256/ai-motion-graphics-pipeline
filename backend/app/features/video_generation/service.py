"""Video Generation Service
Provides high-level functions for generating videos via FAL.ai, retrieving thumbnails, and serving video files.
"""

import asyncio
import base64
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# requests import removed - using httpx via http_manager
from app.core.config import settings
from app.services_clients.http_client_manager import http_manager
from .utils import encode_svg_placeholder
import logging
logger = logging.getLogger(__name__)

try:
    import fal_client  # type: ignore
except ImportError:  # fal-client might not be installed in some dev envs
    fal_client = None  # pragma: no cover


class VideoGenerationError(Exception):
    """Custom exception for video generation errors"""


class RateLimitError(VideoGenerationError):
    """Raised when 429 Too Many Requests occurs"""


class VideoGenerationService:
    """Business logic for video generation and management"""

    def __init__(self):
        self.fal_keys: List[str] = [
            k for k in [
                settings.FAL_KEY,
                settings.FAL_KEY_2,
                settings.FAL_KEY_3,
                settings.FAL_KEY_4,
                settings.FAL_KEY_5,
            ] if k
        ]
        self.max_retries = 3
        self.retry_delay = 5  # seconds between retries
        self.rate_limit_retries = 4  # 429 retries per key
        self.rate_limit_delay = 31  # seconds to back off on 429

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    async def generate_video_for_message(
        self,
        prompt: str,
        image_data: bytes,
        conv_id: str,
        message_index: int,
        backtest_id: str,
        resolution: str = "512P",
    ) -> Dict[str, Any]:
        """Generate a video for a specific message and return metadata."""
        logger.info(f"VIDGEN: Starting video generation for {conv_id} message {message_index}")

        for attempt in range(self.max_retries):
            try:
                video_bytes = await self._call_video_api_with_retry(prompt, image_data, resolution)
                video_path = self._save_video_file(video_bytes, conv_id, message_index, backtest_id)

                return {
                    "enabled": True,
                    "success": True,
                    "video_path": video_path,
                    "prompt_used": prompt,
                    "timestamp": datetime.utcnow().isoformat(),
                    "api_info": {
                        "model": "fal-ai/minimax/hailuo-02/standard/image-to-video",
                        "duration": "6",
                        "prompt_optimizer": False,
                        "resolution": resolution
                    },
                    "generation_attempt": attempt + 1,
                    "cost": self._calculate_video_cost(),
                }

            except RateLimitError as e:
                logger.info(f"VIDGEN: Rate limit exceeded for {conv_id} message {message_index}: {e}")
                return {
                    "enabled": True,
                    "success": False,
                    "error": f"Rate limit exceeded: {str(e)}",
                    "prompt_used": prompt,
                    "timestamp": datetime.utcnow().isoformat(),
                    "cost": 0.0,
                }
            except Exception as e:
                logger.error(f"VIDGEN: Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return {
                        "enabled": True,
                        "success": False,
                        "error": f"Video generation failed after {self.max_retries} attempts: {e}",
                        "prompt_used": prompt,
                        "timestamp": datetime.utcnow().isoformat(),
                        "cost": 0.0,
                    }

    async def get_video_thumbnail(self, backtest_id: str, video_path: str) -> Optional[str]:
        """Return base64 thumbnail or placeholder for a video."""
        full_path = settings.BACKTEST_RESULTS_FOLDER / backtest_id / video_path
        if not full_path.exists():
            return None
        # TODO: Implement real thumbnail generation via ffmpeg
        return encode_svg_placeholder()

    async def get_full_video_path(self, backtest_id: str, video_path: str) -> Optional[Path]:
        """Return full filesystem path to video if it exists."""
        full_path = settings.BACKTEST_RESULTS_FOLDER / backtest_id / video_path
        return full_path if full_path.exists() else None

    async def find_source_image_for_video(
        self, 
        conversation_messages: List[Dict[str, Any]], 
        message_index: int, 
        backtest_id: str
    ) -> Optional[bytes]:
        """
        Find the source image to use for video generation.
        
        Args:
            conversation_messages: List of messages in conversation
            message_index: Current message index
            backtest_id: Backtest ID for loading image files
            
        Returns:
            Image bytes if found, None otherwise
        """
        logger.info(f"VIDGEN: Looking for source image for message {message_index}")
        
        # First, look for explicitly marked images
        for i in range(message_index - 1, -1, -1):  # Look backwards
            if i >= len(conversation_messages):
                continue
                
            message = conversation_messages[i]
            if (message.get('role') == 'assistant' and 
                message.get('generated_image') and 
                message['generated_image'].get('use_for_video')):
                
                image_path = message['generated_image'].get('image_path')
                if image_path:
                    logger.info(f"VIDGEN: Found marked image at message {i}: {image_path}")
                    return await self._load_image_from_path(image_path, backtest_id)
        
        # Fallback: find most recent image
        for i in range(message_index - 1, -1, -1):  # Look backwards
            if i >= len(conversation_messages):
                continue
                
            message = conversation_messages[i]
            if (message.get('role') == 'assistant' and 
                message.get('generated_image') and 
                message['generated_image'].get('image_path')):
                
                image_path = message['generated_image']['image_path']
                logger.info(f"VIDGEN: Using most recent image at message {i}: {image_path}")
                return await self._load_image_from_path(image_path, backtest_id)
        
        logger.info(f"VIDGEN: No source image found for message {message_index}")
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_random_key(self) -> str:
        if not self.fal_keys:
            raise VideoGenerationError("Set FAL_KEY before running the Hailuo generation stage")
        key = random.choice(self.fal_keys)
        logger.info("VIDGEN: Using a configured FAL key")
        return key

    async def _call_video_api_with_retry(self, prompt: str, image_data: bytes, resolution: str) -> bytes:
        """Wrapper that retries on rate limits and rotates API keys."""
        if not fal_client:
            raise VideoGenerationError("fal_client library is not installed")

        attempted_keys = set()
        attempts = 0
        max_attempts = len(self.fal_keys) * self.rate_limit_retries

        while attempts < max_attempts:
            key = self._get_random_key()
            attempted_keys.add(key)
            try:
                return await self._call_video_api(prompt, image_data, key, resolution)
            except RateLimitError as e:
                logger.info(f"VIDGEN: 429 Too Many Requests: {e}")
                attempts += 1
                await asyncio.sleep(self.rate_limit_delay)
                continue
            except VideoGenerationError as e:
                if "insufficient" in str(e).lower() or "balance" in str(e).lower():
                    logger.info("VIDGEN: Insufficient balance, rotating key...")
                    if len(attempted_keys) >= len(self.fal_keys):
                        raise
                    continue
                raise
        raise VideoGenerationError("All FAL keys exhausted or failed")

    async def _call_video_api(self, prompt: str, image_data: bytes, api_key: str, resolution: str) -> bytes:
        """Call fal.ai API and return video bytes"""
        logger.info(f"VIDGEN: Calling fal.ai API with prompt: {prompt[:60]}...")

        # Prepare image as data URI
        img_b64 = base64.b64encode(image_data).decode()
        img_uri = f"data:image/png;base64,{img_b64}"

        # Temporarily set environment variable for fal_client
        original_key = os.environ.get("FAL_KEY")
        os.environ["FAL_KEY"] = api_key
        try:
            # Use async subscribe method
            result = await fal_client.subscribe_async(
                "fal-ai/minimax/hailuo-02/standard/image-to-video",
                arguments={
                    "prompt": prompt,
                    "image_url": img_uri,
                    "duration": "6",
                    "prompt_optimizer": False,
                    "resolution": resolution,
                },
                with_logs=False,
            )
        finally:
            # Restore original key
            if original_key is not None:
                os.environ["FAL_KEY"] = original_key
            else:
                del os.environ["FAL_KEY"]

        if not result or not result.get("video") or not result["video"].get("url"):
            raise VideoGenerationError("No video URL returned from API")

        video_url = result["video"]["url"]
        
        # Use async HTTP client for downloading video
        response = await http_manager.request(
            "fal_cdn",
            "GET",
            video_url
        )
        
        if response.status_code == 429:
            raise RateLimitError("Rate limited while downloading video")
        if response.status_code != 200:
            raise VideoGenerationError(f"Failed to download video: {response.status_code}")
        return response.content

    def _save_video_file(self, data: bytes, conv_id: str, message_index: int, backtest_id: str) -> str:
        """Save video bytes to disk and return relative path."""
        videos_dir = settings.BACKTEST_RESULTS_FOLDER / backtest_id / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{conv_id}_msg{message_index}.mp4"
        file_path = videos_dir / filename
        with open(file_path, "wb") as f:
            f.write(data)
        logger.info(f"VIDGEN: Saved video to {file_path}")
        return f"videos/{filename}"

    def _calculate_video_cost(self) -> float:
        pricing = settings.PRICING.get("video_fixed", {})
        if isinstance(pricing, dict):
            return pricing.get("cost", 0.0)
        return 0.0

    async def _load_image_from_path(self, image_path: str, backtest_id: str) -> Optional[bytes]:
        """Load image bytes from relative path"""
        try:
            full_path = settings.BACKTEST_RESULTS_FOLDER / backtest_id / image_path
            if not full_path.exists():
                logger.info(f"VIDGEN: Image file not found: {full_path}")
                return None
                
            with open(full_path, 'rb') as f:
                image_data = f.read()
            
            logger.info(f"VIDGEN: Successfully loaded image from {image_path}")
            return image_data
            
        except Exception as e:
            logger.error(f"VIDGEN: Error loading image from {image_path}: {e}")
            return None


# Global singleton
video_service = VideoGenerationService() 
