import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, request, render_template, url_for, redirect

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from fog.survey_db_write import write_survey_response

app = Flask(__name__, template_folder=Path(__file__).resolve().parent)

_last_emotion_from_edge = {}

# Gets emotion from the nano to display on the home page
def _current_emotion(user_id: str):
    return _last_emotion_from_edge.get(user_id)

# Displays the home page
@app.route("/")
def index():
    user_id = (request.args.get("user") or "").strip()
    if not user_id:
        return render_template("home.html")
    emotion = _current_emotion(user_id)
    return render_template("home.html", user_id=user_id, emotion=emotion)

# Gets emotion from the nano to display on the home page
@app.route("/emotion", methods=["POST"])
def ingest_emotion():
    data = request.get_json(silent=True) or {}
    user = data.get("user")
    if user is not None:
        _last_emotion_from_edge[str(user)] = data.get("emotion")
    return {"ok": True}, 200

# Displays the survey page
@app.route("/survey")
def survey():
    user_id = request.args.get("user", "")
    return render_template("survey.html", user_id=user_id)

# Submits the survey to the fog
@app.route("/submit", methods=["POST"])
def submit_survey():
    user_id = (request.form.get("user_id") or "").strip()
    if not user_id:
        return render_template(
            "survey.html",
            user_id=request.args.get("user", ""),
            message="User ID is required.",
            success=False,
        ), 400

    mood = request.form.get("mood")
    engagement = request.form.get("engagement")
    energy = request.form.get("energy")

    responses = {
        "mood": int(mood) if mood else None,
        "engagement": int(engagement) if engagement else None,
        "energy": int(energy) if energy else None,
    }
    responses = {k: v for k, v in responses.items() if v is not None}

    if not responses:
        return render_template(
            "survey.html",
            user_id=user_id,
            message="At least one survey response is required.",
            success=False,
        ), 400

    try:
        write_survey_response(user_id, responses, timestamp=datetime.utcnow())
    except Exception as e:
        return render_template(
            "survey.html",
            user_id=user_id,
            message=f"Failed to write to InfluxDB: {e}",
            success=False,
        ), 500

    return redirect(url_for("index", user=user_id))


def _local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    port = 5001
    ip = _local_ip()
    print(f"\n  Survey on this machine:  http://127.0.0.1:{port}")
    print(f"  Survey on your phone:    http://{ip}:{port}")
    print("  (Phone must be on the same Wi‑Fi as this PC)\n")
    app.run(host="0.0.0.0", port=port, debug=True)
