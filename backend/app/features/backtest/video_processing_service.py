"""
Video processing service for backtest video generation
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.services_clients.openrouter_client import openrouter_client
from app.features.video_generation.service import video_service
from app.utils.costs import CostTracker

import logging

# Set up logging
logger = logging.getLogger(__name__)


class VideoProcessingService:
    """Service for video processing in backtests"""
    
    # Removed sync wrapper - use async directly
    
    async def process_video_generation(
        self,
        message_config: Dict[str, Any],
        assistant_content: str,
        conversation_messages: List[Dict[str, Any]],
        conv_id: str,
        backtest_id: str,
        assistant_msg: Dict[str, Any],
        cost_tracker: Optional[CostTracker] = None,
        video_resolution: str = "512P"
    ) -> None:
        """Process video generation for a message"""
        if not message_config.get('generate_video', False):
            return
            
        logger.info(f"VIDGEN: Video generation enabled for message in {conv_id}")
        
        # Get the model parameters for follow-up calls
        model = message_config.get('model', 'x-ai/grok-4')
        temperature = float(message_config.get('temperature', 1.0))
        max_tokens = message_config.get('max_tokens')
        reasoning_enabled = message_config.get('reasoning_enabled', False)
        reasoning_param = message_config.get('reasoning_param')
        
        if max_tokens:
            max_tokens = int(max_tokens)
        
        # Process video prompt (shorten if needed)
        video_prompt = await self._process_video_prompt(
            assistant_content,
            conversation_messages,
            model, temperature, max_tokens,
            reasoning_enabled, reasoning_param
        )
        
        # Find source image for video
        source_image_data = self._find_source_image_for_video(
            conversation_messages=conversation_messages,
            message_index=len(conversation_messages) - 1,
            backtest_id=backtest_id
        )
        
        if source_image_data:
            # Load image bytes from the image metadata
            image_path = source_image_data.get('image_path')
            if not image_path:
                logger.error(f"VIDGEN: Source image has no image_path: {source_image_data}")
                assistant_msg['generated_video'] = {
                    "enabled": True,
                    "error": "Source image missing image_path",
                    "prompt_used": video_prompt,
                    "timestamp": datetime.now().isoformat()
                }
                return
            
            # Load image bytes from file
            from app.core.config import settings
            full_image_path = settings.BACKTEST_RESULTS_FOLDER / backtest_id / image_path
            
            try:
                with open(full_image_path, 'rb') as img_file:
                    image_bytes = img_file.read()
                    
                logger.info(f"VIDGEN: Loaded {len(image_bytes)} bytes from {image_path}")
                
                # Use the correct method name
                video_result = await video_service.generate_video_for_message(
                    prompt=video_prompt,
                    image_data=image_bytes,
                    conv_id=conv_id,
                    message_index=len(conversation_messages) - 1,
                    backtest_id=backtest_id,
                    resolution=video_resolution
                )
                
                if video_result and not video_result.get('error'):
                    # Attach video to the original assistant message (not follow-ups)
                    assistant_msg['generated_video'] = video_result
                    # Track video cost (fixed per video)
                    if cost_tracker is not None:
                        cost_tracker.add_video_usage()
                else:
                    logger.error(f"VIDGEN: Video generation failed: {video_result}")
                    assistant_msg['generated_video'] = video_result or {
                        "enabled": True,
                        "error": "Video generation returned no result",
                        "prompt_used": video_prompt,
                        "timestamp": datetime.now().isoformat()
                    }
                    
            except Exception as e:
                logger.error(f"VIDGEN: Failed to load image from {image_path}: {e}")
                assistant_msg['generated_video'] = {
                    "enabled": True,
                    "error": f"Failed to load source image: {str(e)}",
                    "prompt_used": video_prompt,
                    "timestamp": datetime.now().isoformat()
                }
        else:
            logger.info(f"VIDGEN: No source image found for video generation in {conv_id}")
            assistant_msg['generated_video'] = {
                "enabled": True,
                "error": "No source image found for video generation",
                "prompt_used": video_prompt,
                "timestamp": datetime.now().isoformat()
            }

    async def _process_video_prompt(
        self,
        assistant_content: str,
        conversation_messages: List[Dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        reasoning_enabled: bool,
        reasoning_param: Optional[Any]
    ) -> str:
        """Process video prompt, shortening if necessary"""
        video_prompt = assistant_content
        max_retries = 3
        retry_count = 0
        
        while len(video_prompt) > 2000 and retry_count < max_retries:
            retry_count += 1
            logger.info(f"VIDGEN: Response too long ({len(video_prompt)} chars), attempt {retry_count}/{max_retries}")
            
            # Send automatic follow-up message to get shorter version
            follow_up_message = (
                f"The prompt for the video generation model can be a max of 2000 characters. "
                f"Yours was {len(video_prompt)}. Please rewrite the prompt to make sure it's "
                f"under 2000 characters while maintaining as much detail as you can. "
                f"Output just the updated prompt, do not output any other explanation or "
                f"acknowledgement of this message"
            )
            
            # Add follow-up user message
            follow_up_user_msg = {
                'role': 'user',
                'content': follow_up_message,
                'timestamp': datetime.now().isoformat(),
                'model_info': {
                    'model': model,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                    'reasoning_enabled': reasoning_enabled,
                    'reasoning_param': reasoning_param
                },
                'auto_validation': True  # Mark as auto-generated
            }
            conversation_messages.append(follow_up_user_msg)
            
            # Build messages for API call including the follow-up
            messages_for_followup = []
            for msg in conversation_messages:
                if msg['role'] == 'user':
                    messages_for_followup.append({
                        'role': 'user',
                        'content': [{'type': 'text', 'text': msg['content']}]
                    })
                elif msg['role'] == 'assistant':
                    messages_for_followup.append({
                        'role': 'assistant',
                        'content': msg['content']
                    })
            
            try:
                # Call API for follow-up response using async client instead of blocking requests
                result = await openrouter_client.simple_chat(
                    messages_for_followup,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    reasoning_enabled=reasoning_enabled,
                    reasoning_param=reasoning_param,
                    timeout=300.0,
                )
                
                # Extract follow-up response
                follow_up_content = ""
                follow_up_reasoning = ""
                
                if result.get('choices') and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    message = choice.get('message', {})
                    follow_up_content = message.get('content', '')
                    follow_up_reasoning = message.get('reasoning', '')
                
                # Store follow-up assistant message
                follow_up_assistant_msg = {
                    'role': 'assistant',
                    'content': follow_up_content,
                    'timestamp': datetime.now().isoformat(),
                    'model_info': {
                        'model': model,
                        'temperature': temperature,
                        'max_tokens': max_tokens,
                        'reasoning_enabled': reasoning_enabled,
                        'reasoning_param': reasoning_param
                    },
                    'auto_validation': True  # Mark as auto-generated
                }
                
                if follow_up_reasoning:
                    follow_up_assistant_msg['reasoning_content'] = follow_up_reasoning
                
                conversation_messages.append(follow_up_assistant_msg)
                
                # Update video_prompt for next iteration check
                video_prompt = follow_up_content
                
                if len(video_prompt) <= 2000:
                    logger.info(f"VIDGEN: Successfully shortened prompt to {len(video_prompt)} chars on attempt {retry_count}")
                    break
                else:
                    logger.info(f"VIDGEN: Attempt {retry_count} still too long ({len(video_prompt)} chars), retrying...")
                
            except Exception as e:
                logger.error(f"VIDGEN: Failed to get shortened prompt on attempt {retry_count}: {e}")
                break  # Exit retry loop on API error
        
        # Final fallback if all retries failed
        if len(video_prompt) > 2000:
            logger.info(f"VIDGEN: Failed to shorten prompt after {max_retries} attempts, truncating to 2000 chars")
            video_prompt = video_prompt[:2000]
        
        return video_prompt

    def _find_source_image_for_video(
        self,
        conversation_messages: List[Dict[str, Any]], 
        message_index: int, 
        backtest_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find the most recent image marked for video use"""
        logger.info(f"VIDGEN_DEBUG: Looking for source image, checking {message_index + 1} messages")
        
        # Look backwards from current message for images marked with use_for_video
        for i in range(message_index, -1, -1):
            if i < len(conversation_messages):
                msg = conversation_messages[i]
                logger.info(f"VIDGEN_DEBUG: Message {i} - role: {msg.get('role')}, has_image: {bool(msg.get('generated_image'))}")
                
                if msg.get('generated_image'):
                    use_for_video = msg['generated_image'].get('use_for_video', False)
                    image_path = msg['generated_image'].get('image_path', 'no_path')
                    logger.info(f"VIDGEN_DEBUG: Message {i} image - use_for_video: {use_for_video}, path: {image_path}")
                
                if (msg.get('role') == 'assistant' and 
                    msg.get('generated_image') and 
                    msg['generated_image'].get('use_for_video', False)):
                    logger.info(f"VIDGEN_DEBUG: Found source image at message {i} for video generation")
                    return msg['generated_image']
        
        logger.info(f"VIDGEN_DEBUG: No images with use_for_video=True found in {message_index + 1} messages")
        return None


# Singleton instance
video_processing_service = VideoProcessingService() 