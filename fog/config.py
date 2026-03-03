from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

url = os.getenv("INFLUX_URL", "http://localhost:8086")
token = os.getenv("INFLUX_TOKEN")
org = "MindTrace"
bucket = "emotion_bucket"

edge_ws_url = os.getenv("EDGE_WS_URL", "").strip() or None
