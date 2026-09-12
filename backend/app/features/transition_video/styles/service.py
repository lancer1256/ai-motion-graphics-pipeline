"""
Transition Styles Management Service
Handles CRUD operations for transition video styles
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

from app.core.config import settings

# Transition styles storage directory
TRANSITION_STYLES_FOLDER = settings.BASE_DIR / "data" / "transition_styles"
TRANSITION_STYLES_FOLDER.mkdir(parents=True, exist_ok=True)

DEFAULT_STYLE_ID = "default"


class TransitionStyleService:
    """Service for handling transition style CRUD operations"""
    
    def _create_default_style(self):
        """Create the default transition style if it doesn't exist"""
        default_style = {
            "id": DEFAULT_STYLE_ID,
            "name": "Default",
            "fontFamily": "Times New Roman, serif",
            "fontSize": 48,
            "fontColor": "#000000",
            "backgroundColor": "#ffffff",
            "layout": {
                "mode": "centered",
                "avgStepPct": 6,
                "jitterPct": 3,
                "safeLeftPct": 10,
                "safeRightPct": 90,
                "accent": "longestWord",
                "accentColor": "#6AB0A1",
                "accentScale": 1.05,
                "startTopPct": 30,
                "lineHeight": 1.4,
                "relativeOffsets": []
            },
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "is_default": True
        }
        
        default_path = TRANSITION_STYLES_FOLDER / f"{DEFAULT_STYLE_ID}.json"
        if not default_path.exists():
            with open(default_path, 'w') as f:
                json.dump(default_style, f, indent=2)
        
        return default_style

    async def list_styles(self) -> List[Dict[str, Any]]:
        """List all available transition styles"""
        try:
            styles = []
            
            
            for style_file in TRANSITION_STYLES_FOLDER.glob("*.json"):
                try:
                    with open(style_file, 'r') as f:
                        style = json.load(f)
                        styles.append(style)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"TRANSITION_STYLES: Error loading {style_file}: {e}")
                    continue
            
            # Sort by name, with default first
            styles.sort(key=lambda s: (not s.get('is_default', False), s.get('name', '')))
            
            return styles
            
        except Exception as e:
            print(f"TRANSITION_STYLES: Error listing styles: {e}")
            return [self._create_default_style()]

    async def get_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific transition style by ID"""
        try:
            style_path = TRANSITION_STYLES_FOLDER / f"{style_id}.json"
            
            if not style_path.exists():
                if style_id == DEFAULT_STYLE_ID:
                    return self._create_default_style()
                return None
            
            with open(style_path, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"TRANSITION_STYLES: Error getting style {style_id}: {e}")
            if style_id == DEFAULT_STYLE_ID:
                return self._create_default_style()
            return None

    async def save_style(self, style_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a transition style (create new or update existing)"""
        try:
            # Generate ID if not provided
            if not style_data.get('id'):
                style_data['id'] = str(uuid.uuid4())
            
            # Validate required fields
            required_fields = ['name', 'fontFamily', 'fontSize', 'fontColor', 'backgroundColor']
            for field in required_fields:
                if field not in style_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate font size
            if not isinstance(style_data['fontSize'], (int, float)) or style_data['fontSize'] <= 0:
                raise ValueError("fontSize must be a positive number")
            
            # Validate colors (basic hex validation)
            for color_field in ['fontColor', 'backgroundColor']:
                color = style_data[color_field]
                if not isinstance(color, str) or not color.startswith('#') or len(color) not in [4, 7]:
                    raise ValueError(f"{color_field} must be a valid hex color")
            
            # Ensure layout object exists with defaults
            if 'layout' not in style_data:
                style_data['layout'] = {
                    "mode": "centered",
                    "avgStepPct": 6,
                    "jitterPct": 3,
                    "safeLeftPct": 10,
                    "safeRightPct": 90,
                    "accent": "longestWord",
                    "accentColor": "#6AB0A1",
                    "accentScale": 1.05,
                    "startTopPct": 30,
                    "lineHeight": 1.4,
                    "relativeOffsets": []
                }
            else:
                # Validate layout configuration
                layout = style_data['layout']
                
                # Validate mode
                valid_modes = ['centered', 'diagonalDrift', 'relativeOffsets', 'relativeToCenterOffsets']
                if layout.get('mode') not in valid_modes:
                    raise ValueError(f"layout.mode must be one of: {', '.join(valid_modes)}")
                
                # Validate numeric ranges
                numeric_validations = [
                    ('avgStepPct', 0, 20, "layout.avgStepPct must be between 0 and 20"),
                    ('jitterPct', 0, 20, "layout.jitterPct must be between 0 and 20"),
                    ('safeLeftPct', 0, 100, "layout.safeLeftPct must be between 0 and 100"),
                    ('safeRightPct', 0, 100, "layout.safeRightPct must be between 0 and 100"),
                    ('accentScale', 0.5, 3.0, "layout.accentScale must be between 0.5 and 3.0"),
                    ('startTopPct', 0, 100, "layout.startTopPct must be between 0 and 100"),
                    ('lineHeight', 0.5, 3.0, "layout.lineHeight must be between 0.5 and 3.0")
                ]
                
                for field, min_val, max_val, error_msg in numeric_validations:
                    if field in layout:
                        if not isinstance(layout[field], (int, float)) or not (min_val <= layout[field] <= max_val):
                            raise ValueError(error_msg)
                
                # Validate accent mode
                if layout.get('accent') not in ['none', 'longestWord', 'manual']:
                    raise ValueError("layout.accent must be 'none', 'longestWord', or 'manual'")
                
                # Validate accent color
                if 'accentColor' in layout:
                    accent_color = layout['accentColor']
                    if not isinstance(accent_color, str) or not accent_color.startswith('#') or len(accent_color) not in [4, 7]:
                        raise ValueError("layout.accentColor must be a valid hex color")
                
                # Validate relativeOffsets array
                if 'relativeOffsets' in layout:
                    offsets = layout['relativeOffsets']
                    if not isinstance(offsets, list):
                        raise ValueError("layout.relativeOffsets must be an array")
                    if not all(isinstance(x, (int, float)) for x in offsets):
                        raise ValueError("layout.relativeOffsets must contain only numbers")
                    if len(offsets) > 50:  # Reasonable limit
                        raise ValueError("layout.relativeOffsets cannot have more than 50 values")
            
            # Set timestamps
            now = datetime.now().isoformat()
            if 'created' not in style_data:
                style_data['created'] = now
            style_data['updated'] = now
            
            # Don't allow overwriting default style's core properties
            if style_data['id'] == DEFAULT_STYLE_ID:
                style_data['is_default'] = True
                style_data['name'] = 'Default'
            
            # Save to file
            style_path = TRANSITION_STYLES_FOLDER / f"style_{style_data['id']}.json"
            with open(style_path, 'w') as f:
                json.dump(style_data, f, indent=2)
            
            print(f"TRANSITION_STYLES: Saved style '{style_data['name']}' to {style_path}")
            return style_data
            
        except Exception as e:
            print(f"TRANSITION_STYLES: Error saving style: {e}")
            raise

    async def delete_style(self, style_id: str) -> bool:
        """Delete a transition style by ID"""
        try:
            # Don't allow deleting default style
            if style_id == DEFAULT_STYLE_ID:
                raise ValueError("Cannot delete the default style")
            
            style_path = TRANSITION_STYLES_FOLDER / f"style_{style_id}.json"
            
            if not style_path.exists():
                return False
            
            # Check if style is in use by any pending backtests
            if await self._is_style_in_use(style_id):
                raise ValueError("Cannot delete style that is currently in use by pending backtests")
            
            style_path.unlink()
            print(f"TRANSITION_STYLES: Deleted style {style_id}")
            return True
            
        except Exception as e:
            print(f"TRANSITION_STYLES: Error deleting style {style_id}: {e}")
            raise

    async def _is_style_in_use(self, style_id: str) -> bool:
        """Check if a style is currently in use by any pending backtests"""
        try:
            # Import here to avoid circular imports
            from app.services.conversation_storage import BACKTEST_RESULTS_FOLDER
            
            if not BACKTEST_RESULTS_FOLDER.exists():
                return False
            
            # Check all backtest metadata files
            for backtest_folder in BACKTEST_RESULTS_FOLDER.iterdir():
                if not backtest_folder.is_dir():
                    continue
                    
                metadata_file = backtest_folder / 'metadata.json'
                if not metadata_file.exists():
                    continue
                    
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if this backtest is pending/in_progress and uses this style
                    if (metadata.get('status') in ['pending', 'in_progress'] and 
                        metadata.get('transition_style_id') == style_id):
                        return True
                        
                except (json.JSONDecodeError, IOError):
                    continue
            
            return False
            
        except Exception as e:
            print(f"TRANSITION_STYLES: Error checking if style is in use: {e}")
            return False


# Singleton instance
transition_style_service = TransitionStyleService() 