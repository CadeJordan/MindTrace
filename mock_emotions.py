# mock_emotion_stream.py

import time
import random
from datetime import datetime
from emotion_db_write import write_emotion

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
