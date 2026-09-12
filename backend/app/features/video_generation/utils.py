"""Utility helpers for video generation feature"""

import base64
from pathlib import Path
from typing import Tuple, List
import subprocess
import tempfile

from app.core.config import settings


def encode_svg_placeholder() -> str:
    """Return a simple SVG video placeholder as base64 data URL."""
    placeholder_svg = '''<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#f8f9fa"/>
        <circle cx="150" cy="100" r="30" fill="#667eea"/>
        <polygon points="140,85 140,115 165,100" fill="white"/>
        <text x="150" y="140" text-anchor="middle" font-family="Arial" font-size="12" fill="#666">Video Ready</text>
    </svg>'''
    svg_b64 = base64.b64encode(placeholder_svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{svg_b64}"


def generate_video_concat(concat_list: List[Path], output_path: Path) -> Tuple[bool, str]:
    """Concatenate multiple MP4 files using ffmpeg without re-encoding."""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            concat_file = Path(f.name)
            for p in concat_list:
                f.write(f"file '{p.as_posix()}'\n")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy', str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        concat_file.unlink(missing_ok=True)
        return True, str(output_path)
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode() if e.stderr else str(e) 