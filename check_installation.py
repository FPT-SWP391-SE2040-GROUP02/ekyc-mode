"""Check a recipient's install using bundled models and synthetic input only."""
import argparse
import importlib
from importlib.metadata import version
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", action="store_true", help="Load all models and run a synthetic OCR check")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
        raise RuntimeError("This package requires Python 3.12 64-bit.")
    print("Python:", sys.version.split()[0], "64-bit", flush=True)
    from engine import InputError, LOCK, decode_image, models
    # Initialize Torch before Paddle to avoid DLL loader conflicts on Windows.
    for module, distribution in [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("cv2", "opencv-contrib-python"),
                                 ("torch", "torch"), ("torchvision", "torchvision"),
                                 ("paddleocr", "paddleocr"), ("paddle", "paddlepaddle"), ("vietocr", "vietocr"),
                                 ("mediapipe", "mediapipe")]:
        importlib.import_module(module)
        print(f"OK {distribution}: {version(distribution)}", flush=True)
    import cv2
    if not hasattr(cv2, "FaceRecognizerSF"):
        raise RuntimeError("OpenCV SFace is missing. Run setup.cmd again.")
    readiness = models.readiness()
    for name, available in readiness.items():
        print(f"{'OK' if available else 'MISSING'} model group: {name}", flush=True)
    if not all(readiness.values()):
        raise RuntimeError("A bundled model is missing. Extract the complete ZIP or run setup.cmd again.")
    if args.models:
        import numpy as np
        from logic import extract_fields
        from server import sample_document
        with LOCK:
            models.init_face()
            print("OK YuNet / SFace: weights loaded on CPU", flush=True)
            blank = np.zeros((320, 320, 3), dtype=np.uint8)
            models.anti_spoof(blank, bbox=[120, 120, 80, 80])
            print("OK MiniFASNet V2 / V1SE: weights loaded on CPU", flush=True)
            try:
                models.landmarks(blank)
            except InputError:
                pass
            print("OK FaceLandmarker: weights loaded on CPU", flush=True)
            result = extract_fields(models.read_document(decode_image(sample_document().body)))
        expected = {"id_number": "000000000001", "full_name": "NGUYỄN VĂN AN", "date_of_birth": "2000-02-01"}
        if {key: result['fields'][key] for key in expected} != expected:
            raise RuntimeError(f"Synthetic OCR check differed from expected: {result['fields']}")
        print("OK PaddleOCR + VietOCR: synthetic OCR fields matched", flush=True)
    print("INSTALLATION READY. Run START.cmd; open http://127.0.0.1:8879", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"CHECK FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        print("For DLL/VCRUNTIME errors, install Microsoft Visual C++ Redistributable x64.", file=sys.stderr)
        print("See HUONG_DAN_CHAY.txt. No user photos were used by this check.", file=sys.stderr)
        sys.exit(1)
