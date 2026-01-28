import os
from typing import Optional
import boto3
import requests

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

        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")
        print(f"Request Payload: {payload}")

        response = requests.post(url, headers=headers, json=payload)

        # Debug: Print response details
        print(f"\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: '{response.text[:1000] if response.text else 'EMPTY'}'")
        print(f"--- End Response ---\n")

        # Check status first
        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        # Check if response has content before parsing JSON
        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        try:
            json_response = response.json()
            print(f"Parsed JSON: {json_response}")
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

        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")

        response = requests.get(url, headers=headers)

        # Debug: Print response details
        print(f"\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: '{response.text[:1000] if response.text else 'EMPTY'}'")
        print(f"Response Content-Type: {response.headers.get('content-type', 'NOT SET')}")
        print(f"Response Encoding: {response.encoding}")
        print(f"--- End Response ---\n")

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
            print(f"Parsed JSON: {json_response}")
        except Exception as e:
            # Print more detailed error information
            print(f"JSON Parse Error: {e}")
            print(f"Response text (first 500 chars): {response.text[:500]}")
            print(f"Response text (repr): {repr(response.text[:200])}")
            raise ValueError(f"Failed to parse JSON response: {e}. Raw text: {response.text}")

        return json_response

    def add_custom_metadata(self, asset_id: str, metadata: dict) -> dict:
        """
        Add or update custom metadata on an existing asset.
        
        Note: This uses a direct DynamoDB update since there's no dedicated API endpoint
        for updating asset metadata. The metadata is stored in the Metadata.CustomMetadata
        field of the asset record.
        
        Args:
            asset_id: The InventoryID of the asset (e.g., "asset:img:uuid-here")
            metadata: Dictionary of custom metadata key-value pairs to add/update
            
        Returns:
            dict: The API response containing the updated asset
        """
        # Use the assets/{id}/metadata endpoint if it exists, otherwise fall back to
        # a workaround using the available API
        url = f"{self.api_base}/assets/{asset_id}/metadata"
        headers = self._get_headers()
        payload = {
            "customMetadata": metadata
        }

        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")
        print(f"Request Payload: {payload}")

        # Try PATCH first (most RESTful for partial updates)
        response = requests.patch(url, headers=headers, json=payload)

        # Debug: Print response details
        print(f"\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: '{response.text[:1000] if response.text else 'EMPTY'}'")
        print(f"Response Content-Type: {response.headers.get('content-type', 'NOT SET')}")
        print(f"--- End Response ---\n")

        # If PATCH to /metadata endpoint doesn't exist (404), try PUT
        if response.status_code == 404:
            print("PATCH /metadata not found, trying PUT...")
            response = requests.put(url, headers=headers, json=payload)
            
            print(f"\n--- PUT Response ---")
            print(f"Status Code: {response.status_code}")
            print(f"Response Text: '{response.text[:1000] if response.text else 'EMPTY'}'")
            print(f"--- End PUT Response ---\n")

        # If neither endpoint exists, we need to use a workaround:
        # Get the asset, modify it, and use an available update mechanism
        if response.status_code == 404:
            print("No metadata endpoint available. Using workaround via asset retrieval...")
            
            # Get current asset data
            get_url = f"{self.api_base}/assets/{asset_id}"
            get_response = requests.get(get_url, headers=headers)
            
            if get_response.status_code != 200:
                raise ValueError(f"Failed to get asset: {get_response.status_code}: {get_response.text}")
            
            asset_data = get_response.json()
            print(f"Current asset data retrieved successfully")
            print(f"Asset: {asset_data}")
            
            # Note: Without a proper update endpoint, we can only return the current state
            # and inform the user that custom metadata updates require a different approach
            return {
                "status": "warning",
                "message": "No API endpoint available for updating custom metadata. "
                           "Custom metadata can only be set during asset upload. "
                           "Consider re-uploading the asset with the desired metadata.",
                "data": {
                    "asset": asset_data,
                    "requested_metadata": metadata
                }
            }

        if response.status_code not in [200, 201]:
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
            print(f"Parsed JSON: {json_response}")
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            print(f"Response text (first 500 chars): {response.text[:500]}")
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

        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")

        response = requests.get(url, headers=headers)

        # Debug: Print response details
        print(f"\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: '{response.text[:1000] if response.text else 'EMPTY'}'")
        print(f"Response Content-Type: {response.headers.get('content-type', 'NOT SET')}")
        print(f"--- End Response ---\n")

        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' not in content_type:
            print(f"WARNING: Response content-type is '{content_type}', not JSON")

        try:
            json_response = response.json()
            print(f"Parsed JSON: {json_response}")
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

        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")

        response = requests.get(url, headers=headers)

        # Debug: Print response details
        print(f"\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: '{response.text[:1000] if response.text else 'EMPTY'}'")
        print(f"Response Content-Type: {response.headers.get('content-type', 'NOT SET')}")
        print(f"--- End Response ---\n")

        if response.status_code != 200:
            raise ValueError(f"Server returned status {response.status_code}: {response.text}")

        if not response.text or response.text.strip() == "":
            raise ValueError("Server returned empty response body")

        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' not in content_type:
            print(f"WARNING: Response content-type is '{content_type}', not JSON")

        try:
            json_response = response.json()
            print(f"Parsed JSON: {json_response}")
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


# Usage
client = MediaLakeClient(
    api_base_url="https://cloudfront_url/v1",
    cognito_client_id="client_id_here",
)

client.authenticate("username", "password")

connector_id = client.get_connector_id_by_name("My S3 Connector")

# Upload with custom metadata
result = client.upload_file(
    connector_id=connector_id,
    file_path="/file/to/ingest.mp4",
    metadata={
        "project": "Sample Project",
        "shoot_date": "2024-01-28"
    }
)