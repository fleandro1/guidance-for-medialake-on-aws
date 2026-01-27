"""Credential manager using OS keychain for secure storage."""

import keyring
import json
from typing import Optional, Tuple
from dataclasses import dataclass


SERVICE_NAME = "MediaLakeResolvePlugin"


@dataclass
class StoredCredentials:
    """Stored credential data."""
    username: str
    password: str
    medialake_url: str
    cognito_user_pool_id: str
    cognito_client_id: str
    cognito_region: str


class CredentialManager:
    """Manages secure storage of credentials using OS keychain.
    
    Uses the keyring library which provides:
    - macOS: Keychain
    - Windows: Credential Locker
    - Linux: Secret Service (GNOME Keyring, KWallet)
    """
    
    CREDENTIALS_KEY = "credentials"
    TOKENS_KEY = "tokens"
    
    def __init__(self, service_name: str = SERVICE_NAME):
        """Initialize credential manager.
        
        Args:
            service_name: The service name to use in keychain.
        """
        self.service_name = service_name
    
    def store_credentials(
        self,
        username: str,
        password: str,
        medialake_url: str,
        cognito_user_pool_id: str,
        cognito_client_id: str,
        cognito_region: str = "us-east-1",
    ) -> None:
        """Store credentials securely in the OS keychain.
        
        Args:
            username: The username/email for authentication.
            password: The user's password.
            medialake_url: The Media Lake instance URL.
            cognito_user_pool_id: Cognito User Pool ID.
            cognito_client_id: Cognito Client ID.
            cognito_region: AWS region for Cognito.
        """
        credentials = {
            "username": username,
            "password": password,
            "medialake_url": medialake_url,
            "cognito_user_pool_id": cognito_user_pool_id,
            "cognito_client_id": cognito_client_id,
            "cognito_region": cognito_region,
        }
        
        # Store as JSON string
        keyring.set_password(
            self.service_name,
            self.CREDENTIALS_KEY,
            json.dumps(credentials),
        )
    
    def get_credentials(self) -> Optional[StoredCredentials]:
        """Retrieve stored credentials from the OS keychain.
        
        Returns:
            StoredCredentials if found, None otherwise.
        """
        try:
            credentials_json = keyring.get_password(
                self.service_name,
                self.CREDENTIALS_KEY,
            )
            
            if not credentials_json:
                return None
            
            data = json.loads(credentials_json)
            return StoredCredentials(
                username=data.get("username", ""),
                password=data.get("password", ""),
                medialake_url=data.get("medialake_url", ""),
                cognito_user_pool_id=data.get("cognito_user_pool_id", ""),
                cognito_client_id=data.get("cognito_client_id", ""),
                cognito_region=data.get("cognito_region", "us-east-1"),
            )
        except (json.JSONDecodeError, keyring.errors.KeyringError) as e:
            print(f"Warning: Could not retrieve credentials: {e}")
            return None
    
    def delete_credentials(self) -> None:
        """Delete stored credentials from the OS keychain."""
        try:
            keyring.delete_password(self.service_name, self.CREDENTIALS_KEY)
        except keyring.errors.PasswordDeleteError:
            # Credentials don't exist, ignore
            pass
    
    def has_credentials(self) -> bool:
        """Check if credentials are stored.
        
        Returns:
            True if credentials exist, False otherwise.
        """
        return self.get_credentials() is not None
    
    def store_tokens(
        self,
        access_token: str,
        id_token: str,
        refresh_token: str,
        expires_at: str,
    ) -> None:
        """Store authentication tokens securely.
        
        Args:
            access_token: The access token.
            id_token: The ID token.
            refresh_token: The refresh token.
            expires_at: ISO format expiration timestamp.
        """
        tokens = {
            "access_token": access_token,
            "id_token": id_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        }
        
        keyring.set_password(
            self.service_name,
            self.TOKENS_KEY,
            json.dumps(tokens),
        )
    
    def get_tokens(self) -> Optional[dict]:
        """Retrieve stored tokens from the OS keychain.
        
        Returns:
            Dict with tokens if found, None otherwise.
        """
        try:
            tokens_json = keyring.get_password(
                self.service_name,
                self.TOKENS_KEY,
            )
            
            if not tokens_json:
                return None
            
            return json.loads(tokens_json)
        except (json.JSONDecodeError, keyring.errors.KeyringError) as e:
            print(f"Warning: Could not retrieve tokens: {e}")
            return None
    
    def delete_tokens(self) -> None:
        """Delete stored tokens from the OS keychain."""
        try:
            keyring.delete_password(self.service_name, self.TOKENS_KEY)
        except keyring.errors.PasswordDeleteError:
            # Tokens don't exist, ignore
            pass
    
    def clear_all(self) -> None:
        """Clear all stored credentials and tokens."""
        self.delete_credentials()
        self.delete_tokens()
    
    def update_password(self, new_password: str) -> bool:
        """Update stored password.
        
        Args:
            new_password: The new password to store.
            
        Returns:
            True if successful, False if no credentials exist.
        """
        credentials = self.get_credentials()
        if not credentials:
            return False
        
        self.store_credentials(
            username=credentials.username,
            password=new_password,
            medialake_url=credentials.medialake_url,
            cognito_user_pool_id=credentials.cognito_user_pool_id,
            cognito_client_id=credentials.cognito_client_id,
            cognito_region=credentials.cognito_region,
        )
        return True
