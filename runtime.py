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
    import uvicorn
    uvicorn.run('server:app', host=os.environ.get('EKYC_HOST', '127.0.0.1'), port=int(os.environ.get('EKYC_PORT', '8879')), access_log=False)
