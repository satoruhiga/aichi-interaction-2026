"""Download and verify model files requested by a sample."""
import hashlib
from pathlib import Path
import shutil
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
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


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f"Model path must stay inside {root}: {relative}")
    return path


def download_archive(destination, spec, required):
    marker = destination / ARCHIVE_MARKER
    if (marker.is_file() and marker.read_text().strip() == spec['sha256']
            and all(inside(destination, name).is_file() for name in required)):
        return
    archive = fetch(spec['url'], spec['sha256'], MODEL_DIR, destination.name)
    try:
        with tempfile.TemporaryDirectory(dir=MODEL_DIR) as staging:
            with tarfile.open(archive) as source:
                for member in source.getmembers():
                    inside(Path(staging), member.name)
                    if not (member.isfile() or member.isdir()):
                        raise ValueError(f"Unsupported archive member: {member.name}")
                source.extractall(staging, filter='data')
            extracted = Path(staging) / destination.name
            if not required or not all(inside(extracted, name).is_file() for name in required):
                raise RuntimeError(f"Archive is missing required files: {destination.name}")
            # Only mark complete after every extracted file has been installed.
            destination.mkdir(parents=True, exist_ok=True)
            marker.unlink(missing_ok=True)
            for item in extracted.rglob('*'):
                target = inside(destination, item.relative_to(extracted))
                if item.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    item.replace(target)
            marker.write_text(spec['sha256'] + '\n')
    finally:
        archive.unlink(missing_ok=True)


def ensure_model(*, url, path, sha256, required_files=None):
    """Return a path under models/, fetching the specified model if needed.

    For a tar archive, path names its top-level directory and required_files
    lists the files needed inside it. Call during initialization, not per frame.
    """
    if len(sha256) != 64 or any(c not in '0123456789abcdef' for c in sha256):
        raise ValueError('sha256 must be 64 lowercase hexadecimal characters')
    destination = inside(MODEL_DIR, path)
    if required_files is not None:
        if not required_files:
            raise ValueError('required_files must not be empty for an archive')
        for name in required_files:
            inside(destination, name)
        download_archive(destination, dict(url=url, sha256=sha256), required_files)
    else:
        download_model(destination, url, sha256)
    return destination
