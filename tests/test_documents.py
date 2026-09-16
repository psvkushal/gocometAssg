from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nova.documents import load_document


class DocumentInputTests(unittest.TestCase):
    def test_supported_headers_and_exact_size_limit(self):
        # Minimal header fixtures exercise admission checks, not full file decoding.
        for filename, content, media_type in (
            ("invoice.PDF", b"%PDF-1.7\n", "application/pdf"),
            ("invoice.png", b"\x89PNG\r\n\x1a\n", "image/png"),
            ("invoice.jpg", b"\xff\xd8\xff", "image/jpeg"),
            ("invoice.jpeg", b"\xff\xd8\xff", "image/jpeg"),
        ):
            with self.subTest(filename=filename), TemporaryDirectory() as directory:
                path = Path(directory) / filename
                path.write_bytes(content)
                result = load_document(path, max_bytes=len(content))
                self.assertEqual((result.filename, result.media_type, result.content),
                                 (filename, media_type, content))

    def test_rejects_invalid_inputs_before_extraction(self):
        for filename, content, limit, error in (
            ("invoice.pdf", b"", 10, "empty"),
            ("invoice.pdf", b"%PDF-1.7\n", 8, "exceeds"),
            ("invoice.txt", b"%PDF-1.7\n", 10, "Supported"),
            ("invoice.pdf", b"not a pdf", 10, "header"),
            ("invoice.png", b"%PDF-1.7\n", 10, "header"),
        ):
            with self.subTest(filename=filename, error=error), TemporaryDirectory() as directory:
                path = Path(directory) / filename
                path.write_bytes(content)
                with self.assertRaisesRegex(ValueError, error):
                    load_document(path, max_bytes=limit)


if __name__ == "__main__":
    unittest.main()
