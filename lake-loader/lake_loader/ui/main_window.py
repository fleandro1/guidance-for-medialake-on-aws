"""Main window for LakeLoader application."""

from typing import Optional, List

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QLabel,
    QMessageBox,
    QApplication,
)

from lake_loader.core.config import Config
from lake_loader.core.history import IngestHistory
from lake_loader.core.models import IngestTask, IngestStatus, ConnectorInfo
from lake_loader.services.auth_service import AuthService
from lake_loader.services.credential_manager import CredentialManager
from lake_loader.services.api_client import MediaLakeAPIClient
from lake_loader.services.ingest_manager import IngestManager
from lake_loader.ui.ingest_panel import IngestPanel
from lake_loader.ui.history_panel import HistoryPanel
from lake_loader.ui.settings_dialog import SettingsDialog
from lake_loader.ui.login_dialog import LoginDialog


class MainWindow(QMainWindow):
    """
    Main application window with tabbed interface.

    Tabs:
      - Ingest: File queue and upload controls
      - History: Completed ingest records
      - Settings: Configuration (opens as dialog)
    """

    def __init__(
        self,
        config: Config,
        history: IngestHistory,
        auth_service: AuthService,
        api_client: MediaLakeAPIClient,
        ingest_manager: IngestManager,
    ):
        super().__init__()

        self._config = config
        self._history = history
        self._auth_service = auth_service
        self._api_client = api_client
        self._ingest_manager = ingest_manager
        self._connectors: List[ConnectorInfo] = []

        self.setWindowTitle("LakeLoader - Media Lake Ingest")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)

        self._setup_ui()
        self._connect_signals()

        # Load connectors on start
        QTimer.singleShot(100, self._load_connectors)

    def _setup_ui(self) -> None:
        """Set up the main window UI."""
        # Central widget - tab container
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Ingest panel
        self._ingest_panel = IngestPanel(
            ingest_manager=self._ingest_manager,
        )
        self._tabs.addTab(self._ingest_panel, "Ingest")

        # History panel
        self._history_panel = HistoryPanel(history=self._history)
        self._tabs.addTab(self._history_panel, "History")

        # Settings button (opens dialog)
        settings_tab = self._create_settings_tab()
        self._tabs.addTab(settings_tab, "Settings")

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label, 1)

        self._queue_label = QLabel("Queue: 0")
        self._status_bar.addPermanentWidget(self._queue_label)

        self._active_label = QLabel("Active: 0")
        self._status_bar.addPermanentWidget(self._active_label)

        self._user_label = QLabel()
        self._status_bar.addPermanentWidget(self._user_label)

    def _create_settings_tab(self) -> QLabel:
        """Create a placeholder for settings (opens dialog on tab select)."""
        label = QLabel(
            "Click here to open Settings...\n\n"
            "(Settings open in a separate dialog)"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 14px; color: #666;")
        return label

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        # Ingest manager signals
        self._ingest_manager.task_started.connect(self._on_task_started)
        self._ingest_manager.task_progress.connect(self._on_task_progress)
        self._ingest_manager.task_completed.connect(self._on_task_completed)
        self._ingest_manager.task_failed.connect(self._on_task_failed)
        self._ingest_manager.queue_changed.connect(self._update_status_counts)

        # Tab changed
        self._tabs.currentChanged.connect(self._on_tab_changed)

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab selection."""
        if index == 2:  # Settings tab
            self._tabs.setCurrentIndex(0)  # Go back to first tab
            self._open_settings_dialog()

    def _open_settings_dialog(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(
            config=self._config,
            connectors=self._connectors,
            parent=self,
        )
        dialog.test_connection_requested.connect(
            lambda: self._test_connection(dialog)
        )
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _test_connection(self, dialog: SettingsDialog) -> None:
        """Test the connection with current dialog settings."""
        temp_config = dialog.get_temp_config()

        try:
            # Create temporary auth service
            temp_auth = AuthService(
                user_pool_id=temp_config.cognito_user_pool_id,
                client_id=temp_config.cognito_client_id,
                region=temp_config.cognito_region,
            )

            # We need credentials to test
            login_dialog = LoginDialog(
                config=temp_config,
                auth_service=temp_auth,
                credential_manager=CredentialManager(),
                parent=dialog,
            )
            login_dialog.setWindowTitle("Test Connection - Login")

            if login_dialog.exec() == LoginDialog.DialogCode.Accepted:
                # Create temp API client
                temp_client = MediaLakeAPIClient(
                    base_url=temp_config.api_base_url,
                    token_provider=temp_auth.get_id_token,
                )
                connectors = temp_client.get_connectors()
                dialog.show_test_result(
                    True,
                    f"Connection successful! Found {len(connectors)} connector(s)."
                )
                dialog.update_connectors(connectors)
            else:
                dialog.show_test_result(False, "Login cancelled.")

        except Exception as e:
            dialog.show_test_result(False, f"Connection failed: {str(e)}")

    @Slot()
    def _on_settings_saved(self) -> None:
        """Handle settings saved."""
        self._status_label.setText("Settings saved")
        # Update ingest manager concurrency
        self._ingest_manager.set_max_concurrent(self._config.max_concurrent_uploads)
        # Reload connectors with new settings
        self._load_connectors()

    def _load_connectors(self) -> None:
        """Load connectors from API."""
        try:
            self._connectors = self._api_client.get_connectors()
            self._ingest_panel.set_connectors(self._connectors)
            self._status_label.setText(
                f"Loaded {len(self._connectors)} connector(s)"
            )
        except Exception as e:
            self._status_label.setText(f"Failed to load connectors: {e}")
            QMessageBox.warning(
                self,
                "Connection Error",
                f"Failed to load connectors from Media Lake:\n\n{str(e)}\n\n"
                "Please check your settings.",
            )

    @Slot(IngestTask)
    def _on_task_started(self, task: IngestTask) -> None:
        """Handle task started."""
        self._ingest_panel.update_task(task)
        self._update_status_counts()

    @Slot(IngestTask, int)
    def _on_task_progress(self, task: IngestTask, percent: int) -> None:
        """Handle task progress update."""
        self._ingest_panel.update_task(task)

    @Slot(IngestTask)
    def _on_task_completed(self, task: IngestTask) -> None:
        """Handle task completed."""
        self._ingest_panel.update_task(task)
        # History is already recorded by IngestManager._record_history()
        self._history_panel.refresh()
        self._update_status_counts()

    @Slot(IngestTask, str)
    def _on_task_failed(self, task: IngestTask, error: str) -> None:
        """Handle task failed."""
        self._ingest_panel.update_task(task)
        # History is already recorded by IngestManager._record_history()
        self._history_panel.refresh()
        self._update_status_counts()

    @Slot()
    def _update_status_counts(self) -> None:
        """Update status bar counts."""
        queue_size = len([
            t for t in self._ingest_manager.get_all_tasks()
            if t.status == IngestStatus.PENDING
        ])
        active = len([
            t for t in self._ingest_manager.get_all_tasks()
            if t.status == IngestStatus.UPLOADING
        ])

        self._queue_label.setText(f"Queue: {queue_size}")
        self._active_label.setText(f"Active: {active}")

    def set_authenticated_user(self, username: str) -> None:
        """Set the authenticated username display."""
        self._user_label.setText(f"User: {username}")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close."""
        # Check if there are active uploads
        active = [
            t for t in self._ingest_manager.get_all_tasks()
            if t.status in (IngestStatus.UPLOADING, IngestStatus.PENDING)
        ]

        if active:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                f"There are {len(active)} upload(s) in progress or pending.\n\n"
                "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        # Cancel all active uploads
        self._ingest_manager.cancel_all()

        event.accept()
