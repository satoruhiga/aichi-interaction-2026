import threading
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from day3.scripts.lfm3 import Questions


class QuestionsTest(unittest.TestCase):
    def test_request_requires_frame_and_does_not_queue_busy_clicks(self):
        sender = Mock()
        entered, release = threading.Event(), threading.Event()

        def answer(port, frame, question):
            entered.set()
            release.wait(2)
            return 'answer'

        with patch('day3.scripts.lfm3.ask', side_effect=answer) as ask:
            questions = Questions(sender, 8093)
            try:
                questions.on_message(dict(type='speak', text='ignored'))
                sender.publish.assert_not_called()
                questions.on_message(dict(type='lfm3_ask', text='question'))
                self.assertEqual(sender.publish.call_args.args[0]['state'], 'error')
                questions.receive_frame(np.zeros((2, 2, 3), dtype=np.uint8))
                questions.on_message(dict(type='lfm3_ask', text='question'))
                self.assertTrue(entered.wait(2))
                questions.on_message(dict(type='lfm3_ask', text='duplicate'))
                self.assertTrue(questions.jobs.empty())
                release.set()
                deadline = time.monotonic() + 2
                while questions.busy and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(questions.busy)
                self.assertEqual(ask.call_count, 1)
                self.assertTrue(any(c.args[0].get('text') == 'answer'
                                    for c in sender.publish.call_args_list))
                result = next(c.args[0] for c in sender.publish.call_args_list
                              if c.args[0].get('text') == 'answer')
                self.assertGreaterEqual(result['generation_ms'], 0)
                questions.on_message(dict(type='lfm3_ping', token='probe'))
                self.assertEqual(sender.publish.call_args.args[0],
                                 dict(type='lfm3_pong', token='probe'))
            finally:
                release.set()
                questions.close()
                questions.thread.join(3)


if __name__ == '__main__':
    unittest.main()
