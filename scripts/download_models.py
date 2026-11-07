"""Download a specified model in advance (samples also download on startup)."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.models import ensure_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--path', required=True, help='Path relative to models/')
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--required-files', nargs='+', help='Required paths inside a tar archive')
    args = parser.parse_args()
    print(ensure_model(**vars(args)))


if __name__ == '__main__':
    main()
