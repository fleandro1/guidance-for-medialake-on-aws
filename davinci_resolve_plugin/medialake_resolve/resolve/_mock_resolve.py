"""Mock DaVinci Resolve API for development and testing."""

from typing import Any, Dict, List, Optional
from pathlib import Path
import tempfile


class MockMediaPoolItem:
    """Mock MediaPoolItem for testing."""
    
    def __init__(self, clip_info: Dict[str, Any]):
        self._info = clip_info
        self._proxy_path: Optional[str] = None
    
    def GetClipProperty(self, property_name: str = None) -> Any:
        """Get clip property."""
        if property_name is None:
            return self._info
        return self._info.get(property_name)
    
    def SetClipProperty(self, property_name: str, value: Any) -> bool:
        """Set clip property."""
        self._info[property_name] = value
        return True
    
    def GetMetadata(self, key: str = None) -> Any:
        """Get metadata."""
        metadata = self._info.get("metadata", {})
        if key is None:
            return metadata
        return metadata.get(key)
    
    def SetMetadata(self, key: str, value: str) -> bool:
        """Set metadata."""
        if "metadata" not in self._info:
            self._info["metadata"] = {}
        self._info["metadata"][key] = value
        return True
    
    def LinkProxyMedia(self, proxy_path: str) -> bool:
        """Link proxy media to this item."""
        if Path(proxy_path).exists():
            self._proxy_path = proxy_path
            return True
        return False
    
    def UnlinkProxyMedia(self) -> bool:
        """Unlink proxy media."""
        self._proxy_path = None
        return True


class MockMediaPoolFolder:
    """Mock MediaPoolFolder for testing."""
    
    def __init__(self, name: str):
        self._name = name
        self._clips: List[MockMediaPoolItem] = []
        self._subfolders: List["MockMediaPoolFolder"] = []
    
    def GetName(self) -> str:
        """Get folder name."""
        return self._name
    
    def GetClipList(self) -> List[MockMediaPoolItem]:
        """Get clips in this folder."""
        return self._clips
    
    def GetSubFolderList(self) -> List["MockMediaPoolFolder"]:
        """Get subfolders."""
        return self._subfolders
    
    def AddSubFolder(self, name: str) -> "MockMediaPoolFolder":
        """Add a subfolder."""
        folder = MockMediaPoolFolder(name)
        self._subfolders.append(folder)
        return folder


class MockMediaPool:
    """Mock MediaPool for testing."""
    
    def __init__(self):
        self._root_folder = MockMediaPoolFolder("Master")
        self._current_folder = self._root_folder
    
    def GetRootFolder(self) -> MockMediaPoolFolder:
        """Get root folder."""
        return self._root_folder
    
    def GetCurrentFolder(self) -> MockMediaPoolFolder:
        """Get current folder."""
        return self._current_folder
    
    def SetCurrentFolder(self, folder: MockMediaPoolFolder) -> bool:
        """Set current folder."""
        self._current_folder = folder
        return True
    
    def AddSubFolder(self, parent: MockMediaPoolFolder, name: str) -> MockMediaPoolFolder:
        """Add subfolder to parent."""
        return parent.AddSubFolder(name)
    
    def ImportMedia(self, file_paths: List[str]) -> List[MockMediaPoolItem]:
        """Import media files."""
        items = []
        for path in file_paths:
            item = MockMediaPoolItem({
                "File Path": path,
                "File Name": Path(path).name,
                "Clip Name": Path(path).stem,
                "Type": "Video",
            })
            self._current_folder._clips.append(item)
            items.append(item)
        return items
    
    def CreateEmptyTimeline(self, name: str) -> "MockTimeline":
        """Create empty timeline."""
        return MockTimeline(name)


class MockTimeline:
    """Mock Timeline for testing."""
    
    def __init__(self, name: str):
        self._name = name
    
    def GetName(self) -> str:
        """Get timeline name."""
        return self._name


class MockProject:
    """Mock Project for testing."""
    
    def __init__(self, name: str = "Test Project"):
        self._name = name
        self._media_pool = MockMediaPool()
        self._settings: Dict[str, Any] = {
            "workingDir": tempfile.gettempdir(),
            "cacheFilesLocation": tempfile.gettempdir(),
            "proxyMediaPath": tempfile.gettempdir(),
        }
    
    def GetName(self) -> str:
        """Get project name."""
        return self._name
    
    def GetMediaPool(self) -> MockMediaPool:
        """Get media pool."""
        return self._media_pool
    
    def GetCurrentTimeline(self) -> Optional[MockTimeline]:
        """Get current timeline."""
        return None
    
    def GetSetting(self, setting_name: str) -> Any:
        """Get project setting."""
        return self._settings.get(setting_name)
    
    def SetSetting(self, setting_name: str, value: Any) -> bool:
        """Set project setting."""
        self._settings[setting_name] = value
        return True


class MockProjectManager:
    """Mock ProjectManager for testing."""
    
    def __init__(self):
        self._current_project = MockProject()
    
    def GetCurrentProject(self) -> MockProject:
        """Get current project."""
        return self._current_project
    
    def CreateProject(self, name: str) -> MockProject:
        """Create a new project."""
        project = MockProject(name)
        self._current_project = project
        return project


class MockResolve:
    """Mock Resolve API for testing."""
    
    def __init__(self):
        self._project_manager = MockProjectManager()
    
    def GetProjectManager(self) -> MockProjectManager:
        """Get project manager."""
        return self._project_manager
    
    def GetVersion(self) -> str:
        """Get version."""
        return "18.0.0 (Mock)"
    
    def GetProductName(self) -> str:
        """Get product name."""
        return "DaVinci Resolve (Mock)"
    
    def OpenPage(self, page_name: str) -> bool:
        """Open a page."""
        return True


# Module-level function to get script app
_mock_resolve = MockResolve()
_mock_fusion = None


def scriptapp(app_name: str) -> Any:
    """Get script application instance.
    
    Args:
        app_name: "Resolve" or "Fusion"
        
    Returns:
        The application instance or None.
    """
    if app_name == "Resolve":
        return _mock_resolve
    elif app_name == "Fusion":
        return _mock_fusion
    return None
