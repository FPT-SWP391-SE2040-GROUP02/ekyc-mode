# Nguồn model và thư viện

Ứng dụng dùng model có sẵn, không huấn luyện mới. `download_models.py` tải từ các nguồn sau và ghi SHA256 của file đã tải vào `models/manifest.json`. Hash này ghi nhận bản tải; không thay thế chữ ký phát hành của tác giả.

| Thành phần | Nguồn chính thức | Giấy phép được công bố tại nguồn |
|---|---|---|
| PaddleOCR / PP-OCR | [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), [tài liệu model](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html) | Apache-2.0 |
| VietOCR / VGG Seq2Seq | [pbcquoc/vietocr](https://github.com/pbcquoc/vietocr), trọng số tại URL `vocr.vn` trong config upstream | Apache-2.0, lưu `models/VIETOCR-LICENSE.txt` |
| YuNet | [OpenCV Zoo face detection](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | MIT tại thư mục model |
| SFace | [OpenCV Zoo face recognition](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) | Apache-2.0 tại thư mục model |
| MediaPipe FaceLandmarker | [Google AI Edge Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) | Xem điều khoản model trên trang Google; mã MediaPipe Apache-2.0 |
| MiniFASNet V2 / V1SE | [MiniVision Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) | Apache-2.0, lưu `vendor/MINIFASNET-LICENSE.txt` |

`vendor/minifasnet.py` là mã kiến trúc upstream được tải nguyên bản. Cách crop và input PAD dựa trên demo upstream. Quyết định ngưỡng và logic phiên thuộc prototype.

Ảnh kiểm thử tùy chọn `lena.jpg`, `messi.jpg` đến từ [OpenCV samples](https://github.com/opencv/opencv/tree/master/samples/data); `image_F1.jpg`, `image_T1.jpg` từ demo MiniVision. Các ảnh này chỉ dùng để kiểm tra local, không phải dữ liệu huấn luyện, đánh giá toàn diện hay tài sản minh họa sản phẩm. Kiểm tra quyền sử dụng riêng trước khi phân phối ảnh hoặc dùng thương mại.

Thư viện Python có giấy phép riêng trong các distribution đã cài. Giữ thông báo bản quyền và kiểm tra điều khoản nguồn khi triển khai/phân phối.

Bản ZIP chia sẻ kèm đầy đủ các file giấy phép được tải từ upstream: `models/PADDLEOCR-LICENSE.txt`, `models/YUNET-LICENSE.txt`, `models/SFACE-LICENSE.txt`, `models/VIETOCR-LICENSE.txt`, `models/MEDIAPIPE-CODE-LICENSE.txt` và `vendor/MINIFASNET-LICENSE.txt`. Giấy phép mã MediaPipe được ghi riêng, không đại diện cho điều khoản của mọi model Google. ZIP không chứa các ảnh fixture công khai.
