"""Download public, pretrained models into this prototype only."""
from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
UPSTREAM = "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master"

FILES = {
    "PADDLEOCR-LICENSE.txt": ["https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/LICENSE"],
    "YUNET-LICENSE.txt": ["https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/LICENSE"],
    "SFACE-LICENSE.txt": ["https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_recognition_sface/LICENSE"],
    "MEDIAPIPE-CODE-LICENSE.txt": ["https://raw.githubusercontent.com/google-ai-edge/mediapipe/master/LICENSE"],
    "vgg_seq2seq.pth": [
        "https://vocr.vn/data/vietocr/vgg_seq2seq.pth",
        "https://github.com/pbcquoc/vietocr/releases/download/v0.2.0/vgg_seq2seq.pth",
    ],
    "vietocr-base.yml": ["https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/base.yml"],
    "vietocr-vgg-seq2seq.yml": ["https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/vgg-seq2seq.yml"],
    "VIETOCR-LICENSE.txt": ["https://raw.githubusercontent.com/pbcquoc/vietocr/master/LICENSE"],
    "yunet.onnx": [
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ],
    "sface.onnx": [
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    ],
    "face_landmarker.task": ["https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"],
    "2.7_80x80_MiniFASNetV2.pth": [UPSTREAM + "/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"],
    "4_0_0_80x80_MiniFASNetV1SE.pth": [UPSTREAM + "/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth"],
    "PP-OCRv5_mobile_det.tar": ["https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_mobile_det_infer.tar"],
    "PP-OCRv6_small_rec.tar": ["https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv6_small_rec_infer.tar"],
}


def download(urls, path: Path, max_retries: int = 3):
    if path.exists() and path.stat().st_size > 100:
        print(f"Already downloaded: {path.name}", flush=True)
        return
    if isinstance(urls, str):
        urls = [urls]

    last_error = None
    for url in urls:
        for attempt in range(1, max_retries + 1):
            print(f"Downloading {path.name} from {url} (attempt {attempt}/{max_retries}) ...", flush=True)
            temporary = path.with_suffix(path.suffix + ".part")
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "LegacyVault-eKYC-prototype/1.0"})
                with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
                    while chunk := response.read(1024 * 1024):
                        out.write(chunk)
                if temporary.stat().st_size < 100 or temporary.read_bytes()[:50].startswith(b"version https://git-lfs"):
                    if temporary.exists():
                        temporary.unlink()
                    raise RuntimeError(f"Invalid download or Git LFS pointer: {path.name}")
                temporary.replace(path)
                print(f"Successfully downloaded: {path.name} ({path.stat().st_size} bytes)", flush=True)
                return
            except Exception as exc:
                last_error = exc
                if temporary.exists():
                    temporary.unlink()
                print(f"Attempt {attempt} failed for {url}: {exc}", flush=True)
                time.sleep(2 * attempt)
    raise RuntimeError(f"Could not download {path.name} from any source: {last_error}")


def main():
    MODELS.mkdir(exist_ok=True)
    vendor = ROOT / "vendor"
    vendor.mkdir(exist_ok=True)
    download([UPSTREAM + "/src/model_lib/MiniFASNet.py"], vendor / "minifasnet.py")
    download([UPSTREAM + "/LICENSE"], vendor / "MINIFASNET-LICENSE.txt")
    for name, urls in FILES.items():
        if name.endswith(".tar"):
            target = MODELS / name.removesuffix(".tar")
            if all((target / part).is_file() and (target / part).stat().st_size > 100
                   for part in ("inference.yml", "inference.json", "inference.pdiparams")):
                print(f"Bundled model ready: {target.name}", flush=True)
                continue
        download(urls, MODELS / name)
        if name.endswith(".tar"):
            target_name = name.removesuffix(".tar")
            target_dir = MODELS / target_name
            if not (target_dir / "inference.yml").exists():
                with tarfile.open(MODELS / name) as archive:
                    archive.extractall(MODELS, filter="data")
                extracted = MODELS / (target_name + "_infer")
                if extracted.exists():
                    if target_dir.exists():
                        shutil.rmtree(target_dir, ignore_errors=True)
                    extracted.rename(target_dir)
                    print(f"Extracted bundled model: {target_dir.name}", flush=True)
    manifest = []
    for name, urls in FILES.items():
        primary_url = urls[0] if isinstance(urls, list) else urls
        path = MODELS / name
        paths = sorted((MODELS / name.removesuffix(".tar")).glob("inference.*")) if name.endswith(".tar") else [path]
        for item in paths:
            if item.exists():
                manifest.append({"file": item.relative_to(MODELS).as_posix(), "source": primary_url, "bytes": item.stat().st_size,
                                 "sha256": hashlib.sha256(item.read_bytes()).hexdigest()})
    (MODELS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Models ready. Run start.cmd.", flush=True)


if __name__ == "__main__":
    main()
