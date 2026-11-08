import json
import threading
import unittest

from websockets.sync.server import serve

from common.json_sender import JsonSender


class SenderTest(unittest.TestCase):
    def test_bidirectional_and_callback_failure(self):
        received = threading.Event()
        callback = threading.Event()
        done = threading.Event()
        messages = []

        def handle(ws):
            messages.append(json.loads(ws.recv(timeout=3)))
            received.set()
            for value in ['invalid json', '[]', '{"type":"bad"}', '{"type":"good"}']:
                ws.send(value)
            done.wait(3)

        def on_message(message):
            if message['type'] == 'bad':
                raise ValueError('rejected test message')
            callback.set()

        with serve(handle, '127.0.0.1', 0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with JsonSender(port=server.socket.getsockname()[1], on_message=on_message) as sender:
                    sender.publish(dict(type='test', value=42))
                    self.assertTrue(received.wait(3))
                    self.assertTrue(callback.wait(3))
                    self.assertEqual(messages, [dict(type='test', value=42)])
                    done.set()
            finally:
                done.set()
                server.shutdown()
                thread.join(3)


if __name__ == '__main__':
    unittest.main()
