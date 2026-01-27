"""
Unit tests for the Resolve integration module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestResolveConnection:
    """Tests for ResolveConnection."""
    
    def test_resolve_connection_creation(self):
        """Test that ResolveConnection can be instantiated."""
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        assert conn is not None
    
    def test_mock_mode(self):
        """Test that mock mode is detected when Resolve is unavailable."""
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        # Should fall back to mock mode if Resolve is not running
        assert conn._resolve is not None  # Either real or mock
    
    def test_get_project_name(self):
        """Test getting project name."""
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        # Should return a string (real or mock project name)
        project_name = conn.get_project_name()
        assert isinstance(project_name, str)
    
    def test_get_media_pool(self):
        """Test getting media pool."""
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        media_pool = conn.get_media_pool()
        assert media_pool is not None


class TestProjectSettings:
    """Tests for ResolveProjectSettings."""
    
    def test_project_settings_creation(self):
        """Test that ResolveProjectSettings can be instantiated."""
        from medialake_resolve.resolve.project_settings import ResolveProjectSettings
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        settings = ResolveProjectSettings(conn)
        assert settings is not None
    
    def test_get_working_folder(self):
        """Test getting working folder."""
        from medialake_resolve.resolve.project_settings import ResolveProjectSettings
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        settings = ResolveProjectSettings(conn)
        
        # Should return a Path
        folder = settings.get_capture_folder()
        assert folder is None or isinstance(folder, Path)
    
    def test_get_proxy_folder(self):
        """Test getting proxy folder."""
        from medialake_resolve.resolve.project_settings import ResolveProjectSettings
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        settings = ResolveProjectSettings(conn)
        
        # Should return a Path or None
        folder = settings.get_proxy_folder()
        assert folder is None or isinstance(folder, Path)


class TestMediaImporter:
    """Tests for ResolveMediaImporter."""
    
    def test_media_importer_creation(self):
        """Test that ResolveMediaImporter can be instantiated."""
        from medialake_resolve.resolve.media_importer import ResolveMediaImporter
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        importer = ResolveMediaImporter(conn)
        assert importer is not None
    
    def test_import_to_bin(self):
        """Test importing media to a bin."""
        from medialake_resolve.resolve.media_importer import ResolveMediaImporter
        from medialake_resolve.resolve.connection import ResolveConnection
        import tempfile
        
        conn = ResolveConnection()
        conn.connect()
        
        importer = ResolveMediaImporter(conn)
        
        # Create a temp file to import
        with tempfile.NamedTemporaryFile(suffix='.mov', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # This should work in mock mode
            result = importer.import_media([temp_path])
            # Result depends on implementation
            assert result is not None
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_create_bin(self):
        """Test creating a bin."""
        from medialake_resolve.resolve.media_importer import ResolveMediaImporter
        from medialake_resolve.resolve.connection import ResolveConnection
        
        conn = ResolveConnection()
        conn.connect()
        
        importer = ResolveMediaImporter(conn)
        
        # Should return a folder (real or mock)
        folder = importer.create_bin("Test Bin")
        assert folder is not None


class TestMockResolve:
    """Tests for MockResolve API."""
    
    def test_mock_resolve_creation(self):
        """Test that MockResolve can be instantiated."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        assert resolve is not None
    
    def test_mock_project_manager(self):
        """Test mock project manager."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        assert pm is not None
    
    def test_mock_current_project(self):
        """Test mock current project."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        assert project is not None
    
    def test_mock_project_name(self):
        """Test mock project name."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        name = project.GetName()
        assert isinstance(name, str)
        assert len(name) > 0
    
    def test_mock_media_pool(self):
        """Test mock media pool."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        media_pool = project.GetMediaPool()
        assert media_pool is not None
    
    def test_mock_import_media(self):
        """Test mock media import."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        import tempfile
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        media_pool = project.GetMediaPool()
        
        # Create a temp file
        with tempfile.NamedTemporaryFile(suffix='.mov', delete=False) as f:
            temp_path = f.name
        
        try:
            items = media_pool.ImportMedia([temp_path])
            assert items is not None
            assert len(items) > 0
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_mock_add_sub_folder(self):
        """Test mock adding sub folder."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        media_pool = project.GetMediaPool()
        root_folder = media_pool.GetRootFolder()
        
        new_folder = media_pool.AddSubFolder(root_folder, "Test Folder")
        assert new_folder is not None
    
    def test_mock_timeline_creation(self):
        """Test mock timeline creation."""
        from medialake_resolve.resolve._mock_resolve import MockResolve
        
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        media_pool = project.GetMediaPool()
        
        timeline = media_pool.CreateEmptyTimeline("Test Timeline")
        assert timeline is not None
        assert timeline.GetName() == "Test Timeline"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
