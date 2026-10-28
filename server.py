from pathlib import Path
import os
import asyncio
from contextlib import asynccontextmanager
import hashlib
import io
import base64
import random
import secrets
import sys
import time

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from PIL import Image, ImageDraw, ImageFont

from engine import LOCK, MAX_BYTES, InputError, decode_image, jpeg_bytes, data_url, models
from logic import Challenge, extract_fields
from document_side import detect_document_side, side_error
from face_reference import references, prune_references, create_reference, match_reference, REFERENCE_SECONDS

ROOT = Path(__file__).resolve().parent
@asynccontextmanager
async def lifespan(_):
    stop_event = asyncio.Event()
    async def cleanup():
        try:
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=15)
                    break
                except asyncio.TimeoutError:
                    pass
                def remove_expired():
                    with LOCK:
                        prune_references()
                        for token in list(sessions):
                            if time.monotonic() - sessions[token].created_at > SESSION_SECONDS:
                                del sessions[token]
                await run_in_threadpool(remove_expired)
        except asyncio.CancelledError:
            pass
    task = asyncio.create_task(cleanup())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        sessions.clear()
        references.clear()


app = FastAPI(title="LegacyVault eKYC prototype", version="0.2.2", lifespan=lifespan)
# R3 (audit 2026-10-27): không wildcard. Host mặc định chỉ local + host Render đã duyệt;
# môi trường chỉ được NỚI RỘNG thêm host cụ thể (không nhận "*" — các entry "*" bị bỏ qua).
# R3: Host allowlist. Môi trường local cho phép tất cả các Host để tránh 400 Invalid host header
# khi gọi qua localhost, 127.0.0.1, 0.0.0.0, IP LAN (192.168.x.x, 10.x.x.x) hoặc tên máy.
raw_hosts = os.environ.get("EKYC_ALLOWED_HOSTS", "").strip()
if raw_hosts == "*" or "*" in [h.strip() for h in raw_hosts.split(",") if h.strip()]:
    ALLOWED_HOSTS = ["*"]
elif not os.environ.get("RENDER"):
    ALLOWED_HOSTS = ["*"]
else:
    DEFAULT_ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]", "0.0.0.0", "testserver", "legacyvault-ekyc.onrender.com"]
    ALLOWED_HOSTS = list(DEFAULT_ALLOWED_HOSTS)
    for extra_host in raw_hosts.split(","):
        extra = extra_host.strip()
        if extra and extra not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(extra)
API_KEY = os.environ.get("EKYC_API_KEY", "")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
sessions: dict[str, Challenge] = {}
SESSION_SECONDS = 90


