from datetime import datetime
from influxdb_client import InfluxDBClient, Point

from . import config

client = InfluxDBClient(url=config.url, token=config.token, org=config.org)
write_api = client.write_api()


def write_survey_response(
    user_id: str,
    responses: dict,
    timestamp: datetime | None = None,
) -> None:
    ts = timestamp or datetime.utcnow()
    point = Point("survey_response").tag("user", user_id).time(ts)

    for key, value in responses.items():
        if value is None or value == "":
            continue
        if isinstance(value, (int, float)):
            point = point.field(key, value)
        else:
            point = point.field(key, str(value))

    if not responses or all(v is None or v == "" for v in responses.values()):
        raise ValueError("At least one non-empty response field is required")

    write_api.write(bucket=config.bucket, org=config.org, record=point)
    print(f"[InfluxDB] Survey from {user_id} recorded at {ts}")
