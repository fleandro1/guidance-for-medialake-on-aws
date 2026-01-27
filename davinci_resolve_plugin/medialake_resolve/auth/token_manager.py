"""Token manager for handling authentication token lifecycle."""

from datetime import datetime, timedelta
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, QTimer

from medialake_resolve.core.models import TokenInfo, UserInfo
from medialake_resolve.core.errors import AuthenticationError, TokenExpiredError
from medialake_resolve.auth.credential_manager import CredentialManager
from medialake_resolve.auth.auth_service import AuthService


class TokenManager(QObject):
    """Manages authentication tokens with automatic refresh.
    
    Signals:
        token_refreshed: Emitted when tokens are successfully refreshed.
        token_expired: Emitted when tokens expire and cannot be refreshed.
        authentication_required: Emitted when re-authentication is needed.
    """
    
    # Signals
    token_refreshed = Signal(TokenInfo)
    token_expired = Signal()
    authentication_required = Signal()
    
    # Refresh tokens 5 minutes before expiry
    REFRESH_BUFFER_SECONDS = 300
    
    def __init__(
        self,
        credential_manager: CredentialManager,
        auth_service: Optional[AuthService] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize token manager.
        
        Args:
            credential_manager: Manager for secure credential storage.
            auth_service: Authentication service (can be set later).
            parent: Parent QObject.
        """
        super().__init__(parent)
        
        self._credential_manager = credential_manager
        self._auth_service = auth_service
        self._token_info: Optional[TokenInfo] = None
        self._user_info: Optional[UserInfo] = None
        
        # Timer for automatic token refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._on_refresh_timer)
    
    @property
    def auth_service(self) -> Optional[AuthService]:
        """Get the authentication service."""
        return self._auth_service
    
    @auth_service.setter
    def auth_service(self, service: AuthService) -> None:
        """Set the authentication service."""
        self._auth_service = service
    
    @property
    def token_info(self) -> Optional[TokenInfo]:
        """Get current token information."""
        return self._token_info
    
    @property
    def user_info(self) -> Optional[UserInfo]:
        """Get current user information."""
        return self._user_info
    
    @property
    def access_token(self) -> Optional[str]:
        """Get current access token."""
        if self._token_info:
            return self._token_info.access_token
        return None
    
    @property
    def id_token(self) -> Optional[str]:
        """Get current ID token (used for API authorization)."""
        if self._token_info:
            return self._token_info.id_token
        return None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid tokens."""
        return (
            self._token_info is not None
            and not self._token_info.is_expired
        )
    
    def set_auth_service(self, auth_service: AuthService) -> None:
        """Set the authentication service.
        
        Args:
            auth_service: The authentication service to use.
        """
        self._auth_service = auth_service
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with username and password.
        
        Args:
            username: The username or email.
            password: The user's password.
            
        Returns:
            True if authentication succeeded.
            
        Raises:
            AuthenticationError: If authentication fails.
        """
        if not self._auth_service:
            raise AuthenticationError("Authentication service not configured")
        
        token_info, user_info = self._auth_service.authenticate(username, password)
        
        self._token_info = token_info
        self._user_info = user_info
        
        # Store tokens securely
        self._credential_manager.store_tokens(
            access_token=token_info.access_token,
            id_token=token_info.id_token,
            refresh_token=token_info.refresh_token,
            expires_at=token_info.expires_at.isoformat(),
        )
        
        # Schedule token refresh
        self._schedule_refresh()
        
        return True
    
    def restore_session(self) -> bool:
        """Attempt to restore session from stored tokens.
        
        Returns:
            True if session was restored successfully.
        """
        stored_tokens = self._credential_manager.get_tokens()
        if not stored_tokens:
            return False
        
        try:
            expires_at = datetime.fromisoformat(stored_tokens["expires_at"])
            
            self._token_info = TokenInfo(
                access_token=stored_tokens["access_token"],
                id_token=stored_tokens["id_token"],
                refresh_token=stored_tokens["refresh_token"],
                expires_at=expires_at,
            )
            
            # If tokens need refresh, try to refresh them
            if self._token_info.needs_refresh:
                self._refresh_tokens()
            else:
                self._schedule_refresh()
            
            return True
            
        except (KeyError, ValueError) as e:
            print(f"Warning: Could not restore session: {e}")
            self._credential_manager.delete_tokens()
            return False
    
    def refresh(self) -> bool:
        """Manually refresh tokens.
        
        Returns:
            True if refresh succeeded.
        """
        return self._refresh_tokens()
    
    def logout(self) -> None:
        """Log out and clear all tokens."""
        if self._token_info and self._auth_service:
            try:
                self._auth_service.sign_out(self._token_info.access_token)
            except Exception:
                pass
        
        self._token_info = None
        self._user_info = None
        self._refresh_timer.stop()
        self._credential_manager.delete_tokens()
    
    def _refresh_tokens(self) -> bool:
        """Refresh authentication tokens.
        
        Returns:
            True if refresh succeeded.
        """
        if not self._token_info or not self._auth_service:
            return False
        
        try:
            new_token_info = self._auth_service.refresh_tokens(
                self._token_info.refresh_token
            )
            
            self._token_info = new_token_info
            
            # Store updated tokens
            self._credential_manager.store_tokens(
                access_token=new_token_info.access_token,
                id_token=new_token_info.id_token,
                refresh_token=new_token_info.refresh_token,
                expires_at=new_token_info.expires_at.isoformat(),
            )
            
            # Schedule next refresh
            self._schedule_refresh()
            
            self.token_refreshed.emit(new_token_info)
            return True
            
        except TokenExpiredError:
            self._token_info = None
            self._user_info = None
            self._credential_manager.delete_tokens()
            self.token_expired.emit()
            self.authentication_required.emit()
            return False
            
        except AuthenticationError as e:
            print(f"Warning: Token refresh failed: {e}")
            return False
    
    def _schedule_refresh(self) -> None:
        """Schedule the next token refresh."""
        if not self._token_info:
            return
        
        # Calculate time until refresh is needed (5 minutes before expiry)
        now = datetime.now()
        refresh_at = self._token_info.expires_at - timedelta(seconds=self.REFRESH_BUFFER_SECONDS)
        
        if refresh_at <= now:
            # Need to refresh immediately
            self._refresh_tokens()
        else:
            # Schedule refresh
            delay_ms = int((refresh_at - now).total_seconds() * 1000)
            self._refresh_timer.start(delay_ms)
    
    def _on_refresh_timer(self) -> None:
        """Handle refresh timer timeout."""
        self._refresh_tokens()