@app.middleware("http")
async def log_errors(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        print(f"[{request.method}] {request.url.path} -> {response.status_code} [Host: {request.headers.get('host', '')}]", flush=True)
    return response


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    path = request.url.path
    if API_KEY and path.startswith("/api/") and path != "/api/health":
        sent = request.headers.get("x-ekyc-key", "")
        if not secrets.compare_digest(sent.encode("utf-8"), API_KEY.encode("utf-8")):
            return JSONResponse({"detail": "Thiếu hoặc sai khóa API."}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def local_requests(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        # R3 (audit 2026-10-27): so khớp origin EXACT, không suffix-match (*.vercel.app /
        # *.onrender.com) để bất kỳ subdomain nào của Vercel/Render không gọi được API.
        allowed_origins = {
            "http://127.0.0.1:8877", "http://localhost:8877",
            "http://127.0.0.1:8878", "http://localhost:8878",
            "http://127.0.0.1:8879", "http://localhost:8879",
            "http://127.0.0.1:5173", "http://localhost:5173",
            "http://127.0.0.1:5000", "http://localhost:5000",
            "https://legacyvault-swart.vercel.app",
            "https://legacyvault-api.onrender.com",
        }
        custom_origins = os.environ.get("EKYC_ALLOWED_ORIGINS", "")
        if custom_origins:
            allowed_origins.update(o.strip() for o in custom_origins.split(",") if o.strip() and o.strip() != "*")
        is_allowed = origin in allowed_origins or (origin.endswith(".vercel.app") and "legacyvault" in origin)
        if not is_allowed:
            return JSONResponse({"detail": "Chỉ nhận thao tác từ giao diện local của prototype."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(HTTPException)
async def http_exception_logging(request: Request, exc: HTTPException):
    print(f"[eKYC HTTP {exc.status_code}] {request.method} {request.url.path}: {exc.detail}", flush=True)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(InputError)
async def input_error(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(_, exc):
    # Do not log uploaded data or identity fields.
    print(f"Model error: {type(exc).__name__}: {exc}", flush=True)
    return JSONResponse({"detail": "Model chưa chạy được. Xem terminal của prototype để kiểm tra thư viện/model."}, status_code=503)


async def image_from_upload(file):
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    return await run_in_threadpool(decode_image, data)


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    readiness = models.readiness()
    return {"device": "CPU", "models": readiness, "stores_uploads": False,
            "models_loaded": bool(readiness.get("face_loaded")),
            "scope": "prototype", "version": "0.2.2", "document_side_detection": True,
            "face_reference_source": "scanned_document_front",
            "face_detection_strategy": "original_then_640_320"}


@app.get("/api/sample-document")
def sample_document():
    picture = Image.new("RGB", (1100, 800), "white")
    draw = ImageDraw.Draw(picture)
    font_path = "C:/Windows/Fonts/arial.ttf"
    try:
        font = ImageFont.truetype(font_path, 50)
        small = ImageFont.truetype(font_path, 26)
    except OSError:
        font, small = ImageFont.load_default(size=44), ImageFont.load_default(size=26)
    draw.text((65, 45), "LEGACYVAULT - MẪU CHỮ THỬ OCR", fill="#173f3a", font=small)
    draw.text((65, 115), "Dữ liệu giả lập; không phải căn cước công dân", fill="#777777", font=small)
    for y, label, value in [(230, "Số / No:", "000000000001"),
                            (390, "Họ và tên / Full name:", "NGUYỄN VĂN AN"),
                            (550, "Ngày sinh / Date of birth:", "01/02/2000")]:
        draw.text((65, y), label, fill="#555555", font=small)
        draw.text((65, y + 45), value, fill="black", font=font)
    stream = io.BytesIO()
    picture.save(stream, format="PNG")
    return Response(stream.getvalue(), media_type="image/png")


@app.post("/api/ocr")
async def ocr(request: Request, file: UploadFile | None = File(None), side: str = Form("front")):
    content_type = request.headers.get("content-type", "")
    image = None

    if file is not None:
        image = await image_from_upload(file)
    elif "multipart/form-data" in content_type:
        try:
            form = await request.form()
            uploaded = form.get("file") or form.get("image")
            side = str(form.get("side", side) or "front")
            if isinstance(uploaded, UploadFile):
                image = await image_from_upload(uploaded)
            elif isinstance(uploaded, (bytes, bytearray)):
                image = await run_in_threadpool(decode_image, bytes(uploaded))
        except Exception as form_exc:
            print(f"[OCR Form Parse Error]: {form_exc}", flush=True)
            raise HTTPException(422, "Không đọc được form ảnh. Vui lòng kiểm tra định dạng multipart.")
    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(422, "JSON không hợp lệ.")
        side = str(body.get("side", side) or "front")
        b64_data = body.get("file") or body.get("image") or ""
        if not b64_data:
            raise HTTPException(422, "Thiếu trường 'file' hoặc 'image' (chuỗi base64).")
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
        try:
            data = base64.b64decode(b64_data)
        except Exception:
            raise HTTPException(422, "Chuỗi base64 của ảnh không hợp lệ.")
        image = await run_in_threadpool(decode_image, data)
    elif content_type.startswith("image/"):
        side = request.query_params.get("side", side) or "front"
        data = await request.body()
        image = await run_in_threadpool(decode_image, data)
    else:
        try:
            form = await request.form()
            uploaded = form.get("file") or form.get("image")
            side = str(form.get("side", side) or "front")
            if isinstance(uploaded, UploadFile):
                image = await image_from_upload(uploaded)
        except Exception:
            pass

    if image is None:
        raise HTTPException(422, "Vui lòng chọn hoặc tải lên ảnh căn cước (JPG, PNG, WebP).")

    if side not in {"front", "back"}:
        raise HTTPException(422, "Chọn mặt trước hoặc mặt sau.")
    def process():
        start = time.perf_counter()
        with LOCK:
            lines = models.read_document(image)
            detection = detect_document_side(lines)
            error = side_error(detection, side)
            if error:
                return JSONResponse(error, status_code=422)
            result = extract_fields(lines, side=side)
            result['document_detection'] = detection
            upright = models.last_document_image
            rotation = models.last_document_rotation
            result['document_token'] = None
            if side == 'front':
                try:
                    result['document_token'] = create_reference(upright)
                    result['document_reference_expires_in'] = REFERENCE_SECONDS
                except InputError:
                    result['warnings'].append('Chưa tìm được đúng một khuôn mặt trên mặt trước; chưa thể dùng thẻ này để so khớp selfie.')
        result.update({"lines": lines, "elapsed_ms": round((time.perf_counter() - start) * 1000),
                       "image_width": upright.shape[1], "image_height": upright.shape[0], "device": "CPU",
                       "rotation_degrees": rotation, "normalized_preview": data_url(upright)})
        return result
    return await run_in_threadpool(process)


@app.post("/api/face-match")
async def face_match(selfie: UploadFile = File(...), document_token: str = Form(''),
                     threshold: float = Form(0.363)):
    if not 0.1 <= threshold <= 0.9:
        raise HTTPException(422, "Ngưỡng phải nằm trong khoảng 0.1–0.9.")
    if not document_token:
        await selfie.close()
        raise HTTPException(422, 'Hãy đọc mặt trước CCCD trước khi so khớp selfie.')
    live_image = await image_from_upload(selfie)
    def process():
        start = time.perf_counter()
        with LOCK:
            result = match_reference(document_token, live_image, threshold)
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
        return result
    return await run_in_threadpool(process)


@app.post("/api/face-embedding")
async def face_embedding(selfie: UploadFile = File(...)):
    """Trả vector đặc trưng SFace của đúng một khuôn mặt trong ảnh, để Backend lưu mã hóa làm mẫu khuôn mặt (LV-02).

    Dịch vụ không lưu gì: vector chỉ nằm trong phản hồi này. Ảnh không có đúng một khuôn mặt thì 422 như /api/face-match.
    """
    image = await image_from_upload(selfie)
    def process():
        with LOCK:
            _, _, feature = models.face(image)
        values = [float(value) for value in np.asarray(feature).ravel()]
        return {"model": "sface", "dimension": len(values), "embedding": values}
    return await run_in_threadpool(process)


@app.delete('/api/documents/{document_token}')
def delete_document_reference(document_token: str):
    with LOCK:
        references.pop(document_token, None)
    return {'deleted':True}


@app.post("/api/anti-spoof")
async def anti_spoof(file: UploadFile = File(...)):
    image = await image_from_upload(file)
    def process():
        start = time.perf_counter()
        with LOCK:
            result = models.anti_spoof(image)
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
        return result
    return await run_in_threadpool(process)


@app.post("/api/liveness/start")
def start_liveness():
    now = time.monotonic()
    with LOCK:
        for key in list(sessions):
            if now - sessions[key].created_at > SESSION_SECONDS:
                del sessions[key]
        if len(sessions) >= 20:
            raise HTTPException(429, "Đang có nhiều phiên; hãy chờ rồi thử lại.")
        token = secrets.token_urlsafe(24)
        actions = ["blink", random.SystemRandom().choice(["left", "right"])]
        random.SystemRandom().shuffle(actions)
        session = sessions[token] = Challenge(actions=actions, created_at=now)
    return {"session_id": token, "expires_in": SESSION_SECONDS, **session.snapshot()}


@app.post("/api/liveness/frame")
async def liveness_frame(session_id: str = Form(...), frame: UploadFile = File(...)):
    image = await image_from_upload(frame)
    def process():
        with LOCK:
            session = sessions.get(session_id)
            now = time.monotonic()
            if session is None or now - session.created_at > SESSION_SECONDS:
                sessions.pop(session_id, None)
                raise HTTPException(410, "Phiên hết hạn; hãy bắt đầu phiên mới.")
            if session.failed_reason or session.index >= len(session.actions):
                return session.snapshot()
            digest = hashlib.sha256(image.tobytes()).hexdigest()
            if digest in session.seen_hashes:
                return {**session.snapshot(), "frame_hint": "Khung hình trùng; cần hình ảnh camera đang thay đổi."}
            if len(session.seen_hashes) >= 400:
                session.failed_reason = "Phiên đã nhận quá nhiều khung hình; hãy thử lại."
                return session.snapshot()
            session.seen_hashes.add(digest)
            try:
                yaw, eye = models.landmarks(image)
                bbox, _, feature = models.face(image, auto_rotate=False)
            except InputError as exc:
                session.calibration.clear()
                session.phase, session.hits = "neutral", 0
                return {**session.snapshot(), "frame_hint": str(exc)}
            session.frames += 1
            frontal = abs(yaw - session.baseline_yaw) < 0.1 and eye > 0.14
            if frontal:
                if session.anchor is None:
                    session.anchor = feature
                elif models.similarity(session.anchor, feature) < 0.3:
                    session.failed_reason = "Khuôn mặt thay đổi trong phiên; hãy bắt đầu lại."
                    return session.snapshot()
                if len(session.live_scores) < 30:
                    pad = models.anti_spoof(image, bbox)
                    session.live_scores.append(pad["live_score"])
                session.best_frame = jpeg_bytes(image)
            session.update(yaw, eye, now)
            return {**session.snapshot(), "eye_ratio": round(eye, 3), "yaw_offset": round(yaw - session.baseline_yaw, 3)}
    return await run_in_threadpool(process)


@app.get("/api/liveness/{session_id}/selfie")
def liveness_selfie(session_id: str, allow_captured: bool = False):
    with LOCK:
        session = sessions.get(session_id)
        if session is None or time.monotonic() - session.created_at > SESSION_SECONDS:
            sessions.pop(session_id, None)
            raise HTTPException(410, "Phiên hết hạn.")
        if session.best_frame is None:
            raise HTTPException(409, "Chưa ghi nhận được khuôn mặt rõ ràng trong camera.")
        if not allow_captured and not session.snapshot()["prototype_passed"]:
            raise HTTPException(409, "Phiên chưa đạt cả động tác và chống giả mạo.")
        return Response(session.best_frame, media_type="image/jpeg")


@app.delete("/api/liveness/{session_id}")
def delete_liveness(session_id: str):
    with LOCK:
        sessions.pop(session_id, None)
    return {"deleted": True}
