import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "changeme")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Simple password check via Authorization header
    auth = event.get("headers", {}).get("Authorization", "")
    if auth != f"Bearer {DASHBOARD_PASSWORD}":
        return {
            "statusCode": 401,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Unauthorized"}),
        }

    try:
        days = int(event.get("queryStringParameters", {}).get("days", "30"))
    except (TypeError, ValueError):
        days = 30

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Scan with filter (fine for a personal portfolio scale)
    items = []
    scan_kwargs = {
        "FilterExpression": Attr("timestamp").gte(cutoff) & Attr("type").eq("visitor")
    }
    while True:
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    # Aggregate stats
    unique_visitors = set()
    page_counts = Counter()
    daily_visits = Counter()
    referrer_counts = Counter()
    screen_sizes = Counter()
    hourly = Counter()

    for item in items:
        unique_visitors.add(item.get("visitor_id", ""))
        page_counts[item.get("page", "/")] += 1

        ts = item.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                daily_visits[dt.strftime("%Y-%m-%d")] += 1
                hourly[dt.hour] += 1
            except ValueError:
                pass

        ref = item.get("referrer", "")
        if ref:
            # Extract domain from referrer
            try:
                from urllib.parse import urlparse
                domain = urlparse(ref).netloc or ref
                referrer_counts[domain] += 1
            except Exception:
                referrer_counts[ref] += 1
        else:
            referrer_counts["Direct"] += 1

        w = item.get("screen_width", 0)
        if w:
            w = int(w)
            if w <= 480:
                screen_sizes["Mobile (≤480)"] += 1
            elif w <= 1024:
                screen_sizes["Tablet (481-1024)"] += 1
            else:
                screen_sizes["Desktop (>1024)"] += 1

    # Sort daily visits by date
    sorted_daily = sorted(daily_visits.items())

    stats = {
        "total_visits": len(items),
        "unique_visitors": len(unique_visitors),
        "days": days,
        "daily_visits": [{"date": d, "count": c} for d, c in sorted_daily],
        "top_pages": [{"page": p, "count": c} for p, c in page_counts.most_common(10)],
        "referrers": [{"source": r, "count": c} for r, c in referrer_counts.most_common(10)],
        "screen_sizes": [{"category": k, "count": v} for k, v in screen_sizes.most_common()],
        "hourly": [{"hour": h, "count": hourly.get(h, 0)} for h in range(24)],
    }

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(stats),
    }
