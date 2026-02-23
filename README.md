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
this route should be called at the end of a presentation when all data is collected, it returns a result json with parts that can be visualized on grafana and some other insights
