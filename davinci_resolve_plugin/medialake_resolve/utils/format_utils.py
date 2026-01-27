"""Format utilities for display and conversion."""

from datetime import datetime, timedelta
from typing import Optional


class FormatUtils:
    """Utility class for formatting values for display."""
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes.
            
        Returns:
            Formatted size string (e.g., "1.5 GB").
        """
        if size_bytes < 0:
            return "0 B"
        
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size_bytes < 1024:
                if unit == "B":
                    return f"{size_bytes} {unit}"
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.1f} PB"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format.
        
        Args:
            seconds: Duration in seconds.
            
        Returns:
            Formatted duration string (e.g., "1:23:45" or "2:30").
        """
        if seconds < 0:
            return "0:00"
        
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    @staticmethod
    def format_duration_long(seconds: float) -> str:
        """Format duration in long format.
        
        Args:
            seconds: Duration in seconds.
            
        Returns:
            Formatted duration string (e.g., "1 hour 23 minutes").
        """
        if seconds < 0:
            return "0 seconds"
        
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        
        return " ".join(parts)
    
    @staticmethod
    def format_datetime(dt: datetime, include_time: bool = True) -> str:
        """Format datetime for display.
        
        Args:
            dt: The datetime to format.
            include_time: Whether to include time component.
            
        Returns:
            Formatted datetime string.
        """
        if include_time:
            return dt.strftime("%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d")
    
    @staticmethod
    def format_relative_time(dt: datetime) -> str:
        """Format datetime as relative time (e.g., "2 hours ago").
        
        Args:
            dt: The datetime to format.
            
        Returns:
            Relative time string.
        """
        now = datetime.now()
        if dt.tzinfo:
            now = datetime.now(dt.tzinfo)
        
        diff = now - dt
        
        if diff < timedelta(minutes=1):
            return "just now"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif diff < timedelta(days=30):
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif diff < timedelta(days=365):
            months = diff.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = diff.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
    
    @staticmethod
    def format_resolution(width: int, height: int) -> str:
        """Format resolution for display.
        
        Args:
            width: Width in pixels.
            height: Height in pixels.
            
        Returns:
            Formatted resolution string.
        """
        # Common resolution names
        resolutions = {
            (7680, 4320): "8K UHD",
            (3840, 2160): "4K UHD",
            (2560, 1440): "2K QHD",
            (1920, 1080): "1080p",
            (1280, 720): "720p",
            (854, 480): "480p",
            (640, 360): "360p",
        }
        
        name = resolutions.get((width, height))
        if name:
            return f"{width}×{height} ({name})"
        
        return f"{width}×{height}"
    
    @staticmethod
    def format_frame_rate(fps: float) -> str:
        """Format frame rate for display.
        
        Args:
            fps: Frame rate in frames per second.
            
        Returns:
            Formatted frame rate string.
        """
        # Handle common non-integer frame rates
        if abs(fps - 23.976) < 0.01:
            return "23.976 fps"
        elif abs(fps - 29.97) < 0.01:
            return "29.97 fps"
        elif abs(fps - 59.94) < 0.01:
            return "59.94 fps"
        elif fps == int(fps):
            return f"{int(fps)} fps"
        else:
            return f"{fps:.2f} fps"
    
    @staticmethod
    def format_bitrate(bps: int) -> str:
        """Format bitrate for display.
        
        Args:
            bps: Bitrate in bits per second.
            
        Returns:
            Formatted bitrate string.
        """
        if bps < 1000:
            return f"{bps} bps"
        elif bps < 1000000:
            return f"{bps / 1000:.1f} Kbps"
        else:
            return f"{bps / 1000000:.1f} Mbps"
    
    @staticmethod
    def truncate_string(s: str, max_length: int, suffix: str = "...") -> str:
        """Truncate a string to a maximum length.
        
        Args:
            s: The string to truncate.
            max_length: Maximum length including suffix.
            suffix: Suffix to add if truncated.
            
        Returns:
            Truncated string.
        """
        if len(s) <= max_length:
            return s
        
        return s[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def format_count(count: int, singular: str, plural: Optional[str] = None) -> str:
        """Format a count with appropriate singular/plural label.
        
        Args:
            count: The count.
            singular: Singular form of the label.
            plural: Plural form (defaults to singular + 's').
            
        Returns:
            Formatted count string.
        """
        if plural is None:
            plural = singular + "s"
        
        label = singular if count == 1 else plural
        return f"{count} {label}"
