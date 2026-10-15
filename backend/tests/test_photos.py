"""Photo uploads: names taken from the product, and the checks and clean-up done on every file."""

import io
import os
import tempfile
import unittest
from pathlib import Path

from app.core.exceptions import ValidationFailedError
from app.services import photos

try:
    from PIL import Image

    HAVE_PIL = True
except ImportError:  # pragma: no cover - Pillow is in requirements.txt
    HAVE_PIL = False


class NameTests(unittest.TestCase):
    def test_base_name_comes_from_the_title(self):
        self.assertEqual(photos.base_name("Walnut Cremation Urn — Large"), "walnut-cremation-urn-large")
        self.assertEqual(photos.base_name("Café Plaque"), "cafe-plaque")
        self.assertLessEqual(len(photos.base_name("x" * 300)), photos.MAX_NAME)

    def test_numbers_continue_after_the_highest_used(self):
        existing = {"oak-urn-1.jpg", "oak-urn-3.png", "other-9.jpg", "01.jpg"}
        self.assertEqual(photos.next_names("oak-urn", existing, "jpg", 2), ["oak-urn-4.jpg", "oak-urn-5.jpg"])
        self.assertEqual(photos.next_names("new-name", existing, "webp", 1), ["new-name-1.webp"])


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class ProcessTests(unittest.TestCase):
    def image(self, fmt: str, size=(40, 30), mode="RGB", **save) -> bytes:
        out = io.BytesIO()
        Image.new(mode, size, (200, 120, 40, 255) if mode == "RGBA" else (200, 120, 40)).save(out, fmt, **save)
        return out.getvalue()

    def test_jpeg_is_reencoded_without_metadata(self):
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # camera make
        result = photos.process(self.image("JPEG", exif=exif.tobytes()))
        self.assertEqual(result.ext, "jpg")
        with Image.open(io.BytesIO(result.data)) as img:
            self.assertEqual(len(img.getexif()), 0)

    def test_transparent_png_stays_png_and_large_photos_shrink(self):
        result = photos.process(self.image("PNG", size=(3000, 1500), mode="RGBA"))
        self.assertEqual((result.ext, result.width, result.height), ("png", photos.MAX_SIDE, photos.MAX_SIDE // 2))

    def test_non_images_and_other_formats_are_refused(self):
        with self.assertRaises(ValidationFailedError):
            photos.process(b"<?php echo 'hi'; ?>")
        with self.assertRaises(ValidationFailedError):
            photos.process(self.image("GIF"))
        with self.assertRaises(ValidationFailedError):
            photos.process(self.image("JPEG")[:60])  # truncated


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class SaveTests(unittest.TestCase):
    def setUp(self):
        from app.core.config import get_settings

        self.tmp = tempfile.TemporaryDirectory()
        self.settings = get_settings()
        self.old = (self.settings.media_root, self.settings.media_url)
        self.settings.media_root, self.settings.media_url = self.tmp.name, "https://media.example.com"

    def tearDown(self):
        self.settings.media_root, self.settings.media_url = self.old
        self.tmp.cleanup()

    def test_saved_under_the_product_name_and_removable(self):
        jpg = photos.process(ProcessTests.image(self, "JPEG"))
        urls = photos.save("oak-urn", "Oak Urn", [jpg, jpg])
        self.assertEqual(urls, ["https://media.example.com/products/oak-urn/oak-urn-1.jpg", "https://media.example.com/products/oak-urn/oak-urn-2.jpg"])
        self.assertTrue((Path(self.tmp.name) / "products" / "oak-urn" / "oak-urn-2.jpg").is_file())
        self.assertEqual(photos.save("oak-urn", "Oak Urn", [jpg]), ["https://media.example.com/products/oak-urn/oak-urn-3.jpg"])

        self.assertTrue(photos.remove_file(urls[0]))
        self.assertFalse(os.path.exists(Path(self.tmp.name) / "products" / "oak-urn" / "oak-urn-1.jpg"))
        self.assertFalse(photos.remove_file("https://i.etsystatic.com/x.jpg"))  # not ours: left alone
        self.assertFalse(photos.remove_file("https://media.example.com/products/../../etc/passwd"))


if __name__ == "__main__":
    unittest.main()
