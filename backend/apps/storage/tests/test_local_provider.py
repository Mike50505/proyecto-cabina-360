import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.storage.exceptions import InvalidStorageKey, StorageValidationError
from apps.storage.local import LocalStorageProvider


class LocalStorageProviderTests(SimpleTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.provider = LocalStorageProvider(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def test_put_and_compose_streams_with_checksum(self):
        first = self.provider.put_stream("parts/0", BytesIO(b"abcd"), expected_size=4)
        second = self.provider.put_stream("parts/1", BytesIO(b"ef"), expected_size=2)
        expected = hashlib.sha256(b"abcdef").hexdigest()

        result = self.provider.compose(
            [first.key, second.key],
            "final/video.mp4",
            expected_size=6,
            expected_sha256=expected,
        )

        self.assertEqual(result.size, 6)
        self.assertEqual(result.sha256, expected)
        with self.provider.open(result.key) as stored:
            self.assertEqual(stored.read(), b"abcdef")

    def test_rejects_path_traversal(self):
        with self.assertRaises(InvalidStorageKey):
            self.provider.put_stream("../outside", BytesIO(b"x"), expected_size=1)

    def test_wrong_size_does_not_publish_partial_object(self):
        with self.assertRaises(StorageValidationError):
            self.provider.put_stream("parts/wrong", BytesIO(b"abc"), expected_size=4)

        self.assertFalse(self.provider.exists("parts/wrong"))

    def test_checksum_failure_does_not_publish_composed_object(self):
        self.provider.put_stream("parts/0", BytesIO(b"abcd"), expected_size=4)

        with self.assertRaises(StorageValidationError):
            self.provider.compose(
                ["parts/0"],
                "final/bad.mp4",
                expected_size=4,
                expected_sha256="0" * 64,
            )

        self.assertFalse(self.provider.exists("final/bad.mp4"))

