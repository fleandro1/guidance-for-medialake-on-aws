"""Data models for Media Lake Resolve Plugin."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class MediaType(Enum):
    """Media type enumeration."""
    VIDEO = "Video"
    AUDIO = "Audio"
    IMAGE = "Image"
    DOCUMENT = "Document"
    OTHER = "Other"


class DownloadStatus(Enum):
    """Download task status."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssetVariant(Enum):
    """Asset variant type."""
    ORIGINAL = "original"
    PROXY = "proxy"


class UploadStatus(Enum):
    """Upload task status."""
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Asset:
    """Represents a Media Lake asset."""
    
    asset_id: str
    name: str
    collection_id: str
    media_type: MediaType
    file_extension: str
    file_size: int
    inventory_id: Optional[str] = None  # Full InventoryID (e.g., "urn:medialake:asset:...")
    duration: Optional[float] = None  # Duration in seconds for video/audio
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    codec: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    original_url: Optional[str] = None
    proxy_url: Optional[str] = None
    proxy_file_size: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    score: Optional[float] = None  # Semantic search relevance score
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Asset":
        """Create an Asset from API response data.
        
        Handles MediaLake's nested response format:
        - DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        - DerivedRepresentations (for thumbnails, proxies)
        - Metadata.Consolidated
        """
        # Debug: print first asset's raw data structure
        print(f"  [Asset Parser] Raw data keys: {list(data.keys())}")
        
        # Extract nested structures
        digital_source_asset = data.get("DigitalSourceAsset", {})
        main_rep = digital_source_asset.get("MainRepresentation", {})
        storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
        object_key = storage_info.get("ObjectKey", {})
        file_info = storage_info.get("FileInfo", {})
        
        print(f"  [Asset Parser] DigitalSourceAsset keys: {list(digital_source_asset.keys())}")
        print(f"  [Asset Parser] storage_info: {storage_info}")
        print(f"  [Asset Parser] thumbnailUrl from data: {data.get('thumbnailUrl')}")
        
        # Determine media type from nested structure or flat field
        media_type_str = data.get("mediaType", digital_source_asset.get("Type", "other")).lower()
        # Map common types to MediaType enum values (capitalized to match API)
        type_mapping = {
            "video": "Video",
            "audio": "Audio",
            "image": "Image",
            "document": "Document",
        }
        media_type_str = type_mapping.get(media_type_str, "Other")
        try:
            media_type = MediaType(media_type_str)
        except ValueError:
            media_type = MediaType.OTHER
        
        # Parse dates - check multiple locations
        created_at = None
        updated_at = None
        created_str = (
            data.get("createdAt") or 
            storage_info.get("CreateDate") or
            file_info.get("CreateDate") or
            digital_source_asset.get("CreateDate")
        )
        if created_str:
            try:
                created_at = datetime.fromisoformat(str(created_str).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        updated_str = data.get("updatedAt")
        if updated_str:
            try:
                updated_at = datetime.fromisoformat(str(updated_str).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        # Get file size - check multiple locations
        file_size = (
            data.get("fileSize") or
            storage_info.get("FileSize") or
            file_info.get("Size") or
            0
        )
        if isinstance(file_size, str):
            try:
                file_size = int(file_size)
            except ValueError:
                file_size = 0
        
        # Get file name - check multiple locations
        name = (
            data.get("name") or 
            data.get("fileName") or
            object_key.get("Name") or
            object_key.get("FullPath", "").split("/")[-1] or
            "Unknown"
        )
        
        # Get file extension
        file_extension = data.get("fileExtension") or data.get("extension") or ""
        if not file_extension and name and "." in name:
            file_extension = name.rsplit(".", 1)[-1]
        
        # Get asset ID - check multiple locations
        inventory_id = data.get("InventoryID", "")
        asset_id = (
            data.get("assetId") or
            data.get("id") or
            (inventory_id.split(":")[-1] if inventory_id else "") or
            ""
        )
        
        # Get format/codec from MainRepresentation
        codec = data.get("codec") or main_rep.get("Format") or ""
        
        # Get thumbnail and proxy URLs - check both flat and nested
        thumbnail_url = data.get("thumbnailUrl")
        proxy_url = data.get("proxyUrl")
        proxy_file_size = None
        
        # Also check DerivedRepresentations for URLs and proxy size
        derived_reps = data.get("DerivedRepresentations", [])
        # Also check inside DigitalSourceAsset
        if not derived_reps and "DigitalSourceAsset" in data:
            derived_reps = data["DigitalSourceAsset"].get("DerivedRepresentations", [])
        
        for rep in derived_reps:
            purpose = rep.get("Purpose", "").lower()
            rep_storage = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
            rep_file_info = rep_storage.get("FileInfo", {})
            
            if purpose == "thumbnail" and not thumbnail_url:
                # Thumbnail URL might already be set as presigned
                pass
            elif purpose == "proxy":
                # Get proxy file size from DerivedRepresentations
                if not proxy_file_size:
                    size = rep_file_info.get("Size")
                    if size:
                        try:
                            proxy_file_size = int(size)
                        except (ValueError, TypeError):
                            pass
        
        # Get metadata
        metadata_obj = data.get("Metadata", {})
        consolidated = metadata_obj.get("Consolidated", {})
        metadata = data.get("metadata", consolidated) or {}
        
        # Extract video/audio specific metadata from Consolidated
        duration = data.get("duration")
        width = data.get("width")
        height = data.get("height")
        frame_rate = data.get("frameRate")
        
        # Try to get from consolidated metadata
        if not duration and "Duration" in consolidated:
            try:
                duration = float(consolidated["Duration"])
            except (ValueError, TypeError):
                pass
        
        if not width and "Width" in consolidated:
            try:
                width = int(consolidated["Width"])
            except (ValueError, TypeError):
                pass
                
        if not height and "Height" in consolidated:
            try:
                height = int(consolidated["Height"])
            except (ValueError, TypeError):
                pass
        
        if not frame_rate and "FrameRate" in consolidated:
            try:
                frame_rate = float(consolidated["FrameRate"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            asset_id=asset_id,
            name=name,
            collection_id=data.get("collectionId", ""),
            media_type=media_type,
            file_extension=file_extension,
            file_size=file_size,
            inventory_id=inventory_id,
            duration=duration,
            width=width,
            height=height,
            frame_rate=frame_rate,
            codec=codec,
            thumbnail_url=thumbnail_url,
            preview_url=data.get("previewUrl"),
            original_url=data.get("originalUrl", data.get("downloadUrl")),
            proxy_url=proxy_url,
            proxy_file_size=proxy_file_size or data.get("proxyFileSize"),
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
            tags=data.get("tags", []),
            score=data.get("score"),  # Capture search relevance score
        )
    
    @property
    def display_size(self) -> str:
        """Get human-readable file size."""
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    @property
    def display_duration(self) -> str:
        """Get human-readable duration."""
        if self.duration is None:
            return ""
        
        total_seconds = int(self.duration)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    @property
    def resolution(self) -> str:
        """Get resolution string."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return ""
    
    @property
    def has_proxy(self) -> bool:
        """Check if asset has a proxy available."""
        return bool(self.proxy_url)


@dataclass
class Collection:
    """Represents a Media Lake collection."""
    
    collection_id: str
    name: str
    description: str = ""
    asset_count: int = 0
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Collection":
        """Create a Collection from API response data."""
        created_at = None
        if data.get("createdAt"):
            try:
                created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return cls(
            collection_id=data.get("collectionId", data.get("id", "")),
            name=data.get("name", "Unknown"),
            description=data.get("description", ""),
            asset_count=data.get("assetCount", 0),
            parent_id=data.get("parentId"),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class SearchResult:
    """Represents search results from Media Lake."""
    
    assets: List[Asset]
    total_count: int
    page: int
    page_size: int
    query: str
    search_type: str  # "keyword" or "semantic"
    
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        if self.page_size <= 0:
            return 0
        return (self.total_count + self.page_size - 1) // self.page_size
    
    @property
    def has_more(self) -> bool:
        """Check if there are more results."""
        return self.page < self.total_pages


@dataclass
class DownloadTask:
    """Represents a download task."""
    
    task_id: str
    asset: Asset
    variant: AssetVariant
    destination_path: str
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    bytes_downloaded: int = 0
    total_bytes: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def is_active(self) -> bool:
        """Check if download is currently active."""
        return self.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING)
    
    @property
    def is_complete(self) -> bool:
        """Check if download is complete (success or failure)."""
        return self.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)
    
    @property
    def download_url(self) -> Optional[str]:
        """Get the appropriate download URL based on variant."""
        if self.variant == AssetVariant.PROXY:
            return self.asset.proxy_url
        return self.asset.original_url


@dataclass
class TokenInfo:
    """Represents authentication token information."""
    
    access_token: str
    id_token: str
    refresh_token: str
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now() >= self.expires_at
    
    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh (5 minutes before expiry)."""
        from datetime import timedelta
        refresh_threshold = self.expires_at - timedelta(minutes=5)
        return datetime.now() >= refresh_threshold


@dataclass
class UserInfo:
    """Represents authenticated user information."""
    
    user_id: str
    username: str
    email: str
    groups: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    @property
    def is_admin(self) -> bool:
        """Check if user is an administrator."""
        admin_groups = ["Super Administrator", "Administrators", "Admin"]
        return any(g in admin_groups for g in self.groups)
    
    @property
    def can_edit(self) -> bool:
        """Check if user has edit permissions."""
        editor_groups = ["Super Administrator", "Administrators", "Admin", "Editor", "Editors"]
        return any(g in editor_groups for g in self.groups)


@dataclass
class UploadTask:
    """Represents an upload task."""
    
    task_id: str
    source_path: str
    bucket_name: str  # This is actually the connector's storageIdentifier (bucket name)
    destination_key: str
    connector_id: Optional[str] = None  # The connector ID for /assets/upload endpoint
    upload_url: Optional[str] = None
    presigned_fields: Optional[Dict[str, str]] = None  # Fields for presigned POST upload
    content_type: str = "application/octet-stream"
    status: UploadStatus = UploadStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    bytes_uploaded: int = 0
    total_bytes: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def is_active(self) -> bool:
        """Check if upload is currently active."""
        return self.status in (UploadStatus.PENDING, UploadStatus.UPLOADING)
    
    @property
    def is_complete(self) -> bool:
        """Check if upload is complete (success or failure)."""
        return self.status in (UploadStatus.COMPLETED, UploadStatus.FAILED, UploadStatus.CANCELLED)
