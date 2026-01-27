"""
Unit tests for the utils module.
"""

import pytest
from pathlib import Path
import tempfile
import os


class TestFormatUtils:
    """Tests for format utilities."""
    
    def test_format_file_size_bytes(self):
        """Test formatting bytes."""
        from medialake_resolve.utils.format_utils import format_file_size
        
        assert format_file_size(0) == "0 B"
        assert format_file_size(500) == "500 B"
        assert format_file_size(1023) == "1023 B"
    
    def test_format_file_size_kilobytes(self):
        """Test formatting kilobytes."""
        from medialake_resolve.utils.format_utils import format_file_size
        
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(10240) == "10.0 KB"
    
    def test_format_file_size_megabytes(self):
        """Test formatting megabytes."""
        from medialake_resolve.utils.format_utils import format_file_size
        
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(52428800) == "50.0 MB"
    
    def test_format_file_size_gigabytes(self):
        """Test formatting gigabytes."""
        from medialake_resolve.utils.format_utils import format_file_size
        
        assert format_file_size(1073741824) == "1.0 GB"
        assert format_file_size(5368709120) == "5.0 GB"
    
    def test_format_duration_seconds(self):
        """Test formatting duration in seconds."""
        from medialake_resolve.utils.format_utils import format_duration
        
        assert format_duration(0) == "0:00"
        assert format_duration(30) == "0:30"
        assert format_duration(59) == "0:59"
    
    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        from medialake_resolve.utils.format_utils import format_duration
        
        assert format_duration(60) == "1:00"
        assert format_duration(90) == "1:30"
        assert format_duration(600) == "10:00"
    
    def test_format_duration_hours(self):
        """Test formatting duration in hours."""
        from medialake_resolve.utils.format_utils import format_duration
        
        assert format_duration(3600) == "1:00:00"
        assert format_duration(3661) == "1:01:01"
        assert format_duration(7200) == "2:00:00"
    
    def test_format_timestamp(self):
        """Test formatting timestamps."""
        from medialake_resolve.utils.format_utils import format_timestamp
        
        # ISO format timestamp
        result = format_timestamp("2024-01-15T10:30:00Z")
        assert "2024" in result
        assert "01" in result or "Jan" in result
    
    def test_format_resolution(self):
        """Test formatting resolution."""
        from medialake_resolve.utils.format_utils import format_resolution
        
        assert format_resolution(1920, 1080) == "1920x1080"
        assert format_resolution(3840, 2160) == "3840x2160"
        assert format_resolution(None, None) == "Unknown"


class TestFileUtils:
    """Tests for file utilities."""
    
    def test_ensure_directory(self):
        """Test directory creation."""
        from medialake_resolve.utils.file_utils import ensure_directory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new" / "nested" / "directory"
            ensure_directory(new_dir)
            assert new_dir.exists()
            assert new_dir.is_dir()
    
    def test_get_safe_filename(self):
        """Test safe filename generation."""
        from medialake_resolve.utils.file_utils import get_safe_filename
        
        # Remove special characters
        assert get_safe_filename("file:name?test.mov") == "file_name_test.mov"
        
        # Preserve normal names
        assert get_safe_filename("normal_file.mov") == "normal_file.mov"
        
        # Handle spaces
        assert get_safe_filename("file name.mov") == "file name.mov"
    
    def test_get_unique_filepath(self):
        """Test unique filepath generation."""
        from medialake_resolve.utils.file_utils import get_unique_filepath
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # First file should keep the original name
            path1 = get_unique_filepath(Path(tmpdir) / "test.mov")
            assert path1.name == "test.mov"
            
            # Create the file
            path1.touch()
            
            # Second file should get a suffix
            path2 = get_unique_filepath(Path(tmpdir) / "test.mov")
            assert path2.name == "test_1.mov"
            
            # Create the second file
            path2.touch()
            
            # Third file should get the next suffix
            path3 = get_unique_filepath(Path(tmpdir) / "test.mov")
            assert path3.name == "test_2.mov"
    
    def test_get_file_extension(self):
        """Test file extension extraction."""
        from medialake_resolve.utils.file_utils import get_file_extension
        
        assert get_file_extension("video.mov") == ".mov"
        assert get_file_extension("video.MP4") == ".mp4"
        assert get_file_extension("no_extension") == ""
        assert get_file_extension("multiple.dots.mxf") == ".mxf"
    
    def test_is_video_file(self):
        """Test video file detection."""
        from medialake_resolve.utils.file_utils import is_video_file
        
        assert is_video_file("video.mov") is True
        assert is_video_file("video.mp4") is True
        assert is_video_file("video.mxf") is True
        assert is_video_file("video.prores") is True
        assert is_video_file("image.jpg") is False
        assert is_video_file("document.pdf") is False
    
    def test_is_audio_file(self):
        """Test audio file detection."""
        from medialake_resolve.utils.file_utils import is_audio_file
        
        assert is_audio_file("audio.wav") is True
        assert is_audio_file("audio.mp3") is True
        assert is_audio_file("audio.aac") is True
        assert is_audio_file("video.mov") is False
        assert is_audio_file("image.jpg") is False
    
    def test_is_image_file(self):
        """Test image file detection."""
        from medialake_resolve.utils.file_utils import is_image_file
        
        assert is_image_file("image.jpg") is True
        assert is_image_file("image.png") is True
        assert is_image_file("image.tiff") is True
        assert is_image_file("image.exr") is True
        assert is_image_file("video.mov") is False
        assert is_image_file("audio.wav") is False


class TestFFmpegUtils:
    """Tests for FFmpeg utilities."""
    
    def test_ffmpeg_utils_creation(self):
        """Test that FFmpeg utils can be instantiated."""
        from medialake_resolve.utils.ffmpeg_utils import FFmpegUtils
        
        ffmpeg = FFmpegUtils()
        assert ffmpeg is not None
    
    def test_find_ffmpeg_detection(self):
        """Test FFmpeg detection."""
        from medialake_resolve.utils.ffmpeg_utils import FFmpegUtils
        
        ffmpeg = FFmpegUtils()
        # This test checks that detection doesn't crash
        # Actual availability depends on the system
        path = ffmpeg.find_ffmpeg()
        # path could be None if FFmpeg is not installed
        assert path is None or Path(path).exists()
    
    def test_build_thumbnail_command(self):
        """Test building thumbnail extraction command."""
        from medialake_resolve.utils.ffmpeg_utils import FFmpegUtils
        
        ffmpeg = FFmpegUtils()
        
        # Skip if FFmpeg not available
        if not ffmpeg.is_available():
            pytest.skip("FFmpeg not available")
        
        cmd = ffmpeg._build_thumbnail_command(
            input_path=Path("/tmp/input.mov"),
            output_path=Path("/tmp/thumbnail.jpg"),
            timestamp=5.0,
            width=320,
            height=180
        )
        
        assert "ffmpeg" in cmd[0] or "ffmpeg.exe" in cmd[0]
        assert "-ss" in cmd
        assert "5.0" in cmd or "5" in cmd


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
