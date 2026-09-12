"""
Backtest orchestrator service for managing parallel execution
"""

import asyncio
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
# Removed ThreadPoolExecutor - using asyncio instead

from app.core.config import settings
from app.utils.costs import CostTracker

from .storage import (
    save_backtest_result,
    update_backtest_status,
    load_backtest_variations
)
from .execution_service import execution_service
from .video_processing_service import video_processing_service
from app.features.transition_video.service import transition_video_service

# Set up logging
logger = logging.getLogger(__name__)

# Using asyncio tasks instead of thread pool


class BacktestOrchestrator:
    """Service for orchestrating backtest execution"""
    
    def run_backtest(
        self,
        sequence: List[Dict[str, Any]], 
        name: Optional[str] = None, 
        description: str = '', 
        selected_groups: Optional[List[str]] = None, 
        transition_style_id: str = 'isenberg',
        video_resolution: str = '512P'
    ) -> Dict[str, Any]:
        """Start a new backtest execution"""
        
        # Generate backtest ID
        backtest_id = f"{name.lower().replace(' ', '_') if name else 'backtest'}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"BACKTEST_ORCHESTRATOR_START: Starting backtest {backtest_id} with {len(sequence)} messages")
        
        # Load variations
        variations = load_backtest_variations(selected_groups)
        logger.info(f"BACKTEST_ORCHESTRATOR_VARIATIONS: Loaded {len(variations)} variations for backtest {backtest_id}")
        
        if not variations:
            error_msg = "No variations found for the selected groups"
            logger.error(f"BACKTEST_ORCHESTRATOR_ERROR: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Create metadata
        metadata = {
            'id': backtest_id,
            'name': name or 'Untitled Backtest',
            'description': description,
            'created': datetime.now().isoformat(),
            'sequence': sequence,
            'variations': {k: v.get('variables', {}) for k, v in variations.items()},
            'status': 'pending',
            'transition_style_id': transition_style_id,
            'video_resolution': video_resolution
        }
        
        # Save initial metadata
        save_backtest_result(backtest_id, metadata)
        logger.info(f"BACKTEST_ORCHESTRATOR_METADATA: Saved initial metadata for {backtest_id}")
        
        # Start async task for background execution
        task = asyncio.create_task(
            self._execute_backtest_async(
                backtest_id,
                sequence,
                name or 'Untitled Backtest',
                description,
                variations,
                transition_style_id,
                video_resolution
            )
        )
        
        logger.info(f"BACKTEST_ORCHESTRATOR_SUBMITTED: Started async task for backtest {backtest_id}")
        
        # Add completion callback
        def completion_callback(task):
            try:
                if task.exception():
                    raise task.exception()
                logger.info(f"BACKTEST_ORCHESTRATOR_COMPLETE: Backtest {backtest_id} completed successfully")
                update_backtest_status(backtest_id, 'completed')
            except Exception as e:
                logger.error(f"BACKTEST_ORCHESTRATOR_FAILED: Backtest {backtest_id} failed: {e}")
                update_backtest_status(backtest_id, 'failed', str(e))
        
        task.add_done_callback(completion_callback)
        
        return {
            'success': True,
            'backtest_id': backtest_id,
            'status': 'pending',
            'message': f'Backtest started with {len(variations)} variations',
            'variation_count': len(variations),
            'message_count': len(sequence)
        }

    async def _execute_backtest_async(
        self,
        backtest_id: str, 
        sequence: List[Dict[str, Any]], 
        name: str, 
        description: str, 
        variations: Dict[str, Dict[str, Any]], 
        transition_style_id: str = 'isenberg',
        video_resolution: str = '512P'
    ) -> None:
        """Execute backtest in background thread"""
        logger.info(f"BACKTEST_ASYNC_START: Starting async execution for {backtest_id}")
        
        try:
            update_backtest_status(backtest_id, 'in_progress', progress=0)
            logger.info(f"BACKTEST_ASYNC_STATUS: Set status to in_progress for {backtest_id}")
            
            # Execute backtest for each variation
            conversations = {}
            total_variations = len(variations)
            
            logger.info(f"BACKTEST_ASYNC_VARIATIONS: Processing {total_variations} variations for {backtest_id}")
            
            # Process all variations in parallel using asyncio
            logger.info(f"BACKTEST_ASYNC_PARALLEL: Creating {total_variations} async tasks")
            
            # Create all variation tasks
            variation_tasks = []
            variation_names = []
            for variation_name, variation_data in variations.items():
                task = asyncio.create_task(
                    self._process_variation(
                        variation_name, variation_data, sequence, backtest_id, transition_style_id, video_resolution
                    )
                )
                variation_tasks.append(task)
                variation_names.append(variation_name)
            
            logger.info(f"BACKTEST_ASYNC_SUBMITTED: Created {len(variation_tasks)} async tasks")
            
            # Collect results as they complete
            for idx, task in enumerate(asyncio.as_completed(variation_tasks)):
                try:
                    conversation_data = await task
                    variation_name = conversation_data['variation_name']
                    conversations[conversation_data['id']] = conversation_data
                    logger.info(f"BACKTEST_ASYNC_SUCCESS: Variation {variation_name} completed successfully ({idx+1}/{total_variations})")
                    
                    # Update progress
                    progress = int(((idx + 1) / total_variations) * 100)
                    update_backtest_status(backtest_id, 'in_progress', progress=progress)
                    logger.info(f"BACKTEST_ASYNC_PROGRESS: Progress updated to {progress}% for {backtest_id}")
                    
                except Exception as e:
                    logger.error(f"BACKTEST_ASYNC_VAR_FAILED: Variation failed: {e}")
                    # Try to identify which variation failed
                    variation_name = "unknown"
                    # Create error conversation
                    conv_id = f'{variation_name}_{backtest_id}'
                    conversations[conv_id] = {
                        'id': conv_id,
                        'variation_name': variation_name,
                        'variables': {},
                        'created': datetime.now().isoformat(),
                        'updated': datetime.now().isoformat(),
                        'messages': [{
                            'role': 'assistant',
                            'content': f'Variation failed: {str(e)}',
                            'timestamp': datetime.now().isoformat(),
                            'error': True
                        }],
                        'costs': {} # No costs for failed variations
                    }
            
            # Aggregate costs across conversations
            total_costs = {'llm_cost': 0.0, 'image_cost': 0.0, 'video_cost': 0.0, 'total': 0.0}
            for conv_data in conversations.values():
                if 'costs' in conv_data:
                    for k in total_costs:
                        total_costs[k] += conv_data['costs'].get(k, 0.0)

            logger.info(f"BACKTEST_ASYNC_COSTS: Total costs calculated: {total_costs}")

            metadata = {
                'id': backtest_id,
                'name': name,
                'description': description,
                'created': datetime.now().isoformat(),
                'sequence': sequence,
                'variations': {name: data.get('variables', {}) for name, data in variations.items()},
                'conversation_ids': list(conversations.keys()),
                'costs': total_costs,
                'total_cost': total_costs['total'],
                'status': 'completed',
                'transition_style_id': transition_style_id,
                'video_resolution': video_resolution
            }
            
            save_backtest_result(backtest_id, metadata, conversations)
            update_backtest_status(backtest_id, 'completed', progress=100)
            
            logger.info(f"BACKTEST_ASYNC_FINAL: Saved final results for {backtest_id}")
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"BACKTEST_ASYNC_ERROR: Backtest {backtest_id} failed: {error_message}")
            update_backtest_status(backtest_id, 'failed', error_message=error_message)
            
            # Save partial metadata even on failure
            try:
                metadata = {
                    'id': backtest_id,
                    'name': name,
                    'description': description,
                    'created': datetime.now().isoformat(),
                    'sequence': sequence,
                    'variations': {name: data.get('variables', {}) for name, data in variations.items()},
                    'status': 'failed',
                    'error_message': error_message,
                    'transition_style_id': transition_style_id,
                    'video_resolution': video_resolution
                }
                save_backtest_result(backtest_id, metadata)
                logger.info(f"BACKTEST_ASYNC_PARTIAL: Saved partial metadata for failed backtest {backtest_id}")
            except Exception:
                logger.error(f"BACKTEST_ASYNC_CRITICAL: Could not save partial metadata for {backtest_id}")
                pass

    async def _process_variation(
        self,
        variation_name: str, 
        variation_data: Dict[str, Any],
        sequence: List[Dict[str, Any]],
        backtest_id: str,
        transition_style_id: str = 'isenberg',
        video_resolution: str = '512P'
    ) -> Dict[str, Any]:
        """Process a single variation - can be run in parallel"""
        
        logger.info(f"BACKTEST_VARIATION_START: Processing variation {variation_name} for backtest {backtest_id}")
        
        # Generate conversation ID for this variation
        conv_id = f'{variation_name}_{backtest_id}'
        
        # Extract variables from variation data
        variables = variation_data.get('variables', {})
        logger.info(f"BACKTEST_VARIATION_VARS: Variation {variation_name} has variables: {list(variables.keys())}")
        
        # Check if this is a transition-only variation
        cost_tracker = CostTracker()

        if variation_data.get('variation_type') == 'transition_only':
            logger.info(f"BACKTEST_VARIATION_TRANSITION: Processing transition-only variation {variation_name}")
            
            # Generate transition video using the new service
            try:
                # Use async directly - no need for new event loop
                video_result = await transition_video_service.generate_from_variables(
                    variables=variables,
                    conv_id=conv_id,
                    backtest_id=backtest_id,
                    style_id=transition_style_id
                )
                    
                # Track video cost
                if cost_tracker is not None and video_result.cost > 0:
                    cost_tracker.add_video_usage()
                    
                # Create conversation messages
                conversation_messages = [{
                        'role': 'assistant',
                        'content': f'[Transition Video]: {variables.get("line", "Generated transition video")}',
                        'timestamp': datetime.now().isoformat(),
                        'generated_video': video_result.model_dump()
                    }]
                    

                    
            except Exception as e:
                logger.error(f"BACKTEST_VARIATION_TRANSITION_ERROR: Failed to generate transition video for {variation_name}: {e}")
                conversation_messages = [{
                    'role': 'assistant',
                    'content': f'[Transition Video Error]: {str(e)}',
                    'timestamp': datetime.now().isoformat(),
                    'generated_video': {
                        'enabled': True,
                        'error': f'Transition video generation failed: {str(e)}',
                        'timestamp': datetime.now().isoformat(),
                        'cost': 0.0
                    }
                }]
            
            # Return conversation data
            return {
                'id': conv_id,
                'variation_name': variation_name,
                'variables': variables,
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat(),
                'messages': conversation_messages,
                'costs': cost_tracker.to_dict()
            }
        
        # Execute message sequence
        conversation_messages = []
        
        logger.info(f"BACKTEST_VARIATION_SEQUENCE: Processing {len(sequence)} messages for variation {variation_name}")
        
        for msg_idx, message_config in enumerate(sequence):
            logger.info(f"BACKTEST_VARIATION_MSG: Processing message {msg_idx+1}/{len(sequence)} for variation {variation_name}")
            
            try:
                # Use async version directly
                assistant_msg = await execution_service.execute_single_turn(
                    message_config,
                    variables,
                    conversation_messages,
                    sequence,
                    conv_id,
                    backtest_id,
                    cost_tracker
                )
                
                if assistant_msg is None:
                    logger.warning(f"BACKTEST_VARIATION_SKIP: Skipped empty message {msg_idx+1} for variation {variation_name}")
                    conversation_messages.append({
                        'role': 'assistant',
                        'content': f'Skipped empty message: {message_config.get("message", "Unknown")}',
                        'timestamp': datetime.now().isoformat(),
                        'error': True
                    })
                    continue
                
                logger.info(f"BACKTEST_VARIATION_MSG_SUCCESS: Message {msg_idx+1} processed successfully for variation {variation_name}")
                
            except Exception as e:
                logger.error(f"BACKTEST_VARIATION_MSG_ERROR: Message {msg_idx+1} failed for variation {variation_name}: {e}")
                # Add error message to conversation
                conversation_messages.append({
                    'role': 'assistant',
                    'content': f'Error processing message {msg_idx+1}: {str(e)}',
                    'timestamp': datetime.now().isoformat(),
                    'error': True
                })
                continue
            
            # Process video generation if enabled
            try:
                logger.info(f"BACKTEST_VARIATION_VIDEO: Processing video generation for message {msg_idx+1} in variation {variation_name}")
                
                await video_processing_service.process_video_generation(
                    message_config,
                    assistant_msg.get('content', ''),
                    conversation_messages,
                    conv_id,
                    backtest_id,
                    assistant_msg,
                    cost_tracker,
                    video_resolution
                )
                
                logger.info(f"BACKTEST_VARIATION_VIDEO_SUCCESS: Video processing completed for message {msg_idx+1} in variation {variation_name}")
                
            except Exception as e:
                logger.error(f"BACKTEST_VARIATION_VIDEO_ERROR: Video processing failed for message {msg_idx+1} in variation {variation_name}: {e}")
                # Continue execution even if video fails
                pass
        
        logger.info(f"BACKTEST_VARIATION_COMPLETE: Completed variation {variation_name} with {len(conversation_messages)} messages")
        
        # Return conversation data
        return {
            'id': conv_id,
            'variation_name': variation_name,
            'variables': variables,
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat(),
            'messages': conversation_messages,
            'costs': cost_tracker.to_dict()
        }


# Singleton instance
backtest_orchestrator = BacktestOrchestrator() 