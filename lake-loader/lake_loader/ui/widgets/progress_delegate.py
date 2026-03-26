"""Custom progress bar delegate for table views."""

from PySide6.QtCore import Qt, QModelIndex, QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPen, QFont
from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


class ProgressDelegate(QStyledItemDelegate):
    """
    Custom delegate that renders a progress bar in a table cell.

    The model should return a float 0-100 for the progress value.
    """

    def paint(self, painter, option, index: QModelIndex):
        """Paint the progress bar."""
        progress = index.data(Qt.ItemDataRole.DisplayRole)

        if progress is None:
            super().paint(painter, option, index)
            return

        try:
            progress = float(progress)
        except (ValueError, TypeError):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)

        # Bar geometry — inset from cell edges
        rect = QRectF(option.rect).adjusted(4, 8, -4, -8)
        radius = rect.height() / 2

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(26, 26, 29))
        painter.drawRoundedRect(rect, radius, radius)

        # Filled portion
        if progress > 0:
            fill_width = max(rect.height(), rect.width() * (progress / 100.0))
            fill_rect = QRectF(rect.x(), rect.y(), fill_width, rect.height())

            gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            gradient.setColorAt(0.0, QColor(0, 120, 168))
            gradient.setColorAt(1.0, QColor(0, 160, 210))

            painter.setBrush(gradient)
            painter.drawRoundedRect(fill_rect, radius, radius)

        # Subtle border
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(58, 58, 61), 1))
        painter.drawRoundedRect(rect, radius, radius)

        # Text
        painter.setPen(QColor(210, 210, 210))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{progress:.0f}%",
        )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        """Return the preferred size for the progress bar cell."""
        size = super().sizeHint(option, index)
        if size.height() < 24:
            size.setHeight(24)
        return size
