"""Publish the latest state per type to a TouchDesigner WebSocket server."""
import json
import threading

from websockets.sync.client import connect
from websockets.exceptions import WebSocketException


class JsonSender:
    def __init__(self, host="127.0.0.1", port=8765):
        self.url = f"ws://{host}:{port}"
        self._latest = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def publish(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("type"), str) or not data["type"]:
            raise ValueError('Expected a JSON object with a non-empty string "type"')
        message = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with self._lock:
            self._latest[data["type"]] = message

    def _run(self):
        while not self._stop.is_set():
            try:
                with connect(self.url, open_timeout=2, close_timeout=1,
                             proxy=None, compression=None) as websocket:
                    print(f"WebSocket connected: {self.url}", flush=True)
                    previous = {}
                    while not self._stop.is_set():
                        with self._lock:
                            messages = self._latest.copy()
                        for kind, message in messages.items():
                            if previous.get(kind) is not message:
                                websocket.send(message)
                                previous[kind] = message
                        self._stop.wait(1 / 30)
            except (OSError, WebSocketException, TimeoutError) as error:
                if not self._stop.is_set():
                    print(f"WebSocket waiting: {error}", flush=True)
                    self._stop.wait(1)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
