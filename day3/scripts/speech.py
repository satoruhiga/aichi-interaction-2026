"""Speech.cpp microphone recognition and streaming speech for TouchDesigner."""
import argparse
import base64
import json
from pathlib import Path
import platform
import queue
import subprocess
import threading
import time
import zipfile
import sounddevice as sd
from common.json_sender import JsonSender
from common.models import ensure_model, fetch, inside

ROOT = Path(__file__).resolve().parents[2]
VOICES = ['ono_anna', 'aiden', 'dylan', 'eric', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian']
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def prepare():
    releases = {
        ('Windows', 'AMD64'): ('windows-x64-vulkan', 'a8fe0e4b4f463c460e7ace9d38c363bec08b254cac5a7f764b7967af35d4fa1a'),
        ('Darwin', 'arm64'): ('macos-arm64-metal', 'ff24f6f58c9d2dedb01caa88ba043ae845c76eff228e4cbfae5de749174404c1'),
    }
    target, digest = releases[(platform.system(), platform.machine())]
    directory = ROOT / '.local' / ('speech-cpp-0.10.1-' + target)
    executable = directory / ('speech.exe' if platform.system() == 'Windows' else 'speech')
    marker = directory / '.sha256'
    if not executable.is_file() or not marker.is_file() or marker.read_text() != digest:
        archive = fetch(f'https://github.com/nyosegawa/speech.cpp/releases/download/v0.10.1/speech-0.10.1-{target}.zip', digest, directory, 'speech.cpp')
        try:
            with zipfile.ZipFile(archive) as source:
                for name in source.namelist():
                    inside(directory, name)
                source.extractall(directory)
            executable.chmod(0o755)
            marker.write_text(digest)
        finally:
            archive.unlink(missing_ok=True)
    specs = [
        ('Qwen3-TTS-12Hz-0.6B-CustomVoice-Q8_0.gguf', 'sakasegawa/Qwen3-TTS-12Hz-0.6B-CustomVoice-GGUF', 'fd9df9364613a92a86b4137074bc281204823033', 'f606ea3981aa42762b16db9a94826d2d560eb60f0b102001618f40d5a2f78cc6'),
        ('reazonspeech-nemo-619M-v2-Q8_0.gguf', 'sakasegawa/reazonspeech-nemo-v2-GGUF', 'ed04d9ee2cd156414982a7c0f6123c6fd1093904', '944411cb740938f858c939aa1d42f7eb4bb884fc350d9daae8b7e724853e54a3'),
        ('silero-vad-309K-v6.2-F32.gguf', 'sakasegawa/silero-vad-GGUF', '7fcb7aa2a70c312f8579fc987b3e1cdecf9321ca', '2fc312514e5fc4fa4ffd02b25c76a4853fa4130e8fb9777d01502183b01238cb'),
    ]
    models = [ensure_model(url=f'https://huggingface.co/{repo}/resolve/{rev}/{name}', path='speech-cpp/' + name, sha256=sha) for name, repo, rev, sha in specs]
    return executable, models


def terminate(process):
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=5)


class Listener:
    def __init__(self, executable, models, publish):
        self.command = [str(executable), 'asr', str(models[1]), '--vad', str(models[2]), '--live', '--format', 'json', '--device', 'cpu']
        self.publish = publish
        self.process = None

    def start(self):
        process = subprocess.Popen(self.command, stdout=subprocess.PIPE, text=True, encoding='utf-8', creationflags=FLAGS)
        self.process = process
        def read():
            try:
                for line in process.stdout:
                    message = json.loads(line)
                    if self.process is process and message.get('type') == 'conversation.item.input_audio_transcription.completed':
                        text = message.get('transcript', '').strip()
                        if text:
                            self.publish({'type': 'speech_text', 'text': text})
                if self.process is process:
                    self.publish({'type': 'speech_status', 'speaking': False, 'error': 'Microphone recognition exited; restart RUN_SPEECH.cmd'})
            except Exception as error:
                self.publish({'type': 'speech_status', 'speaking': False, 'error': str(error)})
        threading.Thread(target=read, daemon=True).start()

    def stop(self):
        process, self.process = self.process, None
        if process is not None:
            terminate(process)


