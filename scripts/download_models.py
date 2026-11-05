"""Download required models into workspace/models using the standard library."""
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen

# Official MediaPipe distribution; the hash pins the content if latest changes.
MODELS = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    ),
    "pose_landmarker_full.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
        "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
    ),
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
}
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download_model(destination, url, expected_hash):
    if destination.exists() and sha256(destination) == expected_hash:
        print(f"Already available: {destination.name}", flush=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as target:
            temporary = Path(target.name)
            print(f"Downloading: {destination.name}", flush=True)
            with urlopen(url, timeout=60) as response:
                shutil.copyfileobj(response, target)
        if sha256(temporary) != expected_hash:
            raise RuntimeError(f"SHA256 mismatch: {destination.name}; existing file was not replaced")
        temporary.replace(destination)
        print(f"Ready: {destination.name}", flush=True)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    for name, (url, expected_hash) in MODELS.items():
        download_model(MODEL_DIR / name, url, expected_hash)


if __name__ == "__main__":
    main()
