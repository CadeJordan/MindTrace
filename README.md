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