class Speech:
    def __init__(self, executable, models, publish, output_device=None):
        self.publish = publish
        self.output_device = output_device
        self.listener = Listener(executable, models, publish)
        self.lock = threading.RLock()
        self.generation = 0
        self.active = None
        self.closed = False
        self.requests = queue.Queue()
        self.messages = queue.Queue()
        self.worker = subprocess.Popen([str(executable), 'worker', str(models[0]), '--device', 'gpu'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8', creationflags=FLAGS)
        def read():
            try:
                for line in self.worker.stdout:
                    message = json.loads(line)
                    message['_received_at'] = time.perf_counter()
                    self.messages.put(message)
            finally:
                self.messages.put({'type': 'fatal', 'error': 'speech.cpp worker exited'})
        threading.Thread(target=read, daemon=True).start()
        try:
            ready = self.messages.get(timeout=180)
            if ready.get('type') != 'ready' or ready.get('protocol') != 4:
                raise RuntimeError(ready)
            self.sample_rate = ready['model']['sample_rate']
            self.listener.start()
        except BaseException:
            terminate(self.worker)
            raise
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        self.status(False)

    def send(self, message):
        with self.lock:
            self.worker.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
            self.worker.stdin.flush()

    def status(self, speaking, **extra):
        self.publish({'type': 'speech_status', 'speaking': speaking, **extra})

    def receive(self, message):
        if message.get('type') == 'speech_ping':
            if not self.closed and self.worker.poll() is None and self.thread.is_alive():
                self.publish({'type': 'speech_pong', 'token': message.get('token')})
        elif message.get('type') == 'stop':
            self.stop()
        elif message.get('type') == 'speak':
            text, voice = message.get('text'), message.get('voice', 'ono_anna')
            if not isinstance(text, str) or not text.strip() or voice not in VOICES:
                raise ValueError('speak requires text and a named Qwen3 voice')
            with self.lock:
                self.requests.put((self.generation, text, voice))

    def stop(self):
        with self.lock:
            self.generation += 1
            if self.active is not None and self.worker.poll() is None:
                self.send({'type': 'cancel', 'id': self.active})

    def run(self):
        count = 0
        while True:
            request = self.requests.get()
            if request is None:
                return
            generation, text, voice = request
            with self.lock:
                if generation != self.generation:
                    continue
                count += 1
                self.active = str(count)
                self.listener.stop()
                self.status(True)
                started = time.perf_counter()
                self.send({'type': 'synthesize', 'id': self.active, 'text': text, 'voice': voice, 'language': 'ja'})
            timings = {}
            try:
                with sd.RawOutputStream(samplerate=self.sample_rate, channels=1, dtype='int16', device=self.output_device) as stream:
                    while True:
                        try:
                            message = self.messages.get(timeout=120)
                        except queue.Empty as error:
                            raise TimeoutError('speech.cpp returned no audio or result for 120 seconds') from error
                        kind = message['type']
                        if kind in ('error', 'fatal'):
                            raise RuntimeError(message.get('error'))
                        if kind in ('end', 'cancelled'):
                            timings['generation_ms'] = round((message['_received_at'] - started) * 1000, 1)
                            timings['cancelled'] = generation != self.generation or kind == 'cancelled'
                            break
                        if kind == 'chunk' and generation == self.generation:
                            timings.setdefault('first_audio_ms', round((message['_received_at'] - started) * 1000, 1))
                            stream.write(base64.b64decode(message['pcm'], validate=True))
                    if generation != self.generation:
                        stream.abort()
                timings['playback_complete_ms'] = round((time.perf_counter() - started) * 1000, 1)
                time.sleep(0.3)
            except Exception as error:
                self.status(False, error=str(error))
                # Fail closed: stale protocol messages must not enter the next request.
                self.closed = True
                terminate(self.worker)
                return
            finally:
                with self.lock:
                    self.active = None
                    if not self.closed:
                        self.listener.start()
                        self.status(False, **timings)

    def close(self):
        with self.lock:
            self.closed = True
            self.stop()
            self.listener.stop()
        self.requests.put(None)
        self.thread.join(timeout=5)
        terminate(self.worker)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--output-device', help='Speaker device number or name')
    parser.add_argument('--list-devices', action='store_true')
    args = parser.parse_args()
    if args.list_devices:
        print(sd.query_devices())
        return
    executable, models = prepare()
    speech = None
    def publish(message):
        message['timestamp_ms'] = time.time_ns() // 1_000_000
        sender.publish(message)
        if message['type'] != 'speech_pong':
            print(json.dumps(message, ensure_ascii=True), flush=True)
    def receive(message):
        if speech is not None:
            try:
                speech.receive(message)
            except (ValueError, OSError) as error:
                publish({'type': 'speech_status', 'speaking': speech.active is not None,
                         'error': str(error)})
    output = args.output_device
    if output is not None and output.isdigit():
        output = int(output)
    with JsonSender(port=args.port, on_message=receive) as sender:
        try:
            speech = Speech(executable, models, publish, output)
            while not speech.closed:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            if speech is not None:
                speech.close()


if __name__ == '__main__':
    main()
