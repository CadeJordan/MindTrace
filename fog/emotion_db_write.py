from datetime import datetime
from influxdb_client import InfluxDBClient, Point

from . import config

client = InfluxDBClient(url=config.url, token=config.token, org=config.org)
write_api = client.write_api()

# Writes emotion data to the fog from the nano
def write_emotion_from_payload(payload: dict) -> None:
    user = payload.get("user")
    emotion = payload.get("emotion")
    ts_str = payload.get("timestamp")
    confidence = payload.get("emotion_confidence")
    valence = payload.get("valence")
    arousal = payload.get("arousal")

    if not user or not emotion or not ts_str:
        raise ValueError("payload must include user, emotion, timestamp")

    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp must be ISO 8601")

    point = (
        Point("emotion_data")
        .tag("user", str(user))
        .field(emotion, 1.0)
        .field("valence", float(valence) if valence is not None else 0.0)
        .time(ts)
    )
    if arousal is not None:
        point = point.field("arousal", float(arousal))
    if confidence is not None:
        point = point.field("emotion_confidence", float(confidence))

    write_api.write(bucket=config.bucket, org=config.org, record=point)
    print(f"[InfluxDB] {user} recorded {emotion} at {ts}")


EMOTION_MAP = {
    "happy": 1.0, "surprise": 0.5, "neutral": 0.0, "sad": -0.5,
    "fear": -0.7, "disgust": -0.8, "angry": -1.0,
}

# Old write function to write emotion data to the fog from the nano
def write_emotion(user: str, emotion: str, timestamp: datetime) -> None:
    if emotion not in EMOTION_MAP:
        print(f"Unknown emotion: {emotion}")
        return
    write_emotion_from_payload({
        "user": user,
        "emotion": emotion,
        "timestamp": timestamp.isoformat(),
        "valence": EMOTION_MAP[emotion],
        "emotion_confidence": None,
        "arousal": None,
    })
