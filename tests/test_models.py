import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from common import models


class ModelsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch.object(models, 'MODEL_DIR', self.root / 'models')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_download_reuse_and_failed_verification(self):
        source = self.root / 'source'
        source.write_bytes(b'model')
        args = dict(url=source.as_uri(), path='nested/model.bin',
                    sha256=hashlib.sha256(b'model').hexdigest())
        result = models.ensure_model(**args)
        self.assertEqual(result.read_bytes(), b'model')
        with patch.object(models, 'urlopen', side_effect=AssertionError('downloaded twice')):
            self.assertEqual(models.ensure_model(**args), result)
        source.write_bytes(b'bad')
        with self.assertRaises(RuntimeError):
            models.ensure_model(**dict(args, sha256='0' * 64))
        self.assertEqual(result.read_bytes(), b'model')
        self.assertEqual(list(models.MODEL_DIR.rglob('*.part')), [])

    def test_archive_and_missing_file_repair(self):
        source = self.root / 'source.tar.bz2'
        with tarfile.open(source, 'w:bz2') as archive:
            entry = tarfile.TarInfo('bundle/model.bin')
            entry.size = 5
            archive.addfile(entry, io.BytesIO(b'model'))
        args = dict(url=source.as_uri(), path='bundle', sha256=models.sha256(source),
                    required_files=['model.bin'])
        result = models.ensure_model(**args)
        with patch.object(models, 'urlopen', side_effect=AssertionError('downloaded twice')):
            models.ensure_model(**args)
        (result / 'model.bin').unlink()
        models.ensure_model(**args)
        self.assertEqual((result / 'model.bin').read_bytes(), b'model')

    def test_paths_and_unsafe_archive(self):
        with self.assertRaises(ValueError):
            models.ensure_model(url='unused', path='../outside', sha256='0' * 64)
        source = self.root / 'unsafe.tar'
        with tarfile.open(source, 'w') as archive:
            entry = tarfile.TarInfo('../outside')
            entry.size = 1
            archive.addfile(entry, io.BytesIO(b'x'))
        with self.assertRaises(ValueError):
            models.ensure_model(url=source.as_uri(), path='bundle',
                                sha256=models.sha256(source), required_files=['model.bin'])
        self.assertFalse((self.root / 'outside').exists())


if __name__ == '__main__':
    unittest.main()
