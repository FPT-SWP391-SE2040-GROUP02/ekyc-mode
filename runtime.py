"""Use the CPU runtime and model weights bundled in this integrated directory."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
BASE = Path(os.environ.get('EKYC_BASE_DIR', str(ROOT)))
os.environ.setdefault('EKYC_MODELS_DIR', str(BASE / 'models'))
for key, folder in [('PADDLE_HOME', 'paddle'), ('PADDLE_PDX_CACHE_HOME', 'paddlex'),
                    ('HF_HOME', 'huggingface'), ('MPLCONFIGDIR', 'matplotlib'), ('TORCH_HOME', 'torch')]:
    os.environ.setdefault(key, str(ROOT / '.cache' / folder))
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
os.environ.setdefault('DISABLE_MODEL_SOURCE_CHECK', 'True')
sys.dont_write_bytecode = True

if __name__ == '__main__':
    # Ensure model weights exist before launching server
    try:
        from engine import models, MODELS
        groups = {
            "ocr": ["PP-OCRv5_mobile_det/inference.yml", "PP-OCRv6_small_rec/inference.yml",
                    "vgg_seq2seq.pth", "vietocr-base.yml", "vietocr-vgg-seq2seq.yml"],
            "face": ["yunet.onnx", "sface.onnx"],
            "landmarks": ["face_landmarker.task"],
            "anti_spoof": ["2.7_80x80_MiniFASNetV2.pth", "4_0_0_80x80_MiniFASNetV1SE.pth"],
        }
        weights_missing = not all((MODELS / item).exists() for items in groups.values() for item in items)
        if weights_missing:
            readiness = models.readiness()
            print(f"Missing models detected: {readiness}. Downloading missing weights...", flush=True)
            import download_models
            download_models.main()
            print("Model download completed successfully.", flush=True)
        try:
            models.init_face()
        except Exception as init_exc:
            print(f"Notice during face model init: {init_exc}", flush=True)
    except Exception as exc:
        print(f"Warning during model readiness check: {exc}", flush=True)

    import uvicorn
    host = os.environ.get('EKYC_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT') or os.environ.get('EKYC_PORT') or '8879')
    uvicorn.run('server:app', host=host, port=port, access_log=False)
