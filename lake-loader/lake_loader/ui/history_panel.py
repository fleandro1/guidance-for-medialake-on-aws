"""History panel for viewing past ingest records."""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QModelIndex, QAbstractTableModel, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QPushButton,
    QComboBox,
    QLineEdit,
    QLabel,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QDialog,
    QTextEdit,
    QDialogButtonBox,
)

from lake_loader.core.history import IngestHistory
from lake_loader.core.models import HistoryRecord, format_file_size, format_duration
from lake_loader.ui.theme import DANGER_BUTTON_STYLE


class HistoryTableModel(QAbstractTableModel):
    """Table model for history records."""

    COLUMNS = [
        "Timestamp",
        "Filename",
        "Size",
        "Connector",
        "Destination",
        "Status",
        "Duration",
        "Error",
    ]

    def __init__(self, history: IngestHistory, parent=None):
        super().__init__(parent)
        self._history = history

    def refresh(self) -> None:
        """Refresh the model data."""
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return len(self._history.records)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        records = self._history.records
        if index.row() >= len(records):
            return None

        record = records[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # Timestamp
                return record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:  # Filename
                return record.filename
            elif col == 2:  # Size
                return format_file_size(record.file_size)
            elif col == 3:  # Connector
                return record.connector_name
            elif col == 4:  # Destination
                return record.destination_path or "-"
            elif col == 5:  # Status
                return record.status.capitalize()
            elif col == 6:  # Duration
                if record.duration_seconds:
                    return format_duration(record.duration_seconds)
                return "-"
            elif col == 7:  # Error
                return record.error_message or ""

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 5:  # Status color
                from PySide6.QtGui import QColor

                status_colors = {
                    "completed": QColor("#198754"),
                    "failed": QColor("#dc3545"),
                    "cancelled": QColor("#fd7e14"),
                }
                return status_colors.get(record.status.lower())

        elif role == Qt.ItemDataRole.UserRole:
            return record.record_id

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1:  # Full path tooltip
                return record.file_path
            elif col == 7 and record.error_message:  # Error detail tooltip
                return record.error_detail or record.error_message

        return None

    def get_record(self, row: int) -> Optional[HistoryRecord]:
        """Get record at row."""
        records = self._history.records
        if 0 <= row < len(records):
            return records[row]
        return None


class HistoryFilterProxy(QSortFilterProxyModel):
    """Filter proxy for history table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_filter: Optional[str] = None
        self._search_text: str = ""

    def set_status_filter(self, status: Optional[str]) -> None:
        """Set status filter (None = all)."""
        self._status_filter = status.lower() if status else None
        self.invalidateFilter()

    def set_search_text(self, text: str) -> None:
        """Set search text filter."""
        self._search_text = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Check if row should be shown."""
        model = self.sourceModel()
        if not model:
            return True

        record = model.get_record(source_row)
        if not record:
            return False

        # Status filter
        if self._status_filter:
            if record.status.lower() != self._status_filter:
                return False

        # Search text filter
        if self._search_text:
            if self._search_text not in record.filename.lower():
                return False

        return True


class HistoryPanel(QWidget):
    """Panel for viewing and managing ingest history."""

    def __init__(self, history: IngestHistory, parent=None):
        super().__init__(parent)
        self._history = history

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filter row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # Search
        filter_layout.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter by filename...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._search_edit.setMaximumWidth(250)
        filter_layout.addWidget(self._search_edit)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self._status_combo = QComboBox()
        self._status_combo.addItem("All", None)
        self._status_combo.addItem("Completed", "completed")
        self._status_combo.addItem("Failed", "failed")
        self._status_combo.addItem("Cancelled", "cancelled")
        self._status_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        filter_layout.addWidget(self._status_combo)

        filter_layout.addStretch()

        # Action buttons
        self._delete_btn = QPushButton("Delete Oldest N...")
        self._delete_btn.clicked.connect(self._on_delete_oldest)
        filter_layout.addWidget(self._delete_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setStyleSheet(DANGER_BUTTON_STYLE)
        self._clear_btn.clicked.connect(self._on_clear_all)
        filter_layout.addWidget(self._clear_btn)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._on_export_csv)
        filter_layout.addWidget(self._export_btn)

        layout.addLayout(filter_layout)

        # History table
        self._table_model = HistoryTableModel(self._history)
        self._proxy_model = HistoryFilterProxy()
        self._proxy_model.setSourceModel(self._table_model)

        self._table_view = QTableView()
        self._table_view.setModel(self._proxy_model)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setSortingEnabled(True)
        self._table_view.doubleClicked.connect(self._on_row_double_clicked)

        # Set column widths
        header = self._table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 150)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 120)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 90)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 80)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._table_view, 1)

        # Summary
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("color: #666; padding: 4px;")
        layout.addWidget(self._summary_label)

        self._update_summary()

    def refresh(self) -> None:
        """Refresh the history view."""
        self._history.load()
        self._table_model.refresh()
        self._update_summary()

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self._proxy_model.set_search_text(text)

    def _on_status_filter_changed(self) -> None:
        """Handle status filter change."""
        status = self._status_combo.currentData()
        self._proxy_model.set_status_filter(status)

    def _on_delete_oldest(self) -> None:
        """Handle Delete Oldest N button click."""
        count = self._history.count()
        if count == 0:
            QMessageBox.information(self, "No Records", "History is empty.")
            return

        n, ok = QInputDialog.getInt(
            self,
            "Delete Oldest Records",
            f"Enter number of oldest records to delete (1-{count}):",
            value=10,
            minValue=1,
            maxValue=count,
        )

        if ok:
            deleted = self._history.delete_oldest(n)
            self._table_model.refresh()
            self._update_summary()
            QMessageBox.information(
                self, "Records Deleted", f"Deleted {deleted} oldest record(s)."
            )

    def _on_clear_all(self) -> None:
        """Handle Clear All button click."""
        count = self._history.count()
        if count == 0:
            QMessageBox.information(self, "No Records", "History is empty.")
            return

        reply = QMessageBox.question(
            self,
            "Clear All History",
            f"Are you sure you want to delete all {count} history record(s)?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = self._history.clear_all()
            self._table_model.refresh()
            self._update_summary()
            QMessageBox.information(
                self, "History Cleared", f"Deleted {deleted} record(s)."
            )

    def _on_export_csv(self) -> None:
        """Handle Export CSV button click."""
        if self._history.count() == 0:
            QMessageBox.information(self, "No Records", "History is empty.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export History to CSV",
            "ingest_history.csv",
            "CSV Files (*.csv)",
        )

        if file_path:
            try:
                count = self._history.export_csv(Path(file_path))
                QMessageBox.information(
                    self, "Export Complete", f"Exported {count} record(s) to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Failed", f"Failed to export history:\n{str(e)}"
                )

    def _on_row_double_clicked(self, index: QModelIndex) -> None:
        """Handle double-click on a row."""
        source_index = self._proxy_model.mapToSource(index)
        record = self._table_model.get_record(source_index.row())

        if record and record.status.lower() == "failed" and record.error_message:
            self._show_error_details(record)

    def _show_error_details(self, record: HistoryRecord) -> None:
        """Show error details dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Error Details - {record.filename}")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)

        # Error message
        msg_label = QLabel(f"<b>Error:</b> {record.error_message}")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # Detail text
        layout.addWidget(QLabel("<b>Details:</b>"))
        detail_text = QTextEdit()
        detail_text.setPlainText(record.error_detail or "No additional details available.")
        detail_text.setReadOnly(True)
        layout.addWidget(detail_text)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _update_summary(self) -> None:
        """Update summary label."""
        counts = self._history.count_by_status()
        total = self._history.count()

        completed = counts.get("completed", 0)
        failed = counts.get("failed", 0)
        cancelled = counts.get("cancelled", 0)

        self._summary_label.setText(
            f"Total: {total} records | "
            f"{completed} completed | {failed} failed | {cancelled} cancelled"
        )
