import json
import os
import uuid
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")

        # Extract visitor info from the request
        source_ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp", "unknown")
        user_agent = event.get("headers", {}).get("User-Agent", "unknown")

        item = {
            "visitor_id": body.get("visitor_id", str(uuid.uuid4())),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "page": body.get("page", "/"),
            "referrer": body.get("referrer", ""),
            "ip": source_ip,
            "user_agent": user_agent,
            "screen_width": body.get("screen_width", 0),
            "screen_height": body.get("screen_height", 0),
        }

        table.put_item(Item=item)

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "ok"}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)}),
        }
