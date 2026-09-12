"""FastAPI router for transition video operations"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from .schemas import TransitionVideoRequest, TransitionVideoResponse
from .service import transition_video_service

router = APIRouter()


@router.post("/generate", response_model=TransitionVideoResponse)
async def generate_transition_video(
    request: TransitionVideoRequest,
    conv_id: str,
    backtest_id: str
):
    """
    Generate a transition video
    
    Args:
        request: Video generation request with text, timings, and style
        conv_id: Conversation ID for file naming
        backtest_id: Backtest ID for file organization
        
    Returns:
        TransitionVideoResponse with video result or error
    """
    try:
        response = await transition_video_service.generate_video(
            request=request,
            conv_id=conv_id,
            backtest_id=backtest_id
        )
        
        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.error
            )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate transition video: {str(e)}"
        )


@router.post("/generate-from-variables", response_model=TransitionVideoResponse)
async def generate_from_variables(
    variables: Dict[str, Any],
    conv_id: str,
    backtest_id: str,
    style_id: str = None
):
    """
    Generate transition video from backtest variables
    
    Args:
        variables: Dictionary containing line, rebased_timings, duration
        conv_id: Conversation ID
        backtest_id: Backtest ID
        style_id: Optional transition style ID
        
    Returns:
        TransitionVideoResponse with video result or error
    """
    try:
        result = await transition_video_service.generate_from_variables(
            variables=variables,
            conv_id=conv_id,
            backtest_id=backtest_id,
            style_id=style_id
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate transition video from variables: {str(e)}"
        )