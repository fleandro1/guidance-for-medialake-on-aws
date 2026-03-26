"""Media Lake API client for LakeLoader application."""

import json
import traceback
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from lake_loader.core.models import ConnectorInfo


class APIError(Exception):
    """API request error with details."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        detail: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.detail = detail or self._build_detail()

    def _build_detail(self) -> str:
        """Build detailed error message."""
        parts = [f"Error: {self.message}"]
        if self.status_code:
            parts.append(f"HTTP Status: {self.status_code}")
        if self.response_body:
            parts.append(f"Response: {self.response_body}")
        return "\n".join(parts)


class AuthenticationRequiredError(APIError):
    """Authentication is required or token is invalid."""

    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            "Authentication required. Please log in.",
            status_code=401,
            detail=detail,
        )


class MediaLakeAPIClient:
    """
    Synchronous API client for Media Lake.

    All methods are blocking and should be called from background threads.
    """

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], Optional[str]],
    ):
        """
        Initialize API client.

        Args:
            base_url: Base URL of the Media Lake API.
            token_provider: Callable that returns current ID token.
        """
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._session = requests.Session()

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self._base_url

    @base_url.setter
    def base_url(self, url: str) -> None:
        """Set the base URL."""
        self._base_url = url.rstrip("/")

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        token = self._token_provider()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /connectors)
            data: Request body data
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON response

        Raises:
            APIError: On request failure
            AuthenticationRequiredError: On 401 response
        """
        url = urljoin(self._base_url + "/", endpoint.lstrip("/"))
        headers = self._get_headers()

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                timeout=timeout,
            )

            # Handle authentication errors
            if response.status_code == 401:
                raise AuthenticationRequiredError(
                    f"Token may be expired or invalid. URL: {url}"
                )

            # Handle other errors
            if not response.ok:
                try:
                    error_body = response.text
                except Exception:
                    error_body = "Unable to read response body"

                raise APIError(
                    message=f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                    response_body=error_body,
                )

            # Check for empty response
            if not response.text or response.text.strip() == "":
                raise APIError(
                    message="Server returned empty response body",
                    response_body="",
                )

            # Parse JSON response
            try:
                result = response.json()
                
                # Handle Lambda proxy response format where body is JSON string
                if "body" in result and isinstance(result["body"], str):
                    try:
                        result = json.loads(result["body"])
                    except json.JSONDecodeError:
                        pass  # Keep original result if body isn't valid JSON
                
                return result
            except json.JSONDecodeError as e:
                raise APIError(
                    message="Invalid JSON response from API",
                    response_body=response.text[:500],
                    detail=str(e),
                )

        except Timeout:
            raise APIError(
                message="Connection timed out. Check API URL and network.",
                detail=f"Request to {url} timed out after {timeout} seconds.",
            )
        except ConnectionError as e:
            raise APIError(
                message="Connection failed. Check API URL and network.",
                detail=f"Could not connect to {url}: {str(e)}",
            )
        except RequestException as e:
            raise APIError(
                message=f"Request failed: {str(e)}",
                detail=traceback.format_exc(),
            )

    # -------------------------------------------------------------------------
    # Connector APIs
    # -------------------------------------------------------------------------

    def get_connectors(self) -> List[ConnectorInfo]:
        """
        Get list of available storage connectors.

        Returns:
            List of ConnectorInfo objects.
        """
        response = self._make_request("GET", "/connectors")

        connectors = []
        
        # Handle the response structure: {"data": {"connectors": [...]}}
        data = response.get("data", {})
        
        # data might be a dict with "connectors" key
        if isinstance(data, dict):
            connector_list = data.get("connectors", [])
        else:
            # Fallback if data is the list directly
            connector_list = data if isinstance(data, list) else []

        for item in connector_list:
            if not isinstance(item, dict):
                continue
            try:
                connector = ConnectorInfo.from_api_response(item)
                connectors.append(connector)
            except Exception as e:
                print(f"Warning: Failed to parse connector: {e}")

        return connectors

    # -------------------------------------------------------------------------
    # Upload APIs
    # -------------------------------------------------------------------------

    def initiate_upload(
        self,
        connector_id: str,
        filename: str,
        content_type: str,
        file_size: int,
        path: str = "",
    ) -> Dict[str, Any]:
        """
        Initiate a file upload.

        Args:
            connector_id: Storage connector ID.
            filename: Sanitized filename.
            content_type: MIME type.
            file_size: File size in bytes.
            path: Optional destination path/subfolder.

        Returns:
            Upload info dict with either presigned_post (single-part)
            or multipart upload info.
        """
        response = self._make_request(
            "POST",
            "/assets/upload",
            data={
                "connector_id": connector_id,
                "filename": filename,
                "content_type": content_type,
                "file_size": file_size,
                "path": path,
            },
        )

        return response.get("data", response)

    def sign_multipart_part(
        self,
        connector_id: str,
        upload_id: str,
        key: str,
        part_number: int,
    ) -> str:
        """
        Get a presigned URL for uploading a multipart part.

        Args:
            connector_id: Storage connector ID.
            upload_id: Multipart upload ID.
            key: S3 object key.
            part_number: Part number (1-indexed).

        Returns:
            Presigned PUT URL for the part.
        """
        response = self._make_request(
            "POST",
            "/assets/upload/multipart/sign",
            data={
                "connector_id": connector_id,
                "upload_id": upload_id,
                "key": key,
                "part_number": part_number,
            },
        )

        data = response.get("data", response)
        return data.get("presigned_url", "")

    def complete_multipart_upload(
        self,
        connector_id: str,
        upload_id: str,
        key: str,
        parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Complete a multipart upload.

        Args:
            connector_id: Storage connector ID.
            upload_id: Multipart upload ID.
            key: S3 object key.
            parts: List of {"PartNumber": int, "ETag": str} dicts.

        Returns:
            Completion response.
        """
        response = self._make_request(
            "POST",
            "/assets/upload/multipart/complete",
            data={
                "connector_id": connector_id,
                "upload_id": upload_id,
                "key": key,
                "parts": parts,
            },
        )

        return response.get("data", response)

    def abort_multipart_upload(
        self,
        connector_id: str,
        upload_id: str,
        key: str,
    ) -> None:
        """
        Abort a multipart upload.

        Args:
            connector_id: Storage connector ID.
            upload_id: Multipart upload ID.
            key: S3 object key.
        """
        try:
            self._make_request(
                "POST",
                "/assets/upload/multipart/abort",
                data={
                    "connector_id": connector_id,
                    "upload_id": upload_id,
                    "key": key,
                },
            )
        except APIError as e:
            # Log but don't fail - abort is best-effort cleanup
            print(f"Warning: Failed to abort multipart upload: {e}")

    # -------------------------------------------------------------------------
    # Connection test
    # -------------------------------------------------------------------------

    def test_connection(self) -> bool:
        """
        Test the API connection.

        Returns:
            True if connection is successful.

        Raises:
            APIError: If connection fails.
        """
        # Try to get connectors as a simple test
        self.get_connectors()
        return True
