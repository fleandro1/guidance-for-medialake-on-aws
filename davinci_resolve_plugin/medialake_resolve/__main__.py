"""
Media Lake DaVinci Resolve Plugin - Main Entry Point

This module provides the command-line entry point for the Media Lake plugin.
"""

import sys
import os
import logging

# Configure logging before importing Qt
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from datetime import datetime
f = open("/tmp/medialake_plugin.log", "a")
f.write(f"{datetime.now()} - Plugin started\n")
f.close()


def check_environment():
    """Check that the environment is properly configured."""
    errors = []
    
    # Check Python version
    if sys.version_info < (3, 10):
        errors.append(
            f"Python 3.10 or higher is required. "
            f"Current version: {sys.version_info.major}.{sys.version_info.minor}"
        )
    
    # Check for PySide6
    try:
        import PySide6
        logger.info(f"PySide6 version: {PySide6.__version__}")
    except ImportError:
        errors.append(
            "PySide6 is not installed. "
            "Install it with: pip install PySide6"
        )
    
    # Check for PySide6 Multimedia (optional - for video preview)
    try:
        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
        logger.info("PySide6 Multimedia: OK (video preview enabled)")
    except ImportError:
        logger.warning(
            "PySide6 Multimedia not available - video preview will be disabled. "
            "Thumbnails will be shown instead."
        )
    
    # Check for other dependencies
    required_packages = ['boto3', 'keyring', 'requests']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            errors.append(f"Required package '{package}' is not installed.")
    
    return errors


def main():
    """Main entry point for the Media Lake plugin."""
    # Check environment
    errors = check_environment()
    if errors:
        print("Environment check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("\nPlease install the required dependencies:", file=sys.stderr)
        print("  pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    
    # Now import Qt and application modules
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    
    from medialake_resolve.ui.main_window import MainWindow
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Media Lake for Resolve")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("AWS")
    app.setOrganizationDomain("aws.amazon.com")
    
    # Check if launched from Resolve
    launched_from_resolve = os.environ.get("MEDIALAKE_LAUNCHED_FROM_RESOLVE") == "1"
    if launched_from_resolve:
        logger.info("Media Lake launched from DaVinci Resolve Workflow Integration")
    
    # Set application style
    app.setStyle("Fusion")
    
    # Apply dark theme
    apply_dark_theme(app)
    
    # Create and show main window
    # MainWindow handles its own config and Resolve connection
    main_window = MainWindow()
    
    # Update window title if launched from Resolve
    if launched_from_resolve:
        main_window.setWindowTitle("Media Lake for Resolve (Integrated)")
    
    main_window.show()
    
    # Run event loop
    sys.exit(app.exec())


def apply_dark_theme(app):
    """Apply a dark theme that matches DaVinci Resolve's interface."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette, QColor
    
    palette = QPalette()
    
    # Window background
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(200, 200, 200))
    
    # Base (input fields, list views)
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 32))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(40, 40, 43))
    
    # Text colors
    palette.setColor(QPalette.ColorRole.Text, QColor(200, 200, 200))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    
    # Button colors
    palette.setColor(QPalette.ColorRole.Button, QColor(55, 55, 58))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 200))
    
    # Highlight colors
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    # Link colors
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 150, 255))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(150, 100, 255))
    
    # Tooltip
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 53))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(200, 200, 200))
    
    # Disabled colors
    palette.setColor(
        QPalette.ColorGroup.Disabled, 
        QPalette.ColorRole.WindowText, 
        QColor(120, 120, 120)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, 
        QPalette.ColorRole.Text, 
        QColor(120, 120, 120)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, 
        QPalette.ColorRole.ButtonText, 
        QColor(120, 120, 120)
    )
    
    app.setPalette(palette)
    
    # Additional stylesheet for fine-tuning
    app.setStyleSheet("""
        QToolTip {
            background-color: #323235;
            color: #c8c8c8;
            border: 1px solid #5a5a5e;
            padding: 4px;
        }
        
        QMenu {
            background-color: #2d2d30;
            border: 1px solid #3f3f46;
        }
        
        QMenu::item {
            padding: 6px 24px 6px 12px;
        }
        
        QMenu::item:selected {
            background-color: #0078d7;
        }
        
        QMenu::separator {
            height: 1px;
            background-color: #3f3f46;
            margin: 4px 8px;
        }
        
        QScrollBar:vertical {
            background-color: #2d2d30;
            width: 14px;
            margin: 0;
        }
        
        QScrollBar::handle:vertical {
            background-color: #5a5a5e;
            min-height: 30px;
            margin: 2px;
            border-radius: 4px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #6a6a6e;
        }
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }
        
        QScrollBar:horizontal {
            background-color: #2d2d30;
            height: 14px;
            margin: 0;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #5a5a5e;
            min-width: 30px;
            margin: 2px;
            border-radius: 4px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #6a6a6e;
        }
        
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0;
        }
        
        QLineEdit {
            background-color: #1e1e20;
            border: 1px solid #3f3f46;
            border-radius: 4px;
            padding: 6px;
            selection-background-color: #0078d7;
        }
        
        QLineEdit:focus {
            border: 1px solid #0078d7;
        }
        
        QPushButton {
            background-color: #3f3f46;
            border: 1px solid #5a5a5e;
            border-radius: 4px;
            padding: 6px 16px;
            min-width: 80px;
        }
        
        QPushButton:hover {
            background-color: #4a4a50;
        }
        
        QPushButton:pressed {
            background-color: #0078d7;
        }
        
        QPushButton:disabled {
            background-color: #2d2d30;
            color: #6a6a6e;
        }
        
        QProgressBar {
            background-color: #1e1e20;
            border: 1px solid #3f3f46;
            border-radius: 4px;
            text-align: center;
        }
        
        QProgressBar::chunk {
            background-color: #0078d7;
            border-radius: 3px;
        }
        
        QTableView, QTreeView, QListView {
            background-color: #1e1e20;
            border: 1px solid #3f3f46;
            selection-background-color: #0078d7;
        }
        
        QTableView::item:selected, 
        QTreeView::item:selected,
        QListView::item:selected {
            background-color: #0078d7;
        }
        
        QHeaderView::section {
            background-color: #2d2d30;
            padding: 6px;
            border: none;
            border-right: 1px solid #3f3f46;
            border-bottom: 1px solid #3f3f46;
        }
        
        QTabWidget::pane {
            border: 1px solid #3f3f46;
        }
        
        QTabBar::tab {
            background-color: #2d2d30;
            border: 1px solid #3f3f46;
            padding: 8px 16px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #3f3f46;
            border-bottom-color: #3f3f46;
        }
        
        QTabBar::tab:hover:!selected {
            background-color: #353538;
        }
        
        QComboBox {
            background-color: #3f3f46;
            border: 1px solid #5a5a5e;
            border-radius: 4px;
            padding: 6px;
            min-width: 100px;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        
        QComboBox QAbstractItemView {
            background-color: #2d2d30;
            border: 1px solid #3f3f46;
            selection-background-color: #0078d7;
        }
        
        QSplitter::handle {
            background-color: #3f3f46;
        }
        
        QSplitter::handle:horizontal {
            width: 2px;
        }
        
        QSplitter::handle:vertical {
            height: 2px;
        }
        
        QStatusBar {
            background-color: #007acc;
            color: white;
        }
        
        QStatusBar::item {
            border: none;
        }
    """)


if __name__ == "__main__":
    main()
