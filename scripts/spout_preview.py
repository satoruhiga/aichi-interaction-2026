"""Standalone Spout preview; reusable receiver lives in common."""
import argparse
import sys
from pathlib import Path

# Also support direct execution: python scripts/spout_preview.py.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.spout_receiver import SpoutReceiver

def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main():
    parser = argparse.ArgumentParser(description="Receive a Spout sender and display it. Close the window or press Esc to stop.")
    parser.add_argument("--sender", default="TDSyphonSpoutOut", help="Spout sender name")
    parser.add_argument("--width", type=positive_int, default=640, help="Preview width")
    parser.add_argument("--height", type=positive_int, default=360, help="Preview height")
    parser.add_argument("--fps", type=positive_int, default=30)
    # Match last year's main.py, which passed FLIPPED=True to the receiver.
    parser.add_argument("--flip", action=argparse.BooleanOptionalAction, default=True,
                        help="Flip the received texture vertically (default: enabled; disable with --no-flip)")
    args = parser.parse_args()
    receiver = SpoutReceiver(args.sender, args.width, args.height, args.fps, show_window=True, flipped=args.flip)
    try:
        receiver.start()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
