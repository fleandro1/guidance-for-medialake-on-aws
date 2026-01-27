"""FFmpeg utilities for video processing."""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from medialake_resolve.core.errors import FFmpegError


def get_bundled_ffmpeg_path() -> Optional[Path]:
    """Get the path to the bundled FFmpeg binary.
    
    Returns:
        Path to FFmpeg binary, or None if not found.
    """
    # Get the package directory
    package_dir = Path(__file__).parent.parent
    
    # Platform-specific binary names
    if sys.platform == "darwin":
        binary_name = "ffmpeg"
        binary_paths = [
            package_dir / "ffmpeg" / "bin" / binary_name,
            package_dir / "resources" / "ffmpeg" / binary_name,
        ]
    elif sys.platform == "win32":
        binary_name = "ffmpeg.exe"
        binary_paths = [
            package_dir / "ffmpeg" / "bin" / binary_name,
            package_dir / "resources" / "ffmpeg" / binary_name,
        ]
    else:
        binary_name = "ffmpeg"
        binary_paths = [
            package_dir / "ffmpeg" / "bin" / binary_name,
            package_dir / "resources" / "ffmpeg" / binary_name,
        ]
    
    # Check bundled paths
    for path in binary_paths:
        if path.exists():
            return path
    
    # Fall back to system FFmpeg
    try:
        result = subprocess.run(
            ["which", "ffmpeg"] if sys.platform != "win32" else ["where", "ffmpeg"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    
    return None


def get_bundled_ffprobe_path() -> Optional[Path]:
    """Get the path to the bundled FFprobe binary.
    
    Returns:
        Path to FFprobe binary, or None if not found.
    """
    # Get the package directory
    package_dir = Path(__file__).parent.parent
    
    # Platform-specific binary names
    if sys.platform == "win32":
        binary_name = "ffprobe.exe"
    else:
        binary_name = "ffprobe"
    
    binary_paths = [
        package_dir / "ffmpeg" / "bin" / binary_name,
        package_dir / "resources" / "ffmpeg" / binary_name,
    ]
    
    # Check bundled paths
    for path in binary_paths:
        if path.exists():
            return path
    
    # Fall back to system FFprobe
    try:
        result = subprocess.run(
            ["which", "ffprobe"] if sys.platform != "win32" else ["where", "ffprobe"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    
    return None


@dataclass
class MediaInfo:
    """Information about a media file."""
    
    duration: float  # seconds
    width: Optional[int]
    height: Optional[int]
    frame_rate: Optional[float]
    codec: Optional[str]
    audio_codec: Optional[str]
    bit_rate: Optional[int]
    format_name: str


class FFmpegHelper:
    """Helper class for FFmpeg operations.
    
    Provides utilities for:
    - Getting media file information
    - Generating thumbnails
    - Creating proxy files
    - Checking codec support
    """
    
    def __init__(self):
        """Initialize FFmpeg helper."""
        self._ffmpeg_path = get_bundled_ffmpeg_path()
        self._ffprobe_path = get_bundled_ffprobe_path()
    
    @property
    def is_available(self) -> bool:
        """Check if FFmpeg is available.
        
        Returns:
            True if FFmpeg is available.
        """
        return self._ffmpeg_path is not None
    
    @property
    def ffmpeg_path(self) -> Optional[Path]:
        """Get the FFmpeg binary path."""
        return self._ffmpeg_path
    
    @property
    def ffprobe_path(self) -> Optional[Path]:
        """Get the FFprobe binary path."""
        return self._ffprobe_path
    
    def get_media_info(self, file_path: str) -> MediaInfo:
        """Get information about a media file.
        
        Args:
            file_path: Path to the media file.
            
        Returns:
            MediaInfo with file details.
            
        Raises:
            FFmpegError: If unable to read file info.
        """
        if not self._ffprobe_path:
            raise FFmpegError("FFprobe not available")
        
        cmd = [
            str(self._ffprobe_path),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                raise FFmpegError(
                    "Failed to get media info",
                    command=" ".join(cmd),
                    stderr=result.stderr,
                )
            
            data = json.loads(result.stdout)
            
            # Find video and audio streams
            video_stream = None
            audio_stream = None
            
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and not video_stream:
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and not audio_stream:
                    audio_stream = stream
            
            # Extract info
            format_info = data.get("format", {})
            duration = float(format_info.get("duration", 0))
            
            width = None
            height = None
            frame_rate = None
            codec = None
            
            if video_stream:
                width = video_stream.get("width")
                height = video_stream.get("height")
                codec = video_stream.get("codec_name")
                
                # Parse frame rate
                fps_str = video_stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    if int(den) > 0:
                        frame_rate = float(num) / float(den)
            
            audio_codec = None
            if audio_stream:
                audio_codec = audio_stream.get("codec_name")
            
            return MediaInfo(
                duration=duration,
                width=width,
                height=height,
                frame_rate=frame_rate,
                codec=codec,
                audio_codec=audio_codec,
                bit_rate=int(format_info.get("bit_rate", 0)),
                format_name=format_info.get("format_name", "unknown"),
            )
            
        except subprocess.TimeoutExpired:
            raise FFmpegError("FFprobe timed out", command=" ".join(cmd))
        except json.JSONDecodeError as e:
            raise FFmpegError(f"Failed to parse FFprobe output: {e}")
    
    def generate_thumbnail(
        self,
        input_path: str,
        output_path: str,
        time_seconds: float = 0,
        width: int = 320,
    ) -> bool:
        """Generate a thumbnail from a video file.
        
        Args:
            input_path: Path to the input video.
            output_path: Path for the output thumbnail.
            time_seconds: Time position for thumbnail.
            width: Output thumbnail width (height auto-calculated).
            
        Returns:
            True if thumbnail was generated successfully.
        """
        if not self._ffmpeg_path:
            return False
        
        cmd = [
            str(self._ffmpeg_path),
            "-y",  # Overwrite output
            "-ss", str(time_seconds),
            "-i", input_path,
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            output_path,
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    
    def create_proxy(
        self,
        input_path: str,
        output_path: str,
        resolution: str = "1280x720",
        codec: str = "h264",
        quality: int = 23,
    ) -> bool:
        """Create a proxy file from a video.
        
        Args:
            input_path: Path to the input video.
            output_path: Path for the output proxy.
            resolution: Output resolution (e.g., "1280x720").
            codec: Output codec ("h264", "prores").
            quality: Quality level (CRF for h264).
            
        Returns:
            True if proxy was created successfully.
        """
        if not self._ffmpeg_path:
            return False
        
        width, height = resolution.split("x")
        
        # Build command based on codec
        if codec == "prores":
            cmd = [
                str(self._ffmpeg_path),
                "-y",
                "-i", input_path,
                "-vf", f"scale={width}:{height}",
                "-c:v", "prores_ks",
                "-profile:v", "0",  # Proxy profile
                "-c:a", "pcm_s16le",
                output_path,
            ]
        else:
            cmd = [
                str(self._ffmpeg_path),
                "-y",
                "-i", input_path,
                "-vf", f"scale={width}:{height}",
                "-c:v", "libx264",
                "-crf", str(quality),
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path,
            ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=3600,  # 1 hour timeout
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    
    def check_codec_support(self, codec_name: str) -> bool:
        """Check if a codec is supported.
        
        Args:
            codec_name: Name of the codec to check.
            
        Returns:
            True if codec is supported.
        """
        if not self._ffmpeg_path:
            return False
        
        try:
            result = subprocess.run(
                [str(self._ffmpeg_path), "-codecs"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return codec_name.lower() in result.stdout.lower()
        except Exception:
            return False
    
    def get_supported_formats(self) -> list:
        """Get list of supported formats.
        
        Returns:
            List of supported format names.
        """
        if not self._ffmpeg_path:
            return []
        
        try:
            result = subprocess.run(
                [str(self._ffmpeg_path), "-formats"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            formats = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and not line.startswith("--") and not line.startswith("File"):
                    parts = line.split()
                    if len(parts) >= 2:
                        formats.append(parts[1])
            
            return formats
        except Exception:
            return []
