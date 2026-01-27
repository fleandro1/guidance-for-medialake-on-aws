"""
Notify on Teams Lambda
──────────────────────────────────────────────────────────────────────
Posts a notification to Microsoft Teams with information about the processed image asset.

ENV
───
TEAMS_WEBHOOK_URL       Microsoft Teams webhook URL (can be overridden by input parameter)
EVENT_BUS_NAME          optional (for @lambda_middleware)
"""

import json
import os
from typing import Any, Dict

import requests
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()

# Default webhook URL from environment
DEFAULT_WEBHOOK_URL = os.environ.get(
    "TEAMS_WEBHOOK_URL",
    "https://jwsite.webhook.office.com/webhookb2/af73926d-c9e4-4f46-922e-8c03e69285ba@e9b2b7ba-b238-42a9-b271-2adfc82da650/IncomingWebhook/cf18e1ed0d4f44a38c2faf26218e90e6/b5779401-ebc6-4604-bc3d-c4a6052a60fb/V2_9Tty1Ql3sQFZ4Vb9630IkOcCQwHyEAsrGlW-Je26I81"
)


def format_asset_info(asset: Dict[str, Any]) -> str:
    """Format asset information for Teams message."""
    try:
        asset_id = asset.get("DigitalSourceAsset", {}).get("ID", "Unknown")
        inventory_id = asset.get("InventoryID", "Unknown")
        
        # Get file information
        storage_info = asset.get("DigitalSourceAsset", {}).get("StorageInfo", {})
        primary_location = storage_info.get("PrimaryLocation", {})
        bucket = primary_location.get("Bucket", "Unknown")
        object_key = primary_location.get("ObjectKey", {})
        full_path = object_key.get("FullPath", "Unknown")
        
        # Get metadata if available
        metadata = asset.get("Metadata", {})
        file_size = metadata.get("FileSize", "Unknown")
        mime_type = metadata.get("MimeType", "Unknown")
        
        info_parts = [
            f"**Asset ID:** {asset_id}",
            f"**Inventory ID:** {inventory_id}",
            f"**Bucket:** {bucket}",
            f"**Path:** {full_path}",
            f"**File Size:** {file_size}",
            f"**MIME Type:** {mime_type}"
        ]
        
        return "\n\n".join(info_parts)
    except Exception as e:
        logger.warning(f"Error formatting asset info: {e}")
        return "Asset information unavailable"


def create_teams_message(event: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Microsoft Teams adaptive card message."""
    payload = event.get("payload", {})
    assets = payload.get("assets", [])
    
    # Get pipeline information
    input_payload = payload.get("event", {}).get("input", {})
    pipeline_name = input_payload.get("pipelineName", "Unknown Pipeline")
    
    # Format asset information
    if assets:
        asset_info = format_asset_info(assets[0])
        asset_count = len(assets)
    else:
        asset_info = "No asset information available"
        asset_count = 0
    
    # Create adaptive card for Teams
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "MediaLake Pipeline Notification",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "Accent"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Pipeline: {pipeline_name}",
                            "weight": "Bolder",
                            "size": "Medium",
                            "spacing": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Assets Processed: {asset_count}",
                            "spacing": "Small"
                        },
                        {
                            "type": "TextBlock",
                            "text": asset_info,
                            "wrap": True,
                            "spacing": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Status: ✅ Success",
                            "color": "Good",
                            "weight": "Bolder",
                            "spacing": "Medium"
                        }
                    ]
                }
            }
        ]
    }
    
    return card


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler to post notifications to Microsoft Teams.
    
    Args:
        event: Lambda event containing asset information
        context: Lambda context
        
    Returns:
        Dict with statusCode and response body
    """
    logger.debug("Received event: %s", json.dumps(event))
    
    try:
        # Get webhook URL from input or use default
        input_payload = event.get("payload", {}).get("event", {}).get("input", {})
        webhook_url = input_payload.get("webhookUrl", DEFAULT_WEBHOOK_URL)
        
        if not webhook_url:
            error_msg = "No Teams webhook URL configured"
            logger.error(error_msg)
            return {
                "statusCode": 400,
                "body": json.dumps({"error": error_msg})
            }
        
        # Create Teams message
        teams_message = create_teams_message(event)
        
        # Post to Teams webhook
        logger.info(f"Posting notification to Teams webhook")
        response = requests.post(
            webhook_url,
            json=teams_message,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        response.raise_for_status()
        
        logger.info(f"Successfully posted to Teams. Status: {response.status_code}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Notification sent to Teams successfully",
                "teamsResponse": response.text
            })
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to post to Teams webhook: {str(e)}"
        logger.error(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg})
        }
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg})
        }
