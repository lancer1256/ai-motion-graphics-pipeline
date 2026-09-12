"""Main transition video service"""

import asyncio
import json
import random
import subprocess
import tempfile
import os
import logging
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.utils.costs import calc_video_cost
from .styles.service import transition_style_service
from .schemas import TransitionVideoRequest, TransitionVideoResponse, VideoGenerationResult, WordTiming

# Set up logger for transition video operations
logger = logging.getLogger(__name__)


class TransitionVideoGenerationError(Exception):
    """Custom exception for transition video generation errors"""
    pass


class TransitionVideoService:
    """Service for transition video operations and generation"""
    
    def __init__(self):
        self.fps = settings.TRANSITION_VIDEO_FPS
        self.width = settings.TRANSITION_VIDEO_WIDTH
        self.height = settings.TRANSITION_VIDEO_HEIGHT
        
        # Path to Remotion renderer within transition_video feature
        self.renderer_path = Path(__file__).parent / "renderer"
        
        # Node.js server configuration
        self.server_url = "http://localhost:3002"
        self.server_timeout = 300  # 5 minutes
    
    async def ensure_server_running(self):
        """Ensure the Node.js render server is running"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.server_url}/health")
                if response.status_code == 200:
                    logger.info("Render server is already running")
                    return True
        except (httpx.RequestError, httpx.TimeoutException):
            logger.info("Render server not responding, starting it...")
        
        # Start the server
        try:
            # Check if npm packages are installed
            node_modules_path = self.renderer_path / "node_modules"
            if not node_modules_path.exists():
                logger.info("Installing npm packages...")
                await asyncio.to_thread(
                    subprocess.run,
                    ["npm", "install"],
                    cwd=self.renderer_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info("npm packages installed successfully")
            
            # Start server in background
            logger.info("Starting render server...")
            env = os.environ.copy()
            env.update({
                'TRANSITION_VIDEO_FPS': str(settings.TRANSITION_VIDEO_FPS),
                'TRANSITION_VIDEO_WIDTH': str(settings.TRANSITION_VIDEO_WIDTH),
                'TRANSITION_VIDEO_HEIGHT': str(settings.TRANSITION_VIDEO_HEIGHT)
            })
            subprocess.Popen(
                ["npm", "start"],
                cwd=self.renderer_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            
            # Wait for server to be ready
            for attempt in range(30):  # Wait up to 30 seconds
                try:
                    await asyncio.sleep(1)
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(f"{self.server_url}/health")
                        if response.status_code == 200:
                            logger.info(f"Render server started successfully after {attempt + 1} seconds")
                            return True
                except (httpx.RequestError, httpx.TimeoutException):
                    continue
            
            raise TransitionVideoGenerationError("Failed to start render server within 30 seconds")
            
        except subprocess.CalledProcessError as e:
            raise TransitionVideoGenerationError(f"Failed to start render server: {e}")
    
    async def generate_video(self, request: TransitionVideoRequest, conv_id: str, backtest_id: str) -> TransitionVideoResponse:
        """
        Generate transition video from request
        
        Args:
            request: Video generation request
            conv_id: Conversation ID
            backtest_id: Backtest ID
            
        Returns:
            TransitionVideoResponse with result or error
        """
        try:
            result = await self.generate_transition_video(
                line=request.line,
                rebased_timings=request.rebased_timings,
                duration=request.duration,
                conv_id=conv_id,
                backtest_id=backtest_id,
                style_id=request.style_id,
                layout_seed=request.layout_seed
            )
            
            if result.error:
                return TransitionVideoResponse(
                    success=False,
                    error=result.error
                )
            
            return TransitionVideoResponse(
                success=True,
                result=result
            )
            
        except Exception as e:
            return TransitionVideoResponse(
                success=False,
                error=f"Transition video service error: {str(e)}"
            )
    
    async def generate_from_variables(
        self,
        variables: Dict[str, str],
        conv_id: str,
        backtest_id: str,
        style_id: str = None
    ) -> VideoGenerationResult:
        """
        Generate transition video from backtest variables
        
        Args:
            variables: Backtest variables containing line, rebased_timings, duration
            conv_id: Conversation ID
            backtest_id: Backtest ID
            style_id: Optional style ID
            
        Returns:
            VideoGenerationResult
        """
        # Extract variables
        line = variables.get('line', '').strip()
        rebased_timings_raw = variables.get('rebased_timings', '[]')
        duration_str = variables.get('duration', '1')
        
        # Parse rebased timings
        try:
            if isinstance(rebased_timings_raw, str):
                timings_data = json.loads(rebased_timings_raw)
            else:
                timings_data = rebased_timings_raw
        except json.JSONDecodeError:
            return VideoGenerationResult(
                enabled=True,
                prompt_used=f"[Transition]: {line}",
                timestamp=datetime.now().isoformat(),
                api_info={},
                cost=0.0,
                error="Invalid rebased_timings JSON format"
            )
        
        # Convert to WordTiming objects
        rebased_timings = []
        for timing_data in timings_data:
            if isinstance(timing_data, dict):
                rebased_timings.append(WordTiming(**timing_data))
        
        # Parse duration
        try:
            duration = float(duration_str)
        except ValueError:
            return VideoGenerationResult(
                enabled=True,
                prompt_used=f"[Transition]: {line}",
                timestamp=datetime.now().isoformat(),
                api_info={},
                cost=0.0,
                error=f"Invalid duration: {duration_str}"
            )
        
        # Generate video
        return await self.generate_transition_video(
            line=line,
            rebased_timings=rebased_timings,
            duration=duration,
            conv_id=conv_id,
            backtest_id=backtest_id,
            style_id=style_id
        )

    async def generate_transition_video(
        self,
        line: str,
        rebased_timings: List[WordTiming],
        duration: float,
        conv_id: str,
        backtest_id: str,
        style_id: Optional[str] = None,
        layout_seed: Optional[int] = None
    ) -> VideoGenerationResult:
        """
        Generate transition video for given text and timing data using Node.js server
        
        Args:
            line: Text line to render
            rebased_timings: Word timing data
            duration: Video duration in seconds
            conv_id: Conversation ID for file naming
            backtest_id: Backtest ID for file organization
            style_id: Transition style ID (uses default if None)
            layout_seed: Random seed for layout (generates random if None)
            
        Returns:
            VideoGenerationResult with video info or error details
        """
        try:
            if not line.strip():
                raise TransitionVideoGenerationError("No line text provided")
            
            if not rebased_timings:
                raise TransitionVideoGenerationError("No timing data provided")
            
            # Extract words and start times
            words, start_times = self._extract_words_and_times(rebased_timings)
            
            if not words:
                raise TransitionVideoGenerationError("No words found in timing data")
            
            # Load transition style
            style_data = await self._get_style_data(style_id)
            
            # Generate layout seed if not provided
            if layout_seed is None:
                layout_seed = random.randint(1, 1000000)
            
            # Ensure server is running
            await self.ensure_server_running()
            
            # Create output path
            videos_dir = settings.BACKTEST_RESULTS_FOLDER / backtest_id / "videos"
            videos_dir.mkdir(parents=True, exist_ok=True)
            output_filename = f"{conv_id}_transition.mp4"
            output_path = videos_dir / output_filename
            
            # Prepare render request
            render_request = {
                "words": words,
                "startTimes": start_times,
                "duration": duration,
                "fps": self.fps,
                "width": self.width,
                "height": self.height,
                "style": {
                    "fontFamily": style_data.get("fontFamily", "Times New Roman, serif"),
                    "fontSize": style_data.get("fontSize", 48),
                    "fontColor": style_data.get("fontColor", "#000000"),
                    "backgroundColor": style_data.get("backgroundColor", "#ffffff"),
                    "fontWeight": style_data.get("fontWeight", "normal"),
                    "glow": style_data.get("glow", {}),
                    "layout": style_data.get("layout", {})
                },
                "layoutSeed": layout_seed,
                "outputPath": str(output_path)
            }
            
            logger.info(f"Sending render request to Node.js server: {json.dumps(render_request, indent=2)}")
            
            # Send request to Node.js server
            async with httpx.AsyncClient(timeout=self.server_timeout) as client:
                response = await client.post(
                    f"{self.server_url}/render",
                    json=render_request
                )
                
                if response.status_code != 200:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error": response.text}
                    raise TransitionVideoGenerationError(f"Render server error: {error_data}")
                
                result = response.json()
                logger.info(f"Render server response: {json.dumps(result, indent=2)}")
                
                if not result.get("success"):
                    raise TransitionVideoGenerationError(f"Render failed: {result.get('error', 'Unknown error')}")
            
            return VideoGenerationResult(
                enabled=True,
                video_path=f"videos/{output_filename}",
                prompt_used=f"[Transition]: {line}",
                timestamp=datetime.now().isoformat(),
                api_info={
                    "model": "remotion/transition_video",
                    "duration": str(duration),
                    "fps": self.fps,
                    "resolution": f"{self.width}x{self.height}",
                    "style_id": style_id,
                    "layout_seed": layout_seed,
                    "render_time_ms": result.get("renderTimeMs"),
                    "file_size": result.get("fileSize")
                },
                cost=calc_video_cost()
            )
            
        except Exception as e:
            return VideoGenerationResult(
                enabled=True,
                prompt_used=f"[Transition]: {line}",
                timestamp=datetime.now().isoformat(),
                api_info={},
                cost=0.0,
                error=f"Transition video generation failed: {str(e)}"
            )
    
    def _extract_words_and_times(self, timings: List[WordTiming]) -> tuple[List[str], List[float]]:
        """Extract individual words and their start times - let frontend handle grouping"""
        individual_words = []
        start_times = []
        
        for timing in timings:
            # Use punctuated_word if available, otherwise word
            word = timing.punctuated_word or timing.word
            if not word:
                continue
            
            individual_words.append(word)
            start_times.append(timing.start)
        
        return individual_words, start_times
    
    async def _get_style_data(self, style_id: Optional[str]) -> Dict[str, Any]:
        """Get transition style data"""
        if style_id:
            style = await transition_style_service.get_style(style_id)
            if style:
                return style
        
        # Fallback to default style
        default_style = await transition_style_service.get_style("default")
        if default_style:
            return default_style
        
        # Hard fallback if default doesn't exist
        return {
            "fontFamily": "Times New Roman, serif",
            "fontSize": 48,
            "fontColor": "#000000",
            "backgroundColor": "#ffffff",
            "fontWeight": "normal",
            "glow": {},
            "layout": {
                "mode": "centered",
                "avgStepPct": 6,
                "jitterPct": 3,
                "safeLeftPct": 10,
                "safeRightPct": 90,
                "accent": "longestWord",
                "accentColor": "#6AB0A1",
                "accentScale": 1.05,
                "accentBold": True,
                "startTopPct": 30,
                "lineHeight": 1.4,
                "relativeOffsets": []
            }
        }


# Singleton instance
transition_video_service = TransitionVideoService()