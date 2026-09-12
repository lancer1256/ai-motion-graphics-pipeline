"""FastAPI routes for video generation feature"""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse
from typing import Optional
import tempfile
import json

from .service import video_service
from .schemas import VideoThumbnailResponse, VideoConcatResponse
from .utils import generate_video_concat
from app.core.config import settings

router = APIRouter()


@router.get("/{backtest_id}/video/{video_path:path}/thumbnail", response_model=VideoThumbnailResponse)
async def get_video_thumbnail(
    backtest_id: str = Path(..., description="Backtest ID"),
    video_path: str = Path(..., description="Relative path to video within backtest")
):
    """Return base64 thumbnail data (placeholder for now)."""
    thumbnail = await video_service.get_video_thumbnail(backtest_id, video_path)
    if thumbnail is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoThumbnailResponse(success=True, thumbnail_data=thumbnail)


@router.get("/{backtest_id}/video/{video_path:path}/full")
async def get_full_video(
    backtest_id: str = Path(..., description="Backtest ID"),
    video_path: str = Path(..., description="Relative path to video within backtest")
):
    """Serve full video file."""
    full_path = await video_service.get_full_video_path(backtest_id, video_path)
    if not full_path:
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path=full_path, media_type="video/mp4", filename=full_path.name)


@router.post("/{backtest_id}/videos/concat")
async def concatenate_backtest_videos(
    backtest_id: str = Path(..., description="Backtest ID")
):
    """Concatenate all videos from a backtest, sorted by timing."""
    try:
        # Load backtest data to get video paths and timing info
        backtest_folder = settings.BACKTEST_RESULTS_FOLDER / backtest_id
        if not backtest_folder.exists():
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        # Collect video paths with timing data
        video_info_list = []
        
        # Look for backtest result JSON to get timing information
        result_file = backtest_folder / "result.json"
        if result_file.exists():
            with open(result_file, 'r') as f:
                result_data = json.load(f)
            
            conversations = result_data.get('conversations', {})
            for conv_id, conv_data in conversations.items():
                # Get timing data for sorting
                variables = conv_data.get('variables', {})
                timings_str = variables.get('timings', '[]')
                
                try:
                    if isinstance(timings_str, str):
                        timings = json.loads(timings_str)
                    else:
                        timings = timings_str
                    
                    # Get start time of first word
                    first_word_start = float(timings[0]['start']) if timings else 0.0
                except (json.JSONDecodeError, IndexError, KeyError, ValueError):
                    first_word_start = 0.0
                
                # Find videos in this conversation
                for message in conv_data.get('messages', []):
                    generated_video = message.get('generated_video')
                    if generated_video and generated_video.get('video_path'):
                        video_path = generated_video['video_path']
                        full_path = await video_service.get_full_video_path(backtest_id, video_path)
                        
                        if full_path and full_path.exists():
                            video_info_list.append({
                                'path': full_path,
                                'timing_start': first_word_start,
                                'conv_id': conv_id
                            })
        
        if not video_info_list:
            raise HTTPException(status_code=404, detail="No videos found in this backtest")
        
        # Sort by timing start value
        video_info_list.sort(key=lambda x: x['timing_start'])
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_output:
            output_path = temp_output.name
        
        # Concatenate videos
        video_paths = [info['path'] for info in video_info_list]
        success, result_msg = generate_video_concat(video_paths, output_path)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Video concatenation failed: {result_msg}")
        
        # Return the concatenated video
        output_filename = f"backtest_{backtest_id}_concatenated.mp4"
        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename=output_filename,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error concatenating videos: {str(e)}") 