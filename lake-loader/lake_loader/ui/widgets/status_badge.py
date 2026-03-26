"""Status badge widget for displaying upload status."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QFont
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from lake_loader.core.models import IngestStatus


# Status colors - optimized for dark theme
STATUS_COLORS = {
    IngestStatus.PENDING: QColor("#888888"),      # Grey
    IngestStatus.UPLOADING: QColor("#00a8e8"),    # Cyan/Blue
    IngestStatus.COMPLETED: QColor("#28a745"),    # Green
    IngestStatus.FAILED: QColor("#dc3545"),       # Red
    IngestStatus.CANCELLED: QColor("#fd7e14"),    # Orange
}

STATUS_LABELS = {
    IngestStatus.PENDING: "Pending",
    IngestStatus.UPLOADING: "Uploading",
    IngestStatus.COMPLETED: "Completed",
    IngestStatus.FAILED: "Failed",
    IngestStatus.CANCELLED: "Cancelled",
}


class StatusBadge(QWidget):
    """
    Widget that displays a colored status badge.

    Shows a colored dot and status text.
    """

    def __init__(self, status: IngestStatus = IngestStatus.PENDING, parent=None):
        super().__init__(parent)
        self._status = status

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Status indicator (colored dot)
        self._indicator = StatusIndicator(status)
        layout.addWidget(self._indicator)

        # Status label
        self._label = QLabel(STATUS_LABELS.get(status, "Unknown"))
        self._label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._label)

        layout.addStretch()

    @property
    def status(self) -> IngestStatus:
        """Get current status."""
        return self._status

    @status.setter
    def status(self, value: IngestStatus) -> None:
        """Set status and update display."""
        self._status = value
        self._indicator.status = value
        self._label.setText(STATUS_LABELS.get(value, "Unknown"))


class StatusIndicator(QWidget):
    """Small colored circle indicator."""

    SIZE = 12

    def __init__(self, status: IngestStatus = IngestStatus.PENDING, parent=None):
        super().__init__(parent)
        self._status = status
        self.setFixedSize(self.SIZE, self.SIZE)

    @property
    def status(self) -> IngestStatus:
        """Get current status."""
        return self._status

    @status.setter
    def status(self, value: IngestStatus) -> None:
        """Set status and update display."""
        self._status = value
        self.update()

    def paintEvent(self, event):
        """Paint the colored circle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = STATUS_COLORS.get(self._status, QColor("#6c757d"))
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        # Draw circle centered in widget
        radius = (self.SIZE - 2) // 2
        center_x = self.width() // 2
        center_y = self.height() // 2
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)


def get_status_color(status: IngestStatus) -> QColor:
    """Get the color for a given status."""
    return STATUS_COLORS.get(status, QColor("#6c757d"))


def get_status_label(status: IngestStatus) -> str:
    """Get the label for a given status."""
    return STATUS_LABELS.get(status, "Unknown")
