"""
Unit tests for the authentication module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path


class TestCredentialManager:
    """Tests for CredentialManager."""
    
    def test_credential_manager_creation(self):
        """Test that credential manager can be instantiated."""
        from medialake_resolve.auth.credential_manager import CredentialManager
        
        cm = CredentialManager()
        assert cm is not None
    
    @patch('medialake_resolve.auth.credential_manager.keyring')
    def test_store_credentials(self, mock_keyring):
        """Test storing credentials."""
        from medialake_resolve.auth.credential_manager import CredentialManager
        
        cm = CredentialManager()
        cm.store_credentials('test_user', 'test_password')
        
        # Verify keyring was called
        mock_keyring.set_password.assert_called()
    
    @patch('medialake_resolve.auth.credential_manager.keyring')
    def test_get_credentials(self, mock_keyring):
        """Test retrieving credentials."""
        from medialake_resolve.auth.credential_manager import CredentialManager
        
        mock_keyring.get_password.side_effect = ['test_user', 'test_password']
        
        cm = CredentialManager()
        username, password = cm.get_credentials()
        
        assert username == 'test_user'
        assert password == 'test_password'
    
    @patch('medialake_resolve.auth.credential_manager.keyring')
    def test_delete_credentials(self, mock_keyring):
        """Test deleting credentials."""
        from medialake_resolve.auth.credential_manager import CredentialManager
        
        cm = CredentialManager()
        cm.delete_credentials()
        
        mock_keyring.delete_password.assert_called()
    
    @patch('medialake_resolve.auth.credential_manager.keyring')
    def test_has_credentials(self, mock_keyring):
        """Test checking if credentials exist."""
        from medialake_resolve.auth.credential_manager import CredentialManager
        
        mock_keyring.get_password.return_value = 'some_value'
        
        cm = CredentialManager()
        assert cm.has_credentials() is True
        
        mock_keyring.get_password.return_value = None
        assert cm.has_credentials() is False


class TestAuthService:
    """Tests for AuthService."""
    
    def test_auth_service_creation(self):
        """Test that auth service can be instantiated."""
        from medialake_resolve.auth.auth_service import AuthService
        
        auth = AuthService(
            user_pool_id='us-west-2_abc123',
            client_id='1234567890abcdef'
        )
        assert auth is not None
    
    @patch('medialake_resolve.auth.auth_service.boto3')
    def test_authenticate_success(self, mock_boto3):
        """Test successful authentication."""
        from medialake_resolve.auth.auth_service import AuthService
        
        # Mock Cognito response
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.initiate_auth.return_value = {
            'AuthenticationResult': {
                'IdToken': 'mock_id_token',
                'AccessToken': 'mock_access_token',
                'RefreshToken': 'mock_refresh_token',
                'ExpiresIn': 3600
            }
        }
        
        auth = AuthService(
            user_pool_id='us-west-2_abc123',
            client_id='1234567890abcdef'
        )
        
        result = auth.authenticate('testuser', 'testpassword')
        
        assert result['id_token'] == 'mock_id_token'
        assert result['access_token'] == 'mock_access_token'
        assert result['refresh_token'] == 'mock_refresh_token'
    
    @patch('medialake_resolve.auth.auth_service.boto3')
    def test_authenticate_failure(self, mock_boto3):
        """Test authentication failure."""
        from medialake_resolve.auth.auth_service import AuthService
        from medialake_resolve.core.errors import AuthenticationError
        from botocore.exceptions import ClientError
        
        # Mock Cognito error
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.initiate_auth.side_effect = ClientError(
            {'Error': {'Code': 'NotAuthorizedException', 'Message': 'Invalid credentials'}},
            'InitiateAuth'
        )
        
        auth = AuthService(
            user_pool_id='us-west-2_abc123',
            client_id='1234567890abcdef'
        )
        
        with pytest.raises(AuthenticationError):
            auth.authenticate('testuser', 'wrongpassword')
    
    @patch('medialake_resolve.auth.auth_service.boto3')
    def test_refresh_token(self, mock_boto3):
        """Test token refresh."""
        from medialake_resolve.auth.auth_service import AuthService
        
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.initiate_auth.return_value = {
            'AuthenticationResult': {
                'IdToken': 'new_id_token',
                'AccessToken': 'new_access_token',
                'ExpiresIn': 3600
            }
        }
        
        auth = AuthService(
            user_pool_id='us-west-2_abc123',
            client_id='1234567890abcdef'
        )
        
        result = auth.refresh_tokens('mock_refresh_token')
        
        assert result['id_token'] == 'new_id_token'
        assert result['access_token'] == 'new_access_token'


class TestTokenManager:
    """Tests for TokenManager."""
    
    def test_token_manager_creation(self):
        """Test that token manager can be instantiated."""
        from medialake_resolve.auth.token_manager import TokenManager
        
        tm = TokenManager()
        assert tm is not None
        assert tm.is_authenticated() is False
    
    def test_set_tokens(self):
        """Test setting tokens."""
        from medialake_resolve.auth.token_manager import TokenManager
        import time
        
        tm = TokenManager()
        
        tm.set_tokens(
            id_token='test_id_token',
            access_token='test_access_token',
            refresh_token='test_refresh_token',
            expires_in=3600
        )
        
        assert tm.id_token == 'test_id_token'
        assert tm.access_token == 'test_access_token'
        assert tm.refresh_token == 'test_refresh_token'
        assert tm.is_authenticated() is True
    
    def test_clear_tokens(self):
        """Test clearing tokens."""
        from medialake_resolve.auth.token_manager import TokenManager
        
        tm = TokenManager()
        
        tm.set_tokens(
            id_token='test_id_token',
            access_token='test_access_token',
            refresh_token='test_refresh_token',
            expires_in=3600
        )
        
        tm.clear_tokens()
        
        assert tm.id_token is None
        assert tm.access_token is None
        assert tm.is_authenticated() is False
    
    def test_token_expiration(self):
        """Test token expiration check."""
        from medialake_resolve.auth.token_manager import TokenManager
        
        tm = TokenManager()
        
        # Set tokens that expire immediately
        tm.set_tokens(
            id_token='test_id_token',
            access_token='test_access_token',
            refresh_token='test_refresh_token',
            expires_in=0
        )
        
        assert tm.is_token_expired() is True
        
        # Set tokens that expire in the future
        tm.set_tokens(
            id_token='test_id_token',
            access_token='test_access_token',
            refresh_token='test_refresh_token',
            expires_in=3600
        )
        
        assert tm.is_token_expired() is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
