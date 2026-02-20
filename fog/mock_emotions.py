import sys
import time
import random
from pathlib import Path
from datetime import datetime

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from fog.emotion_db_write import write_emotion

EMOTIONS = [
    "happy",
    "surprise",
    "neutral",
    "sad",
    "fear",
    "disgust",
    "angry"
]

USER = "demo_user"

while True:
    emotion = random.choice(EMOTIONS)
    timestamp = datetime.utcnow()

    write_emotion(USER, emotion, timestamp)

    time.sleep(5)
