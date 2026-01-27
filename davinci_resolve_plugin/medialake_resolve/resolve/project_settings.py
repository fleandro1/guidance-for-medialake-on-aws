"""Access DaVinci Resolve project settings for download destinations."""

from typing import Optional, Any
from pathlib import Path
from dataclasses import dataclass

from medialake_resolve.resolve.connection import ResolveConnection
from medialake_resolve.core.errors import ResolveNoProjectError


@dataclass
class WorkingFolders:
    """Resolve project working folder settings."""
    
    working_dir: Path
    cache_files_location: Path
    proxy_media_path: Path
    
    @property
    def originals_dir(self) -> Path:
        """Directory for original media files."""
        return self.working_dir / "MediaLake" / "Originals"
    
    @property
    def proxies_dir(self) -> Path:
        """Directory for proxy media files."""
        return self.proxy_media_path / "MediaLake" / "Proxies"
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.proxies_dir.mkdir(parents=True, exist_ok=True)


class ResolveProjectSettings:
    """Provides access to DaVinci Resolve project settings.
    
    This class reads project settings to determine appropriate
    download destinations based on the project's Working Folders
    configuration (Master Settings).
    """
    
    def __init__(self, connection: Optional[ResolveConnection] = None):
        """Initialize project settings accessor.
        
        Args:
            connection: Resolve connection instance. Creates one if not provided.
        """
        self._connection = connection or ResolveConnection()
    
    def get_working_folders(self) -> WorkingFolders:
        """Get the project's working folder settings.
        
        Returns:
            WorkingFolders with paths for media storage.
            
        Raises:
            ResolveNoProjectError: If no project is open.
        """
        project = self._connection.get_current_project()
        
        # Get settings from project
        working_dir = project.GetSetting("workingDir")
        cache_location = project.GetSetting("cacheFilesLocation")
        proxy_path = project.GetSetting("proxyMediaPath")
        
        # Use defaults if settings are not available
        if not working_dir:
            working_dir = self._get_default_working_dir()
        if not cache_location:
            cache_location = working_dir
        if not proxy_path:
            proxy_path = working_dir
        
        return WorkingFolders(
            working_dir=Path(working_dir),
            cache_files_location=Path(cache_location),
            proxy_media_path=Path(proxy_path),
        )
    
    def get_original_download_path(self, filename: str) -> Path:
        """Get the path where an original file should be downloaded.
        
        Args:
            filename: The filename to download.
            
        Returns:
            Full path for the download destination.
        """
        folders = self.get_working_folders()
        folders.ensure_directories()
        return folders.originals_dir / filename
    
    def get_proxy_download_path(self, filename: str) -> Path:
        """Get the path where a proxy file should be downloaded.
        
        Args:
            filename: The filename to download.
            
        Returns:
            Full path for the download destination.
        """
        folders = self.get_working_folders()
        folders.ensure_directories()
        return folders.proxies_dir / filename
    
    def _get_default_working_dir(self) -> str:
        """Get a default working directory if not set in project.
        
        Returns:
            Default working directory path.
        """
        import os
        import sys
        
        if sys.platform == "darwin":
            return os.path.expanduser("~/Movies/DaVinci Resolve")
        elif sys.platform == "win32":
            return os.path.expanduser("~/Videos/DaVinci Resolve")
        else:
            return os.path.expanduser("~/Videos/DaVinci Resolve")
    
    def get_project_name(self) -> str:
        """Get the current project name.
        
        Returns:
            Project name string.
        """
        try:
            project = self._connection.get_current_project()
            return project.GetName()
        except ResolveNoProjectError:
            return "No Project"
    
    def get_project_frame_rate(self) -> float:
        """Get the project's timeline frame rate.
        
        Returns:
            Frame rate as float (e.g., 24.0, 29.97, 30.0).
        """
        try:
            project = self._connection.get_current_project()
            fps = project.GetSetting("timelineFrameRate")
            return float(fps) if fps else 24.0
        except (ResolveNoProjectError, ValueError):
            return 24.0
    
    def get_project_resolution(self) -> tuple:
        """Get the project's timeline resolution.
        
        Returns:
            Tuple of (width, height).
        """
        try:
            project = self._connection.get_current_project()
            width = project.GetSetting("timelineResolutionWidth")
            height = project.GetSetting("timelineResolutionHeight")
            return (int(width) if width else 1920, int(height) if height else 1080)
        except (ResolveNoProjectError, ValueError):
            return (1920, 1080)
    
    def get_project_info(self) -> dict:
        """Get comprehensive project information.
        
        Returns:
            Dictionary with project details.
        """
        try:
            project = self._connection.get_current_project()
            folders = self.get_working_folders()
            
            return {
                "name": project.GetName(),
                "frame_rate": self.get_project_frame_rate(),
                "resolution": self.get_project_resolution(),
                "working_dir": str(folders.working_dir),
                "proxy_path": str(folders.proxy_media_path),
                "cache_path": str(folders.cache_files_location),
            }
        except ResolveNoProjectError:
            return {
                "name": "No Project",
                "frame_rate": 24.0,
                "resolution": (1920, 1080),
                "working_dir": "",
                "proxy_path": "",
                "cache_path": "",
            }
