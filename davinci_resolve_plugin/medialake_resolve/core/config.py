"""Configuration management for Media Lake Resolve Plugin."""

import json
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict


def get_config_dir() -> Path:
    """Get the platform-specific configuration directory."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.name == "darwin" or os.uname().sysname == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    
    config_dir = base / "MediaLakeResolve"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cache_dir() -> Path:
    """Get the platform-specific cache directory."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.name == "darwin" or os.uname().sysname == "Darwin":  # macOS
        base = Path.home() / "Library" / "Caches"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    
    cache_dir = base / "MediaLakeResolve"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@dataclass
class Config:
    """Application configuration."""
    
    # Media Lake connection
    medialake_url: str = ""
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"
    
    # UI preferences
    view_mode: str = "grid"  # "grid" or "list"
    thumbnail_size: int = 120
    items_per_page: int = 20  # Default page size (options: 10, 20, 30, 50)
    
    # Download settings
    max_concurrent_downloads: int = 3
    auto_import_to_resolve: bool = True
    auto_link_proxies: bool = True
    
    # Upload settings
    max_concurrent_uploads: int = 3
    
    # Search preferences
    default_search_type: str = "semantic"  # "keyword" or "semantic"
    confidence_threshold: float = 0.63  # Default confidence threshold for semantic search
    search_history: list = field(default_factory=list)
    max_search_history: int = 20
    
    # Cached data (not persisted)
    _config_path: Optional[Path] = field(default=None, repr=False)
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file."""
        if config_path is None:
            config_path = get_config_dir() / "config.json"
        
        config = cls()
        config._config_path = config_path
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key) and not key.startswith("_"):
                            setattr(config, key, value)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config: {e}")
        
        return config
    
    def save(self) -> None:
        """Save configuration to file."""
        if self._config_path is None:
            self._config_path = get_config_dir() / "config.json"
        
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        
        try:
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")
    
    def add_to_search_history(self, query: str) -> None:
        """Add a search query to history."""
        if query in self.search_history:
            self.search_history.remove(query)
        self.search_history.insert(0, query)
        self.search_history = self.search_history[:self.max_search_history]
        self.save()
    
    @property
    def is_configured(self) -> bool:
        """Check if the plugin has been configured with Media Lake URL."""
        return bool(self.medialake_url)
    
    @property
    def thumbnail_cache_dir(self) -> Path:
        """Get the thumbnail cache directory."""
        cache_dir = get_cache_dir() / "thumbnails"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    @property
    def download_cache_dir(self) -> Path:
        """Get the download cache directory."""
        cache_dir = get_cache_dir() / "downloads"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
