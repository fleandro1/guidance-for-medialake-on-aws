"""Credential manager using OS keychain for secure storage.

Uses the same approach as the DaVinci Resolve plugin:
- macOS: Keychain
- Windows: Credential Locker
- Linux: Secret Service (GNOME Keyring, KWallet)
"""

import json
from typing import Optional

import keyring
import keyring.errors

SERVICE_NAME = "LakeLoader"
CREDENTIALS_KEY = "credentials"


class CredentialManager:
    """Manages secure storage of credentials using OS keychain."""

    def __init__(self, service_name: str = SERVICE_NAME):
        self._service_name = service_name

    def store_credentials(self, username: str, password: str) -> None:
        """Store username and password securely in the OS keychain."""
        data = json.dumps({"username": username, "password": password})
        keyring.set_password(self._service_name, CREDENTIALS_KEY, data)

    def get_credentials(self) -> Optional[tuple[str, str]]:
        """Retrieve stored credentials.

        Returns:
            (username, password) tuple, or None if not stored.
        """
        try:
            raw = keyring.get_password(self._service_name, CREDENTIALS_KEY)
            if not raw:
                return None
            data = json.loads(raw)
            username = data.get("username", "")
            password = data.get("password", "")
            if username and password:
                return username, password
            return None
        except (json.JSONDecodeError, keyring.errors.KeyringError) as e:
            print(f"Warning: Could not retrieve credentials: {e}")
            return None

    def delete_credentials(self) -> None:
        """Delete stored credentials from the OS keychain."""
        try:
            keyring.delete_password(self._service_name, CREDENTIALS_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

    def has_credentials(self) -> bool:
        """Check if credentials are stored."""
        return self.get_credentials() is not None
