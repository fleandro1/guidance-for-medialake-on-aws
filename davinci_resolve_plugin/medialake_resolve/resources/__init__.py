"""Resource utilities for loading application resources like icons."""
import os
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QSize, Qt

_RESOURCES_DIR = Path(__file__).parent


def get_app_icon() -> QIcon:
    """Get the application icon.
    
    Returns:
        QIcon: The application icon with multiple sizes.
    """
    icon = QIcon()
    
    # Try to load SVG first (scalable)
    svg_path = _RESOURCES_DIR / "icon.svg"
    if svg_path.exists():
        # Add SVG for all sizes (scalable)
        icon.addFile(str(svg_path), QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        
        # Also create specific sizes from SVG for better rendering on macOS dock
        try:
            renderer = QSvgRenderer(str(svg_path))
            for size in [16, 32, 48, 64, 128, 256, 512]:
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon.addPixmap(pixmap)
        except Exception as e:
            print(f"Warning: Could not render SVG to pixmaps: {e}")
    
    return icon


def get_resource_path(filename: str) -> Path:
    """Get the full path to a resource file.
    
    Args:
        filename: The resource filename.
        
    Returns:
        Path: The full path to the resource.
    """
    return _RESOURCES_DIR / filename
