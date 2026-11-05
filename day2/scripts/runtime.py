"""Shared camera transport and timing for the three independent examples."""
import argparse
from pathlib import Path
import time

import mediapipe as mp
from common.json_sender import JsonSender
from common.spout_receiver import SpoutReceiver

MODELS = Path(__file__).resolve().parents[2] / 'models'


def arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--sender', default='TDSyphonSpoutOut')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--seconds', type=float, default=0)
    parser.add_argument('--hidden', action='store_true')
    return parser.parse_args()


def landmarks(points, visibility=False):
    return [dict(x=p.x, y=1-p.y, z=p.z,
                 **({'visibility': p.visibility, 'presence': p.presence} if visibility else {}))
            for p in points]


def run(args, detector, kind, serialize):
    receiver = SpoutReceiver(args.sender, 640, 360, 30, show_window=not args.hidden, flipped=True)
    previous_ms = -1
    started = time.monotonic()
    with JsonSender(port=args.port) as sender, detector:
        def process(frame):
            nonlocal previous_ms
            timestamp_ms = max(time.monotonic_ns() // 1_000_000, previous_ms + 1)
            previous_ms = timestamp_ms
            result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=frame), timestamp_ms)
            sender.publish(dict(type=kind, timestamp_ms=timestamp_ms,
                                image=dict(width=frame.shape[1], height=frame.shape[0]),
                                **serialize(result)))
            if args.seconds and time.monotonic() - started >= args.seconds:
                return False
        receiver.start(callback=process)
