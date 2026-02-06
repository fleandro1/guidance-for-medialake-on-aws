import os
import time
from typing import Optional, List
import boto3
import requests

os.environ["CONNECTOR_NAME"] = "Storage Connector"
os.environ["API_BASE_URL"] = "<medialake_url>/v1"
os.environ["COGNITO_CLIENT_ID"] = "congnito-client-id-1234567890"
os.environ["AWS_REGION"] = "aws-region-1"
os.environ["USERNAME"] = "username"
os.environ["PASSWORD"] = "password"

class MediaLakeClient:
    def __init__(self, api_base_url: str, cognito_client_id: str, region: str = "us-east-1"):
        self.api_base = api_base_url.rstrip("/")
        self.client_id = cognito_client_id
        self.region = region
        self.cognito = boto3.client("cognito-idp", region_name=region)
        self.token = None
        self.refresh_token = None

    def authenticate(self, username: str, password: str):
        """Authenticate and store tokens."""
        response = self.cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=self.client_id,
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
            }
        )
        self.token = response["AuthenticationResult"]["IdToken"]
        self.refresh_token = response["AuthenticationResult"]["RefreshToken"]
        return self.token

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        if not self.token:
            raise ValueError("Not authenticated. Call authenticate() first.")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def upload_file(self, connector_id: str, file_path: str, metadata: Optional[dict] = None) -> dict:
        """
        Upload a file to Media Lake with optional custom metadata.
        
        Args:
            connector_id: The ID of the connector to upload to
            file_path: Path to the file to upload
            metadata: Optional dictionary of custom metadata key-value pairs
                      Example: {"project": "Marketing Q1", "category": "B-roll", "tags": "outdoor,nature"}
        
        Returns:
            dict: Upload result containing status and asset key
        """
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Determine content type
        ext = filename.lower().split(".")[-1]
        content_types = {
            "mp4": "video/mp4", "mov": "video/quicktime",
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "mp3": "audio/mpeg", "wav": "audio/wav",
            "mxf": "application/mxf",
        }
        content_type = content_types.get(ext, "application/octet-stream")

        # Request presigned URL
        url = f"{self.api_base}/assets/upload"
        headers = self._get_headers()
        payload = {
            "connector_id": connector_id,
            "filename": filename,
            "content_type": content_type,
            "file_size": file_size
        }
        
        # Add custom metadata if provided
        if metadata:
            payload["metadata"] = metadata

        response = requests.post(url, headers=headers, json=payload)

        # Check status first
        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        # Check if response has content before parsing JSON
        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        try:
            json_response = response.json()
        except Exception as e:
            raise ValueError(f"Failed to parse JSON response: {e}. Raw text: {response.text}")

        data = json_response.get("data")
        if not data:
            raise ValueError(f"Response missing 'data' field: {json_response}")

        # Upload file
        if data.get("multipart"):
            return self._multipart_upload(file_path, data, connector_id)
        else:
            return self._single_upload(file_path, data)

    def _single_upload(self, file_path: str, data: dict) -> dict:
        """Handle single-part upload."""
        presigned = data["presigned_post"]
        with open(file_path, "rb") as f:
            response = requests.post(
                presigned["url"],
                data=presigned["fields"],
                files={"file": f}
            )
        response.raise_for_status()
        return {"status": "success", "key": data["key"]}

    def _multipart_upload(self, file_path: str, data: dict, connector_id: str) -> dict:
        """Handle multipart upload."""
        # Implementation similar to examples above
        pass

    def _list_permission_sets(self) -> dict:
        """List permission sets."""
        url = f"{self.api_base}/permissions/permission-sets"
        headers = self._get_headers()

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        # Check if response has content before parsing JSON
        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' not in content_type:
            print(f"WARNING: Response content-type is '{content_type}', not JSON")

        try:
            json_response = response.json()
        except Exception as e:
            # Print more detailed error information
            print(f"JSON Parse Error: {e}")
            print(f"Response text (first 500 chars): {response.text[:500]}")
            print(f"Response text (repr): {repr(response.text[:200])}")
            raise ValueError(f"Failed to parse JSON response: {e}. Raw text: {response.text}")

        return json_response


    def get_asset(self, asset_id: str) -> dict:
        """
        Get details of a specific asset by its ID.
        
        Args:
            asset_id: The InventoryID of the asset
            
        Returns:
            dict: The asset details
        """
        url = f"{self.api_base}/assets/{asset_id}"
        headers = self._get_headers()

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' not in content_type:
            print(f"WARNING: Response content-type is '{content_type}', not JSON")

        try:
            json_response = response.json()
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            raise ValueError(f"Failed to parse JSON response: {e}. Raw text: {response.text}")

        return json_response

    def get_connector_id_by_name(self, connector_name: str) -> str:
        """
        Get the connector ID based on the connector name.
        
        Args:
            connector_name: The name of the connector (e.g., "Main Asset Storage")
            
        Returns:
            str: The connector ID
            
        Raises:
            ValueError: If no connector with the given name is found
        """
        url = f"{self.api_base}/connectors"
        headers = self._get_headers()

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' not in content_type:
            print(f"WARNING: Response content-type is '{content_type}', not JSON")

        try:
            json_response = response.json()
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            raise ValueError(f"Failed to parse JSON response: {e}. Raw text: {response.text}")

        # Search for the connector by name
        connectors = json_response.get("data", []).get("connectors", [])
        for connector in connectors:
            # Ensure connector is a dictionary before calling .get()
            if isinstance(connector, dict) and connector.get("name") == connector_name:
                connector_id = connector.get("id")
                print(f"Found connector '{connector_name}' with ID: {connector_id}")
                return connector_id

        # If not found, list available connectors for user reference
        available_names = [c.get("name") if isinstance(c, dict) else str(c) for c in connectors]
        raise ValueError(
            f"No connector found with name '{connector_name}'. "
            f"Available connectors: {available_names}"
        )

    def wait_for_asset(self, asset_key: str, max_wait_seconds: int = 300, poll_interval: int = 5) -> Optional[dict]:
        """
        Wait for an asset to be fully ingested and available in the system.
        
        Uses the /assets endpoint first (more reliable), falls back to search.
        
        Args:
            asset_key: The S3 key of the uploaded asset (from upload response)
            max_wait_seconds: Maximum time to wait in seconds (default: 300 = 5 minutes)
            poll_interval: Time between polling attempts in seconds (default: 5)
            
        Returns:
            dict: The asset details if found, None if timeout
        """
        # Extract just the filename for searching
        filename = os.path.basename(asset_key)
        print(f"Waiting for asset to be ingested: {asset_key}")
        print(f"  Looking for filename: {filename}")
        start_time = time.time()
        attempt = 0
        
        while (time.time() - start_time) < max_wait_seconds:
            attempt += 1
            try:
                headers = self._get_headers()
                
                # Method 1: Try /assets endpoint (DynamoDB-based, doesn't need OpenSearch)
                assets_url = f"{self.api_base}/assets"
                params = {"limit": 100}  # Get recent assets
                
                response = requests.get(assets_url, headers=headers, params=params)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Handle Lambda proxy response format
                    if "body" in result and isinstance(result["body"], str):
                        import json
                        result = json.loads(result["body"])
                    
                    assets = result.get("data", {}).get("items", [])
                    
                    if attempt == 1:
                        print(f"  /assets endpoint returned {len(assets)} items")
                    
                    # Look for the asset with matching filename
                    for asset in assets:
                        asset_name = asset.get("AssetName", "")
                        
                        # Debug: show first few asset names on first attempt
                        if attempt == 1 and len(assets) > 0:
                            sample_names = [a.get("AssetName", "?") for a in assets[:3]]
                            print(f"  Sample asset names: {sample_names}")
                        
                        # Match by filename
                        if asset_name == filename or filename in asset_name:
                            inventory_id = asset.get("InventoryID")
                            print(f"  ✓ Asset found via /assets: {inventory_id}")
                            return asset
                    
                    if attempt == 1:
                        print(f"  Asset not in /assets response, trying search...")
                
                # Method 2: Fall back to search endpoint
                search_url = f"{self.api_base}/search"
                search_params = {
                    "q": filename,
                    "pageSize": 50
                }
                
                search_response = requests.get(search_url, headers=headers, params=search_params)
                
                if search_response.status_code == 200:
                    search_result = search_response.json()
                    search_assets = search_result.get("data", {}).get("results", [])
                    
                    if attempt == 1:
                        print(f"  Search returned {len(search_assets)} results")
                    
                    for asset in search_assets:
                        storage_path = asset.get("DigitalSourceAsset", {}).get(
                            "MainRepresentation", {}
                        ).get("StorageInfo", {}).get("PrimaryLocation", {}).get(
                            "ObjectKey", {}
                        ).get("FullPath", "")
                        
                        asset_name = asset.get("AssetName", "")
                        
                        key_matches = storage_path and asset_key in storage_path
                        filename_matches = (
                            (storage_path and filename in storage_path) or
                            (asset_name and filename in asset_name) or
                            (asset_name and asset_name == filename)
                        )
                        
                        if key_matches or filename_matches:
                            inventory_id = asset.get("InventoryID")
                            print(f"  ✓ Asset found via search: {inventory_id}")
                            return asset
                
                elapsed = int(time.time() - start_time)
                print(f"  [{elapsed}s] Asset not yet available, waiting {poll_interval}s...")
                time.sleep(poll_interval)
                
            except Exception as e:
                print(f"  Error checking asset: {e}, retrying...")
                time.sleep(poll_interval)
        
        print(f"✗ Timeout waiting for asset after {max_wait_seconds}s")
        return None

    def create_collection(self, name: str, description: str = "") -> dict:
        """
        Create a new collection.
        
        Args:
            name: The name of the collection
            description: Optional description of the collection
            
        Returns:
            dict: The created collection details including its ID
        """
        url = f"{self.api_base}/collections"
        headers = self._get_headers()
        payload = {
            "name": name,
            "description": description or f"Collection created on {time.strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code not in [200, 201]:
            raise ValueError(f"Failed to create collection: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Handle Lambda proxy response format where body is JSON string
        if "body" in result and isinstance(result["body"], str):
            import json
            result = json.loads(result["body"])
        
        collection = result.get("data", {})
        collection_id = collection.get("id")
        
        print(f"✓ Collection created: '{name}' (ID: {collection_id})")
        return collection

    def add_assets_to_collection(self, collection_id: str, asset_ids: List[str]) -> dict:
        """
        Add multiple assets to a collection.
        
        Args:
            collection_id: The ID of the collection
            asset_ids: List of asset InventoryIDs to add
            
        Returns:
            dict: Response from the API
        """
        url = f"{self.api_base}/collections/{collection_id}/items"
        headers = self._get_headers()
        
        # Add assets one by one (API might support batch, but this is safer)
        added_count = 0
        for asset_id in asset_ids:
            try:
                payload = {"assetId": asset_id}
                response = requests.post(url, headers=headers, json=payload)
                
                if response.status_code in [200, 201]:
                    added_count += 1
                else:
                    print(f"  ✗ Failed to add asset {asset_id}: {response.status_code}")
                    print(f"     Response: {response.text}")
            except Exception as e:
                print(f"  ✗ Error adding asset {asset_id}: {e}")
        
        print(f"✓ Added {added_count}/{len(asset_ids)} assets to collection")
        return {"added_count": added_count, "total": len(asset_ids)}


    def create_new_collection(
        self, 
        collection_name: str, 
        file_paths: List[str], 
        connector_id: str,
        metadata: Optional[dict] = None,
        collection_description: str = "",
        max_wait_per_asset: int = 300
    ) -> dict:
        """
        Create a new collection and add ingested files to it.
        
        This method:
        1. Uploads all files to Media Lake
        2. Waits for each asset to be fully ingested
        3. Creates a new collection
        4. Adds all ingested assets to the collection
        
        Args:
            collection_name: Name for the new collection
            file_paths: List of file paths to ingest and add to collection
            connector_id: The connector ID to upload files to
            metadata: Optional metadata to attach to all uploaded files
            collection_description: Optional description for the collection
            max_wait_per_asset: Maximum seconds to wait for each asset (default: 300)
            
        Returns:
            dict: Summary of the operation including collection ID and asset IDs
        """
        print(f"\n{'='*60}")
        print(f"Creating collection '{collection_name}' with {len(file_paths)} files")
        print(f"{'='*60}\n")
        
        # Step 1: Upload all files
        print("Step 1: Uploading files...")
        upload_results = []
        
        for i, file_path in enumerate(file_paths, 1):
            print(f"\n[{i}/{len(file_paths)}] Uploading: {os.path.basename(file_path)}")
            try:
                result = self.upload_file(connector_id, file_path, metadata)
                upload_results.append({
                    "file_path": file_path,
                    "key": result.get("key"),
                    "status": result.get("status")
                })
                print(f"  ✓ Upload successful: {result.get('key')}")
            except Exception as e:
                print(f"  ✗ Upload failed: {e}")
                upload_results.append({
                    "file_path": file_path,
                    "key": None,
                    "status": "failed",
                    "error": str(e)
                })
        
        successful_uploads = [r for r in upload_results if r.get("key")]
        print(f"\n✓ Uploaded {len(successful_uploads)}/{len(file_paths)} files successfully")
        
        if not successful_uploads:
            raise ValueError("No files were uploaded successfully")
        
        # Step 2: Wait for assets to be ingested
        print(f"\nStep 2: Waiting for assets to be ingested...")
        ingested_assets = []
        
        for i, upload_result in enumerate(successful_uploads, 1):
            asset_key = upload_result.get("key")
            filename = os.path.basename(upload_result.get("file_path"))
            print(f"\n[{i}/{len(successful_uploads)}] Waiting for: {filename}")
            
            asset = self.wait_for_asset(asset_key, max_wait_seconds=max_wait_per_asset)
            if asset:
                inventory_id = asset.get("InventoryID")
                ingested_assets.append({
                    "file_path": upload_result.get("file_path"),
                    "inventory_id": inventory_id,
                    "asset": asset
                })
            else:
                print(f"  ⚠ Asset not ready after {max_wait_per_asset}s, skipping")
        
        print(f"\n✓ {len(ingested_assets)}/{len(successful_uploads)} assets ready")
        
        if not ingested_assets:
            raise ValueError("No assets were successfully ingested")
        
        # Step 3: Create the collection
        print(f"\nStep 3: Creating collection '{collection_name}'...")
        collection = self.create_collection(collection_name, collection_description)
        collection_id = collection.get("id")
        
        # Step 4: Add assets to collection
        print(f"\nStep 4: Adding {len(ingested_assets)} assets to collection...")
        asset_ids = [a.get("inventory_id") for a in ingested_assets]
        self.add_assets_to_collection(collection_id, asset_ids)
        
        # Summary
        result = {
            "collection_id": collection_id,
            "collection_name": collection_name,
            "total_files": len(file_paths),
            "uploaded": len(successful_uploads),
            "ingested": len(ingested_assets),
            "added_to_collection": len(asset_ids),
            "asset_ids": asset_ids,
            "failed_uploads": [r for r in upload_results if not r.get("key")]
        }
        
        print(f"\n{'='*60}")
        print(f"✓ Collection '{collection_name}' created successfully!")
        print(f"  Collection ID: {collection_id}")
        print(f"  Assets added: {len(asset_ids)}/{len(file_paths)}")
        print(f"{'='*60}\n")
        
        return result


# Usage

client = MediaLakeClient(
    api_base_url=os.environ["API_BASE_URL"],
    cognito_client_id=os.environ["COGNITO_CLIENT_ID"],
)

client.authenticate(os.environ["USERNAME"], os.environ["PASSWORD"])

connector_id = client.get_connector_id_by_name(os.environ["CONNECTOR_NAME"])

# ## ADDING CUSTOM METADATA EXAMPLE
# for file_path in [
#     "/path/to/file/image-001.jpg",
#     "/path/to/file/image-002.jpg",
# ]:
#     print(f"\nUploading file with custom metadata: {file_path}")
#     result = client.upload_file(
#         connector_id=connector_id,
#         file_path=file_path,
#         metadata={
#             "project": "Test",
#             "tags": "tag1,tag2",
#         }
#     )
#     print(f"Upload result: {result}")

# COLLECTION CREATION EXAMPLE
# result = client.create_new_collection(
#     collection_name="Test Photo Set",
#     file_paths=[
#         "/path/to/file/image-001.jpg",
#         "/path/to/file/image-002.jpg",
#     ],
#     connector_id=connector_id,
#     collection_description="All assets for the Test photo set"
# )
# print(f"Collection ID: {result['collection_id']}")
# print(f"Assets added: {result['added_to_collection']}")
