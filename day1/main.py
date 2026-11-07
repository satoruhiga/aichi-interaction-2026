"""Spout -> MediaPipe face landmarks -> WebSocket JSON."""
import argparse
import time

import mediapipe as mp

from common.json_sender import JsonSender
from common.models import ensure_model
from common.spout_receiver import SpoutReceiver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sender", default="TDSyphonSpoutOut")
    parser.add_argument("--port", type=int, default=8765, help="TouchDesigner Web Server DAT port")
    parser.add_argument("--faces", type=int, default=1)
    args = parser.parse_args()
    if args.faces < 1:
        parser.error("--faces must be at least 1")

    model = ensure_model(
        url='https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task',
        path='face_landmarker.task',
        sha256='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff',
    )
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_faces=args.faces,
    )
    receiver = SpoutReceiver(args.sender, 640, 360, 30, show_window=True, flipped=True)
    previous_ms = -1
    with JsonSender(port=args.port) as sender, mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        def process_frame(frame):
            nonlocal previous_ms
            timestamp_ms = max(time.monotonic_ns() // 1_000_000, previous_ms + 1)
            previous_ms = timestamp_ms
            result = detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=frame), timestamp_ms
            )
            # UV coordinates: bottom-left origin, without aspect correction.
            sender.publish({
                "type": "face_landmarks",
                "timestamp_ms": timestamp_ms,
                "image": {"width": frame.shape[1], "height": frame.shape[0]},
                "faces": [
                    {"landmarks": [
                        {"x": p.x, "y": 1.0 - p.y, "z": p.z}
                        for p in landmarks
                    ]}
                    for landmarks in result.face_landmarks
                ],
            })

        receiver.start(callback=process_frame)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
