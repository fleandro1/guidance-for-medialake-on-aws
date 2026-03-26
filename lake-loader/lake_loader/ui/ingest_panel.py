"""Ingest panel for file upload queue management."""

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QMimeData, QModelIndex, QAbstractTableModel
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QPushButton,
    QComboBox,
    QLineEdit,
    QLabel,
    QFileDialog,
    QHeaderView,
    QMenu,
    QMessageBox,
    QDialog,
    QTextEdit,
    QDialogButtonBox,
    QFrame,
)

from lake_loader.core.models import (
    ConnectorInfo,
    IngestStatus,
    IngestTask,
    format_file_size,
    SUPPORTED_EXTENSIONS,
)
from lake_loader.services.ingest_manager import IngestManager
from lake_loader.ui.widgets.progress_delegate import ProgressDelegate
from lake_loader.ui.widgets.status_badge import get_status_color, get_status_label
from lake_loader.ui.theme import (
    PRIMARY_BUTTON_STYLE,
    DANGER_BUTTON_STYLE,
    DROP_ZONE_STYLE,
    DROP_ZONE_HIGHLIGHT_STYLE,
    TABLE_STYLE,
)


class IngestTableModel(QAbstractTableModel):
    """Table model for the ingest queue."""

    COLUMNS = ["#", "Filename", "Size", "Status", "Progress", "Error"]

    def __init__(self, ingest_manager: IngestManager, parent=None):
        super().__init__(parent)
        self._manager = ingest_manager

        # Connect to manager signals
        self._manager.task_added.connect(self._on_queue_changed)
        self._manager.task_removed.connect(self._on_queue_changed)
        self._manager.task_started.connect(self._on_task_updated)
        self._manager.task_progress.connect(self._on_task_progress)
        self._manager.task_completed.connect(self._on_task_updated)
        self._manager.task_failed.connect(self._on_task_updated)
        self._manager.task_cancelled.connect(self._on_task_updated)

    def rowCount(self, parent=QModelIndex()):
        return len(self._manager.tasks)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        tasks = self._manager.tasks
        if index.row() >= len(tasks):
            return None

        task = tasks[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # #
                return index.row() + 1
            elif col == 1:  # Filename
                return task.filename
            elif col == 2:  # Size
                return format_file_size(task.file_size)
            elif col == 3:  # Status
                return get_status_label(task.status)
            elif col == 4:  # Progress
                return task.progress
            elif col == 5:  # Error
                return task.error_message or ""

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 3:  # Status color
                return get_status_color(task.status)

        elif role == Qt.ItemDataRole.UserRole:
            return task.task_id

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1:  # Full path tooltip
                return task.file_path
            elif col == 5 and task.error_message:  # Error detail tooltip
                return task.error_detail or task.error_message

        return None

    def _on_queue_changed(self):
        """Handle queue structure change."""
        self.layoutChanged.emit()

    def _on_task_updated(self, task_id: str):
        """Handle task state change."""
        tasks = self._manager.tasks
        for row, task in enumerate(tasks):
            if task.task_id == task_id:
                self.dataChanged.emit(
                    self.index(row, 0),
                    self.index(row, self.columnCount() - 1),
                )
                break

    def _on_task_progress(self, task: IngestTask, percent: int):
        """Handle task progress update."""
        tasks = self._manager.tasks
        for row, t in enumerate(tasks):
            if t.task_id == task.task_id:
                # Only update progress column
                self.dataChanged.emit(
                    self.index(row, 4),
                    self.index(row, 4),
                )
                break


class IngestPanel(QWidget):
    """
    Panel for managing file ingestion.

    Supports file selection via buttons or drag-and-drop.
    """

    # Emitted when connectors need to be loaded
    connectors_requested = Signal()

    def __init__(
        self,
        ingest_manager: IngestManager,
        parent=None,
    ):
        super().__init__(parent)
        self._manager = ingest_manager
        self._connectors: List[ConnectorInfo] = []

        self.setAcceptDrops(True)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Controls row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Add Files button
        self._add_files_btn = QPushButton("Add Files")
        self._add_files_btn.clicked.connect(self._on_add_files)
        controls_layout.addWidget(self._add_files_btn)

        # Add Folder button
        self._add_folder_btn = QPushButton("Add Folder")
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        controls_layout.addWidget(self._add_folder_btn)

        controls_layout.addSpacing(16)

        # Connector dropdown
        controls_layout.addWidget(QLabel("Connector:"))
        self._connector_combo = QComboBox()
        self._connector_combo.setMinimumWidth(200)
        controls_layout.addWidget(self._connector_combo)

        # Destination path
        controls_layout.addWidget(QLabel("Path:"))
        self._dest_path_edit = QLineEdit()
        self._dest_path_edit.setPlaceholderText("Optional subfolder")
        self._dest_path_edit.setMaximumWidth(200)
        controls_layout.addWidget(self._dest_path_edit)

        controls_layout.addStretch()

        # Start/Pause/Cancel buttons
        self._start_btn = QPushButton("Start Upload")
        self._start_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        controls_layout.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel All")
        self._cancel_btn.setStyleSheet(DANGER_BUTTON_STYLE)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel_all)
        controls_layout.addWidget(self._cancel_btn)

        layout.addLayout(controls_layout)

        # Drop zone / Table
        self._drop_frame = DropZoneFrame(self)
        self._drop_frame.files_dropped.connect(self._on_files_dropped)

        table_layout = QVBoxLayout(self._drop_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # Queue table
        self._table_model = IngestTableModel(self._manager)
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table_view.customContextMenuRequested.connect(self._on_context_menu)

        # Set column widths
        header = self._table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 120)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        # Progress delegate for progress column
        self._progress_delegate = ProgressDelegate()
        self._table_view.setItemDelegateForColumn(4, self._progress_delegate)

        table_layout.addWidget(self._table_view)

        layout.addWidget(self._drop_frame, 1)

        # Summary bar
        self._summary_label = QLabel("0 pending | 0 uploading | 0 completed | 0 failed")
        self._summary_label.setStyleSheet("color: #888888; padding: 4px;")
        layout.addWidget(self._summary_label)

    def _connect_signals(self) -> None:
        """Connect manager signals."""
        self._manager.queue_updated.connect(self._update_summary)

    def set_connectors(self, connectors: List[ConnectorInfo]) -> None:
        """Update available connectors."""
        self._connectors = connectors
        self._connector_combo.clear()

        for connector in connectors:
            self._connector_combo.addItem(connector.name, connector.id)

    def _get_selected_connector_id(self) -> Optional[str]:
        """Get currently selected connector ID."""
        return self._connector_combo.currentData()

    def _get_destination_path(self) -> str:
        """Get destination path."""
        return self._dest_path_edit.text().strip()

    def _on_add_files(self) -> None:
        """Handle Add Files button click."""
        # Build file filter from supported extensions
        extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        file_filter = f"Media Files ({extensions});;All Files (*)"

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Ingest",
            "",
            file_filter,
        )

        if files:
            self._add_files_to_queue(files)

    def _on_add_folder(self) -> None:
        """Handle Add Folder button click."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Ingest",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )

        if folder:
            connector_id = self._get_selected_connector_id()
            if not connector_id:
                QMessageBox.warning(self, "No Connector", "Please select a connector first.")
                return

            tasks = self._manager.add_folder(
                folder,
                connector_id,
                self._get_destination_path(),
            )

            if tasks:
                self._show_toast(f"Added {len(tasks)} files from folder")

    def _on_files_dropped(self, paths: List[str]) -> None:
        """Handle files dropped onto the panel."""
        self._add_files_to_queue(paths)

    def _add_files_to_queue(self, paths: List[str]) -> None:
        """Add files to the ingest queue."""
        connector_id = self._get_selected_connector_id()
        if not connector_id:
            QMessageBox.warning(self, "No Connector", "Please select a connector first.")
            return

        added = 0
        for path in paths:
            if os.path.isdir(path):
                tasks = self._manager.add_folder(
                    path,
                    connector_id,
                    self._get_destination_path(),
                )
                added += len(tasks)
            elif os.path.isfile(path):
                task = self._manager.add_file(
                    path,
                    connector_id,
                    self._get_destination_path(),
                )
                if task:
                    added += 1

        if added > 0:
            self._show_toast(f"Added {added} file(s) to queue")

    def _on_start(self) -> None:
        """Handle Start Upload button click."""
        self._manager.start_uploads()
        # Only update button states if uploads actually started
        if self._manager.active_count > 0:
            self._start_btn.setEnabled(False)

    def _on_cancel_all(self) -> None:
        """Handle Cancel All button click."""
        reply = QMessageBox.question(
            self,
            "Cancel All Uploads",
            "Are you sure you want to cancel all uploads?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._manager.cancel_all()
            self._start_btn.setEnabled(True)

    def _on_context_menu(self, pos) -> None:
        """Show context menu for table."""
        index = self._table_view.indexAt(pos)
        if not index.isValid():
            return

        task_id = index.data(Qt.ItemDataRole.UserRole)
        task = self._manager.get_task(task_id)
        if not task:
            return

        menu = QMenu(self)

        if task.status == IngestStatus.PENDING:
            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(lambda: self._manager.remove_task(task_id))
            menu.addAction(remove_action)

        if task.status == IngestStatus.FAILED:
            retry_action = QAction("Retry", self)
            retry_action.triggered.connect(lambda: self._manager.retry_task(task_id))
            menu.addAction(retry_action)

        if task.error_message:
            menu.addSeparator()
            details_action = QAction("Show Error Details", self)
            details_action.triggered.connect(lambda: self._show_error_details(task))
            menu.addAction(details_action)

        if not menu.isEmpty():
            menu.exec(self._table_view.viewport().mapToGlobal(pos))

    def _show_error_details(self, task: IngestTask) -> None:
        """Show error details dialog."""
        dialog = ErrorDetailDialog(
            task.filename,
            task.error_message or "Unknown error",
            task.error_detail or "",
            self,
        )
        dialog.exec()

    def _update_summary(self, pending: int, active: int, completed: int, failed: int) -> None:
        """Update summary label."""
        self._summary_label.setText(
            f"{pending} pending | {active} uploading | {completed} completed | {failed} failed"
        )

        # Update button states
        has_pending = pending > 0
        has_active = active > 0

        self._cancel_btn.setEnabled(has_pending or has_active)

        if has_active:
            self._start_btn.setEnabled(False)
        else:
            self._start_btn.setEnabled(has_pending)

    def _show_toast(self, message: str) -> None:
        """Show a brief status message."""
        # For now, update summary label temporarily
        original = self._summary_label.text()
        self._summary_label.setText(message)
        self._summary_label.setStyleSheet("color: #28a745; padding: 4px;")

        # Reset after 2 seconds
        from PySide6.QtCore import QTimer

        QTimer.singleShot(2000, lambda: self._reset_summary_style(original))

    def update_task(self, task: IngestTask) -> None:
        """Update display for a task (triggers model refresh)."""
        # The model is connected to manager signals, so this will update automatically
        # We just need to refresh the view if needed
        self._table_model.layoutChanged.emit()

    def _reset_summary_style(self, original_text: str) -> None:
        """Reset summary label style."""
        self._summary_label.setStyleSheet("color: #888888; padding: 4px;")
        # Trigger summary update
        self._update_summary(
            self._manager.pending_count,
            self._manager.active_count,
            self._manager.completed_count,
            self._manager.failed_count,
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_frame.set_drop_highlight(True)

    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave."""
        self._drop_frame.set_drop_highlight(False)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop."""
        self._drop_frame.set_drop_highlight(False)

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)

        if paths:
            self._on_files_dropped(paths)
            event.acceptProposedAction()


class DropZoneFrame(QFrame):
    """Frame that provides visual feedback for drag-and-drop."""

    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setAcceptDrops(True)
        self._default_style = DROP_ZONE_STYLE
        self._highlight_style = DROP_ZONE_HIGHLIGHT_STYLE
        self.setStyleSheet(self._default_style)

    def set_drop_highlight(self, highlight: bool) -> None:
        """Set drop highlight state."""
        self.setStyleSheet(self._highlight_style if highlight else self._default_style)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_drop_highlight(True)

    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave."""
        self.set_drop_highlight(False)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop."""
        self.set_drop_highlight(False)

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)

        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class ErrorDetailDialog(QDialog):
    """Dialog for showing error details."""

    def __init__(self, filename: str, error_message: str, error_detail: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Error Details - {filename}")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        # Error message
        msg_label = QLabel(f"<b>Error:</b> {error_message}")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # Detail text
        layout.addWidget(QLabel("<b>Details:</b>"))
        detail_text = QTextEdit()
        detail_text.setPlainText(error_detail or "No additional details available.")
        detail_text.setReadOnly(True)
        layout.addWidget(detail_text)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
