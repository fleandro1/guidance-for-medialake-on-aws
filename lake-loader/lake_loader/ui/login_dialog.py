"""Login dialog for LakeLoader authentication."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QCheckBox,
    QGroupBox,
)
from PySide6.QtGui import QFont

from lake_loader.core.config import Config
from lake_loader.services.auth_service import (
    AuthService,
    AuthenticationError,
    InvalidCredentialsError,
)
from lake_loader.services.credential_manager import CredentialManager
from lake_loader.ui.theme import PRIMARY_BUTTON_STYLE, ERROR_STYLE


class LoginDialog(QDialog):
    """
    Dialog for user authentication.

    Allows users to log in with their Media Lake credentials.
    """

    # Emitted when login succeeds
    login_successful = Signal()

    def __init__(
        self,
        config: Config,
        auth_service: AuthService,
        credential_manager: CredentialManager,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._auth_service = auth_service
        self._credential_manager = credential_manager

        self.setWindowTitle("LakeLoader - Sign In")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._setup_ui()
        self._load_saved_credentials()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 32, 32, 32)

        # Title
        title = QLabel("Media Lake Connection")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Sign in with your Media Lake credentials")
        subtitle.setStyleSheet("color: #888888;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Credentials group
        creds_group = QGroupBox("Credentials")
        creds_layout = QFormLayout(creds_group)
        creds_layout.setSpacing(12)

        # Username
        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("username@example.com")
        self._username_edit.returnPressed.connect(self._on_login)
        creds_layout.addRow("Username:", self._username_edit)

        # Password
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("••••••••")
        self._password_edit.returnPressed.connect(self._on_login)
        creds_layout.addRow("Password:", self._password_edit)

        # Remember credentials checkbox
        self._remember_checkbox = QCheckBox("Remember credentials")
        self._remember_checkbox.setChecked(self._credential_manager.has_credentials())
        creds_layout.addRow("", self._remember_checkbox)

        layout.addWidget(creds_group)

        # Error label (hidden by default)
        self._error_label = QLabel()
        self._error_label.setStyleSheet(
            "color: #dc3545; background-color: rgba(220, 53, 69, 0.1); "
            "padding: 10px; border-radius: 4px;"
        )
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        button_layout.addStretch()

        self._login_button = QPushButton("Sign In")
        self._login_button.setDefault(True)
        self._login_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._login_button.clicked.connect(self._on_login)
        button_layout.addWidget(self._login_button)

        layout.addLayout(button_layout)

    def _load_saved_credentials(self) -> None:
        """Load saved credentials from keychain."""
        creds = self._credential_manager.get_credentials()
        if creds:
            self._username_edit.setText(creds[0])
            self._password_edit.setText(creds[1])
            self._login_button.setFocus()
        elif self._config.saved_username:
            # Migration: pick up old saved_username from config
            self._username_edit.setText(self._config.saved_username)
            self._password_edit.setFocus()
        else:
            self._username_edit.setFocus()

    def _on_login(self) -> None:
        """Handle login button click."""
        username = self._username_edit.text().strip()
        password = self._password_edit.text()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        # Disable UI during login
        self._set_ui_enabled(False)
        self._error_label.setVisible(False)

        try:
            # Attempt authentication
            self._auth_service.authenticate(username, password)

            # Save or clear credentials
            if self._remember_checkbox.isChecked():
                self._credential_manager.store_credentials(username, password)
            else:
                self._credential_manager.delete_credentials()

            # Clear legacy saved_username from config
            if self._config.saved_username:
                self._config.saved_username = ""
                self._config.save()

            # Success
            self.login_successful.emit()
            self.accept()

        except InvalidCredentialsError:
            self._show_error("Invalid username or password.")
            self._password_edit.clear()
            self._password_edit.setFocus()

        except AuthenticationError as e:
            error_msg = e.message
            if e.detail:
                error_msg += f"\n\n{e.detail}"
            self._show_error(error_msg)

        except Exception as e:
            self._show_error(f"Login failed: {str(e)}")

        finally:
            self._set_ui_enabled(True)

    def _show_error(self, message: str) -> None:
        """Show error message."""
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable UI elements."""
        self._username_edit.setEnabled(enabled)
        self._password_edit.setEnabled(enabled)
        self._remember_checkbox.setEnabled(enabled)
        self._login_button.setEnabled(enabled)
        self._login_button.setText("Sign In" if enabled else "Signing in...")

    def get_username(self) -> str:
        """Get the entered username."""
        return self._username_edit.text().strip()
