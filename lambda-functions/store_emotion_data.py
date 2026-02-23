
import boto3
import json
from datetime import datetime
from statistics import mean


s3 = boto3.client("s3")

BUCKET_NAME = "mind-trace-data"


def compute_engagement(valence, arousal):
    return 0.6 * arousal + 0.4 * abs(valence)

def lambda_handler(event, context):
    body = json.loads(event["body"])
    user = body["user"]
    session_id = body.get("session_id", "unknown")
    data_points = body["data"]
    survey = body.get("survey", {})

    if not data_points:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No data points provided"})
        }

    engagement_series = []
    engagements = []
    valences = []
    arousals = []

    for point in data_points:
        ts = point["timestamp"]
        valence = float(point["valence"])
        arousal = float(point["arousal"])

        engagement = compute_engagement(valence, arousal)

        engagement_series.append({
            "timestamp": ts,
            "engagement": round(engagement, 4)
        })

        engagements.append(engagement)
        valences.append(valence)
        arousals.append(arousal)

    # Session statistics
    avg_engagement = mean(engagements)
    avg_valence = mean(valences)
    avg_arousal = mean(arousals)

    max_engagement = max(engagements)
    min_engagement = min(engagements)

    max_index = engagements.index(max_engagement)
    min_index = engagements.index(min_engagement)

    most_engaged_timestamp = engagement_series[max_index]["timestamp"]
    least_engaged_timestamp = engagement_series[min_index]["timestamp"]

    # Survey comparison
    survey_comparison = {}
    if survey:
        survey_comparison = {
            "model_vs_self_report": {
                "engagement_difference": round(avg_engagement - survey.get("engagement", 0), 4),
                "mood_difference": round(avg_valence - survey.get("mood", 0), 4),
                "energy_difference": round(avg_arousal - survey.get("energy", 0), 4),
            }
        }

    result = {
        "user": user,
        "session_id": session_id,
        "engagement_series": engagement_series,
        "summary": {
            "average_engagement": round(avg_engagement, 4),
            "average_valence": round(avg_valence, 4),
            "average_arousal": round(avg_arousal, 4),
            "most_engaged_timestamp": most_engaged_timestamp,
            "least_engaged_timestamp": least_engaged_timestamp
        },
        "survey_analysis": survey_comparison
    }
    s3_key = f"{user}/edgedata/{session_id}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(result),
        ContentType="application/json"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }