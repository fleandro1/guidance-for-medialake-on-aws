"""Resource utilities for loading application resources like icons."""
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QSize, Qt

_RESOURCES_DIR = Path(__file__).parent


def get_app_icon() -> QIcon:
    """Return the application icon with multiple pre-rendered sizes for macOS dock."""
    icon = QIcon()

    svg_path = _RESOURCES_DIR / "icon.svg"
    if not svg_path.exists():
        return icon

    # Add the SVG file itself (scalable fallback)
    icon.addFile(str(svg_path), QSize(), QIcon.Mode.Normal, QIcon.State.Off)

    # Pre-render explicit sizes so the macOS dock gets crisp bitmaps
    try:
        renderer = QSvgRenderer(str(svg_path))
        for size in [16, 32, 48, 64, 128, 256, 512]:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pixmap)
    except Exception as e:  # pragma: no cover
        print(f"Warning: could not pre-render icon sizes: {e}")

    return icon
