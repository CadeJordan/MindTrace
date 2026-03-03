import json
import boto3
from datetime import datetime
from statistics import mean

s3 = boto3.client("s3")

BUCKET_NAME = "mind-trace-data"


def compute_engagement(valence, arousal):
    return 0.6 * arousal + 0.4 * abs(valence)


def summarize_session(user, session_id, data_points, survey):
    """Build engagement_series, summary stats, and survey comparison from data points."""
    engagement_series = []
    engagements = []
    valences = []
    arousals = []

    for point in data_points:
        ts = point["timestamp"]
        valence = float(point.get("valence", 0))
        arousal = float(point.get("arousal", 0))
        engagement = compute_engagement(valence, arousal)

        engagement_series.append({
            "timestamp": ts,
            "engagement": round(engagement, 4),
        })
        engagements.append(engagement)
        valences.append(valence)
        arousals.append(arousal)

    avg_engagement = mean(engagements)
    avg_valence = mean(valences)
    avg_arousal = mean(arousals)
    max_engagement = max(engagements)
    min_engagement = min(engagements)
    max_index = engagements.index(max_engagement)
    min_index = engagements.index(min_engagement)
    most_engaged_timestamp = engagement_series[max_index]["timestamp"]
    least_engaged_timestamp = engagement_series[min_index]["timestamp"]

    survey_comparison = {}
    if survey:
        survey_comparison = {
            "model_vs_self_report": {
                "engagement_difference": round(avg_engagement - survey.get("engagement", 0), 4),
                "mood_difference": round(avg_valence - survey.get("mood", 0), 4),
                "energy_difference": round(avg_arousal - survey.get("energy", 0), 4),
            }
        }

    return {
        "user": user,
        "session_id": session_id,
        "engagement_series": engagement_series,
        "summary": {
            "average_engagement": round(avg_engagement, 4),
            "average_valence": round(avg_valence, 4),
            "average_arousal": round(avg_arousal, 4),
            "most_engaged_timestamp": most_engaged_timestamp,
            "least_engaged_timestamp": least_engaged_timestamp,
        },
        "survey_analysis": survey_comparison,
    }


def lambda_handler(event, context):
    try:
        if "body" not in event:
            return response(400, "Missing request body")

        body = event["body"]

        if isinstance(body, str):
            body = json.loads(body)

        user = body.get("user")
        data = body.get("data")
        session_id = body.get("session_id", "")

        # Batch format: user, session_id, data[], survey — run summarization and store result
        if data is not None and isinstance(data, list):
            if not user:
                return response(400, "Missing required field: user")
            if not data:
                return response(400, "No data points provided")
            try:
                for item in data:
                    ts = item.get("timestamp")
                    if ts:
                        datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return response(400, "Invalid timestamp in data. Use ISO 8601.")

            survey = body.get("survey", {})
            result = summarize_session(user, session_id or "unknown", data, survey)

            s3_key = f"{user}/edgedata/{session_id or 'default'}.json"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(result),
                ContentType="application/json",
            )
            return response(200, result)

        # Single-emotion format: user, emotion, timestamp
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