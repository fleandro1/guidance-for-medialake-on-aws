"""Login dialog for Media Lake authentication."""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from medialake_resolve.core.config import Config
from medialake_resolve.auth.credential_manager import CredentialManager, StoredCredentials
from medialake_resolve.auth.auth_service import AuthService
from medialake_resolve.auth.token_manager import TokenManager
from medialake_resolve.core.errors import AuthenticationError, InvalidCredentialsError


class LoginDialog(QDialog):
    """Dialog for configuring Media Lake connection and authentication.
    
    Signals:
        login_successful: Emitted when login succeeds with (username, medialake_url).
    """
    
    login_successful = Signal(str, str)
    
    def __init__(
        self,
        config: Config,
        credential_manager: CredentialManager,
        token_manager: TokenManager,
        parent=None,
    ):
        """Initialize login dialog.
        
        Args:
            config: Application configuration.
            credential_manager: Credential manager for secure storage.
            token_manager: Token manager for authentication.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self._config = config
        self._credential_manager = credential_manager
        self._token_manager = token_manager
        
        self._setup_ui()
        self._load_saved_credentials()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Connect to Media Lake")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Title
        title_label = QLabel("Media Lake Connection")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Server configuration group
        server_group = QGroupBox("Server Configuration")
        server_layout = QFormLayout(server_group)
        
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://medialake.example.com")
        server_layout.addRow("Media Lake URL:", self._url_input)
        
        # Advanced settings (collapsed by default)
        self._user_pool_input = QLineEdit()
        self._user_pool_input.setPlaceholderText("us-east-1_xxxxxxxxx")
        server_layout.addRow("Cognito User Pool ID:", self._user_pool_input)
        
        self._client_id_input = QLineEdit()
        self._client_id_input.setPlaceholderText("xxxxxxxxxxxxxxxxxxxxxxxxxx")
        server_layout.addRow("Cognito Client ID:", self._client_id_input)
        
        self._region_input = QLineEdit()
        self._region_input.setPlaceholderText("us-east-1")
        self._region_input.setText("us-east-1")
        server_layout.addRow("AWS Region:", self._region_input)
        
        layout.addWidget(server_group)
        
        # Credentials group
        creds_group = QGroupBox("Credentials")
        creds_layout = QFormLayout(creds_group)
        
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("username@example.com")
        creds_layout.addRow("Username/Email:", self._username_input)
        
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("••••••••")
        creds_layout.addRow("Password:", self._password_input)
        
        self._remember_checkbox = QCheckBox("Remember credentials")
        self._remember_checkbox.setChecked(True)
        creds_layout.addRow("", self._remember_checkbox)
        
        layout.addWidget(creds_group)
        
        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: red;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)
        
        button_layout.addStretch()
        
        self._connect_button = QPushButton("Connect")
        self._connect_button.setDefault(True)
        self._connect_button.clicked.connect(self._on_connect)
        button_layout.addWidget(self._connect_button)
        
        layout.addLayout(button_layout)
        
        # Connect Enter key
        self._password_input.returnPressed.connect(self._on_connect)
    
    def _load_saved_credentials(self) -> None:
        """Load saved credentials into the form."""
        credentials = self._credential_manager.get_credentials()
        
        if credentials:
            self._url_input.setText(credentials.medialake_url)
            self._user_pool_input.setText(credentials.cognito_user_pool_id)
            self._client_id_input.setText(credentials.cognito_client_id)
            self._region_input.setText(credentials.cognito_region)
            self._username_input.setText(credentials.username)
            # Don't populate password for security
        
        # Also load from config
        if self._config.medialake_url and not self._url_input.text():
            self._url_input.setText(self._config.medialake_url)
        if self._config.cognito_user_pool_id and not self._user_pool_input.text():
            self._user_pool_input.setText(self._config.cognito_user_pool_id)
        if self._config.cognito_client_id and not self._client_id_input.text():
            self._client_id_input.setText(self._config.cognito_client_id)
        if self._config.cognito_region and not self._region_input.text():
            self._region_input.setText(self._config.cognito_region)
    
    def _validate_inputs(self) -> bool:
        """Validate form inputs.
        
        Returns:
            True if all inputs are valid.
        """
        errors = []
        
        if not self._url_input.text().strip():
            errors.append("Media Lake URL is required")
        
        if not self._user_pool_input.text().strip():
            errors.append("Cognito User Pool ID is required")
        
        if not self._client_id_input.text().strip():
            errors.append("Cognito Client ID is required")
        
        if not self._username_input.text().strip():
            errors.append("Username is required")
        
        if not self._password_input.text():
            errors.append("Password is required")
        
        if errors:
            self._status_label.setText("\n".join(errors))
            return False
        
        self._status_label.setText("")
        return True
    
    def _on_connect(self) -> None:
        """Handle connect button click."""
        if not self._validate_inputs():
            return
        
        # Disable UI during connection
        self._set_ui_enabled(False)
        self._status_label.setStyleSheet("color: gray;")
        self._status_label.setText("Connecting...")
        
        # Get values
        medialake_url = self._url_input.text().strip()
        user_pool_id = self._user_pool_input.text().strip()
        client_id = self._client_id_input.text().strip()
        region = self._region_input.text().strip() or "us-east-1"
        username = self._username_input.text().strip()
        password = self._password_input.text()
        
        try:
            # Create auth service
            auth_service = AuthService(user_pool_id, client_id, region)
            self._token_manager.set_auth_service(auth_service)
            
            # Attempt authentication
            self._token_manager.authenticate(username, password)
            
            # Save credentials if requested
            if self._remember_checkbox.isChecked():
                self._credential_manager.store_credentials(
                    username=username,
                    password=password,
                    medialake_url=medialake_url,
                    cognito_user_pool_id=user_pool_id,
                    cognito_client_id=client_id,
                    cognito_region=region,
                )
            
            # Update config
            self._config.medialake_url = medialake_url
            self._config.cognito_user_pool_id = user_pool_id
            self._config.cognito_client_id = client_id
            self._config.cognito_region = region
            self._config.save()
            
            # Emit success and close
            self.login_successful.emit(username, medialake_url)
            self.accept()
            
        except InvalidCredentialsError as e:
            self._status_label.setStyleSheet("color: red;")
            self._status_label.setText("Invalid username or password")
            self._set_ui_enabled(True)
            
        except AuthenticationError as e:
            self._status_label.setStyleSheet("color: red;")
            self._status_label.setText(str(e))
            self._set_ui_enabled(True)
            
        except Exception as e:
            self._status_label.setStyleSheet("color: red;")
            self._status_label.setText(f"Connection failed: {e}")
            self._set_ui_enabled(True)
    
    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable UI elements.
        
        Args:
            enabled: Whether to enable the UI.
        """
        self._url_input.setEnabled(enabled)
        self._user_pool_input.setEnabled(enabled)
        self._client_id_input.setEnabled(enabled)
        self._region_input.setEnabled(enabled)
        self._username_input.setEnabled(enabled)
        self._password_input.setEnabled(enabled)
        self._remember_checkbox.setEnabled(enabled)
        self._connect_button.setEnabled(enabled)
        self._cancel_button.setEnabled(enabled)
