import asyncio
import json
import threading
import time
from datetime import datetime, timezone

_WS_LOOP = None
_WS_CLIENTS = set()
_WS_CLIENTS_LOCK = threading.Lock()


def build_payload(user_id: str, dominant: dict) -> dict:
    return {
        "user": user_id,
        "emotion": dominant.get("emotion"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "emotion_confidence": dominant.get("emotion_confidence"),
        "valence": dominant.get("valence"),
        "arousal": dominant.get("arousal"),
    }


def _local_ip() -> str:
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


def start_ws_server(host: str, port: int) -> None:
    global _WS_LOOP
    if _WS_LOOP is not None:
        return

    def _run():
        try:
            import websockets 
        except Exception as e:
            print(f"Cannot import websockets ({e}). Install: pip install websockets")
            return

        async def _handler(ws):
            with _WS_CLIENTS_LOCK:
                _WS_CLIENTS.add(ws)
            try:
                await ws.wait_closed()
            finally:
                with _WS_CLIENTS_LOCK:
                    _WS_CLIENTS.discard(ws)

        async def _main():
            global _WS_LOOP
            loop = asyncio.get_running_loop()
            _WS_LOOP = loop
            try:
                server = await websockets.serve(_handler, host, port)
            except Exception as e:
                print(f"WS Failed to bind {host}:{port} ({e})")
                return

            ip = _local_ip()
            print(f"Listening on ws://{host}:{port}")
            print(f"Phone/Web browser: ws://{ip}:{port}")
            try:
                await asyncio.Future()
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(_main())

    t = threading.Thread(target=_run, daemon=True, name="ws-server")
    t.start()


def ws_broadcast(payload: dict) -> None:
    if _WS_LOOP is None:
        return

    msg = json.dumps(payload)

    async def _send_all():
        with _WS_CLIENTS_LOCK:
            clients = list(_WS_CLIENTS)
        dead = []
        for ws in clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.append(ws)
        if dead:
            with _WS_CLIENTS_LOCK:
                for ws in dead:
                    _WS_CLIENTS.discard(ws)

    try:
        asyncio.run_coroutine_threadsafe(_send_all(), _WS_LOOP)
    except Exception:
        return


def send_to_fog(payload: dict) -> bool:
    try:
        from fog.emotion_db_write import write_emotion_from_payload

        write_emotion_from_payload(payload)
        return True
    except Exception as e:
        print(f"fog error: {e}", end="", flush=True)
        return False

