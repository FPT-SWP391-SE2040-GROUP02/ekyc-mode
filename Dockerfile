FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by OpenCV, PaddleOCR, and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu

# Copy source code and bundled model weights / cache
COPY . .

ENV PYTHONUTF8=1
ENV EKYC_HOST=0.0.0.0
ENV PORT=8879

EXPOSE 8879

CMD ["python", "-B", "runtime.py"]
