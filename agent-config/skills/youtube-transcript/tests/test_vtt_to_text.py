import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vtt_to_text.py"
SPEC = importlib.util.spec_from_file_location("vtt_to_text", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
convert_vtt = MODULE.convert_vtt


class ConversionTests(unittest.TestCase):
    def test_metadata_identifiers_markup_and_entities(self):
        source = (
            "\ufeffWEBVTT\r\nKind: captions\r\nLanguage: en\r\n\r\n"
            "NOTE ignored text\r\nnot spoken\r\n\r\n"
            "STYLE\r\n::cue { color: red; }\r\n\r\n"
            "cue-1\r\n00:00:01.000 --> 00:00:02.000 align:start\r\n"
            "<v Speaker><c.color>Hello &amp; welcome</c></v>\r\n"
            "to <00:00:01.500>this &lt;example&gt;.\r\n"
        )
        self.assertEqual(convert_vtt(source), "Hello & welcome to this <example>.\n")

    def test_overlapping_rolling_captions(self):
        source = (
            "WEBVTT\n\n"
            "00:00.000 --> 00:03.000\nhello there\n\n"
            "00:01.000 --> 00:04.000\nhello there friend\n\n"
            "00:02.000 --> 00:05.000\nthere friend today\n"
        )
        self.assertEqual(convert_vtt(source), "hello there\nfriend\ntoday\n")

    def test_repeated_speech_is_preserved_in_non_overlapping_cues(self):
        source = (
            "WEBVTT\n\n"
            "00:00.000 --> 00:01.000\nyes yes\n\n"
            "00:01.000 --> 00:02.000\nyes yes\n\n"
            "00:05.000 --> 00:06.000\nyes yes\n"
        )
        self.assertEqual(convert_vtt(source), "yes yes\nyes yes\nyes yes\n")

    def test_hour_timestamps_and_blank_cues(self):
        source = (
            "WEBVTT\n\n"
            "01:00:00.000 --> 01:00:01.000\n\n"
            "01:00:02.000 --> 01:00:03.000\nlate caption\n"
        )
        self.assertEqual(convert_vtt(source), "late caption\n")

    def test_missing_captions_are_an_error(self):
        with self.assertRaisesRegex(ValueError, "no caption text"):
            convert_vtt("WEBVTT\n\nNOTE no captions\n")

    def test_wrong_format_and_invalid_timing_are_errors(self):
        with self.assertRaisesRegex(ValueError, "WEBVTT header"):
            convert_vtt("1\n00:00:01,000 --> 00:00:02,000\nhello\n")
        with self.assertRaisesRegex(ValueError, "cue end"):
            convert_vtt("WEBVTT\n\n00:02.000 --> 00:01.000\nhello\n")

    def test_cli_handles_quoted_paths_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "speaker's [video].vtt"
            output = Path(directory) / "speaker's transcript.txt"
            source.write_text(
                "WEBVTT\n\n00:00.000 --> 00:01.000\nhello\n", encoding="utf-8"
            )
            command = [sys.executable, str(SCRIPT), str(source), "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(output.read_text(encoding="utf-8"), "hello\n")
            output.write_text("existing user content", encoding="utf-8")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing user content")


if __name__ == "__main__":
    unittest.main()
