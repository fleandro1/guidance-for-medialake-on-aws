"""Authentication service using AWS Cognito."""

from datetime import datetime, timedelta
from typing import Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from lake_loader.core.models import TokenInfo


class AuthenticationError(Exception):
    """Base authentication error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""

    def __init__(self, detail: Optional[str] = None):
        super().__init__("Invalid username or password", detail)


class TokenExpiredError(AuthenticationError):
    """Token has expired and could not be refreshed."""

    def __init__(self, detail: Optional[str] = None):
        super().__init__("Session expired. Please log in again.", detail)


class AuthService:
    """
    Handles authentication with AWS Cognito.

    Uses USER_PASSWORD_AUTH flow for direct username/password authentication.
    """

    def __init__(
        self,
        user_pool_id: str,
        client_id: str,
        region: str = "us-east-1",
    ):
        """
        Initialize authentication service.

        Args:
            user_pool_id: Cognito User Pool ID.
            client_id: Cognito Client ID.
            region: AWS region for Cognito.
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region

        # Create Cognito client
        # Cognito public operations (InitiateAuth, etc.) don't require AWS credentials
        # when using a public app client (no client secret)
        self._client = boto3.client(
            "cognito-idp",
            region_name=region,
        )

        # Current token info
        self._token_info: Optional[TokenInfo] = None

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid tokens."""
        return self._token_info is not None and not self._token_info.is_expired()

    @property
    def token_info(self) -> Optional[TokenInfo]:
        """Get current token info."""
        return self._token_info

    @property
    def id_token(self) -> Optional[str]:
        """Get the current ID token for API requests."""
        if self._token_info and not self._token_info.is_expired():
            return self._token_info.id_token
        return None

    def get_id_token(self) -> Optional[str]:
        """Get the current ID token (callable version for token_provider)."""
        return self.id_token

    def authenticate(self, username: str, password: str) -> TokenInfo:
        """
        Authenticate user with username and password.

        Args:
            username: The username or email.
            password: The user's password.

        Returns:
            TokenInfo on success.

        Raises:
            InvalidCredentialsError: If credentials are invalid.
            AuthenticationError: For other authentication failures.
        """
        try:
            response = self._client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=self.client_id,
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password,
                },
            )

            # Handle challenges (e.g., NEW_PASSWORD_REQUIRED)
            if "ChallengeName" in response:
                challenge = response["ChallengeName"]
                if challenge == "NEW_PASSWORD_REQUIRED":
                    raise AuthenticationError(
                        "Password change required",
                        "Please change your password in the Media Lake web interface first.",
                    )
                else:
                    raise AuthenticationError(
                        f"Authentication challenge: {challenge}",
                        "Please complete the challenge in the Media Lake web interface.",
                    )

            # Extract tokens
            auth_result = response.get("AuthenticationResult", {})

            access_token = auth_result.get("AccessToken", "")
            id_token = auth_result.get("IdToken", "")
            refresh_token = auth_result.get("RefreshToken", "")
            expires_in = auth_result.get("ExpiresIn", 3600)

            expires_at = datetime.now() + timedelta(seconds=expires_in)

            self._token_info = TokenInfo(
                access_token=access_token,
                id_token=id_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )

            return self._token_info

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code in ("NotAuthorizedException", "UserNotFoundException"):
                raise InvalidCredentialsError(detail=error_message)
            elif error_code == "UserNotConfirmedException":
                raise AuthenticationError(
                    "Account not confirmed",
                    "Please confirm your account via the link sent to your email.",
                )
            elif error_code == "PasswordResetRequiredException":
                raise AuthenticationError(
                    "Password reset required",
                    "Please reset your password in the Media Lake web interface.",
                )
            elif error_code == "InvalidParameterException":
                if "USER_PASSWORD_AUTH" in error_message:
                    raise AuthenticationError(
                        "Authentication method not available",
                        "USER_PASSWORD_AUTH flow is not enabled for this Cognito client. "
                        "Please contact your administrator.",
                    )
                raise AuthenticationError(f"Invalid parameter: {error_message}")
            else:
                raise AuthenticationError(
                    f"Authentication failed: {error_code}",
                    error_message,
                )

    def refresh_tokens(self) -> TokenInfo:
        """
        Refresh authentication tokens using the refresh token.

        Returns:
            New TokenInfo with refreshed tokens.

        Raises:
            TokenExpiredError: If refresh token is expired.
            AuthenticationError: For other failures.
        """
        if not self._token_info or not self._token_info.refresh_token:
            raise TokenExpiredError("No refresh token available")

        try:
            response = self._client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self.client_id,
                AuthParameters={
                    "REFRESH_TOKEN": self._token_info.refresh_token,
                },
            )

            auth_result = response.get("AuthenticationResult", {})

            access_token = auth_result.get("AccessToken", "")
            id_token = auth_result.get("IdToken", "")
            expires_in = auth_result.get("ExpiresIn", 3600)

            expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Note: Refresh token is not returned on refresh, keep the existing one
            self._token_info = TokenInfo(
                access_token=access_token,
                id_token=id_token,
                refresh_token=self._token_info.refresh_token,
                expires_at=expires_at,
            )

            return self._token_info

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code in ("NotAuthorizedException", "InvalidRefreshTokenException"):
                self._token_info = None
                raise TokenExpiredError(error_message)
            else:
                raise AuthenticationError(
                    f"Token refresh failed: {error_code}",
                    error_message,
                )

    def ensure_valid_token(self) -> str:
        """
        Ensure we have a valid ID token, refreshing if necessary.

        Returns:
            Valid ID token.

        Raises:
            TokenExpiredError: If not authenticated or refresh fails.
        """
        if not self._token_info:
            raise TokenExpiredError("Not authenticated")

        # Refresh if expiring soon (within 5 minutes)
        if self._token_info.is_expiring_soon(threshold_seconds=300):
            self.refresh_tokens()

        if not self._token_info.id_token:
            raise TokenExpiredError("No valid ID token")

        return self._token_info.id_token

    def logout(self) -> None:
        """Clear authentication state."""
        self._token_info = None
