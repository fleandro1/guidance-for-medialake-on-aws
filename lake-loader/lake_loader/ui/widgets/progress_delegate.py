"""Custom progress bar delegate for table views."""

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QApplication,
    QStyle,
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

        # Create progress bar style option
        progress_bar_option = QStyleOptionProgressBar()
        progress_bar_option.rect = option.rect.adjusted(2, 2, -2, -2)
        progress_bar_option.minimum = 0
        progress_bar_option.maximum = 100
        progress_bar_option.progress = int(progress)
        progress_bar_option.text = f"{progress:.1f}%"
        progress_bar_option.textVisible = True
        progress_bar_option.textAlignment = Qt.AlignmentFlag.AlignCenter

        # Draw the progress bar
        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ProgressBar,
            progress_bar_option,
            painter,
        )

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        """Return the preferred size for the progress bar cell."""
        size = super().sizeHint(option, index)
        # Ensure minimum height for progress bar
        if size.height() < 24:
            size.setHeight(24)
        return size
