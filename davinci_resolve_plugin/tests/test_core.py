"""
Unit tests for the core module.
"""

import pytest
from pathlib import Path
import tempfile
import json


class TestConfig:
    """Tests for ConfigManager."""
    
    def test_config_creation(self):
        """Test that config manager can be instantiated."""
        from medialake_resolve.core.config import ConfigManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ConfigManager(config_dir=Path(tmpdir))
            assert config is not None
    
    def test_config_default_values(self):
        """Test that default values are set correctly."""
        from medialake_resolve.core.config import ConfigManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ConfigManager(config_dir=Path(tmpdir))
            
            # Check default values
            assert config.get('theme', 'dark') == 'dark'
            assert config.get('thumbnail_size', 'medium') == 'medium'
    
    def test_config_save_and_load(self):
        """Test saving and loading configuration."""
        from medialake_resolve.core.config import ConfigManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config1 = ConfigManager(config_dir=Path(tmpdir))
            config1.set('api_endpoint', 'https://api.example.com')
            config1.set('region', 'us-west-2')
            config1.save()
            
            # Load in a new instance
            config2 = ConfigManager(config_dir=Path(tmpdir))
            assert config2.get('api_endpoint') == 'https://api.example.com'
            assert config2.get('region') == 'us-west-2'


class TestModels:
    """Tests for data models."""
    
    def test_asset_creation(self):
        """Test Asset model creation."""
        from medialake_resolve.core.models import Asset, AssetType
        
        asset = Asset(
            id='asset-123',
            name='test_video.mov',
            asset_type=AssetType.VIDEO,
            file_size=1024 * 1024 * 100,  # 100 MB
            duration=120.5,
            created_at='2024-01-15T10:30:00Z'
        )
        
        assert asset.id == 'asset-123'
        assert asset.name == 'test_video.mov'
        assert asset.asset_type == AssetType.VIDEO
        assert asset.file_size == 104857600
        assert asset.duration == 120.5
    
    def test_asset_from_dict(self):
        """Test creating Asset from dictionary."""
        from medialake_resolve.core.models import Asset, AssetType
        
        data = {
            'id': 'asset-456',
            'name': 'interview.mp4',
            'asset_type': 'video',
            'file_size': 50000000,
            'duration': 300.0,
            'width': 1920,
            'height': 1080,
            'codec': 'h264'
        }
        
        asset = Asset.from_dict(data)
        
        assert asset.id == 'asset-456'
        assert asset.name == 'interview.mp4'
        assert asset.asset_type == AssetType.VIDEO
        assert asset.width == 1920
        assert asset.height == 1080
    
    def test_collection_creation(self):
        """Test Collection model creation."""
        from medialake_resolve.core.models import Collection
        
        collection = Collection(
            id='collection-789',
            name='Project Alpha',
            description='Raw footage for Project Alpha',
            asset_count=42
        )
        
        assert collection.id == 'collection-789'
        assert collection.name == 'Project Alpha'
        assert collection.asset_count == 42
    
    def test_search_results(self):
        """Test SearchResults model."""
        from medialake_resolve.core.models import SearchResults, Asset, AssetType
        
        assets = [
            Asset(id=f'asset-{i}', name=f'video_{i}.mov', asset_type=AssetType.VIDEO)
            for i in range(10)
        ]
        
        results = SearchResults(
            assets=assets,
            total_count=100,
            page=1,
            page_size=10,
            has_more=True
        )
        
        assert len(results.assets) == 10
        assert results.total_count == 100
        assert results.has_more is True
    
    def test_download_task(self):
        """Test DownloadTask model."""
        from medialake_resolve.core.models import DownloadTask, Asset, AssetType, DownloadStatus
        
        asset = Asset(
            id='asset-123',
            name='test.mov',
            asset_type=AssetType.VIDEO,
            file_size=1000000
        )
        
        task = DownloadTask(
            asset=asset,
            destination=Path('/tmp/test.mov'),
            status=DownloadStatus.PENDING
        )
        
        assert task.status == DownloadStatus.PENDING
        assert task.progress == 0.0
        assert task.asset.id == 'asset-123'


class TestErrors:
    """Tests for custom exceptions."""
    
    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        from medialake_resolve.core.errors import AuthenticationError
        
        error = AuthenticationError("Invalid credentials")
        assert str(error) == "Invalid credentials"
        assert isinstance(error, Exception)
    
    def test_api_error(self):
        """Test APIError exception."""
        from medialake_resolve.core.errors import APIError
        
        error = APIError("Server error", status_code=500)
        assert error.status_code == 500
        assert "Server error" in str(error)
    
    def test_resolve_connection_error(self):
        """Test ResolveConnectionError exception."""
        from medialake_resolve.core.errors import ResolveConnectionError
        
        error = ResolveConnectionError("DaVinci Resolve is not running")
        assert "DaVinci Resolve" in str(error)


class TestVersion:
    """Tests for version information."""
    
    def test_version_format(self):
        """Test version string format."""
        from medialake_resolve.core.version import __version__
        
        # Should be semantic version format
        parts = __version__.split('.')
        assert len(parts) >= 2
        assert all(part.isdigit() for part in parts[:2])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
