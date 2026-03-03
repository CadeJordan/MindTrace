import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from influxdb_client import InfluxDBClient, Point

from fog import config

STORE_ENDPOINT = "https://sucz9366w3.execute-api.us-west-1.amazonaws.com/store"
EMOTION_FIELDS = (
    "angry", "contempt", "disgust", "fear",
    "happy", "neutral", "sad", "surprise",
)


def _parse_ts(ts):
    """Parse InfluxDB _time (datetime or string) to ISO 8601."""
    if hasattr(ts, "isoformat"):
        dt = ts
    else:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def query_emotion_data(client, bucket, org, user_filter=None):
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "emotion_data")
    '''
    if user_filter:
        query += f'\n      |> filter(fn: (r) => r["user"] == "{user_filter}")'
    query += '''
      |> pivot(rowKey: ["_time", "user"], columnKey: ["_field"], valueColumn: "_value")
    '''
    query_api = client.query_api()
    tables = query_api.query(query=query, org=org)

    rows = []
    for table in tables:
        for record in table.records:
            r = record.values
            ts = r.get("_time")
            u = r.get("user", "")
            if ts is None:
                continue
            emotion = None
            for name in EMOTION_FIELDS:
                v = r.get(name)
                if v is not None and float(v) == 1.0:
                    emotion = name
                    break
            if emotion is None:
                continue
            rows.append({
                "timestamp": _parse_ts(ts),
                "emotion": emotion,
                "emotion_confidence": float(r.get("emotion_confidence") or 0.0),
                "valence": float(r.get("valence") or 0.0),
                "arousal": float(r.get("arousal") or 0.0),
                "_user": u,
            })
    rows.sort(key=lambda x: x["timestamp"])
    return rows


def query_survey_data(client, bucket, org, user_filter=None):
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "survey_response")
    '''
    if user_filter:
        query += f'\n      |> filter(fn: (r) => r["user"] == "{user_filter}")'
    query += '''
      |> pivot(rowKey: ["_time", "user"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 1)
    '''
    query_api = client.query_api()
    tables = query_api.query(query=query, org=org)

    for table in tables:
        for record in table.records:
            r = record.values
            mood = r.get("mood")
            engagement = r.get("engagement")
            energy = r.get("energy")
            if mood is None and engagement is None and energy is None:
                continue
            def norm(v):
                if v is None:
                    return None
                v = float(v)
                return v / 10.0 if v > 1 else v
            return {
                "mood": norm(mood),
                "engagement": norm(engagement),
                "energy": norm(energy),
            }
    return None


def build_payload(emotion_rows, survey, user="test", session_id="test"):
    if emotion_rows:
        user = emotion_rows[0].get("_user") or user
    data = []
    for row in emotion_rows:
        data.append({
            "timestamp": row["timestamp"],
            "emotion": row["emotion"],
            "emotion_confidence": row["emotion_confidence"],
            "valence": row["valence"],
            "arousal": row["arousal"],
        })
    payload = {
        "user": user,
        "session_id": session_id,
        "data": data,
        "survey": survey or {},
    }
    return payload


def post_to_store(payload, endpoint):
    resp = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_engagement_ts(ts_str):
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def write_response_to_influx(client, bucket, org, response_body, user, session_id, store_raw_json=True):
    write_api = client.write_api()
    try:
        ts_now = datetime.now(timezone.utc)
        point = (
            Point("store_emotion_response")
            .tag("user", str(user))
            .tag("session_id", str(session_id))
            .time(ts_now)
        )
        if store_raw_json:
            body_str = json.dumps(response_body) if isinstance(response_body, dict) else str(response_body)
            point = point.field("response_body", body_str)

        if isinstance(response_body, dict):
            if store_raw_json:
                if "message" in response_body:
                    point = point.field("message", str(response_body["message"]))
                if "s3_path" in response_body:
                    point = point.field("s3_path", str(response_body["s3_path"]))
            # Numeric summary fields (floats) — InfluxDB/Grafana can aggregate these
            summary = response_body.get("summary") or {}
            for key in ("average_engagement", "average_valence", "average_arousal"):
                v = _safe_float(summary.get(key))
                if v is not None:
                    point = point.field(key, v)
            survey_analysis = response_body.get("survey_analysis") or {}
            model_vs = (survey_analysis.get("model_vs_self_report") or {}) if isinstance(survey_analysis.get("model_vs_self_report"), dict) else {}
            for key in ("engagement_difference", "mood_difference", "energy_difference"):
                v = _safe_float(model_vs.get(key))
                if v is not None:
                    point = point.field(key, v)
        write_api.write(bucket=bucket, org=org, record=point)

        if isinstance(response_body, dict):
            series = response_body.get("engagement_series")
            if isinstance(series, list):
                count = 0
                for item in series:
                    if not isinstance(item, dict):
                        continue
                    ts_dt = _parse_engagement_ts(item.get("timestamp"))
                    eng = _safe_float(item.get("engagement"))
                    if ts_dt is not None and eng is not None:
                        p = (
                            Point("store_engagement_series")
                            .tag("user", str(user))
                            .tag("session_id", str(session_id))
                            .field("engagement", eng)
                            .time(ts_dt)
                        )
                        write_api.write(bucket=bucket, org=org, record=p)
                        count += 1
                if count:
                    print(f"[InfluxDB] Stored {count} engagement_series points for {user} / {session_id}")

        print(f"[InfluxDB] Stored store response for {user} / {session_id} at {ts_now}")
    finally:
        write_api.close()


def main():
    parser = argparse.ArgumentParser(
        description="Sync InfluxDB emotion + survey data to store endpoint and save response to InfluxDB.",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Filter InfluxDB data to this user (default: all users, first user used for payload)",
    )
    parser.add_argument(
        "--session-id",
        default="test",
        help="session_id sent in the payload (default: test)",
    )
    parser.add_argument(
        "--endpoint",
        default=STORE_ENDPOINT,
        help=f"Store API URL (default: {STORE_ENDPOINT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print payload and do not POST or write to InfluxDB",
    )
    parser.add_argument(
        "--no-raw-json",
        action="store_true",
        help="Do not store the full API response as a string; only write numeric and time-series data (avoids string fields in InfluxDB).",
    )
    args = parser.parse_args()

    if not config.token:
        print("Error: INFLUX_TOKEN not set. Set it in .env at repo root.", file=sys.stderr)
        return 2

    client = InfluxDBClient(url=config.url, token=config.token, org=config.org)

    try:
        emotion_rows = query_emotion_data(
            client, config.bucket, config.org, user_filter=args.user
        )
        survey = query_survey_data(
            client, config.bucket, config.org, user_filter=args.user
        )

        user = args.user or (emotion_rows[0]["_user"] if emotion_rows else "test")
        payload = build_payload(emotion_rows, survey, user=user, session_id=args.session_id)

        print("Payload (excerpt):", json.dumps(payload, indent=2)[:800], "...")
        if args.dry_run:
            print("[dry-run] Skipping POST and InfluxDB write.")
            return 0

        response_body = post_to_store(payload, args.endpoint)
        print("Response:", response_body)

        write_response_to_influx(
            client, config.bucket, config.org, response_body, user, args.session_id,
            store_raw_json=not args.no_raw_json,
        )
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
