# LegacyVault eKYC

Dịch vụ xác minh danh tính điện tử (eKYC) dùng cho dự án LegacyVault, viết bằng Python (FastAPI). Đây là **chương trình riêng**, được Backend LegacyVault (.NET) gọi qua HTTP. Backend là nơi quyết định kết quả xác minh; dịch vụ này chỉ đọc giấy tờ, so khuôn mặt và chạy thử thách camera.

> Đây là bản prototype của đồ án. Không thay thế thủ tục pháp lý, không đọc chip NFC, không tra cơ sở dữ liệu dân cư và không bảo đảm chống được mọi kiểu giả mạo (kể cả deepfake hoặc video phát lại).

## Chạy nhanh để test dự án (4 bước)

Chạy trên **Windows 64-bit**. Cả dịch vụ này và Backend chạy **trên cùng một máy**.

1. Cài **Python 3.12 (64-bit)**. Dùng `winget install Python.Python.3.12` hoặc tải ở python.org. Các bản khác (3.13, 3.14, 32-bit) không được chấp nhận.
2. Clone repo này, mở thư mục và chạy **một lần**:

   ```cmd
   .\setup.cmd
   ```

   (Gõ trong cmd hoặc PowerShell thì phải có `.\` ở đầu; hoặc bấm đúp vào file `setup.cmd`.) Lệnh này tự tạo môi trường `.venv`, cài thư viện, cài PyTorch bản CPU và tải model. Cần Internet; lần đầu mất vài phút đến hơn chục phút tùy mạng và chiếm khoảng 2 GB đĩa.
3. Chạy dịch vụ (giữ cửa sổ mở, dừng bằng Ctrl+C):

   ```cmd
   .\START.cmd
   ```

   Mở `http://127.0.0.1:8879/api/health`: phải thấy `ocr`, `face`, `landmarks`, `anti_spoof` đều là `true`.
4. Chạy Backend LegacyVault như bình thường. `appsettings.Development.json` của Backend đã đặt sẵn `Ekyc:BaseUrl = http://127.0.0.1:8879` nên **không cần cấu hình gì thêm**. Dùng Frontend hoặc `http/ekyc.http` của Backend để thử các luồng eKYC.

Lần gọi đầu tiên chậm vì phải nạp model (có thể tới vài chục giây); Backend ở môi trường Development chờ tối đa 120 giây.

### Gặp sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `setup.cmd` báo không tìm thấy Python 3.12 | Cài Python 3.12 64-bit rồi chạy lại. Xem thêm `HUONG_DAN_CHAY.txt` |
| `.venv` báo không tương thích hoặc "copy từ máy khác" | Đổi tên `.venv` thành `.venv-old` rồi chạy lại `setup.cmd`. Không copy `.venv` giữa các máy |
| `setup.cmd` lỗi khi cài thư viện hoặc tải model | Kiểm tra Internet rồi chạy lại; lệnh chỉ tải phần còn thiếu. Trọng số VietOCR tải từ nguồn ngoài (`vocr.vn`), nếu nguồn đó lỗi thì báo người giữ repo |
| `START.cmd` báo thiếu môi trường Python | Chưa chạy `setup.cmd` |
| Cổng 8879 đang bận | Dừng chương trình đang dùng cổng, hoặc đặt biến `EKYC_PORT` rồi sửa `Ekyc:BaseUrl` của Backend cho khớp |
| Backend trả `503 EKYC_SERVICE_UNAVAILABLE` | Dịch vụ chưa chạy, sai cổng, `Ekyc:BaseUrl` đang để trống, hoặc đang đặt `EKYC_API_KEY` mà Backend chưa gửi đúng khóa |
| Trang `/api/health` báo model `false` | Chạy lại `setup.cmd` để tải model còn thiếu |

## Chức năng

| Chức năng | Thành phần |
|---|---|
| Đọc căn cước (mặt trước, mặt sau, số CCCD, họ tên, ngày sinh, nơi cư trú) | PaddleOCR (PP-OCR), VietOCR |
| Phát hiện khuôn mặt và so khớp mặt với ảnh trên thẻ | YuNet, SFace |
| Chống giả mạo ảnh đơn (ảnh in, màn hình) | MiniFASNet |
| Thử thách camera: chớp mắt và quay đầu trái hoặc phải, thứ tự ngẫu nhiên | MediaPipe FaceLandmarker |

Ảnh chỉ được xử lý trong bộ nhớ, không ghi ra đĩa. Nguồn và giấy phép của từng model ở `THIRD_PARTY.md` và `models/*-LICENSE.txt`.

## Cài đặt chi tiết

`setup.cmd` làm các việc sau: tạo `.venv`, cài thư viện trong `requirements.lock.txt`, cài PyTorch CPU, tải các model còn thiếu bằng `download_models.py` (ghi SHA256 vào `models/manifest.json`), rồi kiểm tra cài đặt. Repo **không chứa** `.venv` và trọng số model. Node.js (tùy chọn) chỉ để chạy `test_ui.cjs`.

## Chạy

Biến môi trường (đều tùy chọn):

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `EKYC_PORT` | Cổng lắng nghe | `8879` |
| `EKYC_HOST` | Địa chỉ lắng nghe | `127.0.0.1` |
| `EKYC_ALLOWED_HOSTS` | Danh sách Host được nhận thêm, cách nhau bằng dấu phẩy | chỉ `127.0.0.1`, `localhost`, `[::1]` |
| `EKYC_API_KEY` | Nếu đặt, mọi `/api/*` (trừ `/api/health`) phải gửi header `X-Ekyc-Key` khớp, sai hoặc thiếu trả `401` | không đặt (không kiểm tra) |
| `EKYC_BASE_DIR` | Thư mục chứa `.venv` và `models` | Thư mục của `START.cmd` |
| `EKYC_MODELS_DIR` | Thư mục model | `<EKYC_BASE_DIR>\models` |

## Bảo mật mạng

- Mặc định dịch vụ chỉ lắng nghe `127.0.0.1` và chỉ nhận Host `127.0.0.1`, `localhost`, `[::1]`. **Dùng cùng máy với Backend, không đưa ra Internet.**
- Các yêu cầu có header `Origin` chỉ được chấp nhận từ giao diện local (cổng 8877 đến 8879). Backend gọi trực tiếp, không có `Origin`, nên không bị chặn.
- Chỉ khi cần chạy ở máy khác (ví dụ một máy chung cho cả nhóm): đặt `EKYC_HOST=0.0.0.0`, `EKYC_ALLOWED_HOSTS=<tên hoặc IP máy>` **và bắt buộc đặt `EKYC_API_KEY`**. Backend gửi khóa này trong header `X-Ekyc-Key` khi cấu hình `Ekyc:ApiKey` (đặt bằng `dotnet user-secrets`, không commit). Dịch vụ chưa mã hóa đường truyền nên chỉ dùng trong mạng tin cậy.

## API

| Phương thức | Đường dẫn | Việc làm |
|---|---|---|
| GET | `/api/health` | Tình trạng model và phiên bản (không cần khóa) |
| POST | `/api/ocr` | Form: `file`, `side` (`front` hoặc `back`). Trả `fields`, `warnings`, và `document_token` khi đọc mặt trước tìm được đúng một khuôn mặt |
| POST | `/api/face-match` | Form: `selfie`, `document_token`, `threshold` (0.1 đến 0.9, mặc định 0.363). Trả `score` và `matched` |
| POST | `/api/face-embedding` | Form: `selfie`. Trả `model` (`sface`), `dimension` (128) và `embedding` (128 số thực) của đúng một khuôn mặt; `422` nếu ảnh không có đúng một khuôn mặt. Dịch vụ không lưu vector, chỉ Backend lưu (mã hóa) làm mẫu khuôn mặt Owner |
| DELETE | `/api/documents/{document_token}` | Xóa khuôn mặt đã giữ |
| POST | `/api/anti-spoof` | Form: `file`. Trả `passed` và `live_score` |
| POST | `/api/liveness/start` | Tạo phiên thử thách, trả `session_id`, `actions`, `prompt` |
| POST | `/api/liveness/frame` | Form: `session_id`, `frame`. Trả tiến độ (`completed`, `prompt`, `pad_passed`, `prototype_passed`, `failed_reason`, `frame_hint`) |
| GET | `/api/liveness/{session_id}/selfie` | Ảnh selfie tốt nhất của phiên đã đạt; `409` nếu chưa đạt |
| DELETE | `/api/liveness/{session_id}` | Hủy phiên |
| GET | `/api/sample-document` | Trả một ảnh PNG mẫu giả lập (chữ thử, không phải căn cước thật) để thử OCR |

Giới hạn: ảnh tối đa 8 MiB và 20 triệu điểm ảnh; mã tham chiếu khuôn mặt sống 30 phút (tối đa 50); phiên thử thách sống 90 giây (tối đa 20 phiên cùng lúc, mỗi phiên nhận tối đa 400 khung hình, hai khung hình cách nhau quá 3 giây thì động tác đang làm bị đặt lại).

## Liên hệ với Backend LegacyVault

- Backend cấu hình địa chỉ bằng `Ekyc:BaseUrl` (ví dụ `http://127.0.0.1:8879`) và thời gian chờ bằng `Ekyc:TimeoutSeconds`. Để trống `Ekyc:BaseUrl` thì các lệnh eKYC của Backend trả `503`.
- Frontend **không** gọi trực tiếp dịch vụ này. Trình duyệt gọi Backend (`/api/v1/ekyc/...`), Backend chuyển ảnh sang đây rồi giữ `document_token` và `session_id`; Backend không bao giờ trả hai mã đó cho trình duyệt.
- Backend tự quyết định đạt hay không: nó so lại điểm khuôn mặt với ngưỡng của mình (cosine 0.363), không tin cờ `matched` do dịch vụ này trả.
- Mẫu khuôn mặt Owner: Backend gửi selfie của phiên thử thách đã đạt tới `/api/face-embedding`, mã hóa vector nhận được rồi lưu DB; lần so sau Backend lấy vector của selfie mới và tự tính cosine với mẫu đã lưu (ngưỡng 0.363).
- Họ tên, ngày sinh và số CCCD đầy đủ đọc được chỉ đi qua dịch vụ này và Backend một lần; Backend chỉ lưu 4 số cuối CCCD và kết quả.
- Hợp đồng API phía Backend nằm ở repo Backend, tệp `docs/api-contract.md`, mục 6.10.

## Kiểm thử

```cmd
.\TEST.cmd
```

`TEST.cmd` chạy lần lượt các bộ `test_*.py` (và `test_ui.cjs` nếu có Node.js). Người mới chạy được ngay, không cần ảnh nào:

- Các bộ không cần ảnh (`test_face_detection.py`, `test_regressions.py`, `test_document_side.py`, `test_face_reference.py`, `test_ui.cjs`) chạy đầy đủ.
- Các bộ dùng model thật và ảnh cá nhân (`test_face_detection_real_models.py`, `test_locked_face_real_models.py`, `test_side_real_models.py`, phần ảnh của `test_supplied_images.py`) **tự bỏ qua** và in `SKIP` nếu chưa đặt biến `EKYC_TEST_PHOTOS`. Phần kiểm tra chung của `test_supplied_images.py` (ảnh mẫu giả lập, từ chối ảnh hỏng, chặn `Origin` lạ) vẫn chạy.
- Muốn chạy các bộ dùng ảnh: đặt `EKYC_TEST_PHOTOS` tới một thư mục **cục bộ** chứa ảnh của chính bạn và tệp `expected.local.json` theo mẫu `docs/expected.example.json`. Các bộ `test_*_real_models.py` còn tìm ảnh theo tiền tố tên tệp của bộ ảnh gốc, nên với ảnh khác chúng có thể báo không tìm thấy; đó là bộ kiểm thử của tác giả bản prototype.
- `fetch_test_fixtures.py` tải một số ảnh công khai (mẫu OpenCV, MiniVision) để thử; nguồn ghi ở `THIRD_PARTY.md`.
- **Không được commit ảnh căn cước, ảnh khuôn mặt hay `expected.local.json` thật vào repo** (đã có trong `.gitignore`). Mọi dữ liệu trong các test ở repo là dữ liệu giả lập.

Ghi chú các ca kiểm thử của bản prototype cũ nằm ở `docs/KIEM_THU_PROTOTYPE.md`. Một số mục trong đó nhắc ảnh thử không có trong repo.

## Giới hạn đã biết

- Chỉ hỗ trợ Windows 64-bit (script cài và chạy là `.cmd`/`.ps1`).
- Thử thách camera là bản thử nghiệm; chính kết quả của dịch vụ ghi chưa bảo đảm chống deepfake hoặc video phát lại.
- Ngưỡng so khớp (cosine 0.363) và ngưỡng chống giả mạo (0.7) là ngưỡng của prototype, chưa được nhóm đo và duyệt như một cấu hình chính thức.
- Đọc OCR có thể sai chữ ở ảnh mờ; chưa đọc mã QR trên căn cước.

## Giấy phép

Các model và mã bên thứ ba dùng giấy phép riêng của từng nguồn (Apache-2.0, MIT; riêng MediaPipe FaceLandmarker xem điều khoản trên trang Google). Giữ nguyên `THIRD_PARTY.md` và các tệp `*-LICENSE.txt` khi phân phối. Repo chưa có giấy phép riêng cho mã của nhóm; nhóm cần chọn trước khi mở công khai.
