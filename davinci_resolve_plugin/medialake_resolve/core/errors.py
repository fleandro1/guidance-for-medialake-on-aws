"""Custom exceptions for Media Lake Resolve Plugin."""


class MediaLakeError(Exception):
    """Base exception for Media Lake plugin errors."""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class AuthenticationError(MediaLakeError):
    """Exception raised for authentication failures."""
    
    def __init__(self, message: str = "Authentication failed", details: str = None):
        super().__init__(message, details)


class TokenExpiredError(AuthenticationError):
    """Exception raised when authentication token has expired."""
    
    def __init__(self, message: str = "Token has expired", details: str = None):
        super().__init__(message, details)


class InvalidCredentialsError(AuthenticationError):
    """Exception raised for invalid credentials."""
    
    def __init__(self, message: str = "Invalid username or password", details: str = None):
        super().__init__(message, details)


class APIError(MediaLakeError):
    """Exception raised for Media Lake API errors."""
    
    def __init__(
        self,
        message: str = "API request failed",
        status_code: int = None,
        response_body: str = None,
        details: str = None,
    ):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message, details)
    
    def __str__(self):
        parts = [self.message]
        if self.status_code:
            parts.append(f"Status: {self.status_code}")
        if self.details:
            parts.append(self.details)
        return " - ".join(parts)


class NotFoundError(APIError):
    """Exception raised when a resource is not found."""
    
    def __init__(self, resource_type: str = "Resource", resource_id: str = None):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} '{resource_id}' not found"
        super().__init__(message, status_code=404)


class RateLimitError(APIError):
    """Exception raised when API rate limit is exceeded."""
    
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        message = "API rate limit exceeded"
        if retry_after:
            message += f" (retry after {retry_after} seconds)"
        super().__init__(message, status_code=429)


class DownloadError(MediaLakeError):
    """Exception raised for download failures."""
    
    def __init__(
        self,
        message: str = "Download failed",
        asset_id: str = None,
        details: str = None,
    ):
        self.asset_id = asset_id
        super().__init__(message, details)


class ResolveConnectionError(MediaLakeError):
    """Exception raised when unable to connect to DaVinci Resolve."""
    
    def __init__(
        self,
        message: str = "Could not connect to DaVinci Resolve",
        details: str = None,
    ):
        super().__init__(message, details)


class ResolveNotRunningError(ResolveConnectionError):
    """Exception raised when DaVinci Resolve is not running."""
    
    def __init__(self):
        super().__init__(
            message="DaVinci Resolve is not running",
            details="Please start DaVinci Resolve and try again",
        )


class ResolveNoProjectError(ResolveConnectionError):
    """Exception raised when no project is open in Resolve."""
    
    def __init__(self):
        super().__init__(
            message="No project is open in DaVinci Resolve",
            details="Please open a project and try again",
        )


class ConfigurationError(MediaLakeError):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str = "Configuration error", details: str = None):
        super().__init__(message, details)


class FFmpegError(MediaLakeError):
    """Exception raised for FFmpeg-related errors."""
    
    def __init__(
        self,
        message: str = "FFmpeg operation failed",
        command: str = None,
        stderr: str = None,
    ):
        self.command = command
        self.stderr = stderr
        super().__init__(message, details=stderr)
