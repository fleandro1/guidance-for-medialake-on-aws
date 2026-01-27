"""Import media into DaVinci Resolve's Media Pool."""

from typing import List, Optional, Any, Dict
from pathlib import Path
from dataclasses import dataclass

from medialake_resolve.resolve.connection import ResolveConnection
from medialake_resolve.core.errors import ResolveNoProjectError, ResolveConnectionError


@dataclass
class ImportResult:
    """Result of a media import operation."""
    
    file_path: str
    media_pool_item: Any  # MediaPoolItem from Resolve
    success: bool
    error_message: Optional[str] = None
    
    @property
    def clip_name(self) -> str:
        """Get the clip name in Resolve."""
        if self.media_pool_item:
            try:
                return self.media_pool_item.GetClipProperty("Clip Name")
            except Exception:
                pass
        return Path(self.file_path).stem


class ResolveMediaImporter:
    """Handles importing media files into DaVinci Resolve's Media Pool.
    
    Supports:
    - Importing original media files
    - Linking proxy media to existing clips
    - Creating organized folder structures
    - Adding metadata from Media Lake
    """
    
    # Folder name for Media Lake imports
    MEDIALAKE_FOLDER_NAME = "Media Lake"
    
    def __init__(self, connection: Optional[ResolveConnection] = None):
        """Initialize media importer.
        
        Args:
            connection: Resolve connection instance. Creates one if not provided.
        """
        self._connection = connection or ResolveConnection()
        self._medialake_folder = None
    
    def _get_or_create_medialake_folder(self) -> Any:
        """Get or create the Media Lake folder in the Media Pool.
        
        Returns:
            The Media Lake MediaPoolFolder.
        """
        if self._medialake_folder:
            return self._medialake_folder
        
        media_pool = self._connection.get_media_pool()
        root_folder = media_pool.GetRootFolder()
        
        # Check if Media Lake folder already exists
        subfolders = root_folder.GetSubFolderList()
        for folder in subfolders:
            if folder.GetName() == self.MEDIALAKE_FOLDER_NAME:
                self._medialake_folder = folder
                return folder
        
        # Create the folder
        self._medialake_folder = media_pool.AddSubFolder(
            root_folder,
            self.MEDIALAKE_FOLDER_NAME
        )
        
        return self._medialake_folder
    
    def import_media(
        self,
        file_paths: List[str],
        metadata: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> List[ImportResult]:
        """Import media files into the Media Pool.
        
        Args:
            file_paths: List of absolute file paths to import.
            metadata: Optional dict mapping file paths to metadata dicts.
            
        Returns:
            List of ImportResult objects.
        """
        results = []
        
        try:
            media_pool = self._connection.get_media_pool()
            
            # Set current folder to Media Lake folder
            medialake_folder = self._get_or_create_medialake_folder()
            media_pool.SetCurrentFolder(medialake_folder)
            
            # Import all files at once
            media_pool_items = media_pool.ImportMedia(file_paths)
            
            # Match items to file paths and add metadata
            if media_pool_items:
                for i, item in enumerate(media_pool_items):
                    file_path = file_paths[i] if i < len(file_paths) else ""
                    
                    # Add metadata if provided
                    if metadata and file_path in metadata:
                        self._set_clip_metadata(item, metadata[file_path])
                    
                    results.append(ImportResult(
                        file_path=file_path,
                        media_pool_item=item,
                        success=True,
                    ))
            else:
                # Import failed
                for file_path in file_paths:
                    results.append(ImportResult(
                        file_path=file_path,
                        media_pool_item=None,
                        success=False,
                        error_message="Import failed",
                    ))
                    
        except ResolveNoProjectError as e:
            for file_path in file_paths:
                results.append(ImportResult(
                    file_path=file_path,
                    media_pool_item=None,
                    success=False,
                    error_message=str(e),
                ))
        except Exception as e:
            for file_path in file_paths:
                results.append(ImportResult(
                    file_path=file_path,
                    media_pool_item=None,
                    success=False,
                    error_message=f"Import error: {e}",
                ))
        
        return results
    
    def link_proxy_media(
        self,
        media_pool_item: Any,
        proxy_path: str,
    ) -> bool:
        """Link proxy media to an existing Media Pool item.
        
        Args:
            media_pool_item: The MediaPoolItem to link proxy to.
            proxy_path: Absolute path to the proxy file.
            
        Returns:
            True if linking succeeded.
        """
        try:
            # Verify proxy file exists
            if not Path(proxy_path).exists():
                print(f"Warning: Proxy file not found: {proxy_path}")
                return False
            
            # Link the proxy
            success = media_pool_item.LinkProxyMedia(proxy_path)
            
            if not success:
                print(f"Warning: Failed to link proxy: {proxy_path}")
            
            return success
            
        except Exception as e:
            print(f"Error linking proxy: {e}")
            return False
    
    def link_proxy_to_original(
        self,
        original_path: str,
        proxy_path: str,
    ) -> bool:
        """Find an original in the Media Pool by path and link a proxy to it.
        
        Args:
            original_path: Path to the original media file (already in Media Pool).
            proxy_path: Path to the proxy file to link.
            
        Returns:
            True if the proxy was successfully linked.
        """
        try:
            # Find the media pool item by file path
            media_pool_item = self._find_media_pool_item_by_path(original_path)
            
            if not media_pool_item:
                print(f"  [MediaImporter] Could not find original in Media Pool: {original_path}")
                return False
            
            # Link the proxy
            return self.link_proxy_media(media_pool_item, proxy_path)
            
        except Exception as e:
            print(f"  [MediaImporter] Error linking proxy to original: {e}")
            return False
    
    def _find_media_pool_item_by_path(self, file_path: str) -> Any:
        """Find a MediaPoolItem by its file path.
        
        Args:
            file_path: The file path to search for.
            
        Returns:
            The MediaPoolItem if found, None otherwise.
        """
        try:
            media_pool = self._connection.get_media_pool()
            
            # Search in the Media Lake folder first
            medialake_folder = self._get_or_create_medialake_folder()
            item = self._search_folder_for_path(medialake_folder, file_path)
            if item:
                return item
            
            # If not found, search the entire root folder recursively
            root_folder = media_pool.GetRootFolder()
            return self._search_folder_for_path(root_folder, file_path)
            
        except Exception as e:
            print(f"  [MediaImporter] Error searching for media pool item: {e}")
            return None
    
    def _search_folder_for_path(self, folder: Any, file_path: str) -> Any:
        """Recursively search a folder for a media item by file path.
        
        Args:
            folder: The MediaPoolFolder to search.
            file_path: The file path to match.
            
        Returns:
            The MediaPoolItem if found, None otherwise.
        """
        try:
            # Get all clips in this folder
            clips = folder.GetClipList()
            if clips:
                for clip in clips:
                    try:
                        clip_path = clip.GetClipProperty("File Path")
                        if clip_path == file_path:
                            return clip
                    except Exception:
                        pass
            
            # Search subfolders
            subfolders = folder.GetSubFolderList()
            if subfolders:
                for subfolder in subfolders:
                    item = self._search_folder_for_path(subfolder, file_path)
                    if item:
                        return item
            
            return None
            
        except Exception as e:
            print(f"  [MediaImporter] Error searching folder: {e}")
            return None
    
    def remove_media_by_path(self, file_path: str) -> bool:
        """Remove a media item from the Media Pool by its file path.
        
        Args:
            file_path: The file path of the media to remove.
            
        Returns:
            True if the item was found and removed.
        """
        try:
            media_pool_item = self._find_media_pool_item_by_path(file_path)
            
            if not media_pool_item:
                print(f"  [MediaImporter] Item not found in Media Pool: {file_path}")
                return False
            
            media_pool = self._connection.get_media_pool()
            success = media_pool.DeleteClips([media_pool_item])
            
            if success:
                print(f"  [MediaImporter] Removed from Media Pool: {file_path}")
            else:
                print(f"  [MediaImporter] Failed to remove from Media Pool: {file_path}")
            
            return success
            
        except Exception as e:
            print(f"  [MediaImporter] Error removing media: {e}")
            return False
    
    def import_with_proxy(
        self,
        original_path: str,
        proxy_path: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> ImportResult:
        """Import original media and link its proxy.
        
        Args:
            original_path: Path to the original media file.
            proxy_path: Path to the proxy media file.
            metadata: Optional metadata to add to the clip.
            
        Returns:
            ImportResult with the imported item.
        """
        # Import the original
        results = self.import_media(
            [original_path],
            {original_path: metadata} if metadata else None,
        )
        
        if not results:
            return ImportResult(
                file_path=original_path,
                media_pool_item=None,
                success=False,
                error_message="No import results returned",
            )
        
        result = results[0]
        
        # If import succeeded and proxy exists, link it
        if result.success and result.media_pool_item and proxy_path:
            self.link_proxy_media(result.media_pool_item, proxy_path)
        
        return result
    
    def _set_clip_metadata(
        self,
        media_pool_item: Any,
        metadata: Dict[str, str],
    ) -> None:
        """Set metadata on a Media Pool item.
        
        Args:
            media_pool_item: The MediaPoolItem to modify.
            metadata: Dictionary of metadata key-value pairs.
        """
        try:
            for key, value in metadata.items():
                media_pool_item.SetMetadata(key, str(value))
        except Exception as e:
            print(f"Warning: Could not set metadata: {e}")
    
    def find_clip_by_path(self, file_path: str) -> Optional[Any]:
        """Find a Media Pool item by its file path.
        
        Args:
            file_path: The file path to search for.
            
        Returns:
            MediaPoolItem if found, None otherwise.
        """
        try:
            medialake_folder = self._get_or_create_medialake_folder()
            clips = medialake_folder.GetClipList()
            
            for clip in clips:
                clip_path = clip.GetClipProperty("File Path")
                if clip_path == file_path:
                    return clip
            
            return None
            
        except Exception as e:
            print(f"Error finding clip: {e}")
            return None
    
    def find_clip_by_name(self, clip_name: str) -> Optional[Any]:
        """Find a Media Pool item by its clip name.
        
        Args:
            clip_name: The clip name to search for.
            
        Returns:
            MediaPoolItem if found, None otherwise.
        """
        try:
            medialake_folder = self._get_or_create_medialake_folder()
            clips = medialake_folder.GetClipList()
            
            for clip in clips:
                name = clip.GetClipProperty("Clip Name")
                if name == clip_name:
                    return clip
            
            return None
            
        except Exception as e:
            print(f"Error finding clip: {e}")
            return None
    
    def get_all_medialake_clips(self) -> List[Any]:
        """Get all clips in the Media Lake folder.
        
        Returns:
            List of MediaPoolItem objects.
        """
        try:
            medialake_folder = self._get_or_create_medialake_folder()
            return medialake_folder.GetClipList() or []
        except Exception:
            return []
