import unittest


from jm_download_core import FORMAT_ERROR, parse_jm_command


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


if __name__ == "__main__":
    unittest.main()
