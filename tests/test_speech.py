import queue
import threading
import unittest
from unittest.mock import Mock

from day3.scripts.speech import Speech


class SpeechTests(unittest.TestCase):
    def make_speech(self):
        speech = Speech.__new__(Speech)
        speech.lock = threading.RLock()
        speech.generation = 0
        speech.active = 'running'
        speech.requests = queue.Queue()
        speech.worker = Mock()
        speech.worker.poll.return_value = None
        speech.send = Mock()
        return speech

    def test_stop_invalidates_waiting_requests_and_cancels_current(self):
        speech = self.make_speech()
        speech.receive({'type': 'speak', 'text': 'hello'})
        speech.receive({'type': 'stop'})
        self.assertNotEqual(speech.requests.get()[0], speech.generation)
        speech.send.assert_called_once_with({'type': 'cancel', 'id': 'running'})
        speech.receive({'type': 'speak', 'text': 'next', 'voice': 'ryan'})
        self.assertEqual(speech.requests.get(), (speech.generation, 'next', 'ryan'))

    def test_reject_old_numeric_voice_and_ignore_other_samples(self):
        speech = self.make_speech()
        with self.assertRaises(ValueError):
            speech.receive({'type': 'speak', 'text': 'hello', 'voice': 0})
        speech.receive({'type': 'lfm3_ask', 'text': 'hello'})
        self.assertTrue(speech.requests.empty())

    def test_dead_worker_does_not_claim_to_be_healthy(self):
        speech = self.make_speech()
        speech.closed = False
        speech.thread = Mock()
        speech.publish = Mock()
        speech.receive({'type': 'speech_ping', 'token': 'probe'})
        speech.publish.assert_called_once_with({'type': 'speech_pong', 'token': 'probe'})
        speech.publish.reset_mock()
        speech.worker.poll.return_value = 1
        speech.receive({'type': 'speech_ping', 'token': 'probe2'})
        speech.publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
