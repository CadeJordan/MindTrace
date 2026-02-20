from influxdb_client import InfluxDBClient, Point
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

url = "http://localhost:8086"
token = os.getenv("INFLUX_TOKEN")
org = "MindTrace"
bucket = "emotion_bucket"

# Needs to be changed later with acutal emotion map
EMOTION_MAP = {
    "happy": 1.0,
    "surprise": 0.5,
    "neutral": 0.0,
    "sad": -0.5,
    "fear": -0.7,
    "disgust": -0.8,
    "angry": -1.0
}

client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api()

def write_emotion(user: str, emotion: str, timestamp: datetime):

    if emotion not in EMOTION_MAP:
        print(f"Unknown emotion: {emotion}")
        return

    valence = EMOTION_MAP[emotion]

    point = (
        Point("emotion_data")
        .tag("user", user)
        .field("valence", valence)
        .field(emotion, 1.0)
        .time(timestamp)
    )

    write_api.write(bucket=bucket, org=org, record=point)

    print(f"[InfluxDB] {user} recorded {emotion} at {timestamp}")
