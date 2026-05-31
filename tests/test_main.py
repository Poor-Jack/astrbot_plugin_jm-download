import unittest
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch


from jm_download_core import (
    FORMAT_ERROR,
    coerce_bool,
    coerce_int,
    create_password_zip,
    create_pdf,
    parse_jm_command,
)


class ParseJmCommandTest(unittest.TestCase):
    def test_rejects_missing_non_numeric_and_extra_arguments(self):
        for message in ("/jm", "/jm abc", "/jm 123 456", "jm", "jm abc", "123 456"):
            with self.subTest(message=message):
                album_id, error = parse_jm_command(message)

                self.assertIsNone(album_id)
                self.assertEqual(error, FORMAT_ERROR)

    def test_accepts_single_numeric_album_id(self):
        album_id, error = parse_jm_command("/jm 1424612")

        self.assertEqual(album_id, "1424612")
        self.assertIsNone(error)

    def test_accepts_astrbot_command_text_without_wake_prefix(self):
        album_id, error = parse_jm_command("jm 1424612")

        self.assertEqual(album_id, "1424612")
        self.assertIsNone(error)

    def test_accepts_handler_text_when_only_arguments_remain(self):
        album_id, error = parse_jm_command("1424612")

        self.assertEqual(album_id, "1424612")
        self.assertIsNone(error)


class LowMemoryPackagingTest(unittest.TestCase):
    def test_create_pdf_streams_img2pdf_output_to_file(self):
        calls = []

        def convert(paths, outputstream=None):
            calls.append((paths, outputstream))
            self.assertIsNotNone(outputstream)
            outputstream.write(b"pdf-stream")
            return b"not-used"

        fake_img2pdf = types.SimpleNamespace(convert=convert)
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "out.pdf"
            image_path = Path(tmp_dir) / "001.jpg"
            image_path.write_bytes(b"image")

            with patch.dict(sys.modules, {"img2pdf": fake_img2pdf}):
                create_pdf([image_path], pdf_path)

            self.assertEqual(pdf_path.read_bytes(), b"pdf-stream")
            self.assertEqual(calls[0][0], [str(image_path)])

    def test_create_password_zip_uses_stored_entries_to_avoid_recompressing_pdf(self):
        opened = []

        class FakeAESZipFile:
            def __init__(self, zip_path, mode, compression=None, encryption=None):
                opened.append(
                    {
                        "zip_path": zip_path,
                        "mode": mode,
                        "compression": compression,
                        "encryption": encryption,
                        "password": None,
                        "written": None,
                    }
                )

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def setpassword(self, password):
                opened[-1]["password"] = password

            def write(self, pdf_path, arcname=None):
                opened[-1]["written"] = (pdf_path, arcname)

        fake_pyzipper = types.SimpleNamespace(
            AESZipFile=FakeAESZipFile,
            ZIP_STORED=0,
            ZIP_DEFLATED=8,
            WZ_AES=99,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "150263.pdf"
            zip_path = Path(tmp_dir) / "150263.zip"
            pdf_path.write_bytes(b"pdf")

            with patch.dict(sys.modules, {"pyzipper": fake_pyzipper}):
                create_password_zip(pdf_path, zip_path, "150263")

        self.assertEqual(opened[0]["compression"], fake_pyzipper.ZIP_STORED)
        self.assertEqual(opened[0]["encryption"], fake_pyzipper.WZ_AES)
        self.assertEqual(opened[0]["password"], b"150263")
        self.assertEqual(opened[0]["written"], (pdf_path, "150263.pdf"))


class ConfigCoercionTest(unittest.TestCase):
    def test_coerce_bool_handles_webui_string_values(self):
        for value in ("false", "False", "0", "no", "off", ""):
            with self.subTest(value=value):
                self.assertFalse(coerce_bool(value, default=True))

        for value in ("true", "True", "1", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(coerce_bool(value, default=False))

    def test_coerce_bool_falls_back_for_unknown_values(self):
        self.assertTrue(coerce_bool("maybe", default=True))
        self.assertFalse(coerce_bool(None, default=False))

    def test_coerce_int_handles_strings_and_minimum(self):
        self.assertEqual(coerce_int("3", default=1, minimum=1), 3)
        self.assertEqual(coerce_int("0", default=2, minimum=1), 1)
        self.assertEqual(coerce_int("bad", default=2, minimum=1), 2)


if __name__ == "__main__":
    unittest.main()
