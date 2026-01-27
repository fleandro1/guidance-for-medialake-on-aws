"""DaVinci Resolve connection management."""

import sys
import os
from typing import Optional, Any
from pathlib import Path

from medialake_resolve.core.errors import (
    ResolveConnectionError,
    ResolveNotRunningError,
    ResolveNoProjectError,
)


def _get_resolve_script_path() -> Optional[Path]:
    """Get the path to DaVinci Resolve's Python modules.
    
    Returns:
        Path to the fusionscript module, or None if not found.
    """
    # Platform-specific paths
    if sys.platform == "darwin":  # macOS
        paths = [
            Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"),
            Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"),
        ]
    elif sys.platform == "win32":  # Windows
        paths = [
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / 
            "Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules",
        ]
    else:  # Linux
        paths = [
            Path("/opt/resolve/Developer/Scripting/Modules"),
            Path("/opt/resolve/libs/Fusion/fusionscript.so"),
        ]
    
    for path in paths:
        if path.exists():
            return path
    
    return None


def _setup_resolve_environment() -> None:
    """Set up the environment for DaVinci Resolve scripting."""
    script_path = _get_resolve_script_path()
    
    if script_path:
        # Add to Python path if it's a directory
        if script_path.is_dir():
            sys.path.insert(0, str(script_path))
        else:
            sys.path.insert(0, str(script_path.parent))
    
    # Set environment variables for Resolve
    if sys.platform == "darwin":
        os.environ.setdefault("RESOLVE_SCRIPT_API", "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting")
        os.environ.setdefault("RESOLVE_SCRIPT_LIB", "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
    elif sys.platform == "win32":
        os.environ.setdefault("RESOLVE_SCRIPT_API", r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting")
        os.environ.setdefault("RESOLVE_SCRIPT_LIB", r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
    else:
        os.environ.setdefault("RESOLVE_SCRIPT_API", "/opt/resolve/Developer/Scripting")
        os.environ.setdefault("RESOLVE_SCRIPT_LIB", "/opt/resolve/libs/Fusion/fusionscript.so")


class ResolveConnection:
    """Manages connection to DaVinci Resolve.
    
    This class provides access to the Resolve scripting API and handles
    connection management.
    """
    
    _instance: Optional["ResolveConnection"] = None
    _resolve: Any = None
    
    def __new__(cls) -> "ResolveConnection":
        """Singleton pattern for Resolve connection."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the Resolve connection."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._resolve = None
            self._fusion = None
            _setup_resolve_environment()
    
    def connect(self) -> bool:
        """Establish connection to DaVinci Resolve.
        
        Returns:
            True if connected successfully.
            
        Raises:
            ResolveNotRunningError: If Resolve is not running.
        """
        try:
            # Try to import the Resolve scripting module
            try:
                import DaVinciResolveScript as dvr
            except ImportError:
                # Try alternative import method
                try:
                    import fusionscript as dvr
                except ImportError:
                    # Create a mock module for development
                    from medialake_resolve.resolve import _mock_resolve as dvr
            
            # Get the Resolve instance
            self._resolve = dvr.scriptapp("Resolve")
            
            if self._resolve is None:
                raise ResolveNotRunningError()
            
            # Also get Fusion for potential future use
            self._fusion = dvr.scriptapp("Fusion")
            
            return True
            
        except ResolveNotRunningError:
            raise
        except Exception as e:
            raise ResolveConnectionError(
                "Failed to connect to DaVinci Resolve",
                str(e),
            )
    
    @property
    def resolve(self) -> Any:
        """Get the Resolve instance.
        
        Returns:
            The Resolve scripting object.
            
        Raises:
            ResolveNotRunningError: If not connected.
        """
        if self._resolve is None:
            self.connect()
        return self._resolve
    
    @property
    def fusion(self) -> Any:
        """Get the Fusion instance.
        
        Returns:
            The Fusion scripting object, or None.
        """
        return self._fusion
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Resolve.
        
        Returns:
            True if connected.
        """
        return self._resolve is not None
    
    def get_project_manager(self) -> Any:
        """Get the project manager.
        
        Returns:
            The ProjectManager object.
        """
        return self.resolve.GetProjectManager()
    
    def get_current_project(self) -> Any:
        """Get the current project.
        
        Returns:
            The current Project object.
            
        Raises:
            ResolveNoProjectError: If no project is open.
        """
        pm = self.get_project_manager()
        project = pm.GetCurrentProject()
        
        if project is None:
            raise ResolveNoProjectError()
        
        return project
    
    def get_media_pool(self) -> Any:
        """Get the media pool for the current project.
        
        Returns:
            The MediaPool object.
            
        Raises:
            ResolveNoProjectError: If no project is open.
        """
        project = self.get_current_project()
        return project.GetMediaPool()
    
    def get_current_timeline(self) -> Optional[Any]:
        """Get the current timeline.
        
        Returns:
            The current Timeline object, or None if no timeline is active.
        """
        try:
            project = self.get_current_project()
            return project.GetCurrentTimeline()
        except ResolveNoProjectError:
            return None
    
    def get_resolve_version(self) -> str:
        """Get the DaVinci Resolve version.
        
        Returns:
            Version string.
        """
        try:
            return self.resolve.GetVersion()
        except Exception:
            return "Unknown"
    
    def get_product_name(self) -> str:
        """Get the product name (Resolve or Resolve Studio).
        
        Returns:
            Product name string.
        """
        try:
            return self.resolve.GetProductName()
        except Exception:
            return "DaVinci Resolve"
    
    def disconnect(self) -> None:
        """Disconnect from Resolve."""
        self._resolve = None
        self._fusion = None
