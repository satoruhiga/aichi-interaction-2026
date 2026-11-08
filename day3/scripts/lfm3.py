"""Ask LFM3-VL about a Spout/Syphon frame when TD sends lfm3_ask."""
import argparse
import base64
from contextlib import contextmanager
import json
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

import cv2

from common.json_sender import JsonSender
from common.models import ensure_model
from common.spout_receiver import SpoutReceiver


def prepare_models():
    model = ensure_model(
        url='https://huggingface.co/LiquidAI/LFM3-VL-2B-GGUF/resolve/1add221a5ea6c047fcf1eaaf2d247939d7cf8849/LFM3-VL-2B-Q4_K_M.gguf',
        path='lfm3/LFM3-VL-2B-Q4_K_M.gguf',
        sha256='56dac2e192ff0d9ab8507f4f1aeb4aed0463449bbbefaac79497f041c95f21eb',
    )
    projector = ensure_model(
        url='https://huggingface.co/LiquidAI/LFM3-VL-2B-GGUF/resolve/1add221a5ea6c047fcf1eaaf2d247939d7cf8849/mmproj-LFM3-VL-2B-Q8_0.gguf',
        path='lfm3/mmproj-LFM3-VL-2B-Q8_0.gguf',
        sha256='c5c5b58d544a18da919172d2d0368090ea1a4a351b6feb7f8a326a264a5918ab',
    )
    return model, projector


@contextmanager
def llama_server(model, projector, port):
    # Never adopt or stop another program that already owns this port.
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'Port {port} is already in use; choose --llama-port')
    log = Path(__file__).resolve().parents[2] / '.local' / 'lfm3-server.log'
    log.parent.mkdir(exist_ok=True)
    with log.open('w', encoding='utf-8') as output:
        process = subprocess.Popen([
            'llama-server', '-m', str(model), '--mmproj', str(projector),
            '--host', '127.0.0.1', '--port', str(port), '-c', '8192',
            '-np', '1', '-ngl', '99',
        ], stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'llama-server exited; see {log}')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.25)
            else:
                raise TimeoutError(f'llama-server did not become ready; see {log}')
            yield
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def ask(port, frame, question):
    ok, png = cv2.imencode('.png', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError('Could not encode the camera frame')
    image_url = 'data:image/png;base64,' + base64.b64encode(png).decode()
    body = dict(messages=[dict(role='user', content=[
        dict(type='image_url', image_url=dict(url=image_url)),
        dict(type='text', text=question),
    ])], temperature=0.1, max_tokens=512,
        chat_template_kwargs=dict(enable_thinking=False))
    request = Request(f'http://127.0.0.1:{port}/v1/chat/completions',
                      json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urlopen(request, timeout=120) as response:
        return json.load(response)['choices'][0]['message']['content'].strip()


class Questions:
    def __init__(self, sender, port):
        self.sender = sender
        self.port = port
        self.frame = None
        self.received = 0
        self.lock = threading.Lock()
        self.busy = False
        self.jobs = queue.Queue()
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.thread.start()

    def receive_frame(self, frame):
        with self.lock:
            self.frame = frame.copy()
            self.received = time.monotonic()

    def status(self, state, **values):
        self.sender.publish(dict(type='lfm3_status', state=state, **values))

    def on_message(self, message):
        if message.get('type') == 'lfm3_ping':
            self.sender.publish(dict(type='lfm3_pong', token=message.get('token')))
            return
        if message.get('type') != 'lfm3_ask':
            return
        question = message.get('text')
        if not isinstance(question, str) or not question.strip():
            self.status('error', error='質問の text を指定してください')
            return
        with self.lock:
            if self.busy:
                return  # One visible question at a time; do not accumulate clicks.
            if self.frame is None or time.monotonic() - self.received > 2:
                self.status('error', error='映像が届いていません。TD の映像送信を確認してください')
                return
            self.busy = True
            self.jobs.put((self.frame.copy(), question.strip()))
        self.status('thinking')

    def work(self):
        while True:
            job = self.jobs.get()
            if job is None:
                return
            frame, question = job
            started = time.perf_counter()
            try:
                text = ask(self.port, frame, question)
                generation_ms = round((time.perf_counter() - started) * 1000, 1)
                self.sender.publish(dict(type='lfm3_text', text=text, question=question,
                                         timestamp_ms=time.time_ns() // 1_000_000,
                                         generation_ms=generation_ms))
                self.status('ready', generation_ms=generation_ms)
                print(text, flush=True)
            except Exception as error:
                self.status('error', error=str(error))
            finally:
                with self.lock:
                    self.busy = False

    def close(self):
        self.jobs.put(None)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sender', default='TDSyphonSpoutOut')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--llama-port', type=int, default=8093)
    parser.add_argument('--hidden', action='store_true')
    args = parser.parse_args()
    model, projector = prepare_models()
    receiver = SpoutReceiver(args.sender, 640, 360, 30,
                             show_window=not args.hidden, flipped=True)
    with llama_server(model, projector, args.llama_port):
        questions = None
        def receive(message):
            if questions is not None:
                questions.on_message(message)
        with JsonSender(port=args.port, on_message=receive) as sender:
            questions = Questions(sender, args.llama_port)
            sender.publish(dict(type='lfm3_text', text='', question=''))
            questions.status('ready')
            try:
                receiver.start(callback=questions.receive_frame)
            finally:
                questions.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
