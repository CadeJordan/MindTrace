# MindTrace
131 Project on an edge-based facial emotion recognition system that tracks and visualizes emotional trends over time using cloud storage and analytics.


### API DOCUMENTATION
**Store emotion data**:
```<route>/store```
example request body format:
```
{
  "user": "test",
  "session_id": "test",
  "data": [
    {
      "timestamp": "2026-02-18T15:23:10Z",
      "emotion": "happy",
      "emotion_confidence": 0.91,
      "valence": 0.72,
      "arousal": 0.63
    }
  ],
  "survey": {
    "mood": 0.8,
    "engagement": 0.7,
    "energy": 0.9
  }
}
```
this route should only be called at the end of the presentation by the fog.

### Architecture (Nano + Fog)

- **Edge (Jetson Nano)** runs the model (`model/model.py` or `model/mock_edge_stream.py`): camera inference, WebSocket server for live emotion, and writes emotion data to the fog’s InfluxDB.
- **Fog (e.g. laptop)** runs InfluxDB and the mobile app (`mobile_edge/app.py`): survey UI, emotion display, survey → InfluxDB. The phone opens the app from the fog’s IP.

So the phone loads the app from the **fog** (e.g. `http://LAPTOP_IP:5001`). For live emotion, the in-page WebSocket must connect to the **Nano**. On the fog, set the Nano’s WebSocket URL in `.env`:

```bash
EDGE_WS_URL=ws://NANO_IP:8765
```

Replace `NANO_IP` with the Nano’s IP on your LAN (same Wi‑Fi). If `EDGE_WS_URL` is not set, the app assumes the WebSocket is on the same host as the page (e.g. when running mock + app on one machine).
