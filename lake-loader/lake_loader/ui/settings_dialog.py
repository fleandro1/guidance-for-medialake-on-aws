"""Settings dialog for LakeLoader configuration."""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from lake_loader.core.config import Config, AWS_REGIONS
from lake_loader.core.models import ConnectorInfo
from lake_loader.ui.theme import PRIMARY_BUTTON_STYLE, SUCCESS_STYLE, ERROR_STYLE


class SettingsDialog(QDialog):
    """
    Dialog for editing application settings.

    All config fields are editable through this dialog.
    """

    # Emitted when settings are saved
    settings_saved = Signal()

    # Emitted when test connection is requested
    test_connection_requested = Signal()

    def __init__(
        self,
        config: Config,
        connectors: Optional[List[ConnectorInfo]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._connectors = connectors or []

        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Tab widget for organization
        tabs = QTabWidget()

        # Connection tab
        connection_tab = self._create_connection_tab()
        tabs.addTab(connection_tab, "Connection")

        # Upload tab
        upload_tab = self._create_upload_tab()
        tabs.addTab(upload_tab, "Upload")

        # History tab
        history_tab = self._create_history_tab()
        tabs.addTab(history_tab, "History")

        layout.addWidget(tabs)

        # Test connection result label
        self._test_result_label = QLabel()
        self._test_result_label.setWordWrap(True)
        self._test_result_label.setVisible(False)
        layout.addWidget(self._test_result_label)

        # Buttons
        button_layout = QHBoxLayout()

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._on_test_connection)
        button_layout.addWidget(self._test_btn)

        button_layout.addStretch()

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)
        button_layout.addWidget(self._button_box)

        layout.addLayout(button_layout)

    def _create_connection_tab(self) -> QWidget:
        """Create the connection settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # API Settings
        api_group = QGroupBox("Media Lake API")
        api_layout = QFormLayout(api_group)

        self._api_url_edit = QLineEdit()
        self._api_url_edit.setPlaceholderText("https://your-api.execute-api.region.amazonaws.com/prod")
        api_layout.addRow("API Base URL:", self._api_url_edit)

        layout.addWidget(api_group)

        # Cognito Settings
        cognito_group = QGroupBox("AWS Cognito Authentication")
        cognito_layout = QFormLayout(cognito_group)

        self._user_pool_edit = QLineEdit()
        self._user_pool_edit.setPlaceholderText("us-east-1_XXXXXXXXX")
        cognito_layout.addRow("User Pool ID:", self._user_pool_edit)

        self._client_id_edit = QLineEdit()
        self._client_id_edit.setPlaceholderText("XXXXXXXXXXXXXXXXXXXXXXXXXX")
        cognito_layout.addRow("Client ID:", self._client_id_edit)

        self._region_combo = QComboBox()
        for region in AWS_REGIONS:
            self._region_combo.addItem(region, region)
        cognito_layout.addRow("Region:", self._region_combo)

        layout.addWidget(cognito_group)

        # User Settings
        user_group = QGroupBox("User")
        user_layout = QFormLayout(user_group)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Saved for convenience (optional)")
        user_layout.addRow("Saved Username:", self._username_edit)

        layout.addWidget(user_group)

        layout.addStretch()
        return tab

    def _create_upload_tab(self) -> QWidget:
        """Create the upload settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Concurrency Settings
        concurrency_group = QGroupBox("Concurrency")
        concurrency_layout = QFormLayout(concurrency_group)

        self._concurrent_spin = QSpinBox()
        self._concurrent_spin.setRange(1, 20)
        self._concurrent_spin.setSuffix(" uploads")
        concurrency_layout.addRow("Max Concurrent:", self._concurrent_spin)

        layout.addWidget(concurrency_group)

        # Default Settings
        defaults_group = QGroupBox("Defaults")
        defaults_layout = QFormLayout(defaults_group)

        self._default_connector_combo = QComboBox()
        self._default_connector_combo.addItem("(None)", "")
        for connector in self._connectors:
            self._default_connector_combo.addItem(connector.name, connector.id)
        defaults_layout.addRow("Default Connector:", self._default_connector_combo)

        self._default_path_edit = QLineEdit()
        self._default_path_edit.setPlaceholderText("Optional subfolder")
        defaults_layout.addRow("Default Path:", self._default_path_edit)

        layout.addWidget(defaults_group)

        # Retry Settings
        retry_group = QGroupBox("Retry Behavior")
        retry_layout = QFormLayout(retry_group)

        self._retry_checkbox = QCheckBox("Automatically retry failed uploads")
        retry_layout.addRow("", self._retry_checkbox)

        self._max_retries_spin = QSpinBox()
        self._max_retries_spin.setRange(0, 10)
        self._max_retries_spin.setSuffix(" retries")
        retry_layout.addRow("Max Retries:", self._max_retries_spin)

        layout.addWidget(retry_group)

        # Multipart Settings
        multipart_group = QGroupBox("Multipart Upload")
        multipart_layout = QFormLayout(multipart_group)

        self._chunk_size_spin = QSpinBox()
        self._chunk_size_spin.setRange(5, 100)
        self._chunk_size_spin.setSuffix(" MB")
        multipart_layout.addRow("Chunk Size:", self._chunk_size_spin)

        info_label = QLabel(
            "Files larger than 100 MB are uploaded using multipart upload.\n"
            "Larger chunk size = fewer requests but more memory usage."
        )
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        info_label.setWordWrap(True)
        multipart_layout.addRow("", info_label)

        layout.addWidget(multipart_group)

        layout.addStretch()
        return tab

    def _create_history_tab(self) -> QWidget:
        """Create the history settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # History Settings
        history_group = QGroupBox("History Storage")
        history_layout = QFormLayout(history_group)

        self._max_history_spin = QSpinBox()
        self._max_history_spin.setRange(100, 100000)
        self._max_history_spin.setSingleStep(1000)
        self._max_history_spin.setSuffix(" records")
        history_layout.addRow("Max Records:", self._max_history_spin)

        info_label = QLabel(
            "Older records are automatically removed when the limit is exceeded."
        )
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        info_label.setWordWrap(True)
        history_layout.addRow("", info_label)

        layout.addWidget(history_group)

        layout.addStretch()
        return tab

    def _load_values(self) -> None:
        """Load current config values into the form."""
        self._api_url_edit.setText(self._config.api_base_url)
        self._user_pool_edit.setText(self._config.cognito_user_pool_id)
        self._client_id_edit.setText(self._config.cognito_client_id)
        self._username_edit.setText(self._config.saved_username)

        # Region
        idx = self._region_combo.findData(self._config.cognito_region)
        if idx >= 0:
            self._region_combo.setCurrentIndex(idx)

        # Upload settings
        self._concurrent_spin.setValue(self._config.max_concurrent_uploads)
        self._default_path_edit.setText(self._config.default_destination_path)
        self._retry_checkbox.setChecked(self._config.retry_on_failure)
        self._max_retries_spin.setValue(self._config.max_retries)
        self._chunk_size_spin.setValue(self._config.chunk_size_mb)

        # Default connector
        idx = self._default_connector_combo.findData(self._config.default_connector_id)
        if idx >= 0:
            self._default_connector_combo.setCurrentIndex(idx)

        # History
        self._max_history_spin.setValue(self._config.max_history_records)

    def _on_save(self) -> None:
        """Handle save button click."""
        # Validate required fields
        api_url = self._api_url_edit.text().strip()
        user_pool = self._user_pool_edit.text().strip()
        client_id = self._client_id_edit.text().strip()

        if not api_url:
            QMessageBox.warning(self, "Validation Error", "API Base URL is required.")
            return

        if not user_pool:
            QMessageBox.warning(self, "Validation Error", "User Pool ID is required.")
            return

        if not client_id:
            QMessageBox.warning(self, "Validation Error", "Client ID is required.")
            return

        # Update config
        self._config.api_base_url = api_url
        self._config.cognito_user_pool_id = user_pool
        self._config.cognito_client_id = client_id
        self._config.cognito_region = self._region_combo.currentData()
        self._config.saved_username = self._username_edit.text().strip()

        self._config.max_concurrent_uploads = self._concurrent_spin.value()
        self._config.default_connector_id = self._default_connector_combo.currentData() or ""
        self._config.default_destination_path = self._default_path_edit.text().strip()
        self._config.retry_on_failure = self._retry_checkbox.isChecked()
        self._config.max_retries = self._max_retries_spin.value()
        self._config.chunk_size_mb = self._chunk_size_spin.value()

        self._config.max_history_records = self._max_history_spin.value()

        # Save to file
        try:
            self._config.save()
            self.settings_saved.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Save Failed", f"Failed to save settings:\n{str(e)}"
            )

    def _on_test_connection(self) -> None:
        """Handle test connection button click."""
        # Validate minimum required fields
        api_url = self._api_url_edit.text().strip()
        user_pool = self._user_pool_edit.text().strip()
        client_id = self._client_id_edit.text().strip()

        if not all([api_url, user_pool, client_id]):
            self._show_test_result(False, "Please fill in all connection settings first.")
            return

        self._test_result_label.setText("Testing connection...")
        self._test_result_label.setStyleSheet("color: #888888;")
        self._test_result_label.setVisible(True)
        self._test_btn.setEnabled(False)

        # Emit signal for parent to handle the actual test
        self.test_connection_requested.emit()

    def show_test_result(self, success: bool, message: str) -> None:
        """Show the result of a connection test."""
        self._show_test_result(success, message)
        self._test_btn.setEnabled(True)

    def _show_test_result(self, success: bool, message: str) -> None:
        """Display test result."""
        if success:
            self._test_result_label.setStyleSheet(
                "color: #28a745; background-color: rgba(40, 167, 69, 0.15); "
                "padding: 10px; border-radius: 4px; border: 1px solid rgba(40, 167, 69, 0.3);"
            )
            self._test_result_label.setText(f"✓ {message}")
        else:
            self._test_result_label.setStyleSheet(
                "color: #dc3545; background-color: rgba(220, 53, 69, 0.15); "
                "padding: 10px; border-radius: 4px; border: 1px solid rgba(220, 53, 69, 0.3);"
            )
            self._test_result_label.setText(f"✗ {message}")

        self._test_result_label.setVisible(True)

    def update_connectors(self, connectors: List[ConnectorInfo]) -> None:
        """Update the connector list."""
        self._connectors = connectors
        current_value = self._default_connector_combo.currentData()

        self._default_connector_combo.clear()
        self._default_connector_combo.addItem("(None)", "")
        for connector in connectors:
            self._default_connector_combo.addItem(connector.name, connector.id)

        # Restore selection
        idx = self._default_connector_combo.findData(current_value)
        if idx >= 0:
            self._default_connector_combo.setCurrentIndex(idx)

    def get_temp_config(self) -> Config:
        """Get config with current form values (for testing)."""
        temp = Config()
        temp.api_base_url = self._api_url_edit.text().strip()
        temp.cognito_user_pool_id = self._user_pool_edit.text().strip()
        temp.cognito_client_id = self._client_id_edit.text().strip()
        temp.cognito_region = self._region_combo.currentData()
        return temp
