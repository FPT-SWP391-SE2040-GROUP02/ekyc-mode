"""Optional public upstream test images, not user identity data."""
from pathlib import Path
from download_models import download

root = Path(__file__).resolve().parent / "test-output"
root.mkdir(exist_ok=True)
sources = {
    "lena.jpg": "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg",
    "messi.jpg": "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/messi5.jpg",
    "image_F1.jpg": "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/images/sample/image_F1.jpg",
    "image_T1.jpg": "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/master/images/sample/image_T1.jpg",
}
for name, url in sources.items():
    download(url, root / name)

