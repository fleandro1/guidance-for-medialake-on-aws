"""
Proxy Logger Node - Logs proxy path and passes through input data unchanged.
"""
import json
import os

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()


def _raise(msg: str):
    raise ValueError(msg)


def _extract_proxy_info(event: dict) -> dict:
    """
    Extract proxy path information from the event payload.
    Handles both direct asset data and pipeline payload formats.
    """
    payload = event.get("payload") or {}
    assets = payload.get("assets") or []
    
    proxy_info = {
        "paths": [],
        "asset_count": len(assets),
    }
    
    for asset in assets:
        # Check DerivedRepresentations for proxy
        derived_reps = asset.get("DerivedRepresentations", [])
        for rep in derived_reps:
            if rep.get("Purpose") == "proxy":
                storage_info = rep.get("StorageInfo", {}).get("PrimaryLocation", {})
                bucket = storage_info.get("Bucket", "")
                key = storage_info.get("ObjectKey", {}).get("FullPath", "")
                if bucket and key:
                    proxy_info["paths"].append({
                        "bucket": bucket,
                        "key": key,
                        "full_path": f"s3://{bucket}/{key}",
                        "inventory_id": asset.get("InventoryID", "unknown"),
                    })
        
        # Also check MainRepresentation (in case this IS the proxy)
        main_rep = asset.get("DigitalSourceAsset", {}).get("MainRepresentation", {})
        main_storage = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})
        if main_storage:
            bucket = main_storage.get("Bucket", "")
            key = main_storage.get("ObjectKey", {}).get("FullPath", "")
            if bucket and key:
                proxy_info["paths"].append({
                    "bucket": bucket,
                    "key": key,
                    "full_path": f"s3://{bucket}/{key}",
                    "inventory_id": asset.get("InventoryID", "unknown"),
                    "source": "main_representation",
                })
    
    return proxy_info


@lambda_middleware(
    event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"),
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Main handler - logs proxy paths and passes through input unchanged.
    """
    logger.info("Proxy Logger Node invoked", extra={"event_keys": list(event.keys())})
    
    # Extract and log proxy information
    proxy_info = _extract_proxy_info(event)
    
    logger.info(
        "Proxy paths logged",
        extra={
            "proxy_info": proxy_info,
            "asset_count": proxy_info["asset_count"],
            "path_count": len(proxy_info["paths"]),
        }
    )
    
    # Log each path individually for easy filtering in CloudWatch
    for path_info in proxy_info["paths"]:
        logger.info(
            "PROXY_PATH",
            extra={
                "inventory_id": path_info["inventory_id"],
                "bucket": path_info["bucket"],
                "key": path_info["key"],
                "full_path": path_info["full_path"],
            }
        )
    
    # Pass through the original input unchanged
    # The middleware expects a dict that it will wrap in the standard output format
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Proxy path logged successfully",
            "paths_logged": len(proxy_info["paths"]),
        }),
        "passthrough": True,  # Flag indicating this is a passthrough node
    }
