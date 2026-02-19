import json
import boto3
import os
from datetime import datetime

s3 = boto3.client("s3")

BUCKET_NAME = "mind-trace-data"

def lambda_handler(event, context):
    try:
        if "body" not in event:
            return response(400, "Missing request body")

        body = event["body"]

        if isinstance(body, str):
            body = json.loads(body)

        user = body.get("user")
        emotion = body.get("emotion")
        timestamp = body.get("timestamp")

        if not user or not emotion or not timestamp:
            return response(400, "Missing required fields: user, emotion, timestamp")
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            return response(400, "Invalid timestamp format. Use ISO 8601.")

        s3_key = f"{user}/edgedata/{timestamp}.json"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(body),
            ContentType="application/json"
        )

        return response(200, {
            "message": "Data stored successfully",
            "s3_path": f"s3://{BUCKET_NAME}/{s3_key}"
        })

    except Exception as e:
        return response(500, f"Internal error: {str(e)}")


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }