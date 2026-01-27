"""Authentication service using AWS Cognito."""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime, timedelta
from typing import Optional, Tuple

from medialake_resolve.core.models import TokenInfo, UserInfo
from medialake_resolve.core.errors import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
)


class AuthService:
    """Handles authentication with AWS Cognito.
    
    Uses USER_PASSWORD_AUTH flow for direct username/password authentication.
    """
    
    def __init__(
        self,
        user_pool_id: str,
        client_id: str,
        region: str = "us-east-1",
    ):
        """Initialize authentication service.
        
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
    
    def authenticate(self, username: str, password: str) -> Tuple[TokenInfo, UserInfo]:
        """Authenticate user with username and password.
        
        Args:
            username: The username or email.
            password: The user's password.
            
        Returns:
            Tuple of (TokenInfo, UserInfo) on success.
            
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
                        "Please change your password in the Media Lake web interface",
                    )
                else:
                    raise AuthenticationError(
                        f"Authentication challenge: {challenge}",
                        "Please complete the challenge in the Media Lake web interface",
                    )
            
            # Extract tokens
            auth_result = response.get("AuthenticationResult", {})
            
            access_token = auth_result.get("AccessToken", "")
            id_token = auth_result.get("IdToken", "")
            refresh_token = auth_result.get("RefreshToken", "")
            expires_in = auth_result.get("ExpiresIn", 3600)
            
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            token_info = TokenInfo(
                access_token=access_token,
                id_token=id_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            
            # Get user info from ID token
            user_info = self._get_user_info(access_token)
            
            return token_info, user_info
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            if error_code in ("NotAuthorizedException", "UserNotFoundException"):
                raise InvalidCredentialsError(details=error_message)
            elif error_code == "UserNotConfirmedException":
                raise AuthenticationError(
                    "Account not confirmed",
                    "Please confirm your account via the link sent to your email",
                )
            elif error_code == "PasswordResetRequiredException":
                raise AuthenticationError(
                    "Password reset required",
                    "Please reset your password in the Media Lake web interface",
                )
            else:
                raise AuthenticationError(
                    f"Authentication failed: {error_code}",
                    error_message,
                )
    
    def refresh_tokens(self, refresh_token: str) -> TokenInfo:
        """Refresh authentication tokens.
        
        Args:
            refresh_token: The refresh token.
            
        Returns:
            New TokenInfo with refreshed tokens.
            
        Raises:
            TokenExpiredError: If refresh token is expired.
            AuthenticationError: For other failures.
        """
        try:
            response = self._client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self.client_id,
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                },
            )
            
            auth_result = response.get("AuthenticationResult", {})
            
            access_token = auth_result.get("AccessToken", "")
            id_token = auth_result.get("IdToken", "")
            expires_in = auth_result.get("ExpiresIn", 3600)
            
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            return TokenInfo(
                access_token=access_token,
                id_token=id_token,
                refresh_token=refresh_token,  # Refresh token doesn't change
                expires_at=expires_at,
            )
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            if error_code == "NotAuthorizedException":
                raise TokenExpiredError(details=error_message)
            else:
                raise AuthenticationError(
                    f"Token refresh failed: {error_code}",
                    error_message,
                )
    
    def _get_user_info(self, access_token: str) -> UserInfo:
        """Get user information from Cognito.
        
        Args:
            access_token: The access token.
            
        Returns:
            UserInfo with user details.
        """
        try:
            response = self._client.get_user(AccessToken=access_token)
            
            attributes = {
                attr["Name"]: attr["Value"]
                for attr in response.get("UserAttributes", [])
            }
            
            # Extract groups from cognito:groups attribute
            groups = []
            groups_str = attributes.get("cognito:groups", "")
            if groups_str:
                groups = [g.strip() for g in groups_str.split(",")]
            
            return UserInfo(
                user_id=attributes.get("sub", ""),
                username=response.get("Username", ""),
                email=attributes.get("email", ""),
                groups=groups,
                permissions=[],  # Will be populated from API
            )
            
        except ClientError as e:
            # Return minimal user info on error
            return UserInfo(
                user_id="",
                username="",
                email="",
                groups=[],
                permissions=[],
            )
    
    def sign_out(self, access_token: str) -> None:
        """Sign out user and invalidate tokens.
        
        Args:
            access_token: The access token to invalidate.
        """
        try:
            self._client.global_sign_out(AccessToken=access_token)
        except ClientError:
            # Ignore sign-out errors
            pass
    
    def change_password(
        self,
        access_token: str,
        old_password: str,
        new_password: str,
    ) -> None:
        """Change user's password.
        
        Args:
            access_token: The current access token.
            old_password: The current password.
            new_password: The new password.
            
        Raises:
            AuthenticationError: If password change fails.
        """
        try:
            self._client.change_password(
                PreviousPassword=old_password,
                ProposedPassword=new_password,
                AccessToken=access_token,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise AuthenticationError(
                f"Password change failed: {error_code}",
                error_message,
            )
