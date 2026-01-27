"""Core module for Media Lake Resolve Plugin."""

from medialake_resolve.core.version import __version__
from medialake_resolve.core.config import Config
from medialake_resolve.core.models import Asset, Collection, SearchResult, DownloadTask
from medialake_resolve.core.errors import (
    MediaLakeError,
    AuthenticationError,
    APIError,
    DownloadError,
    ResolveConnectionError,
)

__all__ = [
    "__version__",
    "Config",
    "Asset",
    "Collection",
    "SearchResult",
    "DownloadTask",
    "MediaLakeError",
    "AuthenticationError",
    "APIError",
    "DownloadError",
    "ResolveConnectionError",
]
