#!/usr/bin/env python3
"""
LakeLoader - Media Lake Ingest Application

A desktop application for bulk file ingestion into Media Lake.
Supports drag-and-drop, concurrent uploads, and progress tracking.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from lake_loader.core.config import Config
from lake_loader.core.history import IngestHistory
from lake_loader.services.auth_service import AuthService
from lake_loader.services.api_client import MediaLakeAPIClient
from lake_loader.services.ingest_manager import IngestManager
from lake_loader.ui.login_dialog import LoginDialog
from lake_loader.ui.main_window import MainWindow
from lake_loader.ui.theme import apply_dark_theme


def main() -> int:
    """Application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("LakeLoader")
    app.setApplicationDisplayName("LakeLoader - Media Lake Ingest")
    app.setOrganizationName("MediaLake")
    app.setOrganizationDomain("medialake.aws")

    # Set Fusion style (required for proper dark theme)
    app.setStyle("Fusion")
    
    # Apply dark theme matching DaVinci Resolve
    apply_dark_theme(app)

    # Load or create config
    try:
        config = Config.load()
    except Exception as e:
        config = Config()
        print(f"Using default config: {e}")

    # Load history
    history = IngestHistory(max_records=config.max_history_records)
    # History loads lazily on first access

    # Check if config is valid
    if not config.is_configured():
        # Show first-time setup message
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Welcome to LakeLoader")
        msg.setText("Welcome to LakeLoader!")
        msg.setInformativeText(
            "Before you can start uploading files, you need to configure "
            "your Media Lake connection settings.\n\n"
            "Please enter your Media Lake API URL and Cognito credentials "
            "in the Settings dialog."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        # Open settings dialog for initial configuration
        from lake_loader.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(config=config)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return 0

    # Create services
    auth_service = AuthService(
        user_pool_id=config.cognito_user_pool_id,
        client_id=config.cognito_client_id,
        region=config.cognito_region,
    )
    api_client = MediaLakeAPIClient(
        base_url=config.api_base_url,
        token_provider=auth_service.get_id_token,
    )
    ingest_manager = IngestManager(
        config=config,
        api_client=api_client,
        history=history,
    )

    # Show login dialog
    login_dialog = LoginDialog(
        config=config,
        auth_service=auth_service,
    )

    if login_dialog.exec() != LoginDialog.DialogCode.Accepted:
        return 0

    # Get username from login
    username = login_dialog.get_username()

    # Create and show main window
    main_window = MainWindow(
        config=config,
        history=history,
        auth_service=auth_service,
        api_client=api_client,
        ingest_manager=ingest_manager,
    )
    main_window.set_authenticated_user(username)
    main_window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
