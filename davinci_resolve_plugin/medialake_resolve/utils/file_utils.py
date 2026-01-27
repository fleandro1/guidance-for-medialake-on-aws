"""File system utilities."""

import os
import sys
import shutil
import hashlib
from pathlib import Path
from typing import Optional, List


class FileUtils:
    """Utility class for file system operations."""
    
    # Common video extensions
    VIDEO_EXTENSIONS = {
        ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv",
        ".webm", ".m4v", ".mpg", ".mpeg", ".mxf", ".r3d",
        ".braw", ".ari", ".dpx", ".exr", ".dng",
    }
    
    # Common audio extensions
    AUDIO_EXTENSIONS = {
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a",
        ".wma", ".aiff", ".aif",
    }
    
    # Common image extensions
    IMAGE_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
        ".tif", ".webp", ".psd", ".raw", ".cr2", ".nef",
    }
    
    @staticmethod
    def get_media_type(file_path: str) -> str:
        """Determine media type from file extension.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Media type string: "video", "audio", "image", or "other".
        """
        ext = Path(file_path).suffix.lower()
        
        if ext in FileUtils.VIDEO_EXTENSIONS:
            return "video"
        elif ext in FileUtils.AUDIO_EXTENSIONS:
            return "audio"
        elif ext in FileUtils.IMAGE_EXTENSIONS:
            return "image"
        else:
            return "other"
    
    @staticmethod
    def ensure_directory(path: str) -> Path:
        """Ensure a directory exists, creating it if necessary.
        
        Args:
            path: Path to the directory.
            
        Returns:
            Path object for the directory.
        """
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    @staticmethod
    def get_unique_filename(directory: str, filename: str) -> str:
        """Get a unique filename, appending number if file exists.
        
        Args:
            directory: Directory path.
            filename: Desired filename.
            
        Returns:
            Unique filename that doesn't exist in the directory.
        """
        dir_path = Path(directory)
        file_path = dir_path / filename
        
        if not file_path.exists():
            return filename
        
        # Split name and extension
        stem = file_path.stem
        suffix = file_path.suffix
        
        # Find unique name
        counter = 1
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = dir_path / new_name
            if not new_path.exists():
                return new_name
            counter += 1
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """Convert a string to a safe filename.
        
        Args:
            filename: Original filename.
            
        Returns:
            Sanitized filename safe for all platforms.
        """
        # Characters not allowed in filenames on various platforms
        invalid_chars = '<>:"/\\|?*'
        
        # Replace invalid characters with underscore
        safe_name = filename
        for char in invalid_chars:
            safe_name = safe_name.replace(char, "_")
        
        # Remove leading/trailing spaces and dots
        safe_name = safe_name.strip(" .")
        
        # Ensure not empty
        if not safe_name:
            safe_name = "unnamed"
        
        # Limit length (255 is common max)
        max_length = 200  # Leave room for path
        if len(safe_name) > max_length:
            # Preserve extension
            path = Path(safe_name)
            stem = path.stem[:max_length - len(path.suffix) - 1]
            safe_name = stem + path.suffix
        
        return safe_name
    
    @staticmethod
    def calculate_file_hash(file_path: str, algorithm: str = "md5") -> str:
        """Calculate hash of a file.
        
        Args:
            file_path: Path to the file.
            algorithm: Hash algorithm ("md5", "sha1", "sha256").
            
        Returns:
            Hex string of the file hash.
        """
        hash_func = getattr(hashlib, algorithm)()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Get file size in bytes.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            File size in bytes.
        """
        return Path(file_path).stat().st_size
    
    @staticmethod
    def copy_file(src: str, dst: str, overwrite: bool = False) -> bool:
        """Copy a file to a new location.
        
        Args:
            src: Source file path.
            dst: Destination file path.
            overwrite: Whether to overwrite existing file.
            
        Returns:
            True if copy succeeded.
        """
        try:
            dst_path = Path(dst)
            
            if dst_path.exists() and not overwrite:
                return False
            
            # Ensure destination directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src, dst)
            return True
        except Exception:
            return False
    
    @staticmethod
    def move_file(src: str, dst: str, overwrite: bool = False) -> bool:
        """Move a file to a new location.
        
        Args:
            src: Source file path.
            dst: Destination file path.
            overwrite: Whether to overwrite existing file.
            
        Returns:
            True if move succeeded.
        """
        try:
            dst_path = Path(dst)
            
            if dst_path.exists():
                if overwrite:
                    dst_path.unlink()
                else:
                    return False
            
            # Ensure destination directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(src, dst)
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            True if deletion succeeded.
        """
        try:
            Path(file_path).unlink(missing_ok=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def list_files(
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
    ) -> List[Path]:
        """List files in a directory.
        
        Args:
            directory: Directory to list.
            pattern: Glob pattern to match.
            recursive: Whether to search recursively.
            
        Returns:
            List of matching file paths.
        """
        dir_path = Path(directory)
        
        if recursive:
            return list(dir_path.rglob(pattern))
        else:
            return list(dir_path.glob(pattern))
    
    @staticmethod
    def get_temp_directory() -> Path:
        """Get the system temporary directory.
        
        Returns:
            Path to temp directory.
        """
        import tempfile
        return Path(tempfile.gettempdir())
    
    @staticmethod
    def get_user_documents_directory() -> Path:
        """Get the user's documents directory.
        
        Returns:
            Path to documents directory.
        """
        if sys.platform == "darwin":
            return Path.home() / "Documents"
        elif sys.platform == "win32":
            import ctypes.wintypes
            CSIDL_PERSONAL = 5
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf)
            return Path(buf.value)
        else:
            return Path.home() / "Documents"
    
    @staticmethod
    def get_free_space(path: str) -> int:
        """Get free disk space at a path.
        
        Args:
            path: Path to check.
            
        Returns:
            Free space in bytes.
        """
        stat = shutil.disk_usage(path)
        return stat.free
    
    @staticmethod
    def has_sufficient_space(path: str, required_bytes: int) -> bool:
        """Check if there's sufficient disk space.
        
        Args:
            path: Path to check.
            required_bytes: Required space in bytes.
            
        Returns:
            True if there's enough space.
        """
        return FileUtils.get_free_space(path) >= required_bytes
