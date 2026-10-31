import math
import sys
from pathlib import Path
import time
import unittest

from fastapi.testclient import TestClient
from engine import LOCK, models, decode_image
from logic import Challenge, extract_fields
from server import app, sessions

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


class LogicTests(unittest.TestCase):
    def test_fields_and_invalid_dates(self):
        lines = [{"text": t, "score": 0.99} for t in ["Số: 000000000001", "Họ và tên / Full name:",
                 "NGUYỄN VĂN AN", "Ngày sinh / Date of birth: 31/02/2000", "Ngày hết hạn: 01/02/2040"]]
        result = extract_fields(lines)
        self.assertEqual(result["fields"]["id_number"], "000000000001")
        self.assertEqual(result["fields"]["full_name"], "NGUYỄN VĂN AN")
        self.assertEqual(result["fields"]["date_of_birth"], "")
        self.assertEqual(result["fields"]["date_of_expiry"], "2040-02-01")

    def test_extract_expiry_variants(self):
        cases = [
            ("Có giá trị đến / Date of expiry: 15/10/2035", "2035-10-15"),
            ("Có giá trị đến / Date of expiry\n15/10/2035", "2035-10-15"),
            ("Có giá trị đến: Không thời hạn", "Không thời hạn"),
            ("Date of expiry: No expiry", "Không thời hạn"),
            ("Hạn sử dụng: 20/12/2030", "2030-12-20"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                lines = [{"text": line, "score": 0.99} for line in text.split("\n")]
                res = extract_fields(lines)
                self.assertEqual(res["fields"]["date_of_expiry"], expected)

    def test_name_label_variants_and_unicode(self):
        import unicodedata
        name = "NGUYỄN VĂN AN"
        for label in ["Họ và tên:", "Họ, chữ đệm và tên:", "Họ, chữ đệm và tên / Full name:", "Full name:"]:
            for form in ["NFC", "NFD"]:
                with self.subTest(label=label, form=form):
                    lines = [{"text": unicodedata.normalize(form, text), "score": 0.99}
                             for text in [label, name]]
                    self.assertEqual(extract_fields(lines)["fields"]["full_name"], name)
        inline = [{"text": "Họ, chữ đệm và tên / Full name: " + name, "score": 0.99}]
        self.assertEqual(extract_fields(inline)["fields"]["full_name"], name)

    def test_name_uses_paddle_label_without_rewriting_name(self):
        lines = [{"text": "Họ và tèn lỗi", "paddle_text": "Họ và tên / Full name:", "score": 0.6},
                 {"text": "ĐẶNG THỊ HỒNG", "paddle_text": "DANG THI HONG", "score": 0.99}]
        self.assertEqual(extract_fields(lines)["fields"]["full_name"], "ĐẶNG THỊ HỒNG")

    def test_missing_name_does_not_take_another_field(self):
        for field in ["Ngày sinh:", "Giới tính: Nam", "Quốc tịch: Việt Nam", "Date of birth:"]:
            with self.subTest(field=field):
                lines = [{"text": text, "score": 0.99} for text in ["Họ và tên:", field, "NGUYỄN VĂN AN"]]
                self.assertEqual(extract_fields(lines)["fields"]["full_name"], "")

    def test_separate_english_label(self):
        lines = [{"text": text, "score": 0.99}
                 for text in ["Họ và tên:", "Full name:", "NGUYỄN VĂN AN"]]
        self.assertEqual(extract_fields(lines)["fields"]["full_name"], "NGUYỄN VĂN AN")

    def test_name_without_label_between_id_and_birthday(self):
        lines = [{"text": text, "score": 0.901} for text in
                 ["CĂN CƯỚC CÔNG DÂN", "000000000001", "NGUYỄN VĂN AN",
                  "sinh//Date of birth:", "01/02/2000", "Nam", "Việt Nam"]]
        fields = extract_fields(lines)["fields"]
        self.assertEqual(fields["full_name"], "NGUYỄN VĂN AN")
        self.assertEqual(fields["date_of_birth"], "2000-02-01")

    def test_unlabelled_name_requires_unique_confident_bounded_candidate(self):
        cases = [
            [("000000000001", 1), ("NGUYỄN VĂN AN", 0.6), ("Ngày sinh:", 1)],
            [("000000000001", 1), ("NGUYỄN VĂN AN", 0.9), ("TRẦN VĂN BÌNH", 0.9), ("Ngày sinh:", 1)],
            [("000000000001", 1), ("NGUYỄN VĂN AN", 0.9)],
            [("NGUYỄN VĂN AN", 0.9), ("Ngày sinh:", 1)],
        ]
        for case in cases:
            with self.subTest(case=case):
                lines = [{"text": text, "score": score} for text, score in case]
                self.assertEqual(extract_fields(lines)["fields"]["full_name"], "")

    def test_static_face_cannot_complete_challenge(self):
        session = Challenge(["blink", "left"], created_at=0)
        for i in range(60):
            session.update(0.0, 0.25, i * 0.3)
        self.assertFalse(session.snapshot()["challenge_completed"])
        self.assertFalse(session.snapshot()["prototype_passed"])

    def test_challenge_requires_return_and_pad(self):
        session = Challenge(["blink", "left"], created_at=0)
        timestamp = 0.0
        def frames(yaw, eye, count):
            nonlocal timestamp
            for _ in range(count):
                timestamp += 0.3
                session.update(yaw, eye, timestamp)
        frames(0, 0.25, 6)
        frames(0, 0.08, 2)
        self.assertEqual(session.index, 0)
        frames(0, 0.25, 4)
        frames(0.2, 0.25, 2)
        frames(0, 0.25, 2)
        self.assertTrue(session.snapshot()["challenge_completed"])
        self.assertFalse(session.snapshot()["prototype_passed"])
        session.live_scores = [0.9] * 5
        self.assertTrue(session.snapshot()["prototype_passed"])


class ApiAndModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, base_url="http://127.0.0.1:8877")
        cls.fixture_dir = Path(__file__).parent / "test-output"

    def test_ocr_real_models(self):
        sample = self.client.get("/api/sample-document")
        self.assertEqual(sample.status_code, 200)
        result = self.client.post("/api/ocr", files={"file": ("sample.png", sample.content, "image/png")})
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        print("OCR:", data["fields"], "elapsed_ms:", data["elapsed_ms"], flush=True)
        self.assertEqual(data["fields"]["id_number"], "000000000001")
        self.assertEqual(data["fields"]["full_name"], "NGUYỄN VĂN AN")
        self.assertEqual(data["fields"]["date_of_birth"], "2000-02-01")

    def test_face_requires_scanned_front_reference(self):
        response = self.client.post("/api/face-match", files={"reference": ("a.jpg", b"standalone reference"),
                                   "selfie": ("b.jpg", b"selfie")})
        self.assertEqual(response.status_code, 422)
        # Same/different pairs now run through OCR in test_locked_face_real_models.py.

    def test_pad_and_landmarks_real_models(self):
        for filename in ["image_F1.jpg", "image_T1.jpg"]:
            data = (self.fixture_dir / filename).read_bytes()
            response = self.client.post("/api/anti-spoof", files={"file": (filename, data, "image/jpeg")})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertTrue(0 <= result["live_score"] <= 1)
            self.assertEqual(result["passed"], filename == "image_T1.jpg")
            print("PAD", filename, result, flush=True)
        image = decode_image((self.fixture_dir / "lena.jpg").read_bytes())
        with LOCK:
            yaw, eye = models.landmarks(image)
        self.assertTrue(math.isfinite(yaw) and math.isfinite(eye))
        print("MediaPipe: yaw", round(yaw, 3), "eye", round(eye, 3), flush=True)

    def test_invalid_upload_and_origin(self):
        result = self.client.post("/api/ocr", files={"file": ("fake.jpg", b"not an image", "image/jpeg")})
        self.assertEqual(result.status_code, 422)
        result = self.client.post("/api/liveness/start", headers={"Origin": "https://example.com"})
        self.assertEqual(result.status_code, 403)

    def test_sessions_reject_replay_and_expire(self):
        session = self.client.post("/api/liveness/start").json()
        token = session["session_id"]
        photo = (self.fixture_dir / "lena.jpg").read_bytes()
        for _ in range(8):
            response = self.client.post("/api/liveness/frame", data={"session_id": token},
                                        files={"frame": ("frame.jpg", photo, "image/jpeg")})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()["prototype_passed"])
        self.assertEqual(sessions[token].frames, 1)
        self.assertEqual(self.client.get(f"/api/liveness/{token}/selfie").status_code, 409)
        sessions[token].created_at = time.monotonic() - 100
        response = self.client.post("/api/liveness/frame", data={"session_id": token},
                                    files={"frame": ("frame.jpg", photo, "image/jpeg")})
        self.assertEqual(response.status_code, 410)


if __name__ == "__main__":
    unittest.main(verbosity=2)
