"""Offline tests for skills/iphone-use-windows/scripts/iphone.py against the mock API.

    python -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import mock_iphonemirror  # noqa: E402

TMP = tempfile.mkdtemp(prefix="iphone-use-test-")
os.environ["IPHONE_USE_HOME"] = TMP
os.environ["IPHONE_USE_LANG"] = "en"  # deterministic output; language tests override
spec = importlib.util.spec_from_file_location("iphone", ROOT / "skills/iphone-use-windows/scripts/iphone.py")
iphone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iphone)


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.state = mock_iphonemirror.serve()
        os.environ["IPHONEMIRROR_URL"] = f"http://127.0.0.1:{cls.server.server_port}/api/v1"
        os.environ["IPHONEMIRROR_API_KEY"] = "test-key"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.state.inputs.clear()
        self.state.control = True
        self.state.capture = mock_iphonemirror.CAPTURE
        self.state.geometry_version = "g1"
        for k in self.state.capabilities:
            self.state.capabilities[k] = True
        self.state.launched.clear()
        os.environ["IPHONEMIRROR_API_KEY"] = "test-key"

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = iphone.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_doctor_ready(self):
        code, out, _ = self.run_cli("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("READY", out)

    def test_doctor_without_control(self):
        self.state.control = False
        code, out, _ = self.run_cli("doctor")
        self.assertEqual(code, 1)
        self.assertIn("control not available", out)

    def test_bad_key(self):
        os.environ["IPHONEMIRROR_API_KEY"] = "wrong"
        code, _, err = self.run_cli("devices")
        self.assertEqual(code, 2)
        self.assertIn("UNAUTHORIZED", err)
        self.assertIn("hint:", err)

    def test_shot_downscales_and_maps_taps(self):
        code, out, _ = self.run_cli("shot")
        self.assertEqual(code, 0)
        self.assertIn("view 646x1400", out)
        from PIL import Image
        path = out.split("screenshot: ")[1].splitlines()[0]
        self.assertEqual(Image.open(path).size, (646, 1400))
        # icon centre in capture px is (250, 450); in view px that is ~(137, 246)
        code, out, _ = self.run_cli("tap", "137", "246")
        self.assertEqual(code, 0, out)
        kind, body = self.state.inputs[-1]
        self.assertEqual(kind, "tap")
        self.assertAlmostEqual(body["x"], 250, delta=2)
        self.assertAlmostEqual(body["y"], 450, delta=2)
        self.assertIsNone(self.state.lease, "lease must be released")

    def test_tap_requires_shot_for_same_device(self):
        (Path(TMP) / "state.json").unlink(missing_ok=True)
        code, _, err = self.run_cli("tap", "10", "10")
        self.assertEqual(code, 2)
        self.assertIn("Run `shot` first", err)

    def test_out_of_bounds_rejected_locally(self):
        self.run_cli("shot")
        code, _, err = self.run_cli("tap", "700", "100")
        self.assertEqual(code, 2)
        self.assertIn("outside the screen", err)
        self.assertEqual(self.state.inputs, [])

    def test_geometry_change_blocks_input(self):
        self.run_cli("shot")
        self.state.capture = (2556, 1179)  # rotated
        code, _, err = self.run_cli("tap", "100", "100")
        self.assertEqual(code, 2)
        self.assertIn("geometry changed", err)
        self.assertEqual(self.state.inputs, [])

    def test_home_is_gesture_not_keyboard_home(self):
        # In iPhoneMirror the "HOME" key is the keyboard Home key, not the iPhone Home button.
        self.run_cli("shot")
        code, out, _ = self.run_cli("home")
        self.assertEqual(code, 0, out)
        self.assertIn("home gesture", out)
        self.assertEqual(len(self.state.inputs), 1)
        kind, body = self.state.inputs[-1]
        self.assertEqual(kind, "swipe")
        self.assertGreater(body["y1"], body["y2"])

    def test_input_carries_geometry_version_from_shot(self):
        self.run_cli("shot")
        self.run_cli("tap", "100", "100")
        self.assertEqual(self.state.inputs[-1][1]["geometryVersion"], "g1")

    def test_server_rejects_stale_geometry_version(self):
        self.run_cli("shot")
        self.state.geometry_version = "g2"  # same size, but stream re-initialised
        code, _, err = self.run_cli("tap", "100", "100")
        self.assertEqual(code, 2)
        self.assertIn("GEOMETRY_CHANGED", err)
        self.assertEqual(self.state.inputs, [])
        self.run_cli("shot")
        code, _, _ = self.run_cli("tap", "100", "100")
        self.assertEqual(code, 0)

    def test_capability_false_blocks_locally(self):
        self.run_cli("shot")
        self.state.capabilities["touchPath"] = False
        code, _, err = self.run_cli("switcher")
        self.assertEqual(code, 2)
        self.assertIn("CAPABILITY_NOT_SUPPORTED", err)
        self.assertEqual(self.state.inputs, [])

    def test_apps_and_launch(self):
        code, out, _ = self.run_cli("apps", "cal")
        self.assertEqual(code, 0)
        self.assertIn("com.apple.mobilecal", out)
        self.assertNotIn("MobileSMS", out)
        code, out, _ = self.run_cli("launch", "com.apple.mobilecal")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state.launched, ["com.apple.mobilecal"])
        self.assertIsNone(self.state.lease)

    def test_scroll_down_moves_finger_up(self):
        self.run_cli("shot")
        self.run_cli("scroll", "down", "--amount", "0.1")
        _, body = self.state.inputs[-1]
        self.assertGreater(body["y1"], body["y2"])
        self.assertAlmostEqual(body["y1"] - body["y2"], 0.1 * 2556, delta=3)
        self.run_cli("scroll", "up")
        _, body = self.state.inputs[-1]
        self.assertLess(body["y1"], body["y2"])

    def test_scroll_amount_capped(self):
        self.run_cli("shot")
        code, _, err = self.run_cli("scroll", "down", "--amount", "0.9")
        self.assertEqual(code, 2)

    def test_switcher_back_spotlight(self):
        self.run_cli("shot")
        for cmd, kind in (("switcher", "touch-path"), ("back", "swipe"), ("spotlight", "swipe")):
            code, out, _ = self.run_cli(cmd)
            self.assertEqual(code, 0, out)
            self.assertEqual(self.state.inputs[-1][0], kind)

    def test_text_and_key(self):
        self.run_cli("shot")
        self.run_cli("text", "Xin chào 你好")
        self.assertEqual(self.state.inputs[-1], ("text", {"text": "Xin chào 你好", "geometryVersion": "g1"}))
        self.run_cli("key", "enter")
        self.assertEqual(self.state.inputs[-1], ("key", {"key": "ENTER", "geometryVersion": "g1"}))

    def test_tap_with_shot_after(self):
        self.run_cli("shot")
        code, out, _ = self.run_cli("tap", "100", "100", "--shot", "--wait", "0")
        self.assertEqual(code, 0)
        self.assertIn("screenshot:", out)

    def test_zoom_writes_image(self):
        self.run_cli("shot")
        code, out, _ = self.run_cli("zoom", "50", "150", "250", "350")
        self.assertEqual(code, 0, out)
        self.assertTrue(Path(out.split("zoom: ")[1].splitlines()[0]).exists())

    def test_control_unavailable_message(self):
        self.run_cli("shot")
        self.state.control = False
        code, _, err = self.run_cli("tap", "10", "10")
        self.assertEqual(code, 2)
        self.assertIn("CONTROL_NOT_AVAILABLE", err)
        self.assertIn("setup.md", err)

    def test_clipboard_roundtrip(self):
        self.run_cli("clipboard", "set", "hello")
        _, out, _ = self.run_cli("clipboard", "get")
        self.assertEqual(out.strip(), "hello")


class LanguageTest(CliTest):
    """Output language selection and catalog completeness."""

    def test_every_message_has_every_language(self):
        i18n = sys.modules["i18n"]
        missing = [(k, lang) for k, row in i18n.MESSAGES.items() for lang in i18n.LANGUAGES if not row.get(lang)]
        self.assertEqual(missing, [])

    def test_placeholders_match_english(self):
        import string
        i18n = sys.modules["i18n"]
        fields = lambda s: sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)
        bad = [(k, lang) for k, row in i18n.MESSAGES.items() for lang, txt in row.items()
               if fields(txt) != fields(row["en"])]
        self.assertEqual(bad, [])

    def test_lang_flag_vietnamese(self):
        self.run_cli("shot")
        code, out, _ = self.run_cli("--lang", "vi", "tap", "100", "100")
        self.assertEqual(code, 0)
        self.assertIn("đã gửi: chạm", out)

    def test_env_chinese_error_and_hint(self):
        self.state.control = False
        self.run_cli("shot")
        os.environ["IPHONE_USE_LANG"] = "zh"
        try:
            code, _, err = self.run_cli("tap", "10", "10")
        finally:
            os.environ["IPHONE_USE_LANG"] = "en"
        self.assertEqual(code, 2)
        self.assertIn("错误 [CONTROL_NOT_AVAILABLE]", err)
        self.assertIn("提示:", err)

    def test_doctor_korean_keeps_ready_token(self):
        code, out, _ = self.run_cli("--lang", "ko", "doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("언어: ko", out)
        self.assertTrue(out.rstrip().endswith("READY"))

    def test_japanese_shot_keeps_parseable_path(self):
        code, out, _ = self.run_cli("--lang", "ja", "shot")
        self.assertEqual(code, 0)
        self.assertIn("screenshot: ", out)
        self.assertIn("tap/swipe はこの座標", out)

    def test_normalize(self):
        i18n = sys.modules["i18n"]
        self.assertEqual(i18n.normalize("vi_VN"), "vi")
        self.assertEqual(i18n.normalize("zh-Hans-CN"), "zh")
        self.assertEqual(i18n.normalize("Japanese_Japan.932"), "ja")
        self.assertIsNone(i18n.normalize("xx"))


if __name__ == "__main__":
    unittest.main()
