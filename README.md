# MindTrace
131 Project on an edge-based facial emotion recognition system that tracks and visualizes emotional trends over time using cloud storage and analytics.


### API DOCUMENTATION
**Store emotion data**:

route: ```<url>/store```

request body format:
```
{
    "user" : <user whos data is being captured>,
    "emotion" : <emotion tag returned by model>,
    "timestamp": <time emotion was captured, formatted YYYY-MM-DDTHH:MM:SS>
}
```
this route should only be called by the edge device while recording emotion data

### Architecture (Nano + Fog)

- **Edge (Jetson Nano)** runs the model (`model/model.py` or `model/mock_edge_stream.py`): camera inference, WebSocket server for live emotion, and writes emotion data to the fog’s InfluxDB.
- **Fog (e.g. laptop)** runs InfluxDB and the mobile app (`mobile_edge/app.py`): survey UI, emotion display, survey → InfluxDB. The phone opens the app from the fog’s IP.

So the phone loads the app from the **fog** (e.g. `http://LAPTOP_IP:5001`). For live emotion, the in-page WebSocket must connect to the **Nano**. On the fog, set the Nano’s WebSocket URL in `.env`:

```bash
EDGE_WS_URL=ws://NANO_IP:8765
```

Replace `NANO_IP` with the Nano’s IP on your LAN (same Wi‑Fi). If `EDGE_WS_URL` is not set, the app assumes the WebSocket is on the same host as the page (e.g. when running mock + app on one machine).
