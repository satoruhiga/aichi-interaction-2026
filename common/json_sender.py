"""Publish the latest JSON result to local WebSocket clients."""
import asyncio
from concurrent.futures import Future
import json
import threading

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class JsonSender:
    def __init__(self, host="127.0.0.1", port=8765):
        self.host, self.port = host, port
        self._latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = Future()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def publish(self, data):
        message = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with self._lock:
            self._latest = message

    async def _client(self, websocket):
        print("WebSocket client connected", flush=True)
        previous = None
        try:
            while not self._stop.is_set():
                with self._lock:
                    message = self._latest
                if message is not None and message is not previous:
                    # Keep only the latest unsent result; disconnect stalled clients.
                    await asyncio.wait_for(websocket.send(message), timeout=2)
                    previous = message
                await asyncio.sleep(1 / 30)
        except (ConnectionClosed, TimeoutError):
            pass

    async def _serve(self):
        async with serve(self._client, self.host, self.port, compression=None, close_timeout=1):
            self._ready.set_result(None)
            while not self._stop.is_set():
                await asyncio.sleep(0.05)

    def _run(self):
        try:
            asyncio.run(self._serve())
        except Exception as error:
            if not self._ready.done():
                self._ready.set_exception(error)
            else:
                print(f"WebSocket server failed: {error}", flush=True)

    def __enter__(self):
        self._thread.start()
        self._ready.result(timeout=10)
        print(f"WebSocket server: ws://{self.host}:{self.port}", flush=True)
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
