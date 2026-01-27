import os
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

    def upload_file(self, connector_id: str, file_path: str) -> dict:
        """Upload a file to Media Lake."""
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

# Usage
client = MediaLakeClient(
    api_base_url="https://d13rj50wbm0a7o.cloudfront.net/v1",
    cognito_client_id="4qh19u8khldfgdnhch1evcrn8o"
)

client.authenticate("username@jw.org", "YourPasswordHere")
connector_id = "your_connector_id_here"
result = client.upload_file(connector_id, "/path/to/file/to/be/ingested.xxx")
print(f"Upload complete: {result}")
