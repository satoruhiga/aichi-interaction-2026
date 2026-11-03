"""Spout -> MediaPipe face landmarks -> WebSocket JSON."""
import argparse
from pathlib import Path
import time

import mediapipe as mp

from common.json_sender import JsonSender
from common.spout_receiver import SpoutReceiver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sender", default="TDSyphonSpoutOut")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--faces", type=int, default=1)
    args = parser.parse_args()
    if args.faces < 1:
        parser.error("--faces must be at least 1")

    model = Path(__file__).resolve().parents[1] / "models" / "face_landmarker.task"
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
