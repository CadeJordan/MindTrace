import argparse
import os
import sys
import time
import random

from datetime import datetime, timezone

# Ensure repo root is on path so we can import edge_stream and fog.*
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import edge_stream


EMOTIONS = [
    "angry", "contempt", "disgust", "fear",
    "happy", "neutral", "sad", "surprise",
]


def _make_dominant(emotion: str) -> dict:
    """Build a fake 'dominant' dict like model.py would."""
    return {
        "emotion": emotion,
        "emotion_confidence": random.uniform(0.6, 1.0),
        "valence": random.uniform(-1.0, 1.0),
        "arousal": random.uniform(-1.0, 1.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mock edge stream without camera (test fog + WebSocket)."
    )
    parser.add_argument("--user", type=str, default="mock_user",
                        help="User/session ID to tag in InfluxDB and WebSocket messages.")
    parser.add_argument("--fog", action="store_true",
                        help="Write mock emotions into the fog (InfluxDB).")
    parser.add_argument("--ws", action="store_true",
                        help="Broadcast mock emotions over WebSocket to the phone browser.")
    parser.add_argument("--ws-port", type=int, default=8765,
                        help="WebSocket port (default: 8765).")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds between mock emotion updates (default: 2.0).")
    args = parser.parse_args()

    if not args.fog and not args.ws:
        print("Nothing to do: enable at least one of --fog or --ws.")
        return 1

    if args.ws:
        edge_stream.start_ws_server("0.0.0.0", int(args.ws_port))

    print(f"[MOCK] Starting mock edge stream for user '{args.user}'")
    print(f"       Fog writes: {'ON' if args.fog else 'OFF'}")
    print(f"       WebSocket:  {'ON' if args.ws else 'OFF'} (port {args.ws_port})")

    try:
        while True:
            emotion = random.choice(EMOTIONS)
            dominant = _make_dominant(emotion)

            payload = edge_stream.build_payload(args.user, dominant)

            if args.fog:
                edge_stream.send_to_fog(payload)

            if args.ws:
                edge_stream.ws_broadcast(payload)

            ts = datetime.now(timezone.utc).isoformat()
            print(f"[MOCK {ts}] {args.user} -> {emotion} ({dominant['emotion_confidence']:.0%})")

            time.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        print("\n[MOCK] Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

