"""Download required models into workspace/models using the standard library."""
import hashlib
from pathlib import Path
import shutil
import tarfile
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
    # ReazonSpeech k2 v2 (Apache-2.0); pinned to a Hugging Face revision.
    "reazonspeech-k2-v2/encoder-epoch-99-avg-1.int8.onnx": (
        "https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/291488c8151be24d7da4bf7af26e533fad96e407/encoder-epoch-99-avg-1.int8.onnx",
        "2c7bd08a8a99f9ddd0d9e458456577b1f6279214e51426f114f9eced44c54e1d",
    ),
    "reazonspeech-k2-v2/decoder-epoch-99-avg-1.int8.onnx": (
        "https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/291488c8151be24d7da4bf7af26e533fad96e407/decoder-epoch-99-avg-1.int8.onnx",
        "8f0bff94d38797b03b762634ed03211a8e303d06cc4603cdd0cf4199d6eb1485",
    ),
    "reazonspeech-k2-v2/joiner-epoch-99-avg-1.int8.onnx": (
        "https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/291488c8151be24d7da4bf7af26e533fad96e407/joiner-epoch-99-avg-1.int8.onnx",
        "49cc7ea1d3d35a40a27442db5e89996da64bf0e683a903dce76e99e57a12e4de",
    ),
    "reazonspeech-k2-v2/tokens.txt": (
        "https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/291488c8151be24d7da4bf7af26e533fad96e407/tokens.txt",
        "2c3ac659818a48a0c04010e0593bbc4d7c8a24a054340b01131499c05fd52def",
    ),
    # Silero VAD as distributed by sherpa-onnx (MIT).
    "silero_vad.onnx": (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
        "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
    ),
}
# Archives are extracted to models/<name>; each must contain a top-level <name> folder.
ARCHIVES = {
    # Supertonic 3 TTS for sherpa-onnx (model: OpenRAIL-M, code: MIT).
    "sherpa-onnx-supertonic-3-tts-int8-2026-05-11": (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2",
        "82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427",
    ),
}
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
# Written into an extracted archive folder to record which archive it came from.
ARCHIVE_MARKER = ".archive-sha256"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def fetch(url, expected_hash, directory, label):
    """Download to a temporary file in directory and verify it; the caller deletes the file."""
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as target:
        temporary = Path(target.name)
        try:
            print(f"Downloading: {label}", flush=True)
            with urlopen(url, timeout=60) as response:
                shutil.copyfileobj(response, target)
        except BaseException:
            target.close()
            temporary.unlink(missing_ok=True)
            raise
    if sha256(temporary) != expected_hash:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"SHA256 mismatch: {label}; existing files were not replaced")
    return temporary


def download_model(destination, url, expected_hash):
    if destination.exists() and sha256(destination) == expected_hash:
        print(f"Already available: {destination.name}", flush=True)
        return
    temporary = fetch(url, expected_hash, destination.parent, destination.name)
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Ready: {destination.name}", flush=True)


def download_archive(name, url, expected_hash):
    destination = MODEL_DIR / name
    marker = destination / ARCHIVE_MARKER
    if marker.exists() and marker.read_text().strip() == expected_hash:
        print(f"Already available: {name}", flush=True)
        return
    archive = fetch(url, expected_hash, MODEL_DIR, name)
    try:
        with tempfile.TemporaryDirectory(dir=MODEL_DIR) as staging:
            with tarfile.open(archive) as source:
                source.extractall(staging, filter="data")
            extracted = Path(staging) / name
            if not extracted.is_dir():
                raise RuntimeError(f"Archive does not contain the folder {name}")
            (extracted / ARCHIVE_MARKER).write_text(expected_hash + "\n")
            if destination.exists():
                shutil.rmtree(destination)
            extracted.replace(destination)
    finally:
        archive.unlink(missing_ok=True)
    print(f"Ready: {name}", flush=True)


def main():
    for name, (url, expected_hash) in MODELS.items():
        download_model(MODEL_DIR / name, url, expected_hash)
    for name, (url, expected_hash) in ARCHIVES.items():
        download_archive(name, url, expected_hash)


if __name__ == "__main__":
    main()
