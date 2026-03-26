"""Dark theme for LakeLoader application.

Matches the DaVinci Resolve plugin styling for consistency.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor


def apply_dark_theme(app: QApplication) -> None:
    """Apply a dark theme that matches DaVinci Resolve's interface."""
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
    app.setStyleSheet(DARK_STYLESHEET)


# Main application stylesheet
DARK_STYLESHEET = """
    QToolTip {
        background-color: #2a2a2d;
        color: #d4d4d4;
        border: 1px solid #4a4a4d;
        padding: 6px 8px;
        border-radius: 4px;
    }
    
    QMenu {
        background-color: #2a2a2d;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 4px;
    }
    
    QMenu::item {
        padding: 8px 32px 8px 16px;
        border-radius: 4px;
        margin: 2px 4px;
    }
    
    QMenu::item:selected {
        background-color: #00a8e8;
        color: white;
    }
    
    QMenu::separator {
        height: 1px;
        background-color: #3f3f46;
        margin: 6px 12px;
    }
    
    QScrollBar:vertical {
        background-color: #1e1e20;
        width: 12px;
        margin: 0;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #505055;
        min-height: 30px;
        margin: 2px;
        border-radius: 5px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #606065;
    }
    
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0;
    }
    
    QScrollBar:horizontal {
        background-color: #1e1e20;
        height: 12px;
        margin: 0;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #505055;
        min-width: 30px;
        margin: 2px;
        border-radius: 5px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #606065;
    }
    
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0;
    }
    
    QLineEdit {
        background-color: #1a1a1d;
        border: 1px solid #3a3a3d;
        border-radius: 5px;
        padding: 8px 10px;
        selection-background-color: #00a8e8;
        font-size: 13px;
    }
    
    QLineEdit:focus {
        border: 1px solid #00a8e8;
        background-color: #1e1e20;
    }
    
    QPushButton {
        background-color: #3a3a3f;
        border: 1px solid #4a4a4f;
        border-radius: 5px;
        padding: 8px 18px;
        min-width: 80px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #454550;
        border: 1px solid #5a5a5f;
    }
    
    QPushButton:pressed {
        background-color: #00a8e8;
        border: 1px solid #00c8ff;
    }
    
    QPushButton:disabled {
        background-color: #2a2a2d;
        color: #5a5a5d;
        border: 1px solid #3a3a3d;
    }
    
    QProgressBar {
        background-color: #1a1a1d;
        border: 1px solid #3a3a3d;
        border-radius: 5px;
        text-align: center;
        height: 20px;
    }
    
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #00a8e8, stop:1 #00d4ff);
        border-radius: 4px;
    }
    
    QTableView, QTreeView, QListView {
        background-color: #1a1a1d;
        border: 1px solid #3a3a3d;
        selection-background-color: #00a8e8;
        border-radius: 4px;
        gridline-color: #3a3a3d;
    }
    
    QTableView::item:selected, 
    QTreeView::item:selected,
    QListView::item:selected {
        background-color: #0078d7;
    }
    
    QHeaderView::section {
        background-color: #2d2d30;
        padding: 8px 6px;
        border: none;
        border-right: 1px solid #3f3f46;
        border-bottom: 1px solid #3f3f46;
        font-weight: 500;
    }
    
    QTabWidget::pane {
        border: 1px solid #3f3f46;
        border-radius: 4px;
    }
    
    QTabBar::tab {
        background-color: #2d2d30;
        border: 1px solid #3f3f46;
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
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
        padding: 8px 10px;
        min-width: 100px;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #888888;
        margin-right: 8px;
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
        padding: 4px;
    }
    
    QStatusBar::item {
        border: none;
    }
    
    QGroupBox {
        font-weight: bold;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 10px;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        color: #c8c8c8;
    }
    
    QSpinBox {
        background-color: #1a1a1d;
        border: 1px solid #3a3a3d;
        border-radius: 4px;
        padding: 6px 8px;
    }
    
    QSpinBox:focus {
        border: 1px solid #00a8e8;
    }
    
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #3a3a3f;
        border: none;
        width: 20px;
    }
    
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background-color: #454550;
    }
    
    QCheckBox {
        spacing: 8px;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 3px;
        border: 1px solid #5a5a5e;
        background-color: #1a1a1d;
    }
    
    QCheckBox::indicator:checked {
        background-color: #00a8e8;
        border-color: #00a8e8;
    }
    
    QCheckBox::indicator:hover {
        border-color: #00a8e8;
    }
    
    QDialog {
        background-color: #2d2d30;
    }
    
    QLabel {
        color: #c8c8c8;
    }
    
    QFrame[frameShape="4"] {  /* HLine */
        background-color: #3f3f46;
        max-height: 1px;
    }
    
    QFrame[frameShape="5"] {  /* VLine */
        background-color: #3f3f46;
        max-width: 1px;
    }
"""

# Primary action button style (for important actions like "Start", "Sign In")
PRIMARY_BUTTON_STYLE = """
    QPushButton {
        background-color: #0078a8;
        border: 1px solid #0088b8;
        border-radius: 5px;
        padding: 8px 24px;
        color: #e8e8e8;
        font-weight: bold;
        min-width: 100px;
    }
    QPushButton:hover {
        background-color: #0088b8;
        border: 1px solid #0098c8;
    }
    QPushButton:pressed {
        background-color: #006898;
    }
    QPushButton:disabled {
        background-color: #2a2a2d;
        color: #5a5a5d;
        border: 1px solid #3a3a3d;
    }
"""

# Danger button style (for destructive actions)
DANGER_BUTTON_STYLE = """
    QPushButton {
        background-color: #6b2d2d;
        border: 1px solid #8c4040;
        border-radius: 5px;
        padding: 8px 18px;
        color: #f5cccc;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #7d3636;
        border: 1px solid #9c4e4e;
    }
    QPushButton:pressed {
        background-color: #8a3c3c;
        color: #ffe0e0;
    }
    QPushButton:disabled {
        background-color: #2a2a2d;
        color: #5a5a5d;
        border: 1px solid #3a3a3d;
    }
"""

# Success indicator style
SUCCESS_STYLE = """
    color: #28a745;
    background-color: rgba(40, 167, 69, 0.1);
    padding: 8px;
    border-radius: 4px;
"""

# Error indicator style
ERROR_STYLE = """
    color: #dc3545;
    background-color: rgba(220, 53, 69, 0.1);
    padding: 8px;
    border-radius: 4px;
"""

# Drop zone style
DROP_ZONE_STYLE = """
    QFrame {
        background-color: #2b2b2b;
        border: 2px dashed #555555;
        border-radius: 8px;
    }
"""

DROP_ZONE_HIGHLIGHT_STYLE = """
    QFrame {
        background-color: #1e3a4d;
        border: 2px dashed #00a8e8;
        border-radius: 8px;
    }
"""

# Table-specific styles for better visibility
TABLE_STYLE = """
    QTableView {
        background-color: #1a1a1d;
        alternate-background-color: #222225;
        border: 1px solid #3a3a3d;
        border-radius: 4px;
        gridline-color: #2d2d30;
        selection-background-color: #0078d7;
    }
    QTableView::item {
        padding: 6px;
        border-bottom: 1px solid #2d2d30;
    }
    QTableView::item:selected {
        background-color: #0078d7;
        color: white;
    }
    QTableView::item:hover:!selected {
        background-color: #2d2d30;
    }
"""
