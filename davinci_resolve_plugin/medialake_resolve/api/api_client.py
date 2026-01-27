"""Media Lake API client using Qt's QNetworkAccessManager for async requests."""

import json
from typing import Optional, List, Dict, Any, Callable
from urllib.parse import urljoin, urlencode
from PySide6.QtCore import QObject, Signal, QUrl, QByteArray
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply,
)

from medialake_resolve.core.models import (
    Asset,
    Collection,
    SearchResult,
    MediaType,
)
from medialake_resolve.core.errors import (
    APIError,
    NotFoundError,
    RateLimitError,
    AuthenticationError,
)


class MediaLakeAPIClient(QObject):
    """Async API client for Media Lake using Qt networking.
    
    Uses QNetworkAccessManager for non-blocking HTTP requests.
    All requests emit signals when completed.
    
    Signals:
        collections_loaded: Emitted when collections are loaded.
        assets_loaded: Emitted when assets are loaded.
        search_completed: Emitted when search is completed.
        asset_details_loaded: Emitted when asset details are loaded.
        download_url_ready: Emitted when download URL is retrieved.
        error_occurred: Emitted when an error occurs.
    """
    
    # Signals
    collections_loaded = Signal(list)  # List[Collection]
    assets_loaded = Signal(list, int)  # List[Asset], total_count
    search_completed = Signal(SearchResult)
    asset_details_loaded = Signal(Asset)
    download_url_ready = Signal(str, str)  # asset_id, download_url
    thumbnail_loaded = Signal(str, bytes)  # asset_id, image_data
    upload_url_ready = Signal(str, str, str)  # task_id, upload_url, destination_key
    buckets_loaded = Signal(list)  # List of bucket names
    connectors_loaded = Signal(list)  # List of connector dicts with id and storageIdentifier
    error_occurred = Signal(str, str)  # error_type, error_message
    
    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], Optional[str]],
        config=None,
        parent: Optional[QObject] = None,
    ):
        """Initialize API client.
        
        Args:
            base_url: Base URL of the Media Lake API (e.g., https://medialake.example.com).
            token_provider: Callable that returns current access token.
            config: Application configuration.
            parent: Parent QObject.
        """
        super().__init__(parent)
        
        self._config = config
        
        # Ensure base URL has /v1 API path
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        
        self._base_url = base_url
        self._token_provider = token_provider
        self._network_manager = QNetworkAccessManager(self)
        
        # Track pending requests
        self._pending_requests: Dict[QNetworkReply, Dict[str, Any]] = {}
    
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
    
    def _create_request(self, url: str) -> QNetworkRequest:
        """Create a QNetworkRequest with headers.
        
        Args:
            url: The full URL for the request.
            
        Returns:
            Configured QNetworkRequest.
        """
        request = QNetworkRequest(QUrl(url))
        
        for header, value in self._get_headers().items():
            request.setRawHeader(header.encode(), value.encode())
        
        return request
    
    def _make_url(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Build full URL for an endpoint.
        
        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.
            
        Returns:
            Full URL string.
        """
        url = f"{self._base_url}{endpoint}"
        
        if params:
            # Filter out None values
            filtered_params = {k: v for k, v in params.items() if v is not None}
            if filtered_params:
                url += "?" + urlencode(filtered_params)
        
        return url
    
    def _handle_response(self, reply: QNetworkReply) -> None:
        """Handle completed network response.
        
        Args:
            reply: The completed network reply.
        """
        request_info = self._pending_requests.pop(reply, {})
        request_type = request_info.get("type", "unknown")
        callback = request_info.get("callback")
        
        try:
            # Get status code first
            status_code = reply.attribute(
                QNetworkRequest.Attribute.HttpStatusCodeAttribute
            )
            url = reply.url().toString()
            
            # Debug logging
            print(f"API Response from {url}")
            print(f"  Status Code: {status_code}")
            print(f"  Network Error: {reply.error()}")
            
            # Check for network errors
            if reply.error() != QNetworkReply.NetworkError.NoError:
                error_string = reply.errorString()
                print(f"  Error String: {error_string}")
                
                # Handle specific error codes
                if status_code == 401:
                    self.error_occurred.emit("authentication", "Authentication required")
                    return
                elif status_code == 404:
                    self.error_occurred.emit("not_found", "Resource not found")
                    return
                elif status_code == 429:
                    self.error_occurred.emit("rate_limit", "Rate limit exceeded")
                    return
                elif status_code == 502:
                    # Server error - likely Lambda timeout or error
                    self.error_occurred.emit(
                        "server_error",
                        "Media Lake server error (502). The server may be experiencing issues. Please try again later."
                    )
                    return
                elif status_code == 503:
                    self.error_occurred.emit(
                        "server_error",
                        "Media Lake service temporarily unavailable (503). Please try again later."
                    )
                    return
                else:
                    self.error_occurred.emit("api_error", f"HTTP {status_code}: {error_string}")
                    return
            
            # Read response data
            data = reply.readAll().data()
            
            # Check for empty response
            if not data:
                print(f"  Warning: Empty response body")
                self.error_occurred.emit("api_error", "Server returned empty response")
                return
            
            # For thumbnails, skip JSON checks and handle directly
            if request_type == "thumbnail":
                print(f"  Response Body: [binary image data, {len(data)} bytes]")
                self._handle_thumbnail_response(data, request_info)
                return
            
            # Debug: log response for troubleshooting
            try:
                decoded = data.decode('utf-8')
                print(f"  Response Body: {decoded[:500]}...")
            except:
                print(f"  Response Body: [binary data, {len(data)} bytes]")
            
            # Check for API-level errors in the response body (even with 200 status)
            try:
                response_check = json.loads(data.decode())
                if isinstance(response_check, dict):
                    # Check for error indicators
                    if response_check.get("status") in ["400", "401", "403", "404", "500", 400, 401, 403, 404, 500]:
                        error_msg = response_check.get("message", "API returned an error")
                        print(f"  API Error: {error_msg}")
                        self.error_occurred.emit("api_error", error_msg)
                        return
                    if response_check.get("error"):
                        error_msg = response_check.get("error", {})
                        if isinstance(error_msg, dict):
                            error_msg = error_msg.get("message", str(error_msg))
                        print(f"  API Error: {error_msg}")
                        self.error_occurred.emit("api_error", str(error_msg))
                        return
            except json.JSONDecodeError:
                # Will be handled below
                pass
            
            # Handle based on request type
            if request_type == "collections":
                self._handle_collections_response(data)
            elif request_type == "assets":
                self._handle_assets_response(data, request_info)
            elif request_type == "search":
                self._handle_search_response(data, request_info)
            elif request_type == "asset_details":
                self._handle_asset_details_response(data)
            elif request_type == "download_url":
                self._handle_download_url_response(data, request_info)
            elif request_type == "thumbnail":
                self._handle_thumbnail_response(data, request_info)
            elif request_type == "buckets":
                self._handle_buckets_response(data)
            elif request_type == "upload_url":
                self._handle_upload_url_response(data, request_info)
            elif request_type == "asset_upload_url":
                self._handle_asset_upload_url_response(data, request_info)
            elif request_type == "connectors":
                self._handle_connectors_response(data)
            
            # Call custom callback if provided
            if callback:
                callback(data)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit("parse_error", str(e))
        finally:
            reply.deleteLater()
    
    def _handle_collections_response(self, data: bytes) -> None:
        """Handle collections list response."""
        response = json.loads(data.decode())
        
        collections = []
        
        # Handle different response formats
        if isinstance(response, list):
            # Direct list of collections
            items = response
        else:
            # Wrapped response: data.collections or just collections
            data_obj = response.get("data", response) if isinstance(response, dict) else {}
            if isinstance(data_obj, list):
                items = data_obj
            else:
                items = data_obj.get("collections", data_obj.get("items", []))
        
        for item in items:
            collections.append(Collection.from_api_response(item))
        
        self.collections_loaded.emit(collections)
    
    def _handle_assets_response(self, data: bytes, request_info: Dict) -> None:
        """Handle assets list response."""
        response = json.loads(data.decode())
        
        assets = []
        total_count = 0
        
        # Handle different response formats
        if isinstance(response, list):
            # Direct list of assets
            items = response
            total_count = len(items)
        else:
            # Wrapped response: data.assets, data.results, or data.items
            data_obj = response.get("data", response) if isinstance(response, dict) else {}
            if isinstance(data_obj, list):
                items = data_obj
                total_count = len(items)
            else:
                # Check for results (from search), assets, or items
                items = data_obj.get("results", data_obj.get("assets", data_obj.get("items", [])))
                # Get total count from searchMetadata, pagination, or response
                search_meta = data_obj.get("searchMetadata", {})
                pagination = data_obj.get("pagination", {})
                total_count = (
                    search_meta.get("totalResults") or 
                    pagination.get("totalItems") or 
                    response.get("totalCount") or 
                    response.get("total") or 
                    len(items)
                )
        
        print(f"  Parsed {len(items)} asset items, total_count={total_count}")
        
        for item in items:
            assets.append(Asset.from_api_response(item))
        
        self.assets_loaded.emit(assets, total_count)
    
    def _handle_search_response(self, data: bytes, request_info: Dict) -> None:
        """Handle search response."""
        response = json.loads(data.decode())
        
        query = request_info.get("query", "")
        search_type = request_info.get("search_type", "keyword")
        print(f"  Search response for '{query}' (type={search_type})")
        print(f"  Raw response keys: {response.keys() if isinstance(response, dict) else 'list'}")
        
        assets = []
        total_count = 0
        
        # Get confidence threshold from config or use default
        confidence_threshold = 0.63  # Default fallback
        if self._config:
            confidence_threshold = self._config.confidence_threshold
        
        # Handle different response formats
        if isinstance(response, list):
            # Direct list of results
            items = response
            total_count = len(items)
            print(f"  Response is direct list with {len(items)} items")
        else:
            # Wrapped response: data.results or data.assets
            data_obj = response.get("data", response) if isinstance(response, dict) else {}
            if isinstance(data_obj, list):
                items = data_obj
                total_count = len(items)
                print(f"  Response.data is list with {len(items)} items")
            else:
                items = data_obj.get("results", data_obj.get("assets", data_obj.get("items", [])))
                # Get total from pagination or searchMetadata
                search_metadata = data_obj.get("searchMetadata", {})
                pagination = data_obj.get("pagination", {})
                total_count = (
                    search_metadata.get("totalResults") or
                    pagination.get("totalItems") or 
                    response.get("totalCount") or 
                    response.get("total") or 
                    len(items)
                )
                print(f"  Response.data has {len(items)} results, total_count={total_count}")
                if search_metadata:
                    print(f"  searchMetadata: {search_metadata}")
        
        for item in items:
            asset = Asset.from_api_response(item)
            
            # For semantic search, filter by confidence threshold
            if search_type == "semantic":
                score = asset.score or 0
                if score >= confidence_threshold:
                    assets.append(asset)
                    print(f"  [Semantic] Including asset {asset.name} with score {score:.4f}")
                else:
                    print(f"  [Semantic] Excluding asset {asset.name} with score {score:.4f} (below {confidence_threshold:.2f})")
            else:
                assets.append(asset)
        
        # Update total count to reflect filtered results for semantic search
        if search_type == "semantic":
            filtered_count = len(assets)
            print(f"  [Semantic] Filtered {total_count} results to {filtered_count} (threshold={confidence_threshold:.2f})")
            total_count = filtered_count
        
        result = SearchResult(
            assets=assets,
            total_count=total_count,
            page=request_info.get("page", 1),
            page_size=request_info.get("page_size", 50),
            query=request_info.get("query", ""),
            search_type=request_info.get("search_type", "keyword"),
        )
        
        self.search_completed.emit(result)
    
    def _handle_asset_details_response(self, data: bytes) -> None:
        """Handle asset details response."""
        response = json.loads(data.decode())
        
        # Handle different response formats
        if isinstance(response, dict):
            # Wrapped response: data.asset or just the asset
            data_obj = response.get("data", response)
            if isinstance(data_obj, dict):
                asset_data = data_obj.get("asset", data_obj)
            else:
                asset_data = response
        else:
            asset_data = response
            
        asset = Asset.from_api_response(asset_data)
        self.asset_details_loaded.emit(asset)
    
    def _handle_download_url_response(self, data: bytes, request_info: Dict) -> None:
        """Handle download URL response."""
        response = json.loads(data.decode())
        asset_id = request_info.get("asset_id", "")
        
        print(f"  [Download URL] Response for {asset_id}: {response}")
        
        # Handle different response formats
        if isinstance(response, dict):
            # API may return data.presigned_url, data.downloadUrl or data.url
            data_obj = response.get("data", response)
            if isinstance(data_obj, dict):
                download_url = data_obj.get("presigned_url", data_obj.get("downloadUrl", data_obj.get("url", "")))
            else:
                download_url = str(data_obj) if data_obj else ""
        else:
            download_url = str(response) if response else ""
        
        print(f"  [Download URL] Extracted URL for {asset_id}: {download_url[:100] if download_url else 'NONE'}...")
        self.download_url_ready.emit(asset_id, download_url)
    
    def _handle_thumbnail_response(self, data: bytes, request_info: Dict) -> None:
        """Handle thumbnail response."""
        asset_id = request_info.get("asset_id", "")
        print(f"  [Thumbnail] Received thumbnail for {asset_id}: {len(data)} bytes")
        self.thumbnail_loaded.emit(asset_id, data)
    
    # Public API Methods
    
    def get_collections(self, page: int = 1, page_size: int = 100) -> None:
        """Fetch list of collections.
        
        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
        """
        url = self._make_url("/collections", {
            "page": page,
            "limit": page_size,
        })
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {"type": "collections"}
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_assets(
        self,
        collection_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        media_type: Optional[MediaType] = None,
    ) -> None:
        """Fetch list of assets.
        
        Args:
            collection_id: Filter by collection ID.
            page: Page number (1-indexed).
            page_size: Number of items per page.
            media_type: Filter by media type.
        """
        params = {
            "page": page,
            "limit": page_size,
        }
        
        if collection_id:
            params["collectionId"] = collection_id
        
        if media_type:
            params["mediaType"] = media_type.value
        
        url = self._make_url("/assets", params)
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {
            "type": "assets",
            "page": page,
            "page_size": page_size,
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def browse_assets(
        self,
        collection_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        media_type: Optional[MediaType] = None,
    ) -> None:
        """Browse assets using search as a fallback for /assets endpoint.
        
        This uses the search endpoint with a wildcard query, which can work
        as an alternative when the /assets endpoint has issues.
        
        Args:
            collection_id: Filter by collection ID.
            page: Page number (1-indexed).
            page_size: Number of items per page.
            media_type: Filter by media type.
        """
        # Use search with empty/wildcard query to browse all assets
        params = {
            "q": "*",  # Wildcard to match all
            "page": page,
            "pageSize": page_size,  # API expects 'pageSize' not 'limit'
            "semantic": "false",  # Not semantic for browsing
        }
        
        if collection_id:
            params["collectionId"] = collection_id
        
        if media_type:
            params["type"] = media_type.value  # API expects 'type' not 'mediaType'
        
        url = self._make_url("/search", params)
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        # Use "assets" type so it's processed the same way
        self._pending_requests[reply] = {
            "type": "assets",
            "page": page,
            "page_size": page_size,
            "is_browse": True,  # Mark as browse request
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def search(
        self,
        query: str,
        search_type: str = "keyword",
        collection_id: Optional[str] = None,
        media_type: Optional[MediaType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> None:
        """Search for assets.
        
        Args:
            query: Search query string.
            search_type: "keyword" or "semantic".
            collection_id: Filter by collection ID.
            media_type: Filter by media type.
            page: Page number (1-indexed).
            page_size: Number of items per page.
        """
        # Both keyword and semantic search use the same /search endpoint
        # Semantic search is triggered by adding semantic=true parameter
        endpoint = "/search"
        
        params = {
            "q": query,  # API expects 'q' not 'query'
            "page": page,
            "pageSize": page_size,  # API expects 'pageSize' not 'limit'
            "semantic": "true" if search_type == "semantic" else "false",  # Always include semantic param
        }
        
        if collection_id:
            params["collectionId"] = collection_id
        
        if media_type:
            params["type"] = media_type.value  # API expects 'type' not 'mediaType'
        
        url = self._make_url(endpoint, params)
        print(f"Search URL: {url}")
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {
            "type": "search",
            "query": query,
            "search_type": search_type,
            "page": page,
            "page_size": page_size,
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_asset_details(self, asset_id: str) -> None:
        """Fetch detailed information about an asset.
        
        Args:
            asset_id: The asset ID.
        """
        url = self._make_url(f"/assets/{asset_id}")
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {"type": "asset_details", "asset_id": asset_id}
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_download_url(self, asset_id: str, variant: str = "original") -> None:
        """Get presigned download URL for an asset.
        
        Args:
            asset_id: The asset ID (inventory ID format like "urn:medialake:asset:...").
            variant: "original" or "proxy".
        """
        url = self._make_url("/assets/generate-presigned-url")
        
        request = self._create_request(url)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json"
        )
        
        # Build JSON payload
        payload = {
            "inventory_id": asset_id,
            "expiration_time": 3600,  # 1 hour
            "purpose": variant,  # "original" or "proxy"
        }
        
        import json
        reply = self._network_manager.post(request, json.dumps(payload).encode())
        
        self._pending_requests[reply] = {
            "type": "download_url",
            "asset_id": asset_id,
            "variant": variant,
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_thumbnail(self, asset_id: str, thumbnail_url: str) -> None:
        """Fetch thumbnail image for an asset.
        
        Args:
            asset_id: The asset ID.
            thumbnail_url: URL of the thumbnail.
        """
        print(f"  [Thumbnail] Fetching thumbnail for {asset_id}: {thumbnail_url[:100]}...")
        
        request = QNetworkRequest(QUrl(thumbnail_url))
        
        # Thumbnails from CloudFront may need auth, so always add it if we have a token
        # But CloudFront signed URLs should work without auth headers
        # Only add auth for relative URLs or API URLs
        if not thumbnail_url.startswith("http") or self._base_url in thumbnail_url:
            for header, value in self._get_headers().items():
                request.setRawHeader(header.encode(), value.encode())
        
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {
            "type": "thumbnail",
            "asset_id": asset_id,
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_buckets(self) -> None:
        """Fetch list of available S3 buckets from connectors.
        
        Uses the /connectors/s3 endpoint to get S3 connector information
        which includes bucket names.
        
        Emits buckets_loaded signal when complete.
        """
        url = self._make_url("/connectors/s3")
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {"type": "buckets"}
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_upload_url(
        self,
        task_id: str,
        bucket_name: str,
        destination_key: str,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Get presigned upload URL for an S3 object.
        
        Args:
            task_id: The task ID to associate with the URL.
            bucket_name: The S3 bucket name.
            destination_key: The S3 object key.
            content_type: The content type of the file.
            
        Emits upload_url_ready signal when complete.
        """
        url = self._make_url("/storage/s3/generate-presigned-url")
        
        request = self._create_request(url)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json"
        )
        
        # Build JSON payload
        payload = {
            "bucket": bucket_name,
            "key": destination_key,
            "operation": "putObject",
            "expiration_time": 3600,  # 1 hour
            "content_type": content_type,
        }
        
        import json
        reply = self._network_manager.post(request, json.dumps(payload).encode())
        
        self._pending_requests[reply] = {
            "type": "upload_url",
            "task_id": task_id,
            "bucket": bucket_name,
            "key": destination_key,
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def request_asset_upload_url(
        self,
        task_id: str,
        connector_id: str,
        filename: str,
        content_type: str,
        file_size: int,
    ) -> None:
        """Request a presigned upload URL for ingesting an asset into Media Lake.
        
        This uses the /assets/upload endpoint which is the proper way to ingest
        files into Media Lake (as demonstrated in ingest.py).
        
        Args:
            task_id: The task ID to associate with the URL.
            connector_id: The connector ID (storage connector) to upload to.
            filename: The name of the file being uploaded.
            content_type: The MIME type of the file.
            file_size: The size of the file in bytes.
            
        Emits upload_url_ready signal when complete with (task_id, upload_url, destination_key).
        """
        url = self._make_url("/assets/upload")
        
        request = self._create_request(url)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json"
        )
        
        # Build JSON payload matching ingest.py format
        payload = {
            "connector_id": connector_id,
            "filename": filename,
            "content_type": content_type,
            "file_size": file_size,
        }
        
        print(f"  [Upload] Requesting upload URL for {filename}")
        print(f"  [Upload] Connector ID: {connector_id}")
        print(f"  [Upload] Payload: {payload}")
        
        reply = self._network_manager.post(request, json.dumps(payload).encode())
        
        self._pending_requests[reply] = {
            "type": "asset_upload_url",
            "task_id": task_id,
            "connector_id": connector_id,
            "filename": filename,
        }
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def get_connectors(self) -> None:
        """Fetch list of available storage connectors.
        
        Uses the /connectors endpoint to get connector information
        including connector IDs needed for uploads.
        
        Emits connectors_loaded signal when complete with list of connector dicts.
        """
        url = self._make_url("/connectors")
        
        request = self._create_request(url)
        reply = self._network_manager.get(request)
        
        self._pending_requests[reply] = {"type": "connectors"}
        reply.finished.connect(lambda: self._handle_response(reply))
    
    def _handle_buckets_response(self, data: bytes) -> None:
        """Handle buckets list response from /connectors/s3 endpoint.
        
        The response format is:
        {
            "data": {
                "connectors": [
                    {
                        "id": "...",
                        "name": "...",
                        "type": "s3",
                        "status": "active",
                        "storageIdentifier": "bucket-name",
                        ...
                    }
                ]
            }
        }
        
        We extract the storageIdentifier (bucket name) from each active connector.
        """
        response = json.loads(data.decode())
        
        buckets = []
        
        print(f"  [Buckets] Response: {response}")
        
        # Handle different response formats
        if isinstance(response, dict):
            data_obj = response.get("data", response)
            
            # Check for connectors array (from /connectors/s3 endpoint)
            connectors = data_obj.get("connectors", [])
            if connectors:
                for connector in connectors:
                    if isinstance(connector, dict):
                        # Get bucket name from storageIdentifier
                        bucket_name = connector.get("storageIdentifier")
                        if bucket_name:
                            # Only include active connectors
                            status = connector.get("status", "").lower()
                            if status in ("active", "enabled", ""):
                                buckets.append(bucket_name)
                                print(f"  [Buckets] Found bucket: {bucket_name} (status: {status})")
                            else:
                                print(f"  [Buckets] Skipping inactive bucket: {bucket_name} (status: {status})")
            else:
                # Fallback: check for direct buckets array
                buckets = data_obj.get("buckets", [])
        elif isinstance(response, list):
            # Direct list of connectors or bucket names
            for item in response:
                if isinstance(item, dict):
                    bucket_name = item.get("storageIdentifier") or item.get("name")
                    if bucket_name:
                        buckets.append(bucket_name)
                elif isinstance(item, str):
                    buckets.append(item)
        
        print(f"  [Buckets] Emitting {len(buckets)} buckets: {buckets}")
        self.buckets_loaded.emit(buckets)
    
    def _handle_upload_url_response(self, data: bytes, request_info: Dict) -> None:
        """Handle upload URL response."""
        response = json.loads(data.decode())
        task_id = request_info.get("task_id", "")
        destination_key = request_info.get("key", "")
        
        print(f"  [Upload URL] Response for {task_id}: {response}")
        
        # Handle different response formats
        if isinstance(response, dict):
            # API may return data.presigned_url, data.uploadUrl or data.url
            data_obj = response.get("data", response)
            if isinstance(data_obj, dict):
                upload_url = data_obj.get("presigned_url", data_obj.get("uploadUrl", data_obj.get("url", "")))
            else:
                upload_url = str(data_obj) if data_obj else ""
        else:
            upload_url = str(response) if response else ""
        
        print(f"  [Upload URL] Extracted URL for {task_id}: {upload_url[:100] if upload_url else 'NONE'}...")
        self.upload_url_ready.emit(task_id, upload_url, destination_key)
    
    def _handle_asset_upload_url_response(self, data: bytes, request_info: Dict) -> None:
        """Handle asset upload URL response from /assets/upload endpoint.
        
        The response format from ingest.py is:
        {
            "data": {
                "presigned_post": {
                    "url": "https://...",
                    "fields": {...}
                },
                "key": "...",
                "multipart": false
            }
        }
        
        For single-part uploads, we use presigned_post.url.
        For multipart uploads, additional handling would be needed.
        """
        response = json.loads(data.decode())
        task_id = request_info.get("task_id", "")
        filename = request_info.get("filename", "")
        
        print(f"  [Asset Upload URL] Response for {task_id}: {response}")
        
        # Handle different response formats
        upload_url = ""
        destination_key = ""
        presigned_fields = {}
        is_multipart = False
        
        if isinstance(response, dict):
            data_obj = response.get("data", response)
            if isinstance(data_obj, dict):
                # Check for multipart upload
                is_multipart = data_obj.get("multipart", False)
                destination_key = data_obj.get("key", "")
                
                if is_multipart:
                    # For multipart uploads, we'd need different handling
                    # For now, emit error
                    print(f"  [Asset Upload URL] Multipart upload not yet supported")
                    self.error_occurred.emit("upload_error", "Multipart uploads not yet supported for large files")
                    return
                else:
                    # Single-part upload using presigned POST
                    presigned_post = data_obj.get("presigned_post", {})
                    upload_url = presigned_post.get("url", "")
                    presigned_fields = presigned_post.get("fields", {})
        
        print(f"  [Asset Upload URL] Extracted URL for {task_id}: {upload_url[:100] if upload_url else 'NONE'}...")
        print(f"  [Asset Upload URL] Destination key: {destination_key}")
        print(f"  [Asset Upload URL] Presigned fields: {list(presigned_fields.keys())}")
        
        # Emit the upload URL ready signal
        # Note: For presigned POST, we need to include the fields in the upload
        # We'll encode the fields as JSON in the destination_key for now
        # The upload worker will need to handle this
        if presigned_fields:
            # Encode presigned fields as JSON to pass along
            fields_json = json.dumps(presigned_fields)
            self.upload_url_ready.emit(task_id, upload_url, fields_json)
        else:
            self.upload_url_ready.emit(task_id, upload_url, destination_key)
    
    def _handle_connectors_response(self, data: bytes) -> None:
        """Handle connectors list response from /connectors endpoint.
        
        The response format is:
        {
            "status": "200",
            "message": "ok",
            "data": {
                "connectors": [
                    {
                        "id": "...",
                        "name": "...",
                        "storageIdentifier": "bucket-name",
                        "status": "active",
                        ...
                    }
                ]
            }
        }
        
        Emits connectors_loaded signal with list of connector dicts containing:
        - id: The connector ID
        - storageIdentifier: The bucket name
        - name: The connector name
        - status: The connector status
        """
        response = json.loads(data.decode())
        
        connectors = []
        
        print(f"  [Connectors] Response: {response}")
        
        # Handle different response formats
        if isinstance(response, dict):
            data_obj = response.get("data", response)
            
            # Check for connectors array
            connector_list = data_obj.get("connectors", [])
            if connector_list:
                for connector in connector_list:
                    if isinstance(connector, dict):
                        connector_id = connector.get("id", connector.get("connectorId", ""))
                        bucket_name = connector.get("storageIdentifier", "")
                        name = connector.get("name", "")
                        status = connector.get("status", "").lower()
                        
                        if connector_id and bucket_name:
                            # Only include active connectors
                            if status in ("active", "enabled", ""):
                                connectors.append({
                                    "id": connector_id,
                                    "storageIdentifier": bucket_name,
                                    "name": name,
                                    "status": status,
                                })
                                print(f"  [Connectors] Found connector: {name} ({connector_id}) -> {bucket_name}")
                            else:
                                print(f"  [Connectors] Skipping inactive connector: {name} (status: {status})")
        elif isinstance(response, list):
            # Direct list of connectors
            for connector in response:
                if isinstance(connector, dict):
                    connector_id = connector.get("id", connector.get("connectorId", ""))
                    bucket_name = connector.get("storageIdentifier", "")
                    name = connector.get("name", "")
                    status = connector.get("status", "").lower()
                    
                    if connector_id and bucket_name:
                        connectors.append({
                            "id": connector_id,
                            "storageIdentifier": bucket_name,
                            "name": name,
                            "status": status,
                        })
        
        print(f"  [Connectors] Emitting {len(connectors)} connectors")
        self.connectors_loaded.emit(connectors)
    
    def cancel_all_requests(self) -> None:
        """Cancel all pending requests."""
        for reply in list(self._pending_requests.keys()):
            reply.abort()
            reply.deleteLater()
        self._pending_requests.clear()

