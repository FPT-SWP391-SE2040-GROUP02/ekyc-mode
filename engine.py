"""CPU-only inference, lazy-loaded. Images never written to disk."""
from pathlib import Path
import base64
import io
import os
import threading

ROOT = Path(__file__).resolve().parent
MODELS = Path(os.environ.get("EKYC_MODELS_DIR", str(ROOT / "models")))
for key, value in {"PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
                   "PADDLE_PDX_CACHE_HOME": str(ROOT / ".cache" / "paddlex"),
                   "HF_HOME": str(ROOT / ".cache" / "huggingface"),
                   "MPLCONFIGDIR": str(ROOT / ".cache" / "matplotlib"),
                   "PADDLE_HOME": str(ROOT / ".cache" / "paddle"),
                   "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}.items():
    os.environ.setdefault(key, value)

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
LOCK = threading.RLock()


class InputError(ValueError):
    pass


def decode_image(data, max_side=1024):
    if not data or len(data) > MAX_BYTES:
        raise InputError("Ảnh phải nhỏ hơn 8 MB.")
    try:
        with Image.open(io.BytesIO(data)) as raw:
            if raw.format not in {"JPEG", "PNG", "WEBP"}:
                raise InputError("Hãy dùng ảnh JPG, PNG hoặc WebP.")
            if raw.width * raw.height > Image.MAX_IMAGE_PIXELS:
                raise InputError("Ảnh quá lớn; hãy giảm độ phân giải.")
            picture = ImageOps.exif_transpose(raw).convert("RGB")
            picture.thumbnail((max_side, max_side))
            return cv2.cvtColor(np.array(picture), cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InputError("Không đọc được ảnh. Hãy chọn file ảnh hợp lệ.") from exc


def jpeg_bytes(image):
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise InputError("Không tạo được ảnh xem trước.")
    return data.tobytes()


def data_url(image):
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes(image)).decode("ascii")


class Models:
    def __init__(self):
        self.ocr = self.vietocr = self.detector = self.recognizer = self.landmarker = None
        self.pad_models = []
        self._face_init_ok = False
        self._face_init_error = None

    def readiness(self):
        groups = {"ocr": ["PP-OCRv5_mobile_det/inference.yml", "PP-OCRv6_small_rec/inference.yml",
                          "vgg_seq2seq.pth", "vietocr-base.yml", "vietocr-vgg-seq2seq.yml"],
                  "face": ["yunet.onnx", "sface.onnx"],
                  "landmarks": ["face_landmarker.task"],
                  "anti_spoof": ["2.7_80x80_MiniFASNetV2.pth", "4_0_0_80x80_MiniFASNetV1SE.pth"]}
        result = {key: all((MODELS / item).exists() for item in items) for key, items in groups.items()}
        # R8: phân biệt "weights đủ" với "weights đủ + face đã khởi tạo thật".
        result["face_loaded"] = self._face_init_ok
        if self._face_init_error:
            result["face_error"] = self._face_init_error
        return result

    def init_face(self):
        if self.detector is None:
            try:
                self.detector = cv2.FaceDetectorYN.create(str(MODELS / "yunet.onnx"), "", (320, 320),
                                                          0.85, 0.3, 5000)
                self.recognizer = cv2.FaceRecognizerSF.create(str(MODELS / "sface.onnx"), "")
                self._face_init_ok = True
                self._face_init_error = None
            except Exception as exc:  # noqa: BLE001 - weight hỏng phải hiện ra ở /api/health, không đợi request đầu
                self._face_init_error = f"{type(exc).__name__}: {exc}"
                raise

    # R8 (audit 2026-10-27): readiness() chỉ kiểm tra file tồn tại; init_face()
    # cho biết weight có NẠP ĐƯỢC thật không (file hỏng → lỗi ở lần dùng đầu, 503).
    _face_init_ok: bool = False
    _face_init_error: str | None = None

    def _face_upright(self, image):
        self.init_face()
        height, width = image.shape[:2]
        faces = None
        # YuNet can miss large close-up faces. Keep successful original-size
        # detections, then retry smaller inputs without lowering confidence.
        for limit in (None, 640, 320):
            if limit is None:
                probe = image
            elif limit < max(width, height):
                scale = limit / max(width, height)
                size = (max(1, round(width * scale)), max(1, round(height * scale)))
                probe = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
            else:
                continue
            self.detector.setInputSize((probe.shape[1], probe.shape[0]))
            _, faces = self.detector.detect(probe)
            if faces is not None and len(faces):
                # Box and all five landmarks must refer to the original image
                # passed to SFace, including rounding differences on each axis.
                faces = faces.copy()
                faces[:, :14:2] *= width / probe.shape[1]
                faces[:, 1:14:2] *= height / probe.shape[0]
                break
        if faces is None or len(faces) == 0:
            raise InputError("Chưa tìm được khuôn mặt; hãy dùng ảnh rõ và đủ sáng.")
        if len(faces) != 1:
            raise InputError("Ảnh cần có đúng một khuôn mặt.")
        face = faces[0]
        if min(face[2], face[3]) < 32:
            raise InputError("Khuôn mặt quá nhỏ; hãy chụp gần hơn hoặc cắt sát ảnh chân dung.")
        crop = self.recognizer.alignCrop(image, face)
        feature = self.recognizer.feature(crop).copy()
        return face, crop, feature

    def face(self, image, auto_rotate=True):
        try:
            return self._face_upright(image)
        except InputError as original:
            if not auto_rotate or "Chưa tìm" not in str(original):
                raise
            for rotation in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180):
                try:
                    return self._face_upright(cv2.rotate(image, rotation))
                except InputError:
                    pass
            raise original

    def similarity(self, a, b):
        return float(self.recognizer.match(a, b, cv2.FaceRecognizerSF_FR_COSINE))

    def match(self, reference, selfie, threshold):
        _, ref_crop, ref_feature = self.face(reference)
        _, live_crop, live_feature = self.face(selfie)
        score = self.similarity(ref_feature, live_feature)
        return {"score": round(score, 5), "threshold": threshold, "matched": score >= threshold,
                "reference_crop": data_url(ref_crop), "selfie_crop": data_url(live_crop),
                "note": "Điểm cosine, không phải phần trăm xác suất. Ngưỡng mặc định 0.363 từ demo SFace; cần hiệu chỉnh trên dữ liệu CCCD."}

    def _read_document_upright(self, image):
        # On Windows, importing Paddle before Torch can fail loading Torch's shm.dll.
        # VietOCR needs Torch too, so initialize its runtime before Paddle.
        import torch
        if self.ocr is None:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(text_detection_model_name="PP-OCRv5_mobile_det",
                                 text_detection_model_dir=str(MODELS / "PP-OCRv5_mobile_det"),
                                 text_recognition_model_name="PP-OCRv6_small_rec",
                                 text_recognition_model_dir=str(MODELS / "PP-OCRv6_small_rec"),
                                 use_doc_orientation_classify=False, use_doc_unwarping=False,
                                 use_textline_orientation=False, device="cpu", cpu_threads=1,
                                 enable_mkldnn=False)
        if self.vietocr is None:
            import torch
            import yaml
            from vietocr.tool.translate import build_model
            torch.set_num_threads(1)
            config = yaml.safe_load((MODELS / "vietocr-base.yml").read_text(encoding="utf-8"))
            config.update(yaml.safe_load((MODELS / "vietocr-vgg-seq2seq.yml").read_text(encoding="utf-8")))
            config["device"] = "cpu"
            config["weights"] = str(MODELS / "vgg_seq2seq.pth")
            config["cnn"]["pretrained"] = False
            config["predictor"]["beamsearch"] = False
            network, vocab = build_model(config)
            network.load_state_dict(torch.load(config["weights"], map_location="cpu", weights_only=True))
            network.eval()
            self.vietocr = (network, vocab, config)
        with torch.no_grad():
            results = list(self.ocr.predict(image))
        if not results:
            return []
        result = results[0]
        polygons = result.get("rec_polys", result.get("dt_polys", []))
        lines = []
        for text, score, polygon in zip(result.get("rec_texts", []), result.get("rec_scores", []), polygons):
            points = np.asarray(polygon).astype(float).tolist()
            # Preserve Paddle's numeric reading; use a Vietnamese vocabulary for words.
            latin_text, latin_score = text, float(score)
            if any(char.isalpha() for char in text):
                source = np.asarray(polygon, dtype=np.float32)
                width = max(1, int(max(np.linalg.norm(source[0] - source[1]), np.linalg.norm(source[2] - source[3]))))
                height = max(1, int(max(np.linalg.norm(source[0] - source[3]), np.linalg.norm(source[1] - source[2]))))
                target = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
                patch = cv2.warpPerspective(image, cv2.getPerspectiveTransform(source, target), (width, height), borderMode=cv2.BORDER_REPLICATE)
                from vietocr.tool.translate import process_input, translate
                network, vocab, config = self.vietocr
                crop = Image.fromarray(cv2.cvtColor(patch, cv2.COLOR_BGR2RGB))
                sizes = config["dataset"]
                tensor = process_input(crop, sizes["image_height"], sizes["image_min_width"], sizes["image_max_width"])
                prediction, probabilities = translate(tensor, network)
                text, score = vocab.decode(prediction[0].tolist()), float(probabilities[0])
                if not np.isfinite(score):
                    score = 0.0
            lines.append({"text": text, "score": round(float(score), 4), "box": points,
                          "paddle_text": latin_text, "paddle_score": round(latin_score, 4)})
        return sorted(lines, key=lambda x: (int(min(p[1] for p in x["box"]) / 16), min(p[0] for p in x["box"])))

    @staticmethod
    def document_score(lines):
        from logic import plain, NAME_LABEL, BIRTH_LABEL, RESIDENCE_LABEL, label_in
        import re
        horizontal = [line for line in lines if max(p[0] for p in line['box']) - min(p[0] for p in line['box']) >= max(p[1] for p in line['box']) - min(p[1] for p in line['box'])]
        anchors = sum(label_in(line, pattern) for line in horizontal for pattern in (NAME_LABEL, BIRTH_LABEL, RESIDENCE_LABEL))
        numeric = sum(bool(re.search(r"(?<!\d)\d{12}(?!\d)|\d{1,2}/\d{1,2}/\d{4}", line['text'])) for line in horizontal)
        readable = sum(float(line['score']) >= .8 and len(line['text']) >= 5 for line in horizontal)
        return anchors * 10 + min(numeric, 3) * 3 + min(readable, 10) * .2, anchors

    def read_document(self, image):
        lines = self._read_document_upright(image)
        score, anchors = self.document_score(lines)
        best = (score, lines, image, 0)
        if anchors < 2 and not (anchors >= 1 and score >= 15):
            import gc
            for rotation, angle in ((cv2.ROTATE_90_CLOCKWISE, 90), (cv2.ROTATE_90_COUNTERCLOCKWISE, 270), (cv2.ROTATE_180, 180)):
                gc.collect()
                candidate_image = cv2.rotate(image, rotation)
                candidate_lines = self._read_document_upright(candidate_image)
                candidate_score, candidate_anchors = self.document_score(candidate_lines)
                if candidate_score > best[0]:
                    best = (candidate_score, candidate_lines, candidate_image, angle)
                if candidate_anchors >= 2 or (candidate_anchors >= 1 and candidate_score >= 15):
                    break
        self.last_document_image, self.last_document_rotation = best[2], best[3]
        return best[1]

    def landmarks(self, image):
        import mediapipe as mp
        if self.landmarker is None:
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELS / "face_landmarker.task")),
                running_mode=mp.tasks.vision.RunningMode.IMAGE, num_faces=2,
                min_face_detection_confidence=0.6, min_face_presence_confidence=0.6)
            self.landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        result = self.landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                 data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
        if len(result.face_landmarks) != 1:
            raise InputError("Đưa đúng một khuôn mặt vào khung hình.")
        points = result.face_landmarks[0]
        w, h = image.shape[1], image.shape[0]
        def point(i):
            return np.array([points[i].x * w, points[i].y * h])
        def ear(indices):
            p = [point(i) for i in indices]
            return float((np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])) /
                         max(1, 2 * np.linalg.norm(p[0] - p[3])))
        eye = (ear([33, 160, 158, 133, 153, 144]) + ear([362, 385, 387, 263, 373, 380])) / 2
        yaw = float((point(1)[0] - (point(33)[0] + point(263)[0]) / 2) /
                    max(1, abs(point(263)[0] - point(33)[0])))
        return yaw, eye

    @staticmethod
    def context_crop(image, bbox, scale):
        # Matches upstream CropImage: keep the surrounding context and BGR values 0..255.
        height, width = image.shape[:2]
        x, y, w, h = map(float, bbox[:4])
        scale = min((height - 1) / h, (width - 1) / w, scale)
        cw, ch = w * scale, h * scale
        left, top = x + w / 2 - cw / 2, y + h / 2 - ch / 2
        right, bottom = x + w / 2 + cw / 2, y + h / 2 + ch / 2
        if left < 0:
            right -= left
            left = 0
        if top < 0:
            bottom -= top
            top = 0
        if right > width - 1:
            left -= right - width + 1
            right = width - 1
        if bottom > height - 1:
            top -= bottom - height + 1
            bottom = height - 1
        patch = image[max(0, int(top)):int(bottom) + 1, max(0, int(left)):int(right) + 1]
        return cv2.resize(patch, (80, 80))

    def anti_spoof(self, image, bbox=None):
        import torch
        if not self.pad_models:
            from vendor.minifasnet import MiniFASNetV2, MiniFASNetV1SE
            torch.set_num_threads(1)
            for filename, factory, scale in [("2.7_80x80_MiniFASNetV2.pth", MiniFASNetV2, 2.7),
                                             ("4_0_0_80x80_MiniFASNetV1SE.pth", MiniFASNetV1SE, 4.0)]:
                model = factory(conv6_kernel=(5, 5))
                state = torch.load(MODELS / filename, map_location="cpu", weights_only=True)
                model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
                model.eval()
                self.pad_models.append((model, scale))
        if bbox is None:
            bbox, _, _ = self.face(image, auto_rotate=False)
        scores = []
        with torch.inference_mode():
            for model, scale in self.pad_models:
                patch = self.context_crop(image, bbox, scale)
                tensor = torch.from_numpy(patch.transpose(2, 0, 1).copy()).float().unsqueeze(0)
                scores.append(torch.softmax(model(tensor), dim=1).numpy()[0])
        average = np.mean(scores, axis=0)
        return {"live_score": round(float(average[1]), 5), "label": "live" if int(np.argmax(average)) == 1 else "spoof",
                "scores": average.tolist(), "threshold": 0.7,
                "passed": int(np.argmax(average)) == 1 and float(average[1]) >= 0.7,
                "note": "Ảnh đơn chỉ đánh giá dấu hiệu giả mạo. Kết quả phụ thuộc camera, ánh sáng và cách chụp."}


models = Models()

